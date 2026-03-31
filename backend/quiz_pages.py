from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

page_router = APIRouter()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
QUIZ_PAGES_DIR = FRONTEND_DIR / "pages" / "quiz"


def serve_quiz_page(filename: str) -> FileResponse:
    return FileResponse(QUIZ_PAGES_DIR / filename)


@page_router.get("/quiz", include_in_schema=False)
def quiz_library_page():
    return serve_quiz_page("library.html")


@page_router.get("/quiz/create", include_in_schema=False)
def quiz_create_page():
    return serve_quiz_page("editor.html")


@page_router.get("/quiz/{quiz_id}/edit", include_in_schema=False)
def quiz_edit_page(quiz_id: int):
    return serve_quiz_page("editor.html")


@page_router.get("/quiz/{quiz_id}/start", include_in_schema=False)
def quiz_session_page(quiz_id: int):
    return serve_quiz_page("session.html")


@page_router.get("/quiz/{quiz_id}/results/{attempt_id}/review", include_in_schema=False)
def quiz_review_page(quiz_id: int, attempt_id: int):
    return serve_quiz_page("review.html")


@page_router.get("/quiz/{quiz_id}/results/{attempt_id}", include_in_schema=False)
def quiz_results_page(quiz_id: int, attempt_id: int):
    return serve_quiz_page("results.html")


@page_router.get("/quiz/{quiz_id}", include_in_schema=False)
def quiz_detail_page(quiz_id: int):
    return serve_quiz_page("detail.html")
