from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Request, Response, status
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import get_current_user, get_db
from .decks import (
    ensure_shared_deck_access,
    get_deck_or_404,
    save_deck_to_library,
    serialize_deck,
    serialize_share_meta,
    verify_deck_access_token,
)
from .runtime import DECK_ACCESS_RATE_LIMIT as DEFAULT_DECK_ACCESS_RATE_LIMIT
from .security_services import grant_private_deck_access
from .spaced_repetition import build_deck_detail_for_user, get_active_cards, refresh_user_deck_progress, serialize_card, utcnow

router = APIRouter(tags=["Sharing"])

DECK_ACCESS_RATE_LIMIT = DEFAULT_DECK_ACCESS_RATE_LIMIT


def build_shared_study_preview(deck: models.Deck) -> schemas.StudySession:
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


@router.get(
    "/shared/decks/{deck_id}/meta",
    response_model=schemas.DeckShareMeta,
    summary="Get shared deck metadata",
    description="Return share-safe metadata for a deck without loading the full deck body. If a valid `X-Deck-Access-Token` is supplied, private metadata can be expanded.",
    response_description="Shared deck metadata.",
)
def get_shared_deck_meta(
    deck_id: int,
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck = get_deck_or_404(deck_id, db)
    reveal_owner = bool(x_deck_access_token and verify_deck_access_token(x_deck_access_token, deck.id))
    return serialize_share_meta(deck, reveal_owner=reveal_owner)


@router.get(
    "/shared/decks/{deck_id}",
    response_model=schemas.DeckDetail,
    summary="Get shared deck",
    description="Load a shared deck for preview or study. Private decks require a valid `X-Deck-Access-Token`.",
    response_description="Shared deck details.",
)
def get_shared_deck(
    deck_id: int,
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck = get_deck_or_404(deck_id, db)
    ensure_shared_deck_access(deck, x_deck_access_token)
    return build_deck_detail_for_user(deck, db=db, serialize_deck=serialize_deck, persist_progress=False)


@router.get(
    "/shared/decks/{deck_id}/study",
    response_model=schemas.StudySession,
    summary="Preview shared deck study",
    description="Build a read-only study preview for a shared deck. Private decks require a valid `X-Deck-Access-Token`.",
    response_description="Study preview for the shared deck.",
)
def get_shared_study_session(
    deck_id: int,
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck = get_deck_or_404(deck_id, db)
    ensure_shared_deck_access(deck, x_deck_access_token)
    return build_shared_study_preview(deck)


@router.post(
    "/shared/decks/{deck_id}/access",
    response_model=schemas.DeckAccessToken,
    summary="Unlock private shared deck",
    description="Validate the shared deck password and issue a short-lived deck access token used in the `X-Deck-Access-Token` header.",
    response_description="Deck access token for subsequent shared-deck requests.",
)
def access_private_deck_endpoint(
    deck_id: int,
    payload: schemas.DeckAccessRequest,
    db: Session = Depends(get_db),
    request: Request = None,
):
    return grant_private_deck_access(deck_id, payload, db, request=request, rate_limit=DECK_ACCESS_RATE_LIMIT)


@router.post(
    "/decks/{deck_id}/save-to-library",
    response_model=schemas.DeckOut,
    status_code=status.HTTP_201_CREATED,
    summary="Save shared deck to library",
    description="Legacy alias for saving an accessible shared deck into the authenticated user's library.",
    response_description="Saved deck in the user's library.",
    deprecated=True,
)
@router.post(
    "/shared/decks/{deck_id}/save",
    response_model=schemas.DeckOut,
    status_code=status.HTTP_201_CREATED,
    summary="Save shared deck to library",
    description="Save an accessible shared deck into the authenticated user's library. Private decks require a valid `X-Deck-Access-Token`.",
    response_description="Saved deck in the user's library.",
)
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
