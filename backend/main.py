import os
import socket
from contextlib import asynccontextmanager
from stat import S_ISREG
from uuid import uuid4

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from . import images as image_helpers
from . import schemas
from .account_router import (
    me,
    register,
    router as account_router,
    logout,
    update_account_email,
    update_account_password,
)
from .auth_router import router as auth_router
from .auth import (
    get_current_user,
)
from .config import load_local_env
from .deck_router import (
    create_card,
    create_deck,
    delete_card,
    delete_deck,
    grant_private_deck_access,
    get_deck,
    get_deck_progress,
    get_legacy_study_session,
    get_shared_deck,
    get_shared_deck_meta,
    get_shared_study_session,
    get_study_session,
    list_cards,
    list_decks,
    reorder_cards,
    review_card,
    router as deck_router,
    save_shared_deck,
    submit_review,
    update_card,
    update_deck,
)
from .decks import (
    create_deck_access_token,
    save_deck_to_library,
    serialize_deck,
    validate_deck_privacy,
    verify_deck_access_token,
)
from .db import ensure_schema
from .image_router import (
    build_import_image_response,
    build_search_images_response,
    build_upload_image_response,
    router as image_router,
)
from .page_router import (
    FRONTEND_DIR,
    deck_page,
    home_page,
    router as page_router,
    settings_page,
    study_page,
)
from .runtime import (
    DECK_ACCESS_RATE_LIMIT as DEFAULT_DECK_ACCESS_RATE_LIMIT,
    FAILED_ATTEMPTS,
    IMAGE_REDIRECT_LIMIT as DEFAULT_IMAGE_REDIRECT_LIMIT,
    IMAGE_SEARCH_TIMEOUT as DEFAULT_IMAGE_SEARCH_TIMEOUT,
    LOGIN_RATE_LIMIT as DEFAULT_LOGIN_RATE_LIMIT,
    MAX_IMAGE_DOWNLOAD_BYTES as DEFAULT_MAX_IMAGE_DOWNLOAD_BYTES,
    MAX_IMAGE_UPLOAD_BYTES as DEFAULT_MAX_IMAGE_UPLOAD_BYTES,
    MEDIA_DIR,
    OPENVERSE_API_URL,
    RATE_LIMIT_WINDOW_SECONDS as DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
)
from .security_services import (
    clear_rate_limit_failures,
    enforce_rate_limit,
    get_rate_limit_bucket,
    perform_login,
    rate_limit_key,
    record_rate_limit_failure,
)
from .spaced_repetition import refresh_user_deck_progress
from .quiz_router import (
    answer_quiz_question,
    complete_quiz_attempt,
    create_quiz,
    delete_quiz,
    get_quiz_attempt,
    get_quiz_attempt_results,
    get_quiz_detail,
    get_quiz_edit_data,
    list_quizzes_module,
    router as quiz_router,
    start_quiz_attempt,
    update_quiz,
)


@asynccontextmanager
async def app_lifespan(_: FastAPI):
    ensure_schema()
    yield


load_local_env()

API_DESCRIPTION = """
Deckly API для колод карточек, сценариев интервального повторения, шаринга колод, управления изображениями и квизов.

Аутентификация:
- Браузерные клиенты в основном используют защищённую HTTP-only cookie сессии, которую выставляет маршрут входа.
- Прямые API-клиенты также могут авторизоваться через Bearer-токен.

Маршруты приватных общих колод дополнительно могут требовать заголовок `X-Deck-Access-Token`.
""".strip()

OPENAPI_TAGS = [
    {
        "name": "Auth",
        "description": "Маршруты аутентификации для создания и управления API-сессиями.",
    },
    {
        "name": "Account",
        "description": "Регистрация аккаунта, получение профиля и обновление учетных данных.",
    },
    {
        "name": "Decks",
        "description": "Создание колод карточек, библиотека, просмотр деталей и обновление.",
    },
    {
        "name": "Cards",
        "description": "Создание, чтение, обновление и удаление карточек, а также изменение их порядка внутри колод.",
    },
    {
        "name": "Study",
        "description": "Генерация учебных сессий и прогресс интервального повторения по пользователям.",
    },
    {
        "name": "Sharing",
        "description": "Доступ к общим колодам, метаданные, разблокировка приватных колод и сохранение в библиотеку.",
    },
    {
        "name": "Reviews",
        "description": "Отправка результатов повторения, которые продвигают состояние интервального обучения.",
    },
    {
        "name": "Images",
        "description": "Маршруты поиска, импорта и загрузки изображений для карточек и квизов.",
    },
    {
        "name": "Quizzes",
        "description": "Маршруты создания, списка и просмотра деталей квизов.",
    },
    {
        "name": "Quiz Attempts",
        "description": "Сессии квизов, отправка ответов, завершение и получение результатов.",
    },
]

app = FastAPI(
    title="Deckly API",
    version="0.1.0",
    description=API_DESCRIPTION,
    openapi_tags=OPENAPI_TAGS,
    lifespan=app_lifespan,
    swagger_ui_parameters={
        "displayRequestDuration": True,
        "docExpansion": "list",
        "persistAuthorization": True,
    },
)


