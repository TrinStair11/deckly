import base64
import binascii
import ipaddress
import mimetypes
import os
import socket
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Annotated, Literal
from urllib.parse import urljoin, urlparse
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    clear_auth_cookie,
    create_access_token,
    get_current_user,
    get_db,
    hash_password,
    set_auth_cookie,
    verify_password,
)
from .config import load_local_env
from .db import ensure_schema
from .spaced_repetition import (
    advance_session,
    apply_review_rating,
    build_deck_detail_for_user,
    build_study_session,
    ensure_user_card_state,
    get_active_cards,
    is_card_due,
    refresh_user_deck_progress,
    serialize_card,
    serialize_user_card_state,
    utcnow,
)
from .time_utils import ensure_utc
from .quiz_router import (
    answer_quiz_question,
    complete_quiz_attempt,
    create_quiz,
    delete_quiz,
    get_quiz_attempt,
    get_quiz_attempt_results,
    get_quiz_detail,
    get_quiz_edit_data,
    list_quizzes_module,
    router as quiz_router,
    start_quiz_attempt,
    update_quiz,
)

@asynccontextmanager
async def app_lifespan(_: FastAPI):
    ensure_schema()
    yield


load_local_env()

app = FastAPI(title="Deckly", lifespan=app_lifespan)


def parse_cors_origins(raw_value: str) -> list[str]:
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


CORS_ALLOW_ORIGINS = parse_cors_origins(
    os.getenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(quiz_router)

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
OPENVERSE_API_URL = os.getenv("OPENVERSE_API_URL", "https://api.openverse.org/v1/images/")
IMAGE_SEARCH_TIMEOUT = 15.0
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_IMAGE_DOWNLOAD_BYTES = int(os.getenv("MAX_IMAGE_DOWNLOAD_BYTES", str(5 * 1024 * 1024)))
MAX_IMAGE_UPLOAD_BYTES = int(os.getenv("MAX_IMAGE_UPLOAD_BYTES", str(5 * 1024 * 1024)))
IMAGE_REDIRECT_LIMIT = int(os.getenv("IMAGE_REDIRECT_LIMIT", "3"))
LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "5"))
DECK_ACCESS_RATE_LIMIT = int(os.getenv("DECK_ACCESS_RATE_LIMIT", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "600"))
FAILED_ATTEMPTS: dict[str, dict[str, list[float]]] = defaultdict(dict)
FAILED_ATTEMPTS_LOCK = Lock()


