from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from . import models, schemas
from .auth import get_current_user, get_db
from .quiz_attempts import (
    complete_quiz_attempt_result,
    get_quiz_attempt_result,
    load_quiz_attempt_session,
    start_quiz_attempt_session,
    submit_quiz_answer,
)
from .quiz_pages import (
    page_router,
    quiz_create_page,
    quiz_detail_page,
    quiz_edit_page,
    quiz_library_page,
    quiz_results_page,
    quiz_review_page,
    quiz_session_page,
)
from .quizzes import (
    apply_quiz_payload,
    ensure_quiz_mutation_allowed,
    get_accessible_quiz_or_404,
    get_owned_quiz_or_404,
    list_accessible_quizzes,
    replace_quiz_questions,
    serialize_quiz_detail,
    serialize_quiz_editor,
    serialize_quiz_summary,
    validate_quiz_payload,
)
from .time_utils import now_utc

router = APIRouter()


@router.post(
    "/quizzes",
    response_model=schemas.QuizEditorOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Quizzes"],
    summary="Create quiz",
    description="Create a new quiz with authored questions and editor metadata.",
    response_description="Created quiz in editor format.",
)
def create_quiz(payload: schemas.QuizCreate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    validate_quiz_payload(payload)
    timestamp = now_utc()
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


@router.get(
    "/quizzes",
    response_model=list[schemas.QuizSummaryOut],
    tags=["Quizzes"],
    summary="List quizzes",
    description="List quizzes accessible to the authenticated user, with optional filtering by search, category, difficulty, and sort mode.",
    response_description="Filtered quiz summaries.",
)
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


@router.get(
    "/quizzes/{quiz_id}",
    response_model=schemas.QuizDetailOut,
    tags=["Quizzes"],
    summary="Get quiz details",
    description="Return the full public or accessible detail view for a quiz.",
    response_description="Quiz detail payload.",
)
def get_quiz_detail(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_accessible_quiz_or_404(quiz_id, current_user, db)
    return serialize_quiz_detail(quiz, current_user, db)


@router.get(
    "/quizzes/{quiz_id}/edit-data",
    response_model=schemas.QuizEditorOut,
    tags=["Quizzes"],
    summary="Get quiz editor data",
    description="Return the owner-only editor payload used to populate the quiz editing UI.",
    response_description="Quiz editor payload.",
)
def get_quiz_edit_data(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_owned_quiz_or_404(quiz_id, current_user, db)
    return serialize_quiz_editor(quiz, current_user, db)


@router.put(
    "/quizzes/{quiz_id}",
    response_model=schemas.QuizEditorOut,
    tags=["Quizzes"],
    summary="Update quiz",
    description="Update an existing owned quiz and replace its questions. Mutation is blocked when the quiz has active attempts.",
    response_description="Updated quiz in editor format.",
)
def update_quiz(quiz_id: int, payload: schemas.QuizUpdate, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    validate_quiz_payload(payload)
    quiz = get_owned_quiz_or_404(quiz_id, current_user, db)
    ensure_quiz_mutation_allowed(quiz, db)
    apply_quiz_payload(quiz, payload)
    replace_quiz_questions(quiz, payload.questions, db)
    db.commit()
    db.refresh(quiz)
    return serialize_quiz_editor(quiz, current_user, db)


@router.delete(
    "/quizzes/{quiz_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Quizzes"],
    summary="Delete quiz",
    description="Delete an owned quiz. Mutation is blocked when the quiz has active attempts.",
    response_description="Quiz deleted successfully.",
)
def delete_quiz(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_owned_quiz_or_404(quiz_id, current_user, db)
    ensure_quiz_mutation_allowed(quiz, db)
    db.delete(quiz)
    db.commit()


@router.post(
    "/quizzes/{quiz_id}/start",
    response_model=schemas.QuizAttemptSessionOut,
    tags=["Quiz Attempts"],
    summary="Start quiz attempt",
    description="Create a new attempt session for the specified quiz.",
    response_description="Quiz attempt session.",
)
def start_quiz_attempt(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return start_quiz_attempt_session(quiz_id, current_user, db)


@router.get(
    "/quiz-attempts/{attempt_id}",
    response_model=schemas.QuizAttemptSessionOut,
    tags=["Quiz Attempts"],
    summary="Get quiz attempt",
    description="Load the current state of a quiz attempt session for the authenticated user.",
    response_description="Quiz attempt session.",
)
def get_quiz_attempt(attempt_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return load_quiz_attempt_session(attempt_id, current_user, db)


@router.put(
    "/quiz-attempts/{attempt_id}/answers/{question_id}",
    response_model=schemas.QuizAttemptSessionOut,
    tags=["Quiz Attempts"],
    summary="Submit quiz answer",
    description="Save or replace the answer for a single question within an active quiz attempt.",
    response_description="Updated quiz attempt session.",
)
def answer_quiz_question(
    attempt_id: int,
    question_id: int,
    payload: schemas.QuizAnswerSubmit,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return submit_quiz_answer(attempt_id, question_id, payload, current_user, db)


@router.post(
    "/quiz-attempts/{attempt_id}/complete",
    response_model=schemas.QuizResultOut,
    tags=["Quiz Attempts"],
    summary="Complete quiz attempt",
    description="Finalize an active quiz attempt and calculate the result summary.",
    response_description="Completed quiz result.",
)
def complete_quiz_attempt(attempt_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return complete_quiz_attempt_result(attempt_id, current_user, db)


@router.get(
    "/quiz-attempts/{attempt_id}/results",
    response_model=schemas.QuizResultOut,
    tags=["Quiz Attempts"],
    summary="Get quiz results",
    description="Return the computed results for a completed quiz attempt.",
    response_description="Quiz result payload.",
)
def get_quiz_attempt_results(attempt_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return get_quiz_attempt_result(attempt_id, current_user, db)


router.include_router(page_router)
