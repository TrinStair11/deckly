from datetime import datetime

from backend import schemas


def test_deck_create_schema_supports_legacy_name_alias():
    payload = schemas.DeckCreate(name="React", description="Hooks", access_password="secret")

    assert payload.title == "React"
    assert payload.password == "secret"
    assert payload.cards == []


def test_deck_out_schema_exposes_progress():
    created_at = datetime.utcnow()
    payload = schemas.DeckOut(
        id=1,
        title="Spanish",
        description="Daily words",
        visibility="public",
        created_at=created_at,
        updated_at=created_at,
        card_count=3,
        owner_id=5,
        owner_name="owner",
        owner_email="owner@example.com",
        is_owner=True,
        progress=schemas.ProgressOut(
            total_cards=3,
            new_available_count=1,
            learning_count=1,
            review_count=1,
            due_review_count=2,
            known_count=1,
            last_studied_at=created_at,
            updated_at=created_at,
        ),
    )

    assert payload.title == "Spanish"
    assert payload.progress.due_review_count == 2


def test_card_out_schema_wraps_optional_state():
    created_at = datetime.utcnow()
    payload = schemas.CardOut(
        id=1,
        front="Hola",
        back="Hello",
        image_url="preview",
        position=0,
        deck_id=2,
        state=schemas.UserCardStateOut(
            status="learning",
            due_at=created_at,
            last_reviewed_at=None,
            stability=0.4,
            difficulty=5.0,
            scheduled_days=0.0,
            elapsed_days=0.0,
            reps=0,
            lapses=0,
            learning_step=0,
        ),
    )

    assert payload.state.status == "learning"
    assert payload.deck_id == 2


def test_study_session_schema_keeps_mode_and_progress():
    created_at = datetime.utcnow()
    session = schemas.StudySession(
        session_id="session",
        deck_title="Biology",
        deck_id=2,
        mode="interval",
        current_index=1,
        card_order=[10, 11, 12],
        total_cards=1,
        cards=[],
        progress=schemas.ProgressOut(
            total_cards=10,
            new_available_count=4,
            learning_count=3,
            review_count=3,
            due_review_count=5,
            known_count=3,
            updated_at=created_at,
        ),
    )

    assert session.deck_title == "Biology"
    assert session.mode == "interval"
    assert session.current_index == 1
    assert session.progress.total_cards == 10


def test_account_settings_schemas_capture_payload():
    email_payload = schemas.AccountEmailUpdate(
        new_email="new@example.com",
        confirm_email="new@example.com",
        current_password="secret12",
    )
    password_payload = schemas.AccountPasswordUpdate(
        current_password="secret12",
        new_password="new-secret12",
        confirm_new_password="new-secret12",
    )

    assert email_payload.new_email == "new@example.com"
    assert password_payload.new_password == "new-secret12"
