import pytest
from fastapi import HTTPException

from backend import quizzes as quiz_helpers
from backend import schemas
from backend.main import (
    answer_quiz_question,
    complete_quiz_attempt,
    create_quiz,
    get_quiz_attempt,
    get_quiz_attempt_results,
    get_quiz_detail,
    get_quiz_edit_data,
    list_quizzes_module,
    start_quiz_attempt,
    update_quiz,
)
from tests.helpers import make_email, register_user


def build_quiz_payload(title="Japanese Meanings", is_published=True):
    return schemas.QuizCreate(
        title=title,
        description="Structured vocabulary quiz",
        category="Vocabulary",
        difficulty="beginner",
        subject="Japanese",
        language="English",
        is_published=is_published,
        estimated_time=5,
        tags=["jlpt", "n5"],
        questions=[
            schemas.QuizQuestionInput(
                question_text="What does 銀行 mean?",
                question_type="single_choice",
                explanation="銀行 means bank.",
                points=2,
                options=[
                    schemas.QuizOptionInput(option_text="Library", is_correct=False),
                    schemas.QuizOptionInput(option_text="Hospital", is_correct=False),
                    schemas.QuizOptionInput(option_text="Bank", is_correct=True),
                    schemas.QuizOptionInput(option_text="School", is_correct=False),
                ],
            ),
            schemas.QuizQuestionInput(
                question_text="What does 犬 mean?",
                question_type="single_choice",
                explanation="犬 means dog.",
                points=1,
                options=[
                    schemas.QuizOptionInput(option_text="Cat", is_correct=False),
                    schemas.QuizOptionInput(option_text="Dog", is_correct=True),
                ],
            ),
        ],
    )


def test_create_and_list_quizzes_module(db_session):
    owner = register_user(db_session, email=make_email())

    created = create_quiz(build_quiz_payload(), current_user=owner, db=db_session)
    library = list_quizzes_module(current_user=owner, db=db_session)

    assert created.title == "Japanese Meanings"
    assert library[0].question_count == 2
    assert library[0].can_edit is True
    assert library[0].difficulty == "beginner"


def test_published_quiz_requires_valid_questions(db_session):
    owner = register_user(db_session, email=make_email())

    with pytest.raises(HTTPException, match="Published quizzes must contain at least one valid question"):
      create_quiz(
          schemas.QuizCreate(title="Broken", is_published=True),
          current_user=owner,
          db=db_session,
      )


def test_unpublished_quiz_is_hidden_from_other_users(db_session):
    owner = register_user(db_session, email=make_email())
    other = register_user(db_session, email=make_email())
    created = create_quiz(build_quiz_payload(is_published=False), current_user=owner, db=db_session)

    with pytest.raises(HTTPException) as exc_info:
        get_quiz_detail(created.id, current_user=other, db=db_session)

    assert exc_info.value.status_code == 403


