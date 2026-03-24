import json
import random

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models, schemas
from .time_utils import ensure_utc, now_utc


SUPPORTED_QUESTION_TYPES = {"single_choice", "multiple_choice"}


def owner_name(user: models.User) -> str:
    return user.email.split("@")[0]


def normalize_tags(tags: list[str]) -> list[str]:
    cleaned: list[str] = []
    for tag in tags:
        value = tag.strip()
        if not value or value in cleaned:
            continue
        cleaned.append(value)
    return cleaned


def parse_tags(raw_tags: str) -> list[str]:
    if not raw_tags:
        return []
    try:
        value = json.loads(raw_tags)
    except json.JSONDecodeError:
        return []
    return [str(item) for item in value if str(item).strip()]


def validate_quiz_payload(payload: schemas.QuizCreate | schemas.QuizUpdate) -> None:
    questions = payload.questions or []
    if payload.is_published and not questions:
        raise HTTPException(status_code=400, detail="Published quizzes must contain at least one valid question")
    for index, question in enumerate(questions, start=1):
        if question.question_type not in SUPPORTED_QUESTION_TYPES:
            raise HTTPException(status_code=400, detail=f"Question {index} uses an unsupported question type")
        if not question.question_text.strip():
            raise HTTPException(status_code=400, detail=f"Question {index} cannot be empty")
        if len(question.options) < 2:
            raise HTTPException(status_code=400, detail=f"Question {index} must have at least two options")
        cleaned_options = [option.option_text.strip() for option in question.options]
        if any(not option_text for option_text in cleaned_options):
            raise HTTPException(status_code=400, detail=f"Question {index} contains an empty option")
        correct_count = sum(1 for option in question.options if option.is_correct)
        if question.question_type == "single_choice" and correct_count != 1:
            raise HTTPException(status_code=400, detail=f"Question {index} must have exactly one correct option")
        if question.question_type == "multiple_choice" and correct_count < 1:
            raise HTTPException(status_code=400, detail=f"Question {index} must have at least one correct option")


def ensure_quiz_startable(quiz: models.Quiz) -> list[models.QuizQuestion]:
    ordered_questions = sorted(quiz.questions, key=lambda item: item.order_index)
    if not ordered_questions:
        raise HTTPException(status_code=400, detail="Quiz does not contain any questions")
    for question in ordered_questions:
        if question.question_type != "single_choice":
            raise HTTPException(status_code=400, detail="Only single choice questions are supported right now")
        options = sorted(question.options, key=lambda item: item.order_index)
        if len(options) < 2:
            raise HTTPException(status_code=400, detail="Every quiz question must have at least two options")
        if sum(1 for option in options if option.is_correct) != 1:
            raise HTTPException(status_code=400, detail="Every single choice question must have exactly one correct option")
    return ordered_questions


def build_option_order_map(questions: list[models.QuizQuestion]) -> dict[str, list[int]]:
    option_order: dict[str, list[int]] = {}
    for question in questions:
        option_ids = [option.id for option in sorted(question.options, key=lambda item: item.order_index)]
        random.shuffle(option_ids)
        option_order[str(question.id)] = option_ids
    return option_order


def build_question_order(questions: list[models.QuizQuestion]) -> list[models.QuizQuestion]:
    shuffled_questions = list(questions)
    random.shuffle(shuffled_questions)
    return shuffled_questions


def get_attempt_question_position(attempt: models.QuizAttempt, question_id: int, fallback_order_index: int) -> int:
    try:
        question_order = json.loads(attempt.question_order or "[]")
    except json.JSONDecodeError:
        return fallback_order_index
    try:
        return question_order.index(question_id)
    except ValueError:
        return fallback_order_index


def get_quiz_or_404(quiz_id: int, db: Session) -> models.Quiz:
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    return quiz


def get_accessible_quiz_or_404(quiz_id: int, current_user: models.User, db: Session) -> models.Quiz:
    quiz = get_quiz_or_404(quiz_id, db)
    if quiz.owner_id != current_user.id and not quiz.is_published:
        raise HTTPException(status_code=403, detail="You do not have access to this quiz")
    return quiz


def get_owned_quiz_or_404(quiz_id: int, current_user: models.User, db: Session) -> models.Quiz:
    quiz = get_quiz_or_404(quiz_id, db)
    if quiz.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only the quiz owner can modify this quiz")
    return quiz


