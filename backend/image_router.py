import socket
from uuid import uuid4

import httpx
from fastapi import APIRouter, Depends

from . import images as image_helpers
from . import schemas
from .auth import get_current_user
from .runtime import (
    IMAGE_REDIRECT_LIMIT,
    IMAGE_SEARCH_TIMEOUT,
    MAX_IMAGE_DOWNLOAD_BYTES,
    MAX_IMAGE_UPLOAD_BYTES,
    MEDIA_DIR,
    OPENVERSE_API_URL,
)

router = APIRouter(tags=["Images"])


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


def store_image_bytes(content: bytes, extension: str) -> str:
    filename = f"{uuid4().hex}{extension}"
    output_path = MEDIA_DIR / filename
    output_path.write_bytes(content)
    return f"/media/{filename}"


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


def build_search_images_response(
    payload: schemas.ImageSearchRequest,
    *,
    search_provider,
) -> schemas.ImageSearchResponse:
    query = payload.query.strip()
    results = search_provider(query, payload.page, payload.page_size)
    return schemas.ImageSearchResponse(
        query=query,
        page=payload.page,
        page_size=payload.page_size,
        results=results,
    )


def build_import_image_response(
    payload: schemas.ImageImportRequest,
    *,
    importer,
) -> schemas.StoredImageOut:
    return schemas.StoredImageOut(image_url=importer(payload.source_url.strip()))


def build_upload_image_response(
    payload: schemas.ImageUploadRequest,
    *,
    decoder,
    store_image,
) -> schemas.StoredImageOut:
    content, extension = decoder(payload.content_base64)
    return schemas.StoredImageOut(image_url=store_image(content, extension))


@router.post(
    "/images/search",
    response_model=schemas.ImageSearchResponse,
    summary="Поиск изображений",
    description="Искать у внешних провайдеров изображения, которые можно прикрепить к карточкам или квизам.",
    response_description="Страница результатов поиска изображений.",
)
def search_images_endpoint(payload: schemas.ImageSearchRequest, current_user=Depends(get_current_user)):
    return build_search_images_response(payload, search_provider=search_openverse_images)


@router.post(
    "/images/import",
    response_model=schemas.StoredImageOut,
    summary="Импорт внешнего изображения",
    description="Скачать внешнее HTTPS-изображение после проверки и сохранить его в медиадиректории приложения.",
    response_description="URL сохранённого изображения.",
)
def import_image_endpoint(payload: schemas.ImageImportRequest, current_user=Depends(get_current_user)):
    return build_import_image_response(payload, importer=download_external_image)


@router.post(
    "/images/upload",
    response_model=schemas.StoredImageOut,
    summary="Загрузка изображения",
    description="Декодировать изображение в base64, проверить его и сохранить загруженный файл для дальнейшего использования.",
    response_description="URL сохранённого изображения.",
)
def upload_image_endpoint(payload: schemas.ImageUploadRequest, current_user=Depends(get_current_user)):
    return build_upload_image_response(
        payload,
        decoder=lambda content_base64: image_helpers.decode_uploaded_image(
            content_base64,
            max_upload_bytes=MAX_IMAGE_UPLOAD_BYTES,
        ),
        store_image=store_image_bytes,
    )
