from datetime import timedelta

import pytest
from fastapi import HTTPException

from backend import models, schemas
from backend.main import (
    access_private_deck,
    create_deck,
    create_deck_access_token,
    create_card,
    get_deck,
    get_deck_progress,
    get_shared_deck,
    get_shared_deck_meta,
    get_shared_study_session,
    get_study_session,
    list_decks,
    refresh_user_deck_progress,
    register,
    search_images,
    save_deck_to_library,
    save_shared_deck,
    serialize_deck,
    import_image,
    submit_review,
    upload_image,
    update_card,
    update_account_email,
    update_account_password,
    update_deck,
    validate_deck_privacy,
    verify_deck_access_token,
)
from backend.auth import verify_password
from backend.time_utils import now_utc
from tests.helpers import make_email, register_user


def test_register_creates_user(db_session):
    email = make_email()

    user = register(schemas.UserCreate(email=email, password="secret12"), db_session)

    assert user.email == email
    assert user.id is not None


def test_create_and_list_decks_include_user_progress(db_session):
    owner = register_user(db_session, email=make_email())
    other = register_user(db_session, email=make_email())

    created = create_deck(
        schemas.DeckCreate(
            name="Spanish",
            description="Daily words",
            cards=[schemas.CardSeed(front="Hola", back="Hello")],
        ),
        current_user=owner,
        db=db_session,
    )
    source = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(source, other, db_session)

    owner_decks = list_decks(current_user=owner, db=db_session)
    other_decks = list_decks(current_user=other, db=db_session)

    assert owner_decks[0].title == "Spanish"
    assert owner_decks[0].progress.total_cards == 1
    assert other_decks[0].saved_in_library is True
    assert other_decks[0].progress.new_available_count == 1


def test_serialize_deck_counts_cards_and_progress(db_session):
    owner = register_user(db_session, email=make_email())
    deck = models.Deck(title="React", description="Hooks", visibility="private", owner_id=owner.id, created_at=now_utc(), updated_at=now_utc())
    db_session.add(deck)
    db_session.commit()
    db_session.refresh(deck)
    db_session.add(models.Card(front="Q1", back="A1", deck_id=deck.id))
    db_session.commit()

    progress = refresh_user_deck_progress(deck, owner.id, db_session)
    payload = serialize_deck(deck, current_user_id=owner.id, progress=progress)

    assert payload.title == "React"
    assert payload.card_count == 1
    assert payload.progress.total_cards == 1


def test_get_deck_returns_sorted_cards_and_user_state(db_session):
    owner = register_user(db_session, email=make_email())
    deck_out = create_deck(
        schemas.DeckCreate(name="Algorithms", description="Core deck"),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == deck_out.id).first()
    later = models.Card(front="Later", back="A2", deck_id=deck.id, position=2)
    sooner = models.Card(front="Soon", back="A1", deck_id=deck.id, position=1)
    db_session.add_all([later, sooner])
    db_session.commit()
    db_session.refresh(sooner)
    state = models.UserCardState(user_id=owner.id, deck_id=deck.id, card_id=sooner.id, status="review", due_at=now_utc(), stability=2.0, difficulty=4.0)
    db_session.add(state)
    db_session.commit()

    detail = get_deck(deck.id, current_user=owner, db=db_session)

    assert [card.front for card in detail.cards] == ["Soon", "Later"]
    assert detail.cards[0].state.status == "review"


def test_private_deck_access_requires_password(db_session):
    owner = register_user(db_session, email=make_email())
    deck = create_deck(
        schemas.DeckCreate(name="Secret deck", description="Locked", visibility="private", access_password="abcd1234"),
        current_user=owner,
        db=db_session,
    )

    meta = get_shared_deck_meta(deck.id, db_session)
    token = access_private_deck(deck.id, schemas.DeckAccessRequest(password="abcd1234"), db=db_session)
    detail = get_shared_deck(deck.id, db=db_session, x_deck_access_token=token["access_token"])

    assert meta.requires_password is True
    assert meta.owner_name is None
    assert detail.title == "Secret deck"


