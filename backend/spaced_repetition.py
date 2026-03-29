import json
import random
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models, schemas
from .time_utils import ensure_utc, now_utc

VALID_RATINGS = {"again", "hard", "good", "easy", "perfect"}
INITIAL_STABILITY = 0.4
INITIAL_DIFFICULTY = 5.0
LEARNING_STEPS = [timedelta(minutes=1), timedelta(minutes=10), timedelta(days=1)]
HARD_LEARNING_DELAYS = [timedelta(minutes=10), timedelta(days=1), timedelta(days=1)]
GRADUATION_INTERVALS = {"good": 2.0, "easy": 3.0, "perfect": 4.0}


def utcnow() -> datetime:
    return now_utc()


def validate_rating(rating: str) -> str:
    normalized = (rating or "").strip().lower()
    if normalized not in VALID_RATINGS:
        raise HTTPException(status_code=400, detail="Invalid rating")
    return normalized


def get_active_cards(deck: models.Deck) -> list[models.Card]:
    return sorted((card for card in deck.cards if card.deleted_at is None), key=lambda item: item.position)


def get_user_deck_progress_row(deck_id: int, user_id: int, db: Session) -> models.UserDeckProgress | None:
    return (
        db.query(models.UserDeckProgress)
        .filter(models.UserDeckProgress.deck_id == deck_id, models.UserDeckProgress.user_id == user_id)
        .first()
    )


def get_latest_active_session(
    user_id: int,
    deck_id: int,
    mode: str,
    shuffle_cards: bool,
    db: Session,
) -> models.StudySession | None:
    return (
        db.query(models.StudySession)
        .filter(
            models.StudySession.user_id == user_id,
            models.StudySession.deck_id == deck_id,
            models.StudySession.mode == mode,
            models.StudySession.shuffle_cards == shuffle_cards,
            models.StudySession.completed_at.is_(None),
        )
        .order_by(models.StudySession.created_at.desc())
        .first()
    )


def decode_card_order(session: models.StudySession) -> list[int]:
    try:
        raw = json.loads(session.card_order or "[]")
    except json.JSONDecodeError:
        return []
    return [int(card_id) for card_id in raw]


def encode_card_order(card_ids: list[int]) -> str:
    return json.dumps(card_ids)


def serialize_user_card_state(state: models.UserCardState | None) -> schemas.UserCardStateOut | None:
    if state is None:
        return None
    return schemas.UserCardStateOut(
        status=state.status,
        due_at=ensure_utc(state.due_at),
        last_reviewed_at=ensure_utc(state.last_reviewed_at),
        stability=state.stability,
        difficulty=state.difficulty,
        scheduled_days=state.scheduled_days,
        elapsed_days=state.elapsed_days,
        reps=state.reps,
        lapses=state.lapses,
        learning_step=state.learning_step,
    )


def serialize_card(card: models.Card, state: models.UserCardState | None = None) -> schemas.CardOut:
    return schemas.CardOut(
        id=card.id,
        front=card.front,
        back=card.back,
        image_url=card.image_url,
        position=card.position,
        deck_id=card.deck_id,
        state=serialize_user_card_state(state),
    )


def refresh_user_deck_progress(
    deck: models.Deck,
    user_id: int,
    db: Session,
    persist: bool = True,
) -> models.UserDeckProgress:
    existing_row = get_user_deck_progress_row(deck.id, user_id, db)
    if existing_row and not persist:
        row = models.UserDeckProgress(
            user_id=existing_row.user_id,
            deck_id=existing_row.deck_id,
            total_cards=existing_row.total_cards,
            new_count=existing_row.new_available_count,
            learning_count=existing_row.learning_count,
            review_count=existing_row.review_count,
            due_count=existing_row.due_review_count,
            known_count=existing_row.known_count,
            last_studied_at=existing_row.last_studied_at,
            updated_at=existing_row.updated_at,
        )
    elif existing_row:
        row = existing_row
    else:
        row = models.UserDeckProgress(user_id=user_id, deck_id=deck.id)
        if persist:
            db.add(row)
            db.flush()

    active_cards = get_active_cards(deck)
    active_card_ids = [card.id for card in active_cards]
    states = []
    if active_card_ids:
        states = (
            db.query(models.UserCardState)
            .filter(models.UserCardState.user_id == user_id, models.UserCardState.card_id.in_(active_card_ids))
            .all()
        )

    now = utcnow()
    states_by_card_id = {state.card_id: state for state in states}
    row.total_cards = len(active_cards)
    row.learning_count = sum(1 for state in states if state.status in {"learning", "relearning"})
    row.review_count = sum(1 for state in states if state.status == "review")
    row.due_review_count = sum(
        1
        for state in states
        if state.status in {"learning", "relearning", "review"} and ensure_utc(state.due_at) <= now
    )
    row.new_available_count = sum(
        1
        for card in active_cards
        if card.id not in states_by_card_id or states_by_card_id[card.id].status == "new"
    )
    row.known_count = sum(
        1
        for state in states
        if state.status == "review" and ensure_utc(state.due_at) > now
    )
    row.last_studied_at = max((ensure_utc(state.last_reviewed_at) for state in states if state.last_reviewed_at), default=row.last_studied_at)
    row.updated_at = now
    if persist:
        db.flush()
    return row


