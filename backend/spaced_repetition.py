from dataclasses import dataclass
import json
import random
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models, schemas
from .time_utils import ensure_utc, now_utc

VALID_RATINGS = {"again", "hard", "good", "easy"}
SM2_RATING_QUALITY = {"again": 1, "hard": 3, "good": 4, "easy": 5}
INITIAL_STABILITY = 0.0
INITIAL_EASE_FACTOR = 2.5
SM2_MIN_EASE_FACTOR = 1.3
SM2_MAX_EASE_FACTOR = 2.8
LEARNING_STEPS = [timedelta(minutes=1), timedelta(minutes=10)]
RELEARNING_STEPS = [timedelta(minutes=10), timedelta(days=1)]
FIRST_REVIEW_INTERVAL_DAYS = 1.0
SECOND_REVIEW_INTERVAL_DAYS = 6.0
LEARNING_EASY_GRADUATION_INTERVAL_DAYS = 3.0
REVIEW_HARD_INTERVAL_MULTIPLIER = 1.2
REVIEW_EASY_INTERVAL_MULTIPLIER = 1.3
REVIEW_LAPSE_EASE_PENALTY = 0.2
REVIEW_OVERDUE_BONUS_WEIGHT = 0.5


@dataclass(frozen=True)
class ReviewAuditSnapshot:
    due_at: datetime | None
    status: str
    legacy_stability: float
    legacy_difficulty: float
    ease_factor: float


@dataclass(frozen=True)
class SchedulingOutcome:
    status: str
    due_in: timedelta
    scheduled_interval_days: float
    learning_step_index: int
    review_count: int
    ease_factor: float
    lapse_increment: int = 0


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
        ease_factor=read_ease_factor(state),
        stability=state.stability,
        difficulty=state.difficulty,
        scheduled_days=state.scheduled_days,
        elapsed_days=state.elapsed_days,
        reps=state.reps,
        lapses=state.lapses,
        learning_step=state.learning_step,
    )


def build_interval_preview_state(state: models.UserCardState | None) -> models.UserCardState:
    now = utcnow()
    if state is None:
        return models.UserCardState(
            status="new",
            due_at=now,
            last_reviewed_at=None,
            stability=INITIAL_STABILITY,
            difficulty=INITIAL_EASE_FACTOR,
            ease_factor=INITIAL_EASE_FACTOR,
            scheduled_days=0.0,
            elapsed_days=0.0,
            reps=0,
            lapses=0,
            learning_step=0,
        )
    return models.UserCardState(
        status=state.status,
        due_at=ensure_utc(state.due_at),
        last_reviewed_at=ensure_utc(state.last_reviewed_at),
        stability=state.stability,
        difficulty=state.difficulty,
        ease_factor=read_ease_factor(state),
        scheduled_days=state.scheduled_days,
        elapsed_days=round(get_state_elapsed_days(state, now), 4),
        reps=state.reps,
        lapses=state.lapses,
        learning_step=state.learning_step,
    )


def format_interval_preview_label(delay: timedelta) -> str:
    total_seconds = max(delay.total_seconds(), 0.0)
    if total_seconds < 60:
        return "now"
    total_minutes = max(round(total_seconds / 60), 1)
    if total_minutes < 60:
        return f"in {total_minutes}m"
    total_hours = round(total_seconds / 3600)
    if total_hours < 48:
        return f"in {total_hours}h"
    total_days = round(total_seconds / 86400)
    if total_days < 30:
        return f"in {total_days}d"
    total_months = max(round(total_days / 30), 1)
    return f"in {total_months}mo"


