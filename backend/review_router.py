from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import get_current_user, get_db
from .decks import get_accessible_deck_or_404, get_card_in_deck_or_404
from .spaced_repetition import (
    advance_session,
    apply_review_rating,
    build_interval_rating_preview,
    ensure_user_card_state,
    is_card_due,
    refresh_user_deck_progress,
    serialize_user_card_state,
    utcnow,
)
from .time_utils import ensure_utc

router = APIRouter(tags=["Reviews"])


def build_review_log(
    payload: schemas.ReviewSubmit,
    current_user: models.User,
    deck_id: int,
    state: models.UserCardState,
    audit_snapshot,
    reviewed_at,
) -> models.ReviewLog:
    return models.ReviewLog(
        user_id=current_user.id,
        deck_id=deck_id,
        card_id=payload.card_id,
        session_id=payload.session_id,
        reviewed_at=reviewed_at,
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
        created_at=reviewed_at,
    )


def process_review_submission(
    payload: schemas.ReviewSubmit,
    current_user: models.User,
    db: Session,
    deck_access_token: str | None = None,
) -> schemas.ReviewResult:
    deck, _ = get_accessible_deck_or_404(payload.deck_id, current_user.id, db, deck_access_token)
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
        raise HTTPException(status_code=400, detail="Карточка ещё не готова к повторению")

    audit_snapshot = apply_review_rating(state, payload.rating, now)
    session = advance_session(
        payload.session_id,
        payload.card_id,
        current_user.id,
        deck.id,
        db,
        rating=payload.rating,
    )
    db.add(build_review_log(payload, current_user, deck.id, state, audit_snapshot, now))
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
        interval_preview=build_interval_rating_preview(state),
    )


@router.post(
    "/reviews/submit",
    response_model=schemas.ReviewResult,
    summary="Отправить результат повторения",
    description="Отправить оценку интервального повторения для карточки в активной или временной учебной сессии и обновить состояние повторения пользователя.",
    response_description="Обновлённый результат повторения и снимок прогресса.",
)
def submit_review(
    payload: schemas.ReviewSubmit,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    return process_review_submission(payload, current_user, db, x_deck_access_token)


@router.post(
    "/cards/{card_id}/review",
    response_model=schemas.ReviewResult,
    summary="Повторить карточку напрямую",
    description="Отправить оценку для одной карточки без предварительной загрузки полной учебной сессии. Сервер автоматически создаёт временный идентификатор сессии.",
    response_description="Обновлённый результат повторения для карточки.",
)
def review_card(
    card_id: int,
    payload: schemas.CardReview,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
    x_deck_access_token: Annotated[str | None, Header()] = None,
):
    card = db.query(models.Card).filter(models.Card.id == card_id, models.Card.deleted_at.is_(None)).first()
    if not card:
        raise HTTPException(status_code=404, detail="Карточка не найдена")
    return process_review_submission(
        schemas.ReviewSubmit(deck_id=card.deck_id, card_id=card.id, rating=payload.rating, session_id=uuid4().hex),
        current_user,
        db,
        x_deck_access_token,
    )