def build_deck_detail_for_user(
    deck: models.Deck,
    db: Session,
    serialize_deck,
    current_user_id: int | None = None,
    saved_link: models.UserSavedDeck | None = None,
    persist_progress: bool = False,
) -> schemas.DeckDetail:
    states_by_card_id = {}
    progress = None
    active_cards = get_active_cards(deck)
    if current_user_id is not None and active_cards:
        states = (
            db.query(models.UserCardState)
            .filter(
                models.UserCardState.user_id == current_user_id,
                models.UserCardState.deck_id == deck.id,
                models.UserCardState.card_id.in_([card.id for card in active_cards]),
            )
            .all()
        )
        states_by_card_id = {state.card_id: state for state in states}
        progress = refresh_user_deck_progress(deck, current_user_id, db, persist=persist_progress)
    elif current_user_id is not None:
        progress = refresh_user_deck_progress(deck, current_user_id, db, persist=persist_progress)
    return schemas.DeckDetail(
        **serialize_deck(deck, current_user_id=current_user_id, saved_link=saved_link, progress=progress).dict(),
        cards=[serialize_card(card, states_by_card_id.get(card.id)) for card in active_cards],
    )


def ensure_user_card_state(user_id: int, deck_id: int, card_id: int, db: Session) -> models.UserCardState:
    state = (
        db.query(models.UserCardState)
        .filter(
            models.UserCardState.user_id == user_id,
            models.UserCardState.deck_id == deck_id,
            models.UserCardState.card_id == card_id,
        )
        .first()
    )
    if state:
        return state
    now = utcnow()
    state = models.UserCardState(
        user_id=user_id,
        deck_id=deck_id,
        card_id=card_id,
        status="new",
        due_at=now,
        stability=INITIAL_STABILITY,
        difficulty=INITIAL_DIFFICULTY,
        scheduled_days=0.0,
        elapsed_days=0.0,
        reps=0,
        lapses=0,
        learning_step=0,
        created_at=now,
        updated_at=now,
    )
    db.add(state)
    db.flush()
    return state


def get_state_elapsed_days(state: models.UserCardState, now: datetime) -> float:
    reviewed_at = ensure_utc(state.last_reviewed_at)
    if not reviewed_at:
        return 0.0
    return max((now - reviewed_at).total_seconds() / 86400, 0.0)


def graduate_interval_days(stability: float, rating: str, previous_status: str) -> float:
    capped_base = min(max(stability * 2.4, 1.0), 4.0 if previous_status in {"new", "learning"} else 7.0)
    interval = max(capped_base, GRADUATION_INTERVALS[rating])
    return round(interval, 2)


def apply_learning_step(state: models.UserCardState, due_in: timedelta, step: int, next_status: str, now: datetime) -> None:
    state.status = next_status
    state.learning_step = step
    state.scheduled_days = round(due_in.total_seconds() / 86400, 4)
    state.due_at = now + due_in


def graduate_to_review(state: models.UserCardState, rating: str, now: datetime, previous_status: str) -> None:
    state.status = "review"
    state.learning_step = 0
    state.stability = min(
        max(0.8, state.stability * {"good": 1.12, "easy": 1.18, "perfect": 1.22}[rating] + 0.2),
        4.0 if previous_status in {"new", "learning"} else 12.0,
    )
    state.difficulty = max(1.0, state.difficulty - {"good": 0.04, "easy": 0.08, "perfect": 0.1}[rating])
    state.scheduled_days = graduate_interval_days(state.stability, rating, previous_status)
    state.due_at = now + timedelta(days=state.scheduled_days)


