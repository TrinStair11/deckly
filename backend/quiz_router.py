import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import get_current_user, get_db
from .quizzes import (
    apply_quiz_payload,
    build_attempt_session,
    build_option_order_map,
    build_question_order,
    ensure_quiz_startable,
    finalize_attempt,
    get_accessible_quiz_or_404,
    get_attempt_or_404,
    get_owned_quiz_or_404,
    list_accessible_quizzes,
    replace_quiz_questions,
    serialize_quiz_detail,
    serialize_quiz_editor,
    serialize_quiz_summary,
    serialize_result,
    upsert_attempt_answer,
    validate_quiz_payload,
)
from .spaced_repetition import utcnow

router = APIRouter()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@router.post("/quizzes", response_model=schemas.QuizEditorOut, status_code=status.HTTP_201_CREATED)
def create_quiz(payload: schemas.QuizCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    validate_quiz_payload(payload)
    timestamp = utcnow()
    quiz = models.Quiz(
        title=payload.title.strip(),
        description="",
        category="",
        difficulty=payload.difficulty,
        subject="",
        language="",
        is_published=payload.is_published,
        cover_image="",
        estimated_time=payload.estimated_time,
        tags="[]",
        created_at=timestamp,
        updated_at=timestamp,
        owner_id=current_user.id,
    )
    db.add(quiz)
    db.flush()
    apply_quiz_payload(quiz, payload)
    replace_quiz_questions(quiz, payload.questions, db)
    db.commit()
    db.refresh(quiz)
    return serialize_quiz_editor(quiz, current_user, db)


@router.get("/quizzes", response_model=list[schemas.QuizSummaryOut])
def list_quizzes_module(
    search: str = Query(default=""),
    category: str = Query(default=""),
    difficulty: str = Query(default=""),
    sort: str = Query(default="newest"),
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    quizzes = list_accessible_quizzes(current_user, db)
    search_value = search.strip().lower() if isinstance(search, str) else ""
    category_value = category.strip().lower() if isinstance(category, str) else ""
    difficulty_value = difficulty.strip().lower() if isinstance(difficulty, str) else ""
    sort_value = sort if isinstance(sort, str) else "newest"

    filtered: list[models.Quiz] = []
    for quiz in quizzes:
        if search_value:
            haystack = " ".join(
                [
                    quiz.title,
                    quiz.description,
                    quiz.category,
                    quiz.subject,
                    quiz.language,
                    quiz.owner.email,
                ]
            ).lower()
            if search_value not in haystack:
                continue
        if category_value and quiz.category.lower() != category_value:
            continue
        if difficulty_value and quiz.difficulty.lower() != difficulty_value:
            continue
        filtered.append(quiz)

    items = [serialize_quiz_summary(quiz, current_user, db) for quiz in filtered]
    if sort_value == "title":
        items.sort(key=lambda item: item.title.lower())
    elif sort_value == "most_played":
        items.sort(key=lambda item: (-item.attempt_count, item.title.lower()))
    else:
        items.sort(key=lambda item: item.created_at, reverse=True)
    return items


@router.get("/quizzes/{quiz_id}", response_model=schemas.QuizDetailOut)
def get_quiz_detail(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_accessible_quiz_or_404(quiz_id, current_user, db)
    return serialize_quiz_detail(quiz, current_user, db)


@router.get("/quizzes/{quiz_id}/edit-data", response_model=schemas.QuizEditorOut)
def get_quiz_edit_data(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_owned_quiz_or_404(quiz_id, current_user, db)
    return serialize_quiz_editor(quiz, current_user, db)


@router.put("/quizzes/{quiz_id}", response_model=schemas.QuizEditorOut)
def update_quiz(quiz_id: int, payload: schemas.QuizUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    validate_quiz_payload(payload)
    quiz = get_owned_quiz_or_404(quiz_id, current_user, db)
    apply_quiz_payload(quiz, payload)
    replace_quiz_questions(quiz, payload.questions, db)
    db.commit()
    db.refresh(quiz)
    return serialize_quiz_editor(quiz, current_user, db)


@router.delete("/quizzes/{quiz_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_quiz(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_owned_quiz_or_404(quiz_id, current_user, db)
    db.delete(quiz)
    db.commit()


@router.post("/quizzes/{quiz_id}/start", response_model=schemas.QuizAttemptSessionOut)
def start_quiz_attempt(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_accessible_quiz_or_404(quiz_id, current_user, db)
    ordered_questions = build_question_order(ensure_quiz_startable(quiz))
    attempt = models.QuizAttempt(
        quiz_id=quiz.id,
        user_id=current_user.id,
        started_at=utcnow(),
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


@router.get("/quiz-attempts/{attempt_id}", response_model=schemas.QuizAttemptSessionOut)
def get_quiz_attempt(attempt_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    attempt = get_attempt_or_404(attempt_id, current_user, db)
    return build_attempt_session(attempt, db)


@router.put("/quiz-attempts/{attempt_id}/answers/{question_id}", response_model=schemas.QuizAttemptSessionOut)
def answer_quiz_question(
    attempt_id: int,
    question_id: int,
    payload: schemas.QuizAnswerSubmit,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
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


@router.post("/quiz-attempts/{attempt_id}/complete", response_model=schemas.QuizResultOut)
def complete_quiz_attempt(attempt_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    attempt = get_attempt_or_404(attempt_id, current_user, db)
    if attempt.status == "completed":
        return serialize_result(attempt)
    finalize_attempt(attempt, db)
    db.commit()
    db.refresh(attempt)
    return serialize_result(attempt)


@router.get("/quiz-attempts/{attempt_id}/results", response_model=schemas.QuizResultOut)
def get_quiz_attempt_results(attempt_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    attempt = get_attempt_or_404(attempt_id, current_user, db)
    if attempt.status != "completed":
        raise HTTPException(status_code=400, detail="Quiz attempt is not completed yet")
    return serialize_result(attempt)


@router.get("/quiz", include_in_schema=False)
def quiz_library_page():
    return FileResponse(FRONTEND_DIR / "quiz.html")


@router.get("/quiz/create", include_in_schema=False)
def quiz_create_page():
    return FileResponse(FRONTEND_DIR / "quiz-editor.html")


@router.get("/quiz/{quiz_id}/edit", include_in_schema=False)
def quiz_edit_page(quiz_id: int):
    return FileResponse(FRONTEND_DIR / "quiz-editor.html")


@router.get("/quiz/{quiz_id}/start", include_in_schema=False)
def quiz_session_page(quiz_id: int):
    return FileResponse(FRONTEND_DIR / "quiz-session.html")


@router.get("/quiz/{quiz_id}/results/{attempt_id}/review", include_in_schema=False)
def quiz_review_page(quiz_id: int, attempt_id: int):
    return FileResponse(FRONTEND_DIR / "quiz-review.html")


@router.get("/quiz/{quiz_id}/results/{attempt_id}", include_in_schema=False)
def quiz_results_page(quiz_id: int, attempt_id: int):
    return FileResponse(FRONTEND_DIR / "quiz-results.html")


@router.get("/quiz/{quiz_id}", include_in_schema=False)
def quiz_detail_page(quiz_id: int):
    return FileResponse(FRONTEND_DIR / "quiz-detail.html")
