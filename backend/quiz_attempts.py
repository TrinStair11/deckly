import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from . import models, schemas
from .quizzes import (
    build_option_order_map,
    build_question_order,
    ensure_quiz_startable,
    get_accessible_quiz_or_404,
)
from .time_utils import ensure_utc, now_utc


def get_attempt_question_position(attempt: models.QuizAttempt, question_id: int, fallback_order_index: int) -> int:
    try:
        question_order = json.loads(attempt.question_order or "[]")
    except json.JSONDecodeError:
        return fallback_order_index
    try:
        return question_order.index(question_id)
    except ValueError:
        return fallback_order_index


def get_attempt_or_404(attempt_id: int, current_user: models.User, db: Session) -> models.QuizAttempt:
    attempt = db.query(models.QuizAttempt).filter(models.QuizAttempt.id == attempt_id).first()
    if not attempt:
        raise HTTPException(status_code=404, detail="Quiz attempt not found")
    if attempt.user_id is not None and attempt.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have access to this quiz attempt")
    return attempt


def find_correct_option(question: models.QuizQuestion) -> models.QuizOption:
    correct_option = next((option for option in question.options if option.is_correct), None)
    if not correct_option:
        raise HTTPException(status_code=400, detail="Question is missing a correct option")
    return correct_option


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


def start_quiz_attempt_session(quiz_id: int, current_user: models.User, db: Session) -> schemas.QuizAttemptSessionOut:
    quiz = get_accessible_quiz_or_404(quiz_id, current_user, db)
    ordered_questions = build_question_order(ensure_quiz_startable(quiz))
    attempt = models.QuizAttempt(
        quiz_id=quiz.id,
        user_id=current_user.id,
        started_at=now_utc(),
        finished_at=None,
        score=0.0,
        correct_count=0,
        wrong_count=0,
        total_questions=len(ordered_questions),
        status="in_progress",
        question_order=json.dumps([question.id for question in ordered_questions]),
        option_order=json.dumps(build_option_order_map(ordered_questions)),
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return build_attempt_session(attempt, db)


def load_quiz_attempt_session(attempt_id: int, current_user: models.User, db: Session) -> schemas.QuizAttemptSessionOut:
    attempt = get_attempt_or_404(attempt_id, current_user, db)
    return build_attempt_session(attempt, db)


def submit_quiz_answer(
    attempt_id: int,
    question_id: int,
    payload: schemas.QuizAnswerSubmit,
    current_user: models.User,
    db: Session,
) -> schemas.QuizAttemptSessionOut:
    attempt = get_attempt_or_404(attempt_id, current_user, db)
    if attempt.status != "in_progress":
        raise HTTPException(status_code=400, detail="Completed quizzes cannot be changed")
    question = (
        db.query(models.QuizQuestion)
        .filter(models.QuizQuestion.id == question_id, models.QuizQuestion.quiz_id == attempt.quiz_id)
        .first()
    )
    if not question:
        raise HTTPException(status_code=404, detail="Quiz question not found")
    if question.question_type != "single_choice":
        raise HTTPException(status_code=400, detail="Only single choice questions are supported right now")
    selected_option = (
        db.query(models.QuizOption)
        .filter(models.QuizOption.id == payload.selected_option_id, models.QuizOption.question_id == question.id)
        .first()
    )
    if not selected_option:
        raise HTTPException(status_code=400, detail="Selected option does not belong to this question")
    upsert_attempt_answer(attempt, question, selected_option, db)
    db.commit()
    db.refresh(attempt)
    return build_attempt_session(attempt, db)


def complete_quiz_attempt_result(attempt_id: int, current_user: models.User, db: Session) -> schemas.QuizResultOut:
    attempt = get_attempt_or_404(attempt_id, current_user, db)
    if attempt.status == "completed":
        return serialize_result(attempt)
    finalize_attempt(attempt, db)
    db.commit()
    db.refresh(attempt)
    return serialize_result(attempt)


def get_quiz_attempt_result(attempt_id: int, current_user: models.User, db: Session) -> schemas.QuizResultOut:
    attempt = get_attempt_or_404(attempt_id, current_user, db)
    if attempt.status != "completed":
        raise HTTPException(status_code=400, detail="Quiz attempt is not completed yet")
    return serialize_result(attempt)
