import json
import random

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from . import models, schemas
from .time_utils import ensure_utc, now_utc


SUPPORTED_QUESTION_TYPES = {"single_choice"}


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
        raise HTTPException(status_code=400, detail="Опубликованный квиз должен содержать хотя бы один корректный вопрос")
    for index, question in enumerate(questions, start=1):
        if question.question_type not in SUPPORTED_QUESTION_TYPES:
            raise HTTPException(status_code=400, detail="Сейчас поддерживаются только вопросы с одним вариантом ответа")
        if not question.question_text.strip():
            raise HTTPException(status_code=400, detail=f"Вопрос {index} не может быть пустым")
        if len(question.options) < 2:
            raise HTTPException(status_code=400, detail=f"У вопроса {index} должно быть минимум два варианта ответа")
        cleaned_options = [option.option_text.strip() for option in question.options]
        if any(not option_text for option_text in cleaned_options):
            raise HTTPException(status_code=400, detail=f"В вопросе {index} есть пустой вариант ответа")
        correct_count = sum(1 for option in question.options if option.is_correct)
        if correct_count != 1:
            raise HTTPException(status_code=400, detail=f"У вопроса {index} должен быть ровно один правильный вариант")


def ensure_quiz_startable(quiz: models.Quiz) -> list[models.QuizQuestion]:
    ordered_questions = sorted(quiz.questions, key=lambda item: item.order_index)
    if not ordered_questions:
        raise HTTPException(status_code=400, detail="Квиз не содержит ни одного вопроса")
    for question in ordered_questions:
        if question.question_type != "single_choice":
            raise HTTPException(status_code=400, detail="Сейчас поддерживаются только вопросы с одним вариантом ответа")
        options = sorted(question.options, key=lambda item: item.order_index)
        if len(options) < 2:
            raise HTTPException(status_code=400, detail="У каждого вопроса квиза должно быть минимум два варианта ответа")
        if sum(1 for option in options if option.is_correct) != 1:
            raise HTTPException(status_code=400, detail="У каждого вопроса с одним вариантом ответа должен быть ровно один правильный вариант")
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


def get_quiz_or_404(quiz_id: int, db: Session) -> models.Quiz:
    quiz = db.query(models.Quiz).filter(models.Quiz.id == quiz_id).first()
    if not quiz:
        raise HTTPException(status_code=404, detail="Квиз не найден")
    return quiz


def get_accessible_quiz_or_404(quiz_id: int, current_user: models.User, db: Session) -> models.Quiz:
    quiz = get_quiz_or_404(quiz_id, db)
    if quiz.owner_id != current_user.id and not quiz.is_published:
        raise HTTPException(status_code=403, detail="У вас нет доступа к этому квизу")
    return quiz


def get_owned_quiz_or_404(quiz_id: int, current_user: models.User, db: Session) -> models.Quiz:
    quiz = get_quiz_or_404(quiz_id, db)
    if quiz.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Изменять этот квиз может только владелец")
    return quiz


def ensure_quiz_mutation_allowed(quiz: models.Quiz, db: Session) -> None:
    in_progress_attempts = (
        db.query(models.QuizAttempt)
        .filter(models.QuizAttempt.quiz_id == quiz.id, models.QuizAttempt.status == "in_progress")
        .count()
    )
    if in_progress_attempts:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Нельзя изменять квиз, пока есть активные попытки",
        )


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


def list_accessible_quizzes(current_user: models.User, db: Session) -> list[models.Quiz]:
    return (
        db.query(models.Quiz)
        .filter(or_(models.Quiz.owner_id == current_user.id, models.Quiz.is_published.is_(True)))
        .all()
    )