def schedule_learning(state: models.UserCardState, rating: str, now: datetime, previous_status: str) -> None:
    next_status = "learning" if previous_status in {"new", "learning"} else "relearning"
    current_step = max(state.learning_step, 0)

    if rating == "again":
        state.stability = max(0.15, state.stability * 0.72)
        state.difficulty = min(10.0, state.difficulty + 0.25)
        apply_learning_step(state, LEARNING_STEPS[0], 0, next_status, now)
        return

    if rating == "hard":
        state.stability = max(0.2, state.stability * 0.98 + 0.03)
        state.difficulty = min(10.0, state.difficulty + 0.1)
        hard_step = min(current_step, len(HARD_LEARNING_DELAYS) - 1)
        apply_learning_step(state, HARD_LEARNING_DELAYS[hard_step], hard_step, next_status, now)
        return

    if rating == "good":
        if current_step >= len(LEARNING_STEPS) - 1:
            graduate_to_review(state, "good", now, previous_status)
            return
        state.stability = max(0.3, state.stability * 1.04 + 0.05)
        state.difficulty = max(1.0, state.difficulty - 0.03)
        next_step = current_step + 1
        apply_learning_step(state, LEARNING_STEPS[next_step], next_step, next_status, now)
        return

    if previous_status == "new" and current_step == 0:
        state.stability = max(0.35, state.stability * (1.08 if rating == "easy" else 1.1) + 0.06)
        state.difficulty = max(1.0, state.difficulty - (0.05 if rating == "easy" else 0.07))
        final_step = len(LEARNING_STEPS) - 1
        apply_learning_step(state, LEARNING_STEPS[final_step], final_step, next_status, now)
        return

    graduate_to_review(state, rating, now, previous_status)


def schedule_review(state: models.UserCardState, rating: str, now: datetime) -> None:
    if rating == "again":
        state.status = "relearning"
        state.learning_step = 0
        state.lapses += 1
        state.stability = max(0.2, state.stability * 0.42)
        state.difficulty = min(10.0, state.difficulty + 0.35)
        state.scheduled_days = round(LEARNING_STEPS[0].total_seconds() / 86400, 4)
        state.due_at = now + LEARNING_STEPS[0]
        return

    scheduled_reference = max(state.scheduled_days, 1.0)
    recall_pressure = min(1.2, max(0.75, 0.85 + (state.elapsed_days / scheduled_reference) * 0.18))
    growth_scale = max(0.1, 1.28 - (state.difficulty / 10.0))
    rating_factor = {"hard": 0.52, "good": 0.84, "easy": 0.98, "perfect": 1.05}[rating]
    interval_factor = {"hard": 0.88, "good": 1.0, "easy": 1.1, "perfect": 1.15}[rating]
    difficulty_delta = {"hard": 0.08, "good": -0.03, "easy": -0.07, "perfect": -0.09}[rating]

    state.status = "review"
    state.learning_step = 0
    state.stability = max(0.4, state.stability * (1.0 + growth_scale * rating_factor * recall_pressure) + 0.08)
    state.difficulty = max(1.0, min(10.0, state.difficulty + difficulty_delta))
    state.scheduled_days = round(max(1.0, state.stability * interval_factor), 2)
    state.due_at = now + timedelta(days=state.scheduled_days)


def apply_review_rating(state: models.UserCardState, rating: str, now: datetime) -> tuple[datetime | None, str, float, float]:
    validated_rating = validate_rating(rating)
    previous_due_at = ensure_utc(state.due_at)
    previous_status = state.status
    previous_stability = state.stability
    previous_difficulty = state.difficulty
    state.elapsed_days = round(get_state_elapsed_days(state, now), 4)
    state.reps += 1
    state.updated_at = now
    state.last_reviewed_at = now
    if previous_status in {"new", "learning", "relearning"}:
        schedule_learning(state, validated_rating, now, previous_status)
    else:
        schedule_review(state, validated_rating, now)
    return previous_due_at, previous_status, previous_stability, previous_difficulty


