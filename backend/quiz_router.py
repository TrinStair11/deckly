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
    summary="Создать квиз",
    description="Создать новый квиз с авторскими вопросами и метаданными редактора.",
    response_description="Созданный квиз в формате редактора.",
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
    summary="Список квизов",
    description="Вернуть квизы, доступные авторизованному пользователю, с дополнительной фильтрацией по поиску, категории, сложности и сортировке.",
    response_description="Отфильтрованные сводки по квизам.",
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
    summary="Детали квиза",
    description="Вернуть полное публичное или доступное детальное представление квиза.",
    response_description="Данные детального представления квиза.",
)
def get_quiz_detail(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_accessible_quiz_or_404(quiz_id, current_user, db)
    return serialize_quiz_detail(quiz, current_user, db)


@router.get(
    "/quizzes/{quiz_id}/edit-data",
    response_model=schemas.QuizEditorOut,
    tags=["Quizzes"],
    summary="Данные редактора квиза",
    description="Вернуть данные редактора, доступные только владельцу, для заполнения интерфейса редактирования квиза.",
    response_description="Данные редактора квиза.",
)
def get_quiz_edit_data(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    quiz = get_owned_quiz_or_404(quiz_id, current_user, db)
    return serialize_quiz_editor(quiz, current_user, db)


@router.put(
    "/quizzes/{quiz_id}",
    response_model=schemas.QuizEditorOut,
    tags=["Quizzes"],
    summary="Обновить квиз",
    description="Обновить существующий квиз владельца и заменить его вопросы. Изменение блокируется, если у квиза есть активные попытки.",
    response_description="Обновлённый квиз в формате редактора.",
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
    summary="Удалить квиз",
    description="Удалить квиз владельца. Изменение блокируется, если у квиза есть активные попытки.",
    response_description="Квиз успешно удалён.",
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
    summary="Начать попытку квиза",
    description="Создать новую попытку прохождения для указанного квиза.",
    response_description="Сессия попытки квиза.",
)
def start_quiz_attempt(quiz_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return start_quiz_attempt_session(quiz_id, current_user, db)


@router.get(
    "/quiz-attempts/{attempt_id}",
    response_model=schemas.QuizAttemptSessionOut,
    tags=["Quiz Attempts"],
    summary="Получить попытку квиза",
    description="Загрузить текущее состояние сессии попытки квиза для авторизованного пользователя.",
    response_description="Сессия попытки квиза.",
)
def get_quiz_attempt(attempt_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return load_quiz_attempt_session(attempt_id, current_user, db)


@router.put(
    "/quiz-attempts/{attempt_id}/answers/{question_id}",
    response_model=schemas.QuizAttemptSessionOut,
    tags=["Quiz Attempts"],
    summary="Отправить ответ квиза",
    description="Сохранить или заменить ответ на один вопрос в активной попытке квиза.",
    response_description="Обновлённая сессия попытки квиза.",
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
    summary="Завершить попытку квиза",
    description="Завершить активную попытку квиза и вычислить сводный результат.",
    response_description="Результат завершённой попытки квиза.",
)
def complete_quiz_attempt(attempt_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return complete_quiz_attempt_result(attempt_id, current_user, db)


@router.get(
    "/quiz-attempts/{attempt_id}/results",
    response_model=schemas.QuizResultOut,
    tags=["Quiz Attempts"],
    summary="Получить результаты квиза",
    description="Вернуть вычисленные результаты завершённой попытки квиза.",
    response_description="Данные результата квиза.",
)
def get_quiz_attempt_results(attempt_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return get_quiz_attempt_result(attempt_id, current_user, db)


router.include_router(page_router)