def build_interval_rating_preview(state: models.UserCardState | None) -> schemas.IntervalRatingPreview:
    preview_state = build_interval_preview_state(state)

    def preview_for(rating: str) -> str:
        if preview_state.status in {"new", "learning", "relearning"}:
            outcome = plan_learning_outcome(preview_state, rating, preview_state.status)
        else:
            outcome = plan_review_outcome(preview_state, rating)
        return format_interval_preview_label(outcome.due_in)

    return schemas.IntervalRatingPreview(
        again=preview_for("again"),
        hard=preview_for("hard"),
        good=preview_for("good"),
        easy=preview_for("easy"),
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
        interval_preview=build_interval_rating_preview(state),
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
        difficulty=INITIAL_EASE_FACTOR,
        ease_factor=INITIAL_EASE_FACTOR,
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


def is_card_due(state: models.UserCardState, now: datetime) -> bool:
    if state.status == "new":
        return True
    return ensure_utc(state.due_at) <= now


def normalize_ease_factor(value: float | None) -> float:
    if value is None:
        return INITIAL_EASE_FACTOR
    return round(min(max(value, SM2_MIN_EASE_FACTOR), SM2_MAX_EASE_FACTOR), 2)


def read_ease_factor(state: models.UserCardState) -> float:
    if state.ease_factor is not None:
        return normalize_ease_factor(state.ease_factor)
    legacy_mirror = state.difficulty
    if legacy_mirror is not None and SM2_MIN_EASE_FACTOR <= legacy_mirror <= SM2_MAX_EASE_FACTOR:
        return normalize_ease_factor(legacy_mirror)
    return INITIAL_EASE_FACTOR


def sync_legacy_scheduler_fields(state: models.UserCardState, ease_factor: float) -> None:
    normalized_ease_factor = normalize_ease_factor(ease_factor)
    state.ease_factor = normalized_ease_factor
    # Keep legacy compatibility for existing clients that still read `difficulty`.
    state.difficulty = normalized_ease_factor
    # Do not fake FSRS-like stability from SM-2 intervals.
    # The legacy field remains available for compatibility, but the scheduler does not synthesize it.


def sm2_next_ease_factor(ease_factor: float, quality: int) -> float:
    adjusted = ease_factor + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    return normalize_ease_factor(adjusted)


def build_learning_outcome(
    next_status: str,
    due_in: timedelta,
    learning_step_index: int,
    ease_factor: float,
) -> SchedulingOutcome:
    return SchedulingOutcome(
        status=next_status,
        due_in=due_in,
        scheduled_interval_days=round(due_in.total_seconds() / 86400, 4),
        learning_step_index=learning_step_index,
        review_count=0,
        ease_factor=ease_factor,
    )


def build_review_outcome(
    interval_days: float,
    review_count: int,
    ease_factor: float,
) -> SchedulingOutcome:
    scheduled_interval_days = max(interval_days, FIRST_REVIEW_INTERVAL_DAYS)
    return SchedulingOutcome(
        status="review",
        due_in=timedelta(days=scheduled_interval_days),
        scheduled_interval_days=scheduled_interval_days,
        learning_step_index=0,
        review_count=review_count,
        ease_factor=ease_factor,
    )


def apply_scheduling_outcome(state: models.UserCardState, outcome: SchedulingOutcome, now: datetime) -> None:
    state.status = outcome.status
    state.learning_step = outcome.learning_step_index
    state.reps = outcome.review_count
    state.lapses += outcome.lapse_increment
    state.scheduled_days = outcome.scheduled_interval_days
    state.due_at = now + outcome.due_in
    sync_legacy_scheduler_fields(state, outcome.ease_factor)


def resolve_learning_workflow(previous_status: str) -> tuple[str, list[timedelta]]:
    if previous_status == "relearning":
        return "relearning", RELEARNING_STEPS
    return "learning", LEARNING_STEPS


def clamp_learning_step_index(raw_step_index: int, steps: list[timedelta]) -> int:
    return min(max(raw_step_index, 0), len(steps) - 1)


def get_hard_learning_delay(steps: list[timedelta], learning_step_index: int) -> timedelta:
    current_delay = steps[learning_step_index]
    if learning_step_index + 1 < len(steps):
        next_delay = steps[learning_step_index + 1]
        return current_delay + (next_delay - current_delay) / 2
    return current_delay * 1.5


def calculate_interval_anchor_days(
    scheduled_interval_days: float,
    elapsed_days: float,
) -> float:
    scheduled = max(scheduled_interval_days, FIRST_REVIEW_INTERVAL_DAYS)
    observed = max(elapsed_days, 0.0)
    effective_elapsed = max(observed, FIRST_REVIEW_INTERVAL_DAYS)
    if effective_elapsed <= scheduled:
        return effective_elapsed
    return scheduled + (effective_elapsed - scheduled) * REVIEW_OVERDUE_BONUS_WEIGHT


def calculate_review_interval_days(
    review_count: int,
    scheduled_interval_days: float,
    elapsed_days: float,
    ease_factor: float,
) -> float:
    if review_count <= 0:
        return FIRST_REVIEW_INTERVAL_DAYS
    if review_count == 1:
        return SECOND_REVIEW_INTERVAL_DAYS
    base_interval_days = calculate_interval_anchor_days(scheduled_interval_days, elapsed_days)
    return base_interval_days * ease_factor


def plan_learning_outcome(state: models.UserCardState, rating: str, previous_status: str) -> SchedulingOutcome:
    next_status, learning_steps = resolve_learning_workflow(previous_status)
    learning_step_index = clamp_learning_step_index(state.learning_step, learning_steps)
    current_ease_factor = read_ease_factor(state)

    if rating == "again":
        return build_learning_outcome(next_status, learning_steps[0], 0, current_ease_factor)

    if rating == "hard":
        return build_learning_outcome(
            next_status,
            get_hard_learning_delay(learning_steps, learning_step_index),
            learning_step_index,
            current_ease_factor,
        )

    if rating == "good":
        if learning_step_index >= len(learning_steps) - 1:
            return build_review_outcome(FIRST_REVIEW_INTERVAL_DAYS, 1, current_ease_factor)
        next_step_index = learning_step_index + 1
        return build_learning_outcome(next_status, learning_steps[next_step_index], next_step_index, current_ease_factor)

    if previous_status == "relearning":
        return build_review_outcome(FIRST_REVIEW_INTERVAL_DAYS, 1, current_ease_factor)

    return build_review_outcome(LEARNING_EASY_GRADUATION_INTERVAL_DAYS, 1, current_ease_factor)


def plan_review_outcome(state: models.UserCardState, rating: str) -> SchedulingOutcome:
    quality = SM2_RATING_QUALITY[rating]
    current_ease_factor = read_ease_factor(state)
    review_count = max(state.reps, 0)
    scheduled_interval_days = max(state.scheduled_days, 0.0)
    elapsed_days = max(state.elapsed_days, 0.0)

    if quality < 3:
        # Penalize forgotten review cards so future interval growth stays cautious after a lapse.
        lapse_ease_factor = normalize_ease_factor(current_ease_factor - REVIEW_LAPSE_EASE_PENALTY)
        return SchedulingOutcome(
            status="relearning",
            due_in=RELEARNING_STEPS[0],
            scheduled_interval_days=round(RELEARNING_STEPS[0].total_seconds() / 86400, 4),
            learning_step_index=0,
            review_count=0,
            ease_factor=lapse_ease_factor,
            lapse_increment=1,
        )

    next_ease_factor = sm2_next_ease_factor(current_ease_factor, quality)
    if rating == "hard":
        base_interval_days = calculate_interval_anchor_days(scheduled_interval_days, elapsed_days)
        next_interval_days = max(FIRST_REVIEW_INTERVAL_DAYS, base_interval_days * REVIEW_HARD_INTERVAL_MULTIPLIER)
    else:
        next_interval_days = calculate_review_interval_days(
            review_count,
            scheduled_interval_days,
            elapsed_days,
            next_ease_factor,
        )
        if rating == "easy":
            next_interval_days *= REVIEW_EASY_INTERVAL_MULTIPLIER
    next_review_count = 1 if review_count <= 0 else review_count + 1
    return build_review_outcome(next_interval_days, next_review_count, next_ease_factor)


def build_review_audit_snapshot(state: models.UserCardState) -> ReviewAuditSnapshot:
    return ReviewAuditSnapshot(
        due_at=ensure_utc(state.due_at),
        status=state.status,
        legacy_stability=state.stability,
        legacy_difficulty=state.difficulty,
        ease_factor=read_ease_factor(state),
    )


def apply_review_rating(state: models.UserCardState, rating: str, now: datetime) -> ReviewAuditSnapshot:
    validated_rating = validate_rating(rating)
    audit_snapshot = build_review_audit_snapshot(state)
    state.elapsed_days = round(get_state_elapsed_days(state, now), 4)
    state.updated_at = now
    state.last_reviewed_at = now
    if audit_snapshot.status in {"new", "learning", "relearning"}:
        outcome = plan_learning_outcome(state, validated_rating, audit_snapshot.status)
    else:
        outcome = plan_review_outcome(state, validated_rating)
    apply_scheduling_outcome(state, outcome, now)
    return audit_snapshot


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
    restart_session: bool = False,
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
    if session and restart_session:
        session.completed_at = utcnow()
        session.updated_at = session.completed_at
        db.flush()
        session = None
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


def advance_session(
    session_id: str,
    card_id: int,
    user_id: int,
    deck_id: int,
    db: Session,
    *,
    rating: str | None = None,
    validate_only: bool = False,
) -> models.StudySession | None:
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
        if validate_only:
            return None
        session.completed_at = session.completed_at or utcnow()
        session.updated_at = utcnow()
        db.flush()
        return session

    expected_card_id = card_order[session.current_index]
    if expected_card_id != card_id:
        raise HTTPException(status_code=400, detail="Review card does not match the current session order")

    if validate_only:
        return session

    if session.mode == "interval" and rating in {"again", "hard"}:
        card_order.append(card_id)
        session.card_order = encode_card_order(card_order)

    session.current_index += 1
    session.updated_at = utcnow()
    if session.current_index >= len(card_order):
        session.completed_at = session.updated_at
    db.flush()
    return session
