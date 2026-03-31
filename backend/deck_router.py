from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import get_current_user, get_db
from .card_router import (
    create_card,
    delete_card,
    list_cards,
    reorder_cards,
    router as card_router,
    update_card,
)
from .deck_share_router import (
    access_private_deck_endpoint,
    build_shared_study_preview,
    get_shared_deck,
    get_shared_deck_meta,
    get_shared_study_session,
    grant_private_deck_access,
    router as deck_share_router,
    save_shared_deck,
)
from .deck_study_router import (
    get_deck_progress,
    get_legacy_study_session,
    get_study_session,
    router as deck_study_router,
)
from .decks import (
    get_accessible_deck_or_404,
    get_next_card_position,
    get_owned_deck_or_404,
    hash_private_deck_password,
    serialize_deck,
    validate_deck_privacy,
)
from .review_router import (
    build_review_log,
    process_review_submission,
    review_card,
    router as review_router,
    submit_review,
)
from .spaced_repetition import (
    build_deck_detail_for_user,
    refresh_user_deck_progress,
    utcnow,
)

router = APIRouter()


def apply_deck_update(deck: models.Deck, payload: schemas.DeckUpdate) -> None:
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
    deck.password_hash = hash_private_deck_password(raw_visibility, password, deck.password_hash)
    deck.updated_at = utcnow()


@router.post("/decks", response_model=schemas.DeckOut, status_code=status.HTTP_201_CREATED)
def create_deck(deck: schemas.DeckCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    visibility, password = validate_deck_privacy(deck.visibility, deck.password if deck.visibility == "private" else "")
    now = utcnow()
    new_deck = models.Deck(
        title=deck.title.strip(),
        description=deck.description.strip(),
        visibility=visibility,
        password_hash=hash_private_deck_password(visibility, password),
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


@router.get("/decks", response_model=list[schemas.DeckOut])
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


@router.get("/decks/{deck_id}", response_model=schemas.DeckDetail)
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


@router.put("/decks/{deck_id}", response_model=schemas.DeckOut)
def update_deck(deck_id: int, payload: schemas.DeckUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    deck = get_owned_deck_or_404(deck_id, current_user.id, db)
    apply_deck_update(deck, payload)
    db.commit()
    db.refresh(deck)
    progress = refresh_user_deck_progress(deck, current_user.id, db)
    db.commit()
    return serialize_deck(deck, current_user_id=current_user.id, progress=progress)


@router.delete("/decks/{deck_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_deck(deck_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    deck = get_owned_deck_or_404(deck_id, current_user.id, db)
    db.delete(deck)
    db.commit()


router.include_router(deck_study_router)
router.include_router(deck_share_router)
router.include_router(card_router)
router.include_router(review_router)