def detect_image_extension(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return None


def is_public_ip_address(raw_address: str) -> bool:
    address = ipaddress.ip_address(raw_address)
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def validate_external_image_url(source_url: str) -> str:
    parsed = urlparse(source_url.strip())
    if parsed.scheme.lower() != "https":
        raise HTTPException(status_code=400, detail="Only https image URLs are allowed")
    if not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Invalid image URL")

    try:
        resolved_addresses = {
            item[4][0]
            for item in socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as error:
        raise HTTPException(status_code=400, detail="Image host could not be resolved") from error

    if not resolved_addresses or any(not is_public_ip_address(address) for address in resolved_addresses):
        raise HTTPException(status_code=400, detail="Image host is not allowed")
    return parsed.geturl()


def ensure_redirect_allowed(current_url: str, location: str) -> str:
    redirected_url = urljoin(current_url, location)
    return validate_external_image_url(redirected_url)


def get_rate_limit_bucket(scope: str) -> dict[str, list[float]]:
    return FAILED_ATTEMPTS[scope]


def rate_limit_key(scope: str, identifier: str, request: Request | None) -> str:
    client_host = request.client.host if request and request.client else "unknown"
    return f"{scope}:{client_host}:{identifier.strip().lower()}"


def enforce_rate_limit(scope: str, identifier: str, request: Request | None, limit: int) -> str:
    key = rate_limit_key(scope, identifier, request)
    now = time.time()
    with FAILED_ATTEMPTS_LOCK:
        attempts = [timestamp for timestamp in get_rate_limit_bucket(scope).get(key, []) if now - timestamp < RATE_LIMIT_WINDOW_SECONDS]
        get_rate_limit_bucket(scope)[key] = attempts
        if len(attempts) >= limit:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed attempts. Try again later",
            )
    return key


def record_rate_limit_failure(scope: str, key: str) -> None:
    now = time.time()
    with FAILED_ATTEMPTS_LOCK:
        attempts = [timestamp for timestamp in get_rate_limit_bucket(scope).get(key, []) if now - timestamp < RATE_LIMIT_WINDOW_SECONDS]
        attempts.append(now)
        get_rate_limit_bucket(scope)[key] = attempts


def clear_rate_limit_failures(scope: str, key: str) -> None:
    with FAILED_ATTEMPTS_LOCK:
        get_rate_limit_bucket(scope).pop(key, None)


def guess_image_extension(content_type: str | None, fallback_name: str = "") -> str:
    normalized_type = (content_type or "").split(";")[0].strip().lower()
    guessed = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(normalized_type)
    if not guessed and normalized_type:
        guessed = mimetypes.guess_extension(normalized_type)
    if guessed in {".jpe"}:
        guessed = ".jpg"
    if guessed and guessed.lower() in ALLOWED_IMAGE_EXTENSIONS:
        return guessed.lower()
    suffix = Path(fallback_name).suffix.lower()
    if suffix in ALLOWED_IMAGE_EXTENSIONS:
        return suffix
    return ".jpg"


def store_image_bytes(content: bytes, extension: str) -> str:
    filename = f"{uuid4().hex}{extension}"
    output_path = MEDIA_DIR / filename
    output_path.write_bytes(content)
    return f"/media/{filename}"


def normalize_openverse_results(payload: dict) -> list[schemas.ImageSearchResult]:
    results = []
    for item in payload.get("results", []):
        thumbnail_url = item.get("thumbnail")
        source_url = item.get("url")
        if not thumbnail_url or not source_url:
            continue
        results.append(
            schemas.ImageSearchResult(
                provider="openverse",
                external_id=str(item.get("id") or source_url),
                title=item.get("title") or "Untitled image",
                thumbnail_url=thumbnail_url,
                source_url=source_url,
                author=item.get("creator"),
                license=item.get("license"),
            )
        )
    return results


def search_openverse_images(query: str, page: int, page_size: int) -> list[schemas.ImageSearchResult]:
    try:
        with httpx.Client(timeout=IMAGE_SEARCH_TIMEOUT, follow_redirects=True) as client:
            response = client.get(
                OPENVERSE_API_URL,
                params={"q": query, "page": page, "page_size": page_size},
                headers={"User-Agent": "Deckly/1.0"},
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Image search provider is unavailable") from error
    return normalize_openverse_results(response.json())


def download_external_image(source_url: str) -> str:
    current_url = validate_external_image_url(source_url)
    redirects_followed = 0

    try:
        with httpx.Client(timeout=IMAGE_SEARCH_TIMEOUT, follow_redirects=False) as client:
            while True:
                with client.stream("GET", current_url, headers={"User-Agent": "Deckly/1.0"}) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise HTTPException(status_code=502, detail="Image provider returned an invalid redirect")
                        redirects_followed += 1
                        if redirects_followed > IMAGE_REDIRECT_LIMIT:
                            raise HTTPException(status_code=502, detail="Image provider redirected too many times")
                        current_url = ensure_redirect_allowed(current_url, location)
                        continue

                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if not content_type.startswith("image/"):
                        raise HTTPException(status_code=400, detail="The selected file is not an image")

                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > MAX_IMAGE_DOWNLOAD_BYTES:
                        raise HTTPException(status_code=413, detail="The selected image is too large")

                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > MAX_IMAGE_DOWNLOAD_BYTES:
                            raise HTTPException(status_code=413, detail="The selected image is too large")

                    if not content:
                        raise HTTPException(status_code=400, detail="The selected image is empty")

                    detected_extension = detect_image_extension(bytes(content))
                    if not detected_extension:
                        raise HTTPException(status_code=400, detail="The selected file is not a supported image")

                    extension = detected_extension or guess_image_extension(content_type, current_url)
                    return store_image_bytes(bytes(content), extension)
    except HTTPException:
        raise
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Failed to download the selected image") from error


def get_owner_name(user: models.User) -> str:
    return user.email.split("@")[0]


def get_saved_deck_link(deck_id: int, user_id: int, db: Session) -> models.UserSavedDeck | None:
    return (
        db.query(models.UserSavedDeck)
        .filter(models.UserSavedDeck.deck_id == deck_id, models.UserSavedDeck.user_id == user_id)
        .first()
    )


def serialize_progress(progress: models.UserDeckProgress | None) -> schemas.ProgressOut | None:
    if not progress:
        return None
    return schemas.ProgressOut.from_orm(progress)


def serialize_deck(
    deck: models.Deck,
    current_user_id: int | None = None,
    saved_link: models.UserSavedDeck | None = None,
    progress: models.UserDeckProgress | None = None,
) -> schemas.DeckOut:
    is_owner = current_user_id is not None and deck.owner_id == current_user_id
    saved_in_library = bool(saved_link) and not is_owner
    return schemas.DeckOut(
        id=deck.id,
        title=deck.title,
        description=deck.description,
        visibility=deck.visibility,
        created_at=deck.created_at,
        updated_at=deck.updated_at,
        card_count=len(get_active_cards(deck)),
        owner_id=deck.owner_id,
        owner_name=get_owner_name(deck.owner),
        is_owner=is_owner,
        saved_in_library=saved_in_library,
        saved_at=saved_link.saved_at if saved_in_library else None,
        progress=serialize_progress(progress),
    )


def serialize_share_meta(deck: models.Deck, reveal_owner: bool = False) -> schemas.DeckShareMeta:
    is_public = deck.visibility == "public"
    return schemas.DeckShareMeta(
        id=deck.id,
        title=deck.title if is_public or reveal_owner else "Private deck",
        visibility=deck.visibility,
        requires_password=deck.visibility == "private",
        owner_id=deck.owner_id if is_public or reveal_owner else None,
        owner_name=get_owner_name(deck.owner) if is_public or reveal_owner else None,
    )


def validate_deck_privacy(visibility: str, password: str) -> tuple[str, str]:
    normalized_visibility = visibility.strip().lower()
    normalized_password = password.strip()
    if normalized_visibility not in {"public", "private"}:
        raise HTTPException(status_code=400, detail="Visibility must be public or private")
    if normalized_visibility == "private" and len(normalized_password) < 4:
        raise HTTPException(status_code=400, detail="Private decks require a password with at least 4 characters")
    return normalized_visibility, normalized_password


def create_deck_access_token(deck_id: int) -> str:
    return create_access_token(
        {"deck_access": str(deck_id), "purpose": "deck-share"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def verify_deck_access_token(token: str, deck_id: int) -> bool:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return False
    return payload.get("purpose") == "deck-share" and payload.get("deck_access") == str(deck_id)


def get_deck_or_404(deck_id: int, db: Session) -> models.Deck:
    deck = db.query(models.Deck).filter(models.Deck.id == deck_id).first()
    if not deck:
        raise HTTPException(status_code=404, detail="Deck not found")
    return deck


def get_owned_deck_or_404(deck_id: int, user_id: int, db: Session) -> models.Deck:
    deck = get_deck_or_404(deck_id, db)
    if deck.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only the deck owner can modify this deck")
    return deck


def get_accessible_deck_or_404(
    deck_id: int,
    user_id: int,
    db: Session,
    deck_access_token: str | None = None,
) -> tuple[models.Deck, models.UserSavedDeck | None]:
    deck = get_deck_or_404(deck_id, db)
    if deck.owner_id == user_id:
        return deck, None
    saved_link = get_saved_deck_link(deck_id, user_id, db)
    if saved_link:
        if deck.visibility == "private":
            ensure_shared_deck_access(deck, deck_access_token)
        return deck, saved_link
    raise HTTPException(status_code=403, detail="You do not have access to this deck")


def ensure_shared_deck_access(deck: models.Deck, deck_access_token: str | None) -> None:
    if deck.visibility == "public":
        return
    if not deck_access_token or not verify_deck_access_token(deck_access_token, deck.id):
        raise HTTPException(status_code=403, detail="Password is required for this deck")


def get_next_card_position(deck_id: int, db: Session) -> int:
    max_position = (
        db.query(models.Card.position)
        .filter(models.Card.deck_id == deck_id, models.Card.deleted_at.is_(None))
        .order_by(models.Card.position.desc())
        .first()
    )
    return 0 if not max_position else max_position[0] + 1


def get_owned_card_or_404(card_id: int, user_id: int, db: Session) -> models.Card:
    card = db.query(models.Card).filter(models.Card.id == card_id, models.Card.deleted_at.is_(None)).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    if card.deck.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Only the deck owner can modify this deck")
    return card


def get_card_in_deck_or_404(deck_id: int, card_id: int, db: Session) -> models.Card:
    card = (
        db.query(models.Card)
        .filter(models.Card.id == card_id, models.Card.deck_id == deck_id, models.Card.deleted_at.is_(None))
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card


def save_deck_to_library(
    deck: models.Deck,
    current_user: models.User,
    db: Session,
) -> tuple[models.UserSavedDeck, bool]:
    if deck.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot save your own deck")
    saved_link = get_saved_deck_link(deck.id, current_user.id, db)
    if saved_link:
        return saved_link, False
    saved_link = models.UserSavedDeck(user_id=current_user.id, deck_id=deck.id)
    db.add(saved_link)
    db.commit()
    db.refresh(saved_link)
    return saved_link, True


@app.post("/register", response_model=schemas.UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: schemas.UserCreate, db: Session = Depends(get_db)):
    normalized_email = payload.email.strip().lower()
    existing = db.query(models.User).filter(models.User.email == normalized_email).first()
    if existing:
        raise HTTPException(status_code=400, detail="User already exists")
    user = models.User(email=normalized_email, password_hash=hash_password(payload.password))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@app.post("/login", response_model=schemas.Token)
def login(
    payload: schemas.UserLogin,
    db: Session = Depends(get_db),
    response: Response = None,
    request: Request = None,
):
    normalized_email = payload.email.strip().lower()
    rate_limit_scope = enforce_rate_limit("login", normalized_email, request, LOGIN_RATE_LIMIT)
    user = db.query(models.User).filter(models.User.email == normalized_email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        record_rate_limit_failure("login", rate_limit_scope)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id)}, expires_delta=timedelta(minutes=60 * 24))
    if response is not None:
        set_auth_cookie(response, token)
    clear_rate_limit_failures("login", rate_limit_scope)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/logout", response_model=schemas.AccountActionResult)
def logout(response: Response):
    clear_auth_cookie(response)
    return schemas.AccountActionResult(message="Logged out successfully")


@app.get("/me", response_model=schemas.UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


@app.put("/account/email", response_model=schemas.UserOut)
def update_account_email(
    payload: schemas.AccountEmailUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if payload.new_email != payload.confirm_email:
        raise HTTPException(status_code=400, detail="Email confirmation does not match")

    target_email = payload.new_email.strip().lower()
    if target_email == current_user.email:
        raise HTTPException(status_code=400, detail="New email must be different from current email")

    existing = (
        db.query(models.User)
        .filter(models.User.email == target_email, models.User.id != current_user.id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Email is already in use")

    current_user.email = target_email
    db.commit()
    db.refresh(current_user)
    return current_user


@app.put("/account/password", response_model=schemas.AccountActionResult)
def update_account_password(
    payload: schemas.AccountPasswordUpdate,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if payload.new_password != payload.confirm_new_password:
        raise HTTPException(status_code=400, detail="Password confirmation does not match")
    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=400, detail="New password must be different from current password")

    current_user.password_hash = hash_password(payload.new_password)
    db.commit()
    return schemas.AccountActionResult(message="Password updated successfully")


@app.post("/decks", response_model=schemas.DeckOut, status_code=status.HTTP_201_CREATED)
def create_deck(deck: schemas.DeckCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    visibility, password = validate_deck_privacy(deck.visibility, deck.password if deck.visibility == "private" else "")
    now = utcnow()
    new_deck = models.Deck(
        title=deck.title.strip(),
        description=deck.description.strip(),
        visibility=visibility,
        password_hash=hash_password(password) if visibility == "private" else None,
        created_at=now,
        updated_at=now,
        owner_id=current_user.id,
    )
    db.add(new_deck)
    db.flush()
    next_position = get_next_card_position(new_deck.id, db)
    for position_offset, card in enumerate(deck.cards):
        db.add(
            models.Card(
                front=card.front.strip(),
                back=card.back.strip(),
                image_url=card.image_url.strip(),
                position=next_position + position_offset,
                deck_id=new_deck.id,
                created_at=now,
                updated_at=now,
            )
        )
    db.commit()
    db.refresh(new_deck)
    progress = refresh_user_deck_progress(new_deck, current_user.id, db)
    db.commit()
    return serialize_deck(new_deck, current_user_id=current_user.id, progress=progress)


@app.get("/decks", response_model=list[schemas.DeckOut])
def list_decks(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    owned_decks = db.query(models.Deck).filter(models.Deck.owner_id == current_user.id).all()
    saved_links = db.query(models.UserSavedDeck).filter(models.UserSavedDeck.user_id == current_user.id).all()
    items = [(deck.created_at, deck, None) for deck in owned_decks]
    items.extend((link.saved_at, link.deck, link) for link in saved_links if link.deck.owner_id != current_user.id)
    items.sort(key=lambda item: item[0], reverse=True)
    return [
        serialize_deck(
            deck,
            current_user_id=current_user.id,
            saved_link=saved_link,
            progress=refresh_user_deck_progress(deck, current_user.id, db, persist=False),
        )
        for _, deck, saved_link in items
    ]


@app.get("/decks/{deck_id}", response_model=schemas.DeckDetail)
def get_deck(
    deck_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, saved_link = get_accessible_deck_or_404(deck_id, current_user.id, db, x_deck_access_token)
    return build_deck_detail_for_user(
        deck,
        db=db,
        serialize_deck=serialize_deck,
        current_user_id=current_user.id,
        saved_link=saved_link,
        persist_progress=False,
    )


@app.get("/decks/{deck_id}/study/session", response_model=schemas.StudySession)
def get_study_session(
    deck_id: int,
    mode: str = "interval",
    limit: Annotated[int | None, Query(ge=1)] = None,
    new_cards_limit: Annotated[int, Query(ge=0, le=200)] = 10,
    shuffle_cards: bool = False,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, _ = get_accessible_deck_or_404(deck_id, current_user.id, db, x_deck_access_token)
    return build_study_session(
        deck,
        current_user,
        db,
        mode=mode,
        limit=limit,
        new_cards_limit=new_cards_limit,
        shuffle_cards=shuffle_cards,
        persist_progress=False,
    )


@app.get("/decks/{deck_id}/study", response_model=schemas.StudySession)
def get_legacy_study_session(
    deck_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, _ = get_accessible_deck_or_404(deck_id, current_user.id, db, x_deck_access_token)
    return build_study_session(deck, current_user, db, mode="interval", persist_progress=False)


@app.get("/decks/{deck_id}/progress", response_model=schemas.ProgressOut)
def get_deck_progress(
    deck_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, _ = get_accessible_deck_or_404(deck_id, current_user.id, db, x_deck_access_token)
    progress = refresh_user_deck_progress(deck, current_user.id, db, persist=False)
    return progress


@app.get("/shared/decks/{deck_id}/meta", response_model=schemas.DeckShareMeta)
def get_shared_deck_meta(
    deck_id: int,
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck = get_deck_or_404(deck_id, db)
    reveal_owner = bool(x_deck_access_token and verify_deck_access_token(x_deck_access_token, deck.id))
    return serialize_share_meta(deck, reveal_owner=reveal_owner)


@app.post("/shared/decks/{deck_id}/access", response_model=schemas.DeckAccessToken)
def access_private_deck(
    deck_id: int,
    payload: schemas.DeckAccessRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    deck = get_deck_or_404(deck_id, db)
    if deck.visibility != "private":
        raise HTTPException(status_code=400, detail="This deck does not require a password")
    rate_limit_scope = enforce_rate_limit("deck-access", str(deck_id), request, DECK_ACCESS_RATE_LIMIT)
    if not deck.password_hash or not verify_password(payload.password, deck.password_hash):
        record_rate_limit_failure("deck-access", rate_limit_scope)
        raise HTTPException(status_code=401, detail="Incorrect deck password")
    clear_rate_limit_failures("deck-access", rate_limit_scope)
    return {"access_token": create_deck_access_token(deck.id), "token_type": "deck-access"}


@app.get("/shared/decks/{deck_id}", response_model=schemas.DeckDetail)
def get_shared_deck(
    deck_id: int,
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck = get_deck_or_404(deck_id, db)
    ensure_shared_deck_access(deck, x_deck_access_token)
    return build_deck_detail_for_user(deck, db=db, serialize_deck=serialize_deck, persist_progress=False)


@app.get("/shared/decks/{deck_id}/study", response_model=schemas.StudySession)
def get_shared_study_session(
    deck_id: int,
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck = get_deck_or_404(deck_id, db)
    ensure_shared_deck_access(deck, x_deck_access_token)
    active_cards = get_active_cards(deck)
    zero_progress = schemas.ProgressOut(
        total_cards=len(active_cards),
        new_available_count=len(active_cards),
        learning_count=0,
        review_count=0,
        due_review_count=0,
        known_count=0,
        last_studied_at=None,
        updated_at=utcnow(),
    )
    return schemas.StudySession(
        session_id=uuid4().hex,
        deck_id=deck.id,
        deck_title=deck.title,
        mode="review_all",
        current_index=0,
        card_order=[card.id for card in active_cards],
        total_cards=len(active_cards),
        cards=[serialize_card(card) for card in active_cards],
        progress=zero_progress,
    )


@app.post("/decks/{deck_id}/save-to-library", response_model=schemas.DeckOut, status_code=status.HTTP_201_CREATED)
@app.post("/shared/decks/{deck_id}/save", response_model=schemas.DeckOut, status_code=status.HTTP_201_CREATED)
def save_shared_deck(
    deck_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
    response: Response = None,
):
    deck = get_deck_or_404(deck_id, db)
    ensure_shared_deck_access(deck, x_deck_access_token)
    saved_link, created = save_deck_to_library(deck, current_user, db)
    progress = refresh_user_deck_progress(deck, current_user.id, db)
    db.commit()
    if response is not None and not created:
        response.status_code = status.HTTP_200_OK
    return serialize_deck(deck, current_user_id=current_user.id, saved_link=saved_link, progress=progress)


@app.put("/decks/{deck_id}", response_model=schemas.DeckOut)
def update_deck(deck_id: int, payload: schemas.DeckUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    deck = get_owned_deck_or_404(deck_id, current_user.id, db)
    raw_visibility = payload.visibility.strip().lower()
    password = payload.password.strip()
    if raw_visibility not in {"public", "private"}:
        raise HTTPException(status_code=400, detail="Visibility must be public or private")
    if raw_visibility == "private" and not password and not deck.password_hash:
        raise HTTPException(status_code=400, detail="Private decks require a password with at least 4 characters")
    if raw_visibility == "private" and password:
        _, password = validate_deck_privacy(raw_visibility, password)
    deck.title = payload.title.strip()
    deck.description = payload.description.strip()
    deck.visibility = raw_visibility
    deck.password_hash = None if raw_visibility == "public" else (hash_password(password) if password else deck.password_hash)
    deck.updated_at = utcnow()
    db.commit()
    db.refresh(deck)
    progress = refresh_user_deck_progress(deck, current_user.id, db)
    db.commit()
    return serialize_deck(deck, current_user_id=current_user.id, progress=progress)


@app.delete("/decks/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deck(deck_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    deck = get_owned_deck_or_404(deck_id, current_user.id, db)
    db.delete(deck)
    db.commit()


@app.post("/decks/{deck_id}/cards", response_model=schemas.CardOut, status_code=status.HTTP_201_CREATED)
def create_card(deck_id: int, card: schemas.CardCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    deck = get_owned_deck_or_404(deck_id, current_user.id, db)
    now = utcnow()
    new_card = models.Card(
        front=card.front.strip(),
        back=card.back.strip(),
        image_url=card.image_url.strip(),
        position=get_next_card_position(deck.id, db),
        deck_id=deck.id,
        created_at=now,
        updated_at=now,
    )
    deck.updated_at = now
    db.add(new_card)
    db.commit()
    db.refresh(new_card)
    return serialize_card(new_card)


@app.put("/cards/{card_id}", response_model=schemas.CardOut)
def update_card(card_id: int, payload: schemas.CardUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    card = get_owned_card_or_404(card_id, current_user.id, db)
    card.front = payload.front.strip()
    card.back = payload.back.strip()
    card.image_url = payload.image_url.strip()
    card.updated_at = utcnow()
    card.deck.updated_at = card.updated_at
    db.commit()
    db.refresh(card)
    return serialize_card(card)


@app.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_card(card_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    card = get_owned_card_or_404(card_id, current_user.id, db)
    now = utcnow()
    card.deleted_at = now
    card.updated_at = now
    card.deck.updated_at = now
    db.commit()


@app.put("/decks/{deck_id}/cards/reorder", response_model=list[schemas.CardOut])
def reorder_cards(deck_id: int, payload: schemas.CardReorder, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    deck = get_owned_deck_or_404(deck_id, current_user.id, db)
    cards_by_id = {card.id: card for card in get_active_cards(deck)}
    if {item.id for item in payload.items} != set(cards_by_id):
        raise HTTPException(status_code=400, detail="Reorder payload must include every card in the deck")
    if len({item.position for item in payload.items}) != len(payload.items):
        raise HTTPException(status_code=400, detail="Reorder payload must use unique positions")
    for item in payload.items:
        cards_by_id[item.id].position = item.position
        cards_by_id[item.id].updated_at = utcnow()
    deck.updated_at = utcnow()
    db.commit()
    return [serialize_card(card) for card in sorted(cards_by_id.values(), key=lambda item: item.position)]


@app.post("/reviews/submit", response_model=schemas.ReviewResult)
def submit_review(
    payload: schemas.ReviewSubmit,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, _ = get_accessible_deck_or_404(payload.deck_id, current_user.id, db, x_deck_access_token)
    get_card_in_deck_or_404(deck.id, payload.card_id, db)
    state = ensure_user_card_state(current_user.id, deck.id, payload.card_id, db)
    now = utcnow()
    session = advance_session(
        payload.session_id,
        payload.card_id,
        current_user.id,
        deck.id,
        db,
        validate_only=True,
    )
    if not session and not is_card_due(state, now):
        raise HTTPException(status_code=400, detail="Card is not due for review")
    audit_snapshot = apply_review_rating(state, payload.rating, now)
    session = advance_session(
        payload.session_id,
        payload.card_id,
        current_user.id,
        deck.id,
        db,
        rating=payload.rating,
    )
    review_log = models.ReviewLog(
        user_id=current_user.id,
        deck_id=deck.id,
        card_id=payload.card_id,
        session_id=payload.session_id,
        reviewed_at=now,
        rating=payload.rating,
        previous_status=audit_snapshot.status,
        new_status=state.status,
        previous_due_at=audit_snapshot.due_at,
        new_due_at=state.due_at,
        previous_stability=audit_snapshot.legacy_stability,
        new_stability=state.stability,
        previous_difficulty=audit_snapshot.legacy_difficulty,
        new_difficulty=state.difficulty,
        previous_ease_factor=audit_snapshot.ease_factor,
        new_ease_factor=state.ease_factor,
        response_time_ms=payload.response_time_ms,
        created_at=now,
    )
    db.add(review_log)
    progress = refresh_user_deck_progress(deck, current_user.id, db)
    db.commit()
    db.refresh(state)
    return schemas.ReviewResult(
        card_id=payload.card_id,
        deck_id=deck.id,
        rating=payload.rating,
        session_id=payload.session_id,
        session_current_index=session.current_index if session else None,
        state=serialize_user_card_state(state),
        progress=schemas.ProgressOut.from_orm(progress),
        next_due_at=ensure_utc(state.due_at),
    )


@app.post("/cards/{card_id}/review", response_model=schemas.ReviewResult)
def review_card(
    card_id: int,
    payload: schemas.CardReview,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    card = db.query(models.Card).filter(models.Card.id == card_id, models.Card.deleted_at.is_(None)).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return submit_review(
        schemas.ReviewSubmit(deck_id=card.deck_id, card_id=card.id, rating=payload.rating, session_id=uuid4().hex),
        current_user=current_user,
        db=db,
        x_deck_access_token=x_deck_access_token,
    )


@app.get("/cards", response_model=list[schemas.CardOut])
def list_cards(current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    cards = (
        db.query(models.Card)
        .join(models.Deck, models.Card.deck_id == models.Deck.id)
        .filter(models.Deck.owner_id == current_user.id, models.Card.deleted_at.is_(None))
        .order_by(models.Card.position)
        .all()
    )
    return [serialize_card(card) for card in cards]


@app.post("/images/search", response_model=schemas.ImageSearchResponse)
def search_images(payload: schemas.ImageSearchRequest, current_user=Depends(get_current_user)):
    query = payload.query.strip()
    results = search_openverse_images(query, payload.page, payload.page_size)
    return schemas.ImageSearchResponse(
        query=query,
        page=payload.page,
        page_size=payload.page_size,
        results=results,
    )


@app.post("/images/import", response_model=schemas.StoredImageOut)
def import_image(payload: schemas.ImageImportRequest, current_user=Depends(get_current_user)):
    return schemas.StoredImageOut(image_url=download_external_image(payload.source_url.strip()))


@app.post("/images/upload", response_model=schemas.StoredImageOut)
def upload_image(payload: schemas.ImageUploadRequest, current_user=Depends(get_current_user)):
    try:
        content = base64.b64decode(payload.content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=400, detail="Invalid image payload") from error
    if not content:
        raise HTTPException(status_code=400, detail="Image payload is empty")
    if len(content) > MAX_IMAGE_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image payload is too large")
    extension = detect_image_extension(content)
    if not extension:
        raise HTTPException(status_code=400, detail="Uploaded file is not a supported image")
    return schemas.StoredImageOut(image_url=store_image_bytes(content, extension))


FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
PAGES_DIR = FRONTEND_DIR / "pages"


def serve_page(*parts: str) -> FileResponse:
    return FileResponse(PAGES_DIR.joinpath(*parts))


@app.get("/", include_in_schema=False)
@app.get("/index.html", include_in_schema=False)
def home_page():
    return serve_page("home", "index.html")


@app.get("/deck.html", include_in_schema=False)
def deck_page():
    return serve_page("deck", "index.html")


@app.get("/study.html", include_in_schema=False)
def study_page():
    return serve_page("study", "index.html")


@app.get("/settings.html", include_in_schema=False)
def settings_page():
    return serve_page("settings", "index.html")

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=False), name="frontend")