def get_attempt_or_404(attempt_id: int, current_user: models.User, db: Session) -> models.QuizAttempt:
    attempt = db.query(models.QuizAttempt).filter(models.QuizAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this quiz attempt")
    return attempt


def apply_quiz_payload(quiz: models.Quiz, payload: schemas.QuizCreate | schemas.QuizUpdate) -> None:
    quiz.title = payload.title.strip()
    quiz.description = payload.description.strip()
    quiz.category = payload.category.strip()
    quiz.difficulty = payload.difficulty
    quiz.subject = payload.subject.strip()
    quiz.language = payload.language.strip()
    quiz.is_published = payload.is_published
    quiz.cover_image = payload.cover_image.strip()
    quiz.estimated_time = payload.estimated_time
    quiz.tags = json.dumps(normalize_tags(payload.tags))
    quiz.updated_at = now_utc()


def replace_quiz_questions(quiz: models.Quiz, payload_questions: list[schemas.QuizQuestionInput], db: Session) -> None:
    existing_questions = list(quiz.questions)
    for question in existing_questions:
        db.delete(question)
    db.flush()

    timestamp = now_utc()
    for question_index, question_payload in enumerate(payload_questions):
        question = models.QuizQuestion(
            quiz_id=quiz.id,
            question_text=question_payload.question_text.strip(),
            question_type=question_payload.question_type,
            explanation=question_payload.explanation.strip(),
            order_index=question_payload.order_index if question_payload.order_index is not None else question_index,
            points=question_payload.points,
            created_at=timestamp,
            updated_at=timestamp,
        )
        db.add(question)
        db.flush()

        for option_index, option_payload in enumerate(question_payload.options):
            db.add(
                models.QuizOption(
                    question_id=question.id,
                    option_text=option_payload.option_text.strip(),
                    is_correct=option_payload.is_correct,
                    order_index=option_payload.order_index if option_payload.order_index is not None else option_index,
                )
            )


def find_correct_option(question: models.QuizQuestion) -> models.QuizOption:
    correct_option = next((option for option in question.options if option.is_correct), None)
    if not correct_option:
        raise HTTPException(status_code=400, detail="Question is missing a correct option")
    return correct_option


def serialize_quiz_option(option: models.QuizOption) -> schemas.QuizOptionOut:
    return schemas.QuizOptionOut.from_orm(option)


def serialize_quiz_question(question: models.QuizQuestion) -> schemas.QuizQuestionOut:
    ordered_options = sorted(question.options, key=lambda item: item.order_index)
    return schemas.QuizQuestionOut(
        id=question.id,
        question_text=question.question_text,
        question_type=question.question_type,
        explanation=question.explanation,
        order_index=question.order_index,
        points=question.points,
        options=[serialize_quiz_option(option) for option in ordered_options],
    )


def compute_quiz_attempt_metrics(quiz: models.Quiz, current_user: models.User | None, db: Session) -> tuple[int, float | None, float | None, int | None]:
    attempt_count = db.query(models.QuizAttempt).filter(models.QuizAttempt.quiz_id == quiz.id).count()
    if current_user is None:
        return attempt_count, None, None, None

    completed_attempts = (
        db.query(models.QuizAttempt)
        .filter(
            models.QuizAttempt.quiz_id == quiz.id,
            models.QuizAttempt.user_id == current_user.id,
            models.QuizAttempt.status == "completed",
        )
        .order_by(models.QuizAttempt.finished_at.desc(), models.QuizAttempt.id.desc())
        .all()
    )
    if not completed_attempts:
        return attempt_count, None, None, None

    last_attempt = completed_attempts[0]
    best_percentage = max(attempt.score for attempt in completed_attempts)
    return attempt_count, last_attempt.score, best_percentage, last_attempt.id


def serialize_quiz_summary(quiz: models.Quiz, current_user: models.User | None, db: Session) -> schemas.QuizSummaryOut:
    question_count = len(quiz.questions)
    total_points = sum(question.points for question in quiz.questions)
    attempt_count, last_percentage, best_percentage, _ = compute_quiz_attempt_metrics(quiz, current_user, db)
    return schemas.QuizSummaryOut(
        id=quiz.id,
        title=quiz.title,
        description=quiz.description,
        category=quiz.category,
        difficulty=quiz.difficulty,
        subject=quiz.subject,
        language=quiz.language,
        is_published=quiz.is_published,
        cover_image=quiz.cover_image,
        estimated_time=quiz.estimated_time,
        tags=parse_tags(quiz.tags),
        question_count=question_count,
        total_points=total_points,
        attempt_count=attempt_count,
        owner_id=quiz.owner_id,
        owner_name=owner_name(quiz.owner),
        owner_email=quiz.owner.email,
        can_edit=bool(current_user and quiz.owner_id == current_user.id),
        last_attempt_percentage=last_percentage,
        best_attempt_percentage=best_percentage,
        created_at=ensure_utc(quiz.created_at),
        updated_at=ensure_utc(quiz.updated_at),
    )


def serialize_quiz_detail(quiz: models.Quiz, current_user: models.User | None, db: Session) -> schemas.QuizDetailOut:
    summary = serialize_quiz_summary(quiz, current_user, db)
    _, _, _, last_attempt_id = compute_quiz_attempt_metrics(quiz, current_user, db)
    return schemas.QuizDetailOut(**summary.dict(), last_attempt_id=last_attempt_id)


def serialize_quiz_editor(quiz: models.Quiz, current_user: models.User, db: Session) -> schemas.QuizEditorOut:
    detail = serialize_quiz_detail(quiz, current_user, db)
    ordered_questions = sorted(quiz.questions, key=lambda item: item.order_index)
    return schemas.QuizEditorOut(
        **detail.dict(),
        questions=[serialize_quiz_question(question) for question in ordered_questions],
    )


def build_attempt_session(attempt: models.QuizAttempt, db: Session) -> schemas.QuizAttemptSessionOut:
    question_order = json.loads(attempt.question_order or "[]")
    option_order = json.loads(attempt.option_order or "{}")
    questions_by_id = {question.id: question for question in attempt.quiz.questions}
    answers_by_question = {answer.question_id: answer for answer in attempt.answers}
    ordered_questions: list[schemas.QuizQuestionSessionOut] = []

    for order_index, question_id in enumerate(question_order):
        question = questions_by_id.get(question_id)
        if not question:
            continue
        base_options = sorted(question.options, key=lambda item: item.order_index)
        ordered_options = base_options
        question_option_order = option_order.get(str(question.id))
        if isinstance(question_option_order, list):
            base_options_by_id = {option.id: option for option in base_options}
            configured_ids = [int(option_id) for option_id in question_option_order if int(option_id) in base_options_by_id]
            if configured_ids:
                configured_set = set(configured_ids)
                ordered_options = [base_options_by_id[option_id] for option_id in configured_ids]
                ordered_options.extend([option for option in base_options if option.id not in configured_set])
        answer = answers_by_question.get(question.id)
        ordered_questions.append(
            schemas.QuizQuestionSessionOut(
                id=question.id,
                question_text=question.question_text,
                question_type=question.question_type,
                order_index=order_index,
                points=question.points,
                options=[
                    schemas.QuizOptionChoiceOut(id=option.id, option_text=option.option_text, order_index=option.order_index)
                    for option in ordered_options
                ],
                selected_option_id=answer.selected_option_id if answer else None,
            )
        )

    answered_count = sum(1 for question in ordered_questions if question.selected_option_id is not None)
    current_question_index = next(
        (index for index, question in enumerate(ordered_questions) if question.selected_option_id is None),
        max(len(ordered_questions) - 1, 0),
    )
    return schemas.QuizAttemptSessionOut(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        quiz_title=attempt.quiz.title,
        status=attempt.status,
        started_at=ensure_utc(attempt.started_at),
        total_questions=attempt.total_questions,
        answered_count=answered_count,
        current_question_index=current_question_index,
        questions=ordered_questions,
    )


def upsert_attempt_answer(
    attempt: models.QuizAttempt,
    question: models.QuizQuestion,
    selected_option: models.QuizOption,
    db: Session,
) -> models.QuizAttemptAnswer:
    answer = (
        db.query(models.QuizAttemptAnswer)
        .filter(models.QuizAttemptAnswer.attempt_id == attempt.id, models.QuizAttemptAnswer.question_id == question.id)
        .first()
    )
    correct_option = find_correct_option(question)
    now = now_utc()
    session_order_index = get_attempt_question_position(attempt, question.id, question.order_index)
    if answer is None:
        answer = models.QuizAttemptAnswer(
            attempt_id=attempt.id,
            question_id=question.id,
            selected_option_id=selected_option.id,
            is_correct=selected_option.id == correct_option.id,
            answered_at=now,
            question_text=question.question_text,
            selected_option_text=selected_option.option_text,
            correct_option_text=correct_option.option_text,
            explanation=question.explanation,
            points=question.points,
            question_order=session_order_index,
        )
        db.add(answer)
    else:
        answer.selected_option_id = selected_option.id
        answer.is_correct = selected_option.id == correct_option.id
        answer.answered_at = now
        answer.question_text = question.question_text
        answer.selected_option_text = selected_option.option_text
        answer.correct_option_text = correct_option.option_text
        answer.explanation = question.explanation
        answer.points = question.points
        answer.question_order = session_order_index
    return answer


def finalize_attempt(attempt: models.QuizAttempt, db: Session) -> models.QuizAttempt:
    question_order = json.loads(attempt.question_order or "[]")
    questions_by_id = {question.id: question for question in attempt.quiz.questions}
    answers_by_question = {answer.question_id: answer for answer in attempt.answers}

    for question_id in question_order:
        question = questions_by_id.get(question_id)
        if not question or question_id in answers_by_question:
            continue
        correct_option = find_correct_option(question)
        session_order_index = get_attempt_question_position(attempt, question.id, question.order_index)
        db.add(
            models.QuizAttemptAnswer(
                attempt_id=attempt.id,
                question_id=question.id,
                selected_option_id=None,
                is_correct=False,
                answered_at=now_utc(),
                question_text=question.question_text,
                selected_option_text=None,
                correct_option_text=correct_option.option_text,
                explanation=question.explanation,
                points=question.points,
                question_order=session_order_index,
            )
        )

    db.flush()
    answers = (
        db.query(models.QuizAttemptAnswer)
        .filter(models.QuizAttemptAnswer.attempt_id == attempt.id)
        .order_by(models.QuizAttemptAnswer.question_order, models.QuizAttemptAnswer.id)
        .all()
    )
    correct_count = sum(1 for answer in answers if answer.is_correct)
    wrong_count = max(attempt.total_questions - correct_count, 0)
    percentage = (correct_count / attempt.total_questions * 100.0) if attempt.total_questions else 0.0
    attempt.correct_count = correct_count
    attempt.wrong_count = wrong_count
    attempt.score = round(percentage, 2)
    attempt.finished_at = now_utc()
    attempt.status = "completed"
    return attempt


def serialize_result_summary(attempt: models.QuizAttempt) -> schemas.QuizResultSummaryOut:
    completion_time_seconds = None
    if attempt.finished_at:
        completion_time_seconds = max(int((ensure_utc(attempt.finished_at) - ensure_utc(attempt.started_at)).total_seconds()), 0)
    return schemas.QuizResultSummaryOut(
        id=attempt.id,
        quiz_id=attempt.quiz_id,
        quiz_title=attempt.quiz.title,
        status=attempt.status,
        started_at=ensure_utc(attempt.started_at),
        finished_at=ensure_utc(attempt.finished_at) if attempt.finished_at else None,
        score=attempt.score,
        correct_count=attempt.correct_count,
        wrong_count=attempt.wrong_count,
        total_questions=attempt.total_questions,
        percentage=attempt.score,
        completion_time_seconds=completion_time_seconds,
    )


def serialize_result(attempt: models.QuizAttempt) -> schemas.QuizResultOut:
    summary = serialize_result_summary(attempt)
    ordered_answers = sorted(attempt.answers, key=lambda item: (item.question_order, item.id))
    return schemas.QuizResultOut(
        **summary.dict(),
        review_items=[
            schemas.QuizReviewItemOut(
                question_id=answer.question_id,
                question_text=answer.question_text,
                selected_option_id=answer.selected_option_id,
                selected_option_text=answer.selected_option_text,
                correct_option_text=answer.correct_option_text,
                explanation=answer.explanation,
                is_correct=answer.is_correct,
                order_index=answer.question_order,
                points=answer.points,
            )
            for answer in ordered_answers
        ],
    )


def list_accessible_quizzes(current_user: models.User, db: Session) -> list[models.Quiz]:
    return (
        db.query(models.Quiz)
        .filter(or_(models.Quiz.owner_id == current_user.id, models.Quiz.is_published.is_(True)))
        .all()
    )
