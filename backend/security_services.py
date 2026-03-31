from datetime import timedelta

from fastapi import HTTPException, Request, Response
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import create_access_token, set_auth_cookie, verify_password
from .decks import check_private_deck_password, create_deck_access_token, get_deck_or_404
from .runtime import FAILED_ATTEMPTS, RATE_LIMIT_STORE, RATE_LIMIT_WINDOW_SECONDS


def get_rate_limit_bucket(scope: str) -> dict[str, list[float]]:
    return FAILED_ATTEMPTS[scope]


def rate_limit_key(scope: str, identifier: str, request: Request | None) -> str:
    return RATE_LIMIT_STORE.build_key(scope, identifier, request)


def enforce_rate_limit(scope: str, identifier: str, request: Request | None, limit: int) -> str:
    return RATE_LIMIT_STORE.enforce(scope, identifier, request, limit, RATE_LIMIT_WINDOW_SECONDS)


def record_rate_limit_failure(scope: str, key: str) -> None:
    RATE_LIMIT_STORE.record_failure(scope, key, RATE_LIMIT_WINDOW_SECONDS)


def clear_rate_limit_failures(scope: str, key: str) -> None:
    RATE_LIMIT_STORE.clear_failures(scope, key)


def perform_login(
    payload: schemas.UserLogin,
    db: Session,
    response: Response | None = None,
    request: Request | None = None,
    *,
    rate_limit: int,
) -> schemas.Token:
    normalized_email = payload.email.strip().lower()
    rate_limit_scope = enforce_rate_limit("login", normalized_email, request, rate_limit)
    user = db.query(models.User).filter(models.User.email == normalized_email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        record_rate_limit_failure("login", rate_limit_scope)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": str(user.id)}, expires_delta=timedelta(minutes=60 * 24))
    if response is not None:
        set_auth_cookie(response, token)
    clear_rate_limit_failures("login", rate_limit_scope)
    return {"access_token": token, "token_type": "bearer"}


def grant_private_deck_access(
    deck_id: int,
    payload: schemas.DeckAccessRequest,
    db: Session,
    request: Request | None = None,
    *,
    rate_limit: int,
) -> schemas.DeckAccessToken:
    deck = get_deck_or_404(deck_id, db)
    if deck.visibility != "private":
        raise HTTPException(status_code=400, detail="This deck does not require a password")
    rate_limit_scope = enforce_rate_limit("deck-access", str(deck_id), request, rate_limit)
    if not check_private_deck_password(payload.password, deck.password_hash):
        record_rate_limit_failure("deck-access", rate_limit_scope)
        raise HTTPException(status_code=401, detail="Incorrect deck password")
    clear_rate_limit_failures("deck-access", rate_limit_scope)
    return {"access_token": create_deck_access_token(deck.id), "token_type": "deck-access"}