def test_update_account_email_requires_current_password_and_unique_email(db_session):
    user = register_user(db_session, email=make_email())
    second_user = register_user(db_session, email=make_email())

    with pytest.raises(HTTPException, match="Current password is incorrect"):
        update_account_email(
            schemas.AccountEmailUpdate(
                new_email="fresh@example.com",
                confirm_email="fresh@example.com",
                current_password="wrong-pass",
            ),
            current_user=user,
            db=db_session,
        )

    with pytest.raises(HTTPException, match="Email is already in use"):
        update_account_email(
            schemas.AccountEmailUpdate(
                new_email=second_user.email,
                confirm_email=second_user.email,
                current_password="secret12",
            ),
            current_user=user,
            db=db_session,
        )


def test_update_account_email_updates_profile(db_session):
    user = register_user(db_session, email=make_email())

    updated = update_account_email(
        schemas.AccountEmailUpdate(
            new_email="new-address@example.com",
            confirm_email="new-address@example.com",
            current_password="secret12",
        ),
        current_user=user,
        db=db_session,
    )

    assert updated.email == "new-address@example.com"
    persisted = db_session.query(models.User).filter(models.User.id == user.id).first()
    assert persisted.email == "new-address@example.com"


def test_update_account_password_requires_current_password_and_confirmation(db_session):
    user = register_user(db_session, email=make_email())

    with pytest.raises(HTTPException, match="Current password is incorrect"):
        update_account_password(
            schemas.AccountPasswordUpdate(
                current_password="bad-pass",
                new_password="new-secret12",
                confirm_new_password="new-secret12",
            ),
            current_user=user,
            db=db_session,
        )

    with pytest.raises(HTTPException, match="Password confirmation does not match"):
        update_account_password(
            schemas.AccountPasswordUpdate(
                current_password="secret12",
                new_password="new-secret12",
                confirm_new_password="not-matching",
            ),
            current_user=user,
            db=db_session,
        )


def test_update_account_password_persists_new_hash(db_session):
    user = register_user(db_session, email=make_email())

    result = update_account_password(
        schemas.AccountPasswordUpdate(
            current_password="secret12",
            new_password="new-secret12",
            confirm_new_password="new-secret12",
        ),
        current_user=user,
        db=db_session,
    )

    refreshed = db_session.query(models.User).filter(models.User.id == user.id).first()
    assert result.message == "Password updated successfully"
    assert verify_password("new-secret12", refreshed.password_hash) is True
    assert verify_password("secret12", refreshed.password_hash) is False


def test_shared_study_session_returns_read_only_preview_for_public_deck(db_session):
    owner = register_user(db_session, email=make_email())
    deck = create_deck(
        schemas.DeckCreate(name="Preview deck", description="Shared", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )

    session = get_shared_study_session(deck.id, db=db_session)

    assert session.mode == "review_all"
    assert session.total_cards == 1
    assert session.progress.new_available_count == 1


def test_save_shared_deck_creates_reference_without_duplication(db_session):
    owner = register_user(db_session, email=make_email())
    other = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(
            name="Biology",
            description="Cells",
            cards=[schemas.CardSeed(front="Cell", back="Basic unit")],
        ),
        current_user=owner,
        db=db_session,
    )

    first = save_shared_deck(created.id, current_user=other, db=db_session)
    second = save_shared_deck(created.id, current_user=other, db=db_session)

    assert first.id == second.id
    assert db_session.query(models.UserSavedDeck).filter_by(user_id=other.id, deck_id=created.id).count() == 1