class FrontendStaticFiles(StaticFiles):
    async def get_response(self, path: str, scope):
        if path.lower().endswith(".html"):
            raise HTTPException(status_code=404)
        return await super().get_response(path, scope)

    def lookup_path(self, path: str):
        full_path, stat_result = super().lookup_path(path)
        if stat_result and S_ISREG(stat_result.st_mode) and full_path.lower().endswith(".html"):
            return "", None
        return full_path, stat_result


def parse_cors_origins(raw_value: str) -> list[str]:
    return [origin.strip() for origin in raw_value.split(",") if origin.strip()]


CORS_ALLOW_ORIGINS = parse_cors_origins(
    os.getenv("CORS_ALLOW_ORIGINS", "http://127.0.0.1:8000,http://localhost:8000")
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(auth_router)
app.include_router(account_router)
app.include_router(deck_router)
app.include_router(image_router)
app.include_router(page_router)
app.include_router(quiz_router)

IMAGE_SEARCH_TIMEOUT = DEFAULT_IMAGE_SEARCH_TIMEOUT
MAX_IMAGE_DOWNLOAD_BYTES = DEFAULT_MAX_IMAGE_DOWNLOAD_BYTES
MAX_IMAGE_UPLOAD_BYTES = DEFAULT_MAX_IMAGE_UPLOAD_BYTES
IMAGE_REDIRECT_LIMIT = DEFAULT_IMAGE_REDIRECT_LIMIT
LOGIN_RATE_LIMIT = DEFAULT_LOGIN_RATE_LIMIT
DECK_ACCESS_RATE_LIMIT = DEFAULT_DECK_ACCESS_RATE_LIMIT
RATE_LIMIT_WINDOW_SECONDS = DEFAULT_RATE_LIMIT_WINDOW_SECONDS


def detect_image_extension(content: bytes) -> str | None:
    return image_helpers.detect_image_extension(content)


def validate_external_image_url(source_url: str) -> str:
    return image_helpers.validate_external_image_url(
        source_url,
        resolve_host=socket.getaddrinfo,
    )


def ensure_redirect_allowed(current_url: str, location: str) -> str:
    return image_helpers.ensure_redirect_allowed(
        current_url,
        location,
        validate_url=validate_external_image_url,
    )


def guess_image_extension(content_type: str | None, fallback_name: str = "") -> str:
    return image_helpers.guess_image_extension(content_type, fallback_name)


def store_image_bytes(content: bytes, extension: str) -> str:
    filename = f"{uuid4().hex}{extension}"
    output_path = MEDIA_DIR / filename
    output_path.write_bytes(content)
    return f"/media/{filename}"


def normalize_openverse_results(payload: dict) -> list[schemas.ImageSearchResult]:
    return image_helpers.normalize_openverse_results(payload)


def search_openverse_images(query: str, page: int, page_size: int) -> list[schemas.ImageSearchResult]:
    return image_helpers.search_openverse_images(
        query,
        page,
        page_size,
        api_url=OPENVERSE_API_URL,
        timeout=IMAGE_SEARCH_TIMEOUT,
        client_factory=httpx.Client,
    )


def download_external_image(source_url: str) -> str:
    return image_helpers.download_external_image(
        source_url,
        timeout=IMAGE_SEARCH_TIMEOUT,
        redirect_limit=IMAGE_REDIRECT_LIMIT,
        max_download_bytes=MAX_IMAGE_DOWNLOAD_BYTES,
        store_image=store_image_bytes,
        client_factory=httpx.Client,
        validate_url=validate_external_image_url,
        ensure_redirect=ensure_redirect_allowed,
    )


def login(
    payload: schemas.UserLogin,
    db: Session,
    response: Response = None,
    request: Request = None,
):
    return perform_login(payload, db, response=response, request=request, rate_limit=LOGIN_RATE_LIMIT)


def access_private_deck(
    deck_id: int,
    payload: schemas.DeckAccessRequest,
    db: Session,
    request: Request = None,
):
    return grant_private_deck_access(deck_id, payload, db, request=request, rate_limit=DECK_ACCESS_RATE_LIMIT)


def search_images(payload: schemas.ImageSearchRequest, current_user=Depends(get_current_user)):
    return build_search_images_response(
        payload,
        search_provider=search_openverse_images,
    )


def import_image(payload: schemas.ImageImportRequest, current_user=Depends(get_current_user)):
    return build_import_image_response(payload, importer=download_external_image)


def upload_image(payload: schemas.ImageUploadRequest, current_user=Depends(get_current_user)):
    return build_upload_image_response(
        payload,
        decoder=lambda content_base64: image_helpers.decode_uploaded_image(
            content_base64,
            max_upload_bytes=MAX_IMAGE_UPLOAD_BYTES,
        ),
        store_image=store_image_bytes,
    )


app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")
app.mount("/", FrontendStaticFiles(directory=FRONTEND_DIR, html=False), name="frontend")