def test_quiz_attempt_flow_scores_and_returns_review_items(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_quiz(build_quiz_payload(), current_user=owner, db=db_session)
    editor_view = get_quiz_edit_data(created.id, current_user=owner, db=db_session)

    session = start_quiz_attempt(created.id, current_user=learner, db=db_session)
    first_question = next(question for question in session.questions if question.question_text == "What does 銀行 mean?")
    second_question = next(question for question in session.questions if question.question_text == "What does 犬 mean?")
    correct_first = next(option for option in first_question.options if option.option_text == "Bank")
    wrong_second = next(option for option in second_question.options if option.option_text == "Cat")

    updated_session = answer_quiz_question(
        session.id,
        first_question.id,
        schemas.QuizAnswerSubmit(selected_option_id=correct_first.id),
        current_user=learner,
        db=db_session,
    )
    answer_quiz_question(
        session.id,
        second_question.id,
        schemas.QuizAnswerSubmit(selected_option_id=wrong_second.id),
        current_user=learner,
        db=db_session,
    )
    result = complete_quiz_attempt(session.id, current_user=learner, db=db_session)
    fetched_result = get_quiz_attempt_results(session.id, current_user=learner, db=db_session)

    assert updated_session.answered_count == 1
    assert result.correct_count == 1
    assert result.wrong_count == 1
    assert result.percentage == 50.0
    assert len(fetched_result.review_items) == 2
    first_review = next(item for item in fetched_result.review_items if item.question_text == "What does 銀行 mean?")
    second_review = next(item for item in fetched_result.review_items if item.question_text == "What does 犬 mean?")
    assert first_review.correct_option_text == "Bank"
    assert second_review.selected_option_text == "Cat"
    assert editor_view.questions[0].options[2].is_correct is True


def test_quiz_attempt_shuffles_options_once_per_attempt(db_session, monkeypatch):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_quiz(build_quiz_payload(), current_user=owner, db=db_session)
    authored = get_quiz_edit_data(created.id, current_user=owner, db=db_session)

    def reverse_shuffle(values):
        values[:] = list(reversed(values))

    monkeypatch.setattr(quiz_helpers.random, "shuffle", reverse_shuffle)

    session = start_quiz_attempt(created.id, current_user=learner, db=db_session)
    target_question = next(question for question in session.questions if question.question_text == "What does 銀行 mean?")
    authored_question = next(question for question in authored.questions if question.question_text == "What does 銀行 mean?")
    shuffled_text = [option.option_text for option in target_question.options]
    authored_text = [option.option_text for option in authored_question.options]

    assert shuffled_text == list(reversed(authored_text))

    reloaded = get_quiz_attempt(session.id, current_user=learner, db=db_session)
    reloaded_question = next(question for question in reloaded.questions if question.question_text == "What does 銀行 mean?")
    assert [option.option_text for option in reloaded_question.options] == shuffled_text


def test_quiz_attempt_shuffles_question_order_once_per_attempt(db_session, monkeypatch):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_quiz(build_quiz_payload(), current_user=owner, db=db_session)
    authored = get_quiz_edit_data(created.id, current_user=owner, db=db_session)

    def reverse_shuffle(values):
        values[:] = list(reversed(values))

    monkeypatch.setattr(quiz_helpers.random, "shuffle", reverse_shuffle)

    session = start_quiz_attempt(created.id, current_user=learner, db=db_session)
    authored_questions = [question.question_text for question in authored.questions]
    session_questions = [question.question_text for question in session.questions]

    assert session_questions == list(reversed(authored_questions))

    reloaded = get_quiz_attempt(session.id, current_user=learner, db=db_session)
    assert [question.question_text for question in reloaded.questions] == session_questions


def test_quiz_attempt_can_finish_early_and_marks_unanswered_wrong(db_session):
    owner = register_user(db_session, email=make_email())
    learner = register_user(db_session, email=make_email())
    created = create_quiz(build_quiz_payload(), current_user=owner, db=db_session)

    session = start_quiz_attempt(created.id, current_user=learner, db=db_session)
    first_question = next(question for question in session.questions if question.question_text == "What does 銀行 mean?")
    correct_first = next(option for option in first_question.options if option.option_text == "Bank")

    answer_quiz_question(
        session.id,
        first_question.id,
        schemas.QuizAnswerSubmit(selected_option_id=correct_first.id),
        current_user=learner,
        db=db_session,
    )
    result = complete_quiz_attempt(session.id, current_user=learner, db=db_session)

    assert result.correct_count == 1
    assert result.wrong_count == 1
    assert result.total_questions == 2
    assert result.percentage == 50.0
    assert result.review_items[1].selected_option_text is None
    assert result.review_items[1].is_correct is False


def test_update_quiz_replaces_questions_and_metadata(db_session):
    owner = register_user(db_session, email=make_email())
    created = create_quiz(build_quiz_payload(title="Original"), current_user=owner, db=db_session)

    updated = update_quiz(
        created.id,
        schemas.QuizUpdate(
            title="Updated Quiz",
            description="New description",
            category="Kanji",
            difficulty="intermediate",
            subject="Japanese",
            language="English",
            is_published=True,
            estimated_time=8,
            tags=["kanji"],
            questions=[
                schemas.QuizQuestionInput(
                    question_text="What does 山 mean?",
                    question_type="single_choice",
                    explanation="山 means mountain.",
                    options=[
                        schemas.QuizOptionInput(option_text="Mountain", is_correct=True),
                        schemas.QuizOptionInput(option_text="River", is_correct=False),
                    ],
                )
            ],
        ),
        current_user=owner,
        db=db_session,
    )

    assert updated.title == "Updated Quiz"
    assert updated.question_count == 1
    assert updated.category == "Kanji"
    assert updated.questions[0].question_text == "What does 山 mean?"
