from pathlib import Path

from fastapi.responses import FileResponse

from backend.main import deck_page, home_page, settings_page, study_page
from backend.quiz_router import (
    quiz_create_page,
    quiz_detail_page,
    quiz_edit_page,
    quiz_library_page,
    quiz_results_page,
    quiz_review_page,
    quiz_session_page,
)


ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIR = ROOT / "frontend"


def assert_file_response(response: FileResponse, expected_path: Path):
    assert isinstance(response, FileResponse)
    assert Path(response.path) == expected_path
    assert expected_path.is_file()


def test_core_page_handlers_point_to_moved_entrypoints():
    assert_file_response(home_page(), FRONTEND_DIR / "pages" / "home" / "index.html")
    assert_file_response(deck_page(), FRONTEND_DIR / "pages" / "deck" / "index.html")
    assert_file_response(study_page(), FRONTEND_DIR / "pages" / "study" / "index.html")
    assert_file_response(settings_page(), FRONTEND_DIR / "pages" / "settings" / "index.html")


def test_quiz_page_handlers_point_to_moved_entrypoints():
    assert_file_response(quiz_library_page(), FRONTEND_DIR / "pages" / "quiz" / "library.html")
    assert_file_response(quiz_create_page(), FRONTEND_DIR / "pages" / "quiz" / "editor.html")
    assert_file_response(quiz_edit_page(1), FRONTEND_DIR / "pages" / "quiz" / "editor.html")
    assert_file_response(quiz_detail_page(1), FRONTEND_DIR / "pages" / "quiz" / "detail.html")
    assert_file_response(quiz_session_page(1), FRONTEND_DIR / "pages" / "quiz" / "session.html")
    assert_file_response(quiz_results_page(1, 1), FRONTEND_DIR / "pages" / "quiz" / "results.html")
    assert_file_response(quiz_review_page(1, 1), FRONTEND_DIR / "pages" / "quiz" / "review.html")


def test_reorganized_frontend_assets_exist():
    expected_files = [
        FRONTEND_DIR / "shared" / "scripts" / "app-common.js",
        FRONTEND_DIR / "shared" / "scripts" / "app-shell.js",
        FRONTEND_DIR / "shared" / "scripts" / "app-auth.js",
        FRONTEND_DIR / "pages" / "home" / "index.css",
        FRONTEND_DIR / "pages" / "deck" / "deck-page.js",
        FRONTEND_DIR / "pages" / "study" / "study-session.js",
        FRONTEND_DIR / "pages" / "quiz" / "quiz-common.css",
    ]

    for path in expected_files:
        assert path.is_file()
