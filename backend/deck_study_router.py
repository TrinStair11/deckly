from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from . import schemas
from .auth import get_current_user, get_db
from .decks import get_accessible_deck_or_404
from .spaced_repetition import build_study_session, refresh_user_deck_progress

router = APIRouter()


@router.get("/decks/{deck_id}/study/session", response_model=schemas.StudySession)
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


@router.get("/decks/{deck_id}/study", response_model=schemas.StudySession)
def get_legacy_study_session(
    deck_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, _ = get_accessible_deck_or_404(deck_id, current_user.id, db, x_deck_access_token)
    return build_study_session(deck, current_user, db, mode="interval", persist_progress=False)


@router.get("/decks/{deck_id}/progress", response_model=schemas.ProgressOut)
def get_deck_progress(
    deck_id: int,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    deck, _ = get_accessible_deck_or_404(deck_id, current_user.id, db, x_deck_access_token)
    return refresh_user_deck_progress(deck, current_user.id, db, persist=False)
