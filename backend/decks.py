from datetime import timedelta

from fastapi import HTTPException
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ALGORITHM,
    SECRET_KEY,
    create_access_token,
    hash_password,
    verify_password,
)
from .spaced_repetition import get_active_cards


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
        title=deck.title if is_public or reveal_owner else "Приватная колода",
        visibility=deck.visibility,
        requires_password=deck.visibility == "private",
        owner_id=deck.owner_id if is_public or reveal_owner else None,
        owner_name=get_owner_name(deck.owner) if is_public or reveal_owner else None,
    )


def validate_deck_privacy(visibility: str, password: str) -> tuple[str, str]:
    normalized_visibility = visibility.strip().lower()
    normalized_password = password.strip()
    if normalized_visibility not in {"public", "private"}:
        raise HTTPException(status_code=400, detail="Видимость должна быть public или private")
    if normalized_visibility == "private" and len(normalized_password) < 4:
        raise HTTPException(status_code=400, detail="Для приватной колоды нужен пароль минимум из 4 символов")
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
        raise HTTPException(status_code=404, detail="Колода не найдена")
    return deck


def get_owned_deck_or_404(deck_id: int, user_id: int, db: Session) -> models.Deck:
    deck = get_deck_or_404(deck_id, db)
    if deck.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Изменять эту колоду может только владелец")
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
    raise HTTPException(status_code=403, detail="У вас нет доступа к этой колоде")


def ensure_shared_deck_access(deck: models.Deck, deck_access_token: str | None) -> None:
    if deck.visibility == "public":
        return
    if not deck_access_token or not verify_deck_access_token(deck_access_token, deck.id):
        raise HTTPException(status_code=403, detail="Для этой колоды требуется пароль")


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
        raise HTTPException(status_code=404, detail="Карточка не найдена")
    if card.deck.owner_id != user_id:
        raise HTTPException(status_code=403, detail="Изменять эту колоду может только владелец")
    return card


def get_card_in_deck_or_404(deck_id: int, card_id: int, db: Session) -> models.Card:
    card = (
        db.query(models.Card)
        .filter(models.Card.id == card_id, models.Card.deck_id == deck_id, models.Card.deleted_at.is_(None))
        .first()
    )
    if not card:
        raise HTTPException(status_code=404, detail="Карточка не найдена")
    return card


def save_deck_to_library(
    deck: models.Deck,
    current_user: models.User,
    db: Session,
) -> tuple[models.UserSavedDeck, bool]:
    if deck.owner_id == current_user.id:
        raise HTTPException(status_code=400, detail="Нельзя сохранить в библиотеку собственную колоду")
    saved_link = get_saved_deck_link(deck.id, current_user.id, db)
    if saved_link:
        return saved_link, False
    saved_link = models.UserSavedDeck(user_id=current_user.id, deck_id=deck.id)
    db.add(saved_link)
    db.commit()
    db.refresh(saved_link)
    return saved_link, True


def hash_private_deck_password(visibility: str, password: str, existing_hash: str | None = None) -> str | None:
    if visibility == "public":
        return None
    if password:
        return hash_password(password)
    return existing_hash


def check_private_deck_password(password: str, password_hash: str | None) -> bool:
    return bool(password_hash) and verify_password(password, password_hash)
