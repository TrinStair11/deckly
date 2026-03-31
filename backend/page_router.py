from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
PAGES_DIR = FRONTEND_DIR / "pages"


def serve_page(*parts: str) -> FileResponse:
    return FileResponse(PAGES_DIR.joinpath(*parts))


@router.get("/", include_in_schema=False)
@router.get("/index.html", include_in_schema=False)
def home_page():
    return serve_page("home", "index.html")


@router.get("/deck.html", include_in_schema=False)
def deck_page():
    return serve_page("deck", "index.html")


@router.get("/study.html", include_in_schema=False)
def study_page():
    return serve_page("study", "index.html")


@router.get("/settings.html", include_in_schema=False)
def settings_page():
    return serve_page("settings", "index.html")