def select_session_cards(
    deck: models.Deck,
    current_user: models.User,
    db: Session,
    mode: str,
    limit: int | None,
    new_cards_limit: int,
) -> list[models.Card]:
    active_cards = get_active_cards(deck)
    if mode == "review_all":
        selected_cards = active_cards
    elif mode == "limited":
        selected_cards = active_cards[: max(limit or 0, 0)]
    else:
        now = utcnow()
        card_ids = [card.id for card in active_cards]
        states = []
        if card_ids:
            states = (
                db.query(models.UserCardState)
                .filter(models.UserCardState.user_id == current_user.id, models.UserCardState.deck_id == deck.id, models.UserCardState.card_id.in_(card_ids))
                .all()
            )
        states_by_card_id = {state.card_id: state for state in states}
        due_cards = [
            card
            for card in active_cards
            if (state := states_by_card_id.get(card.id))
            and state.status in {"learning", "relearning", "review"}
            and ensure_utc(state.due_at) <= now
        ]
        new_cards = [
            card
            for card in active_cards
            if card.id not in states_by_card_id or states_by_card_id[card.id].status == "new"
        ][: max(new_cards_limit, 0)]
        selected_cards = due_cards + [card for card in new_cards if card.id not in {due.id for due in due_cards}]
    if limit is not None and mode != "limited":
        selected_cards = selected_cards[:limit]
    return selected_cards


def build_study_session(
    deck: models.Deck,
    current_user: models.User,
    db: Session,
    mode: str,
    limit: int | None = None,
    new_cards_limit: int = 10,
    shuffle_cards: bool = False,
    persist_progress: bool = False,
) -> schemas.StudySession:
    if mode not in {"review_all", "limited", "interval"}:
        raise HTTPException(status_code=400, detail="Unsupported study mode")
    if limit is not None and limit < 1:
        raise HTTPException(status_code=400, detail="Study session limit must be at least 1")
    if new_cards_limit < 0:
        raise HTTPException(status_code=400, detail="New cards limit cannot be negative")

    active_cards = get_active_cards(deck)
    active_card_ids = {card.id for card in active_cards}
    session = get_latest_active_session(current_user.id, deck.id, mode, shuffle_cards, db)
    if session:
        card_order = [card_id for card_id in decode_card_order(session) if card_id in active_card_ids]
        if session.current_index >= len(card_order):
            session.completed_at = utcnow()
            session.updated_at = session.completed_at
            db.flush()
            session = None
        else:
            session.card_order = encode_card_order(card_order)
            session.updated_at = utcnow()
            db.flush()

    if not session:
        selected_cards = select_session_cards(deck, current_user, db, mode, limit, new_cards_limit)
        if shuffle_cards:
            shuffled_cards = selected_cards[:]
            random.shuffle(shuffled_cards)
            selected_cards = shuffled_cards
        session = models.StudySession(
            id=uuid4().hex,
            user_id=current_user.id,
            deck_id=deck.id,
            mode=mode,
            shuffle_cards=shuffle_cards,
            card_order=encode_card_order([card.id for card in selected_cards]),
            current_index=0,
            created_at=utcnow(),
            updated_at=utcnow(),
        )
        db.add(session)
        db.flush()

    card_order = decode_card_order(session)
    cards_by_id = {card.id: card for card in active_cards}
    ordered_cards = [cards_by_id[card_id] for card_id in card_order if card_id in cards_by_id]
    states = []
    if ordered_cards:
        states = (
            db.query(models.UserCardState)
            .filter(
                models.UserCardState.user_id == current_user.id,
                models.UserCardState.deck_id == deck.id,
                models.UserCardState.card_id.in_([card.id for card in ordered_cards]),
            )
            .all()
        )
    states_by_card_id = {state.card_id: state for state in states}
    progress = refresh_user_deck_progress(deck, current_user.id, db, persist=persist_progress)

    return schemas.StudySession(
        session_id=session.id,
        deck_id=deck.id,
        deck_title=deck.title,
        mode=mode,
        current_index=session.current_index,
        card_order=card_order,
        total_cards=len(ordered_cards),
        cards=[serialize_card(card, states_by_card_id.get(card.id)) for card in ordered_cards],
        progress=schemas.ProgressOut.from_orm(progress),
    )


def advance_session(session_id: str, card_id: int, user_id: int, deck_id: int, db: Session) -> models.StudySession | None:
    session = (
        db.query(models.StudySession)
        .filter(
            models.StudySession.id == session_id,
            models.StudySession.user_id == user_id,
            models.StudySession.deck_id == deck_id,
        )
        .first()
    )
    if not session:
        return None

    card_order = decode_card_order(session)
    if session.current_index >= len(card_order):
        session.completed_at = session.completed_at or utcnow()
        session.updated_at = utcnow()
        db.flush()
        return session

    expected_card_id = card_order[session.current_index]
    if expected_card_id != card_id:
        raise HTTPException(status_code=400, detail="Review card does not match the current session order")

    session.current_index += 1
    session.updated_at = utcnow()
    if session.current_index >= len(card_order):
        session.completed_at = session.updated_at
    db.flush()
    return session