def test_interval_study_session_is_personal_per_user(db_session):
    owner = register_user(db_session, email=make_email())
    learner_a = register_user(db_session, email=make_email())
    learner_b = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(
            name="Shared",
            description="Deck",
            cards=[
                schemas.CardSeed(front="One", back="1"),
                schemas.CardSeed(front="Two", back="2"),
            ],
        ),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    for learner in (learner_a, learner_b):
        save_deck_to_library(deck, learner, db_session)
    card_one = db_session.query(models.Card).filter(models.Card.deck_id == deck.id, models.Card.front == "One").first()
    card_two = db_session.query(models.Card).filter(models.Card.deck_id == deck.id, models.Card.front == "Two").first()
    db_session.add(
        models.UserCardState(
            user_id=learner_a.id,
            deck_id=deck.id,
            card_id=card_one.id,
            status="review",
            due_at=now_utc() + timedelta(days=3),
            last_reviewed_at=now_utc(),
            stability=5.0,
            difficulty=3.0,
            ease_factor=2.5,
            scheduled_days=5.0,
            elapsed_days=1.0,
            reps=4,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.add(
        models.UserCardState(
            user_id=learner_b.id,
            deck_id=deck.id,
            card_id=card_one.id,
            status="review",
            due_at=now_utc() - timedelta(minutes=1),
            last_reviewed_at=now_utc() - timedelta(days=5),
            stability=5.0,
            difficulty=3.0,
            ease_factor=2.5,
            scheduled_days=5.0,
            elapsed_days=5.0,
            reps=4,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    session_a = get_study_session(deck.id, current_user=learner_a, db=db_session)
    session_b = get_study_session(deck.id, current_user=learner_b, db=db_session)

    assert [card.front for card in session_a.cards] == ["Two"]
    assert [card.front for card in session_b.cards] == ["One", "Two"]


def test_submit_review_creates_and_persists_personal_state(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Spanish", description="Words", cards=[schemas.CardSeed(front="Hola", back="Hello")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="session-1", response_time_ms=1200),
        current_user=learner,
        db=db_session,
    )

    state = db_session.query(models.UserCardState).filter_by(user_id=learner.id, card_id=card.id).first()
    log = db_session.query(models.ReviewLog).filter_by(user_id=learner.id, card_id=card.id).first()

    assert result.state.status in {"learning", "review"}
    assert state is not None
    assert log.rating == "good"
    assert result.state.ease_factor == 2.5
    assert result.progress.total_cards == 1


def test_sm2_new_card_good_moves_card_to_learning_step_before_graduation(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Spanish", description="Words", cards=[schemas.CardSeed(front="Hola", back="Hello")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="sm2-step-1"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "learning"
    assert result.state.learning_step == 1
    assert result.state.reps == 0
    assert result.state.ease_factor == 2.5
    assert result.next_due_at <= now_utc() + timedelta(minutes=11)


def test_sm2_learning_graduation_sets_first_review_interval_to_one_day(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Graduate", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="learning",
            due_at=now_utc(),
            last_reviewed_at=now_utc() - timedelta(minutes=15),
            stability=0.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=0.0069,
            elapsed_days=0.0,
            reps=0,
            lapses=0,
            learning_step=1,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="sm2-step-2"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "review"
    assert result.state.reps == 1
    assert result.state.scheduled_days == 1.0
    assert result.state.ease_factor == 2.5
    assert result.next_due_at >= now_utc() + timedelta(hours=23)


def test_sm2_review_second_success_uses_six_day_interval(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Intervals", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() - timedelta(hours=1),
            last_reviewed_at=now_utc() - timedelta(days=1),
            stability=1.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=1.0,
            elapsed_days=1.0,
            reps=1,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="sm2-review-2"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "review"
    assert result.state.reps == 2
    assert result.state.scheduled_days == 6.0


def test_sm2_review_second_hard_is_more_conservative_than_good(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Intervals", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() - timedelta(hours=1),
            last_reviewed_at=now_utc() - timedelta(days=1),
            stability=1.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=1.0,
            elapsed_days=1.0,
            reps=1,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="hard", session_id="sm2-review-2-hard"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "review"
    assert result.state.reps == 2
    assert result.state.ease_factor == 2.36
    assert result.state.scheduled_days == pytest.approx(1.2)


def test_sm2_review_growth_uses_ease_factor_after_second_success(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Intervals", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() - timedelta(hours=1),
            last_reviewed_at=now_utc() - timedelta(days=6),
            stability=42.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=6.0,
            elapsed_days=6.0,
            reps=2,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="sm2-review-3"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "review"
    assert result.state.reps == 3
    assert result.state.scheduled_days == 15.0
    assert result.state.stability == 42.0


def test_sm2_review_hard_growth_is_more_conservative_than_good(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Intervals", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() - timedelta(hours=1),
            last_reviewed_at=now_utc() - timedelta(days=6),
            stability=6.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=6.0,
            elapsed_days=6.0,
            reps=2,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="hard", session_id="sm2-review-3-hard"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "review"
    assert result.state.reps == 3
    assert result.state.ease_factor == 2.36
    assert result.state.scheduled_days == pytest.approx(7.2)


def test_sm2_review_easy_growth_is_more_aggressive_than_good(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Intervals", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() - timedelta(hours=1),
            last_reviewed_at=now_utc() - timedelta(days=6),
            stability=6.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=6.0,
            elapsed_days=6.0,
            reps=2,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="easy", session_id="sm2-review-3-easy"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "review"
    assert result.state.reps == 3
    assert result.state.ease_factor == 2.6
    assert result.state.scheduled_days == pytest.approx(20.28)


def test_sm2_review_keeps_fractional_intervals_without_rounding_up(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Round up", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() - timedelta(hours=1),
            last_reviewed_at=now_utc() - timedelta(days=7),
            stability=7.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=7.0,
            elapsed_days=7.0,
            reps=2,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="sm2-round-up"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "review"
    assert result.state.reps == 3
    assert result.state.scheduled_days == pytest.approx(17.5)


def test_sm2_learning_hard_keeps_step_and_delay_without_changing_ease_factor(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Hard step", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="hard", session_id="sm2-hard-learning"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "learning"
    assert result.state.learning_step == 0
    assert result.state.ease_factor == 2.5
    assert result.next_due_at >= now_utc() + timedelta(minutes=5)
    assert result.next_due_at <= now_utc() + timedelta(minutes=7)


def test_sm2_learning_easy_graduates_without_changing_ease_factor(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Easy step", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="easy", session_id="sm2-easy-learning"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "review"
    assert result.state.reps == 1
    assert result.state.ease_factor == 2.5
    assert result.state.scheduled_days == 3.0
    assert result.next_due_at >= now_utc() + timedelta(days=2, hours=23)
    assert result.next_due_at <= now_utc() + timedelta(days=3, hours=1)


def test_relearning_good_advances_to_cautious_one_day_step_before_review(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Relearning", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="relearning",
            due_at=now_utc() - timedelta(minutes=1),
            last_reviewed_at=now_utc() - timedelta(minutes=15),
            stability=4.0,
            difficulty=2.3,
            ease_factor=2.3,
            scheduled_days=0.0069,
            elapsed_days=0.01,
            reps=0,
            lapses=1,
            learning_step=0,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="sm2-relearning-step-1"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "relearning"
    assert result.state.learning_step == 1
    assert result.state.reps == 0
    assert result.state.ease_factor == 2.3
    assert result.state.scheduled_days == 1.0
    assert result.next_due_at >= now_utc() + timedelta(hours=23)
    assert result.next_due_at <= now_utc() + timedelta(hours=25)


def test_sm2_overdue_success_rewards_observed_retention(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Overdue", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() - timedelta(days=4),
            last_reviewed_at=now_utc() - timedelta(days=10),
            stability=6.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=6.0,
            elapsed_days=10.0,
            reps=2,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="sm2-overdue-success"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "review"
    assert result.state.reps == 3
    assert result.state.scheduled_days == pytest.approx(20.0)


def test_submit_review_rejects_non_due_card_without_matching_session(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Too early", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() + timedelta(days=2),
            last_reviewed_at=now_utc() - timedelta(days=1),
            stability=6.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=6.0,
            elapsed_days=1.0,
            reps=2,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    with pytest.raises(HTTPException, match="not due"):
        submit_review(
            schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="no-active-session"),
            current_user=learner,
            db=db_session,
        )


def test_interval_session_requeues_below_four_responses(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Repeat today", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)

    session = get_study_session(deck.id, current_user=learner, db=db_session)
    card = session.cards[0]
    review_result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="hard", session_id=session.session_id),
        current_user=learner,
        db=db_session,
    )
    resumed = get_study_session(deck.id, current_user=learner, db=db_session)

    assert review_result.session_current_index == 1
    assert resumed.session_id == session.session_id
    assert resumed.current_index == 1
    assert resumed.card_order == [card.id, card.id]
    assert [item.id for item in resumed.cards] == [card.id, card.id]


def test_interval_session_immediate_second_success_is_less_generous_after_early_retry(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Repeat today", description="Deck", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() - timedelta(hours=1),
            last_reviewed_at=now_utc() - timedelta(days=6),
            stability=6.0,
            difficulty=2.5,
            ease_factor=2.5,
            scheduled_days=6.0,
            elapsed_days=6.0,
            reps=2,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    session = get_study_session(deck.id, current_user=learner, db=db_session)
    first_result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="hard", session_id=session.session_id),
        current_user=learner,
        db=db_session,
    )
    second_result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id=session.session_id),
        current_user=learner,
        db=db_session,
    )

    assert first_result.state.scheduled_days == pytest.approx(7.2)
    assert second_result.state.reps == 4
    assert second_result.state.scheduled_days == pytest.approx(2.36)


def test_interval_session_resumes_current_index_after_review(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(
            name="Resume",
            description="Session",
            cards=[schemas.CardSeed(front="One", back="1"), schemas.CardSeed(front="Two", back="2")],
        ),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)

    session = get_study_session(deck.id, current_user=learner, db=db_session)
    first_card = session.cards[0]
    review_result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=first_card.id, rating="good", session_id=session.session_id),
        current_user=learner,
        db=db_session,
    )
    resumed = get_study_session(deck.id, current_user=learner, db=db_session)

    assert review_result.session_current_index == 1
    assert resumed.session_id == session.session_id
    assert resumed.current_index == 1


def test_review_lapse_moves_card_to_relearning(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="History", description="Dates", cards=[schemas.CardSeed(front="1066", back="Norman conquest")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    db_session.add(
        models.UserCardState(
            user_id=learner.id,
            deck_id=deck.id,
            card_id=card.id,
            status="review",
            due_at=now_utc() - timedelta(days=1),
            last_reviewed_at=now_utc() - timedelta(days=5),
            stability=4.0,
            difficulty=4.0,
            ease_factor=2.5,
            scheduled_days=4.0,
            elapsed_days=5.0,
            reps=3,
            lapses=0,
            learning_step=0,
        )
    )
    db_session.commit()

    result = submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="again", session_id="session-2"),
        current_user=learner,
        db=db_session,
    )

    assert result.state.status == "relearning"
    assert result.state.lapses == 1
    assert result.state.ease_factor == 2.3
    assert result.next_due_at >= now_utc() + timedelta(minutes=9)
    assert result.next_due_at <= now_utc() + timedelta(minutes=11)


def test_get_deck_progress_is_user_specific(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="French", description="Words", cards=[schemas.CardSeed(front="Bonjour", back="Hello")]),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)

    progress_before = get_deck_progress(deck.id, current_user=learner, db=db_session)
    before_new_count = progress_before.new_available_count
    card = db_session.query(models.Card).filter(models.Card.deck_id == deck.id).first()
    submit_review(
        schemas.ReviewSubmit(deck_id=deck.id, card_id=card.id, rating="good", session_id="session-3"),
        current_user=learner,
        db=db_session,
    )
    progress_after = get_deck_progress(deck.id, current_user=learner, db=db_session)

    assert progress_before.total_cards == 1
    assert before_new_count == 1
    assert progress_after.new_available_count <= before_new_count


def test_owner_updates_are_visible_to_saved_deck_users(db_session):
    owner = register_user(db_session, email=make_email())
    other = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="History", description="Old copy", cards=[schemas.CardSeed(front="One", back="1")]),
        current_user=owner,
        db=db_session,
    )
    save_shared_deck(created.id, current_user=other, db=db_session)

    update_deck(
        created.id,
        schemas.DeckUpdate(name="History Updated", description="Fresh source"),
        current_user=owner,
        db=db_session,
    )
    updated = get_deck(created.id, current_user=other, db=db_session)

    assert updated.title == "History Updated"
    assert updated.description == "Fresh source"


def test_create_deck_assigns_incrementing_card_positions(db_session):
    owner = register_user(db_session, email=make_email())

    created = create_deck(
        schemas.DeckCreate(
            name="Ordered",
            cards=[
                schemas.CardSeed(front="One", back="1"),
                schemas.CardSeed(front="Two", back="2"),
                schemas.CardSeed(front="Three", back="3"),
            ],
        ),
        current_user=owner,
        db=db_session,
    )

    cards = (
        db_session.query(models.Card)
        .filter(models.Card.deck_id == created.id)
        .order_by(models.Card.id)
        .all()
    )

    assert [card.position for card in cards] == [0, 1, 2]


def test_saved_private_deck_requires_access_token_after_visibility_change(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Protected", description="Deck"),
        current_user=owner,
        db=db_session,
    )
    deck = db_session.query(models.Deck).filter(models.Deck.id == created.id).first()
    save_deck_to_library(deck, learner, db_session)

    update_deck(
        created.id,
        schemas.DeckUpdate(name="Protected", description="Deck", visibility="private", access_password="abcd"),
        current_user=owner,
        db=db_session,
    )

    with pytest.raises(HTTPException, match="Password is required for this deck"):
        get_deck(created.id, current_user=learner, db=db_session)

    token = access_private_deck(created.id, schemas.DeckAccessRequest(password="abcd"), db=db_session)
    detail = get_deck(created.id, current_user=learner, db=db_session, x_deck_access_token=token["access_token"])

    assert detail.title == "Protected"


def test_only_owner_can_edit_deck_content(db_session):
    owner = register_user(db_session, email=make_email())
    other = register_user(db_session, email=make_email())
    created = create_deck(
        schemas.DeckCreate(name="Protected", description="Deck"),
        current_user=owner,
        db=db_session,
    )

    with pytest.raises(HTTPException) as exc_info:
        update_deck(created.id, schemas.DeckUpdate(name="Hack", description="Nope"), current_user=other, db=db_session)

    assert exc_info.value.status_code == 403


def test_owner_can_add_and_update_cards(db_session):
    owner = register_user(db_session, email=make_email())
    created = create_deck(schemas.DeckCreate(name="Science", description="Deck"), current_user=owner, db=db_session)

    card = create_card(created.id, schemas.CardCreate(front="Atom", back="Matter"), current_user=owner, db=db_session)
    updated = update_card(card.id, schemas.CardUpdate(front="Atom", back="Smallest unit"), current_user=owner, db=db_session)

    assert updated.back == "Smallest unit"


def test_validate_deck_privacy_and_access_token_helpers():
    with pytest.raises(HTTPException):
        validate_deck_privacy("private", "123")

    token = create_deck_access_token(12)

    assert verify_deck_access_token(token, 12) is True
    assert verify_deck_access_token(token, 11) is False


def test_search_images_returns_normalized_results(monkeypatch, db_session):
    user = register_user(db_session, email=make_email())

    monkeypatch.setattr(
        "backend.main.search_openverse_images",
        lambda query, page, page_size: [
            schemas.ImageSearchResult(
                provider="openverse",
                external_id="img-1",
                title="Bus",
                thumbnail_url="https://example.com/thumb.jpg",
                source_url="https://example.com/source.jpg",
                author="Author",
                license="cc-by",
            )
        ],
    )

    response = search_images(schemas.ImageSearchRequest(query="bus"), current_user=user)

    assert response.query == "bus"
    assert response.results[0].title == "Bus"


def test_import_image_returns_internal_media_url(monkeypatch, db_session):
    user = register_user(db_session, email=make_email())
    monkeypatch.setattr("backend.main.download_external_image", lambda source_url: "/media/test-image.jpg")

    response = import_image(schemas.ImageImportRequest(source_url="https://example.com/source.jpg"), current_user=user)

    assert response.image_url == "/media/test-image.jpg"


def test_upload_image_decodes_base64_payload(db_session):
    user = register_user(db_session, email=make_email())
    payload = schemas.ImageUploadRequest(
        filename="card.png",
        content_base64="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jr1UAAAAASUVORK5CYII=",
    )

    response = upload_image(payload, current_user=user)

    assert response.image_url.startswith("/media/")
