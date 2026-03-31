import base64
import binascii
import ipaddress
import mimetypes
import socket
from pathlib import Path
from typing import Callable
from urllib.parse import urljoin, urlparse

import httpx
from fastapi import HTTPException

from . import schemas

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

ResolveHost = Callable[..., list[tuple]]
StoreImageFunc = Callable[[bytes, str], str]
ValidateUrlFunc = Callable[[str], str]
EnsureRedirectFunc = Callable[[str, str], str]
ClientFactory = Callable[..., httpx.Client]


def detect_image_extension(content: bytes) -> str | None:
    if content.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if content.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if content.startswith((b"GIF87a", b"GIF89a")):
        return ".gif"
    if len(content) >= 12 and content[:4] == b"RIFF" and content[8:12] == b"WEBP":
        return ".webp"
    return None


def is_public_ip_address(raw_address: str) -> bool:
    address = ipaddress.ip_address(raw_address)
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_reserved
        or address.is_unspecified
    )


def validate_external_image_url(
    source_url: str,
    *,
    resolve_host: ResolveHost = socket.getaddrinfo,
) -> str:
    parsed = urlparse(source_url.strip())
    if parsed.scheme.lower() != "https":
        raise HTTPException(status_code=400, detail="Only https image URLs are allowed")
    if not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(status_code=400, detail="Invalid image URL")

    try:
        resolved_addresses = {
            item[4][0]
            for item in resolve_host(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as error:
        raise HTTPException(status_code=400, detail="Image host could not be resolved") from error

    if not resolved_addresses or any(not is_public_ip_address(address) for address in resolved_addresses):
        raise HTTPException(status_code=400, detail="Image host is not allowed")
    return parsed.geturl()


def ensure_redirect_allowed(
    current_url: str,
    location: str,
    *,
    validate_url: ValidateUrlFunc = validate_external_image_url,
) -> str:
    return validate_url(urljoin(current_url, location))


def guess_image_extension(content_type: str | None, fallback_name: str = "") -> str:
    normalized_type = (content_type or "").split(";")[0].strip().lower()
    guessed = {
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
    }.get(normalized_type)
    if not guessed and normalized_type:
        guessed = mimetypes.guess_extension(normalized_type)
    if guessed in {".jpe"}:
        guessed = ".jpg"
    if guessed and guessed.lower() in ALLOWED_IMAGE_EXTENSIONS:
        return guessed.lower()
    suffix = Path(fallback_name).suffix.lower()
    if suffix in ALLOWED_IMAGE_EXTENSIONS:
        return suffix
    return ".jpg"


def normalize_openverse_results(payload: dict) -> list[schemas.ImageSearchResult]:
    results = []
    for item in payload.get("results", []):
        thumbnail_url = item.get("thumbnail")
        source_url = item.get("url")
        if not thumbnail_url or not source_url:
            continue
        results.append(
            schemas.ImageSearchResult(
                provider="openverse",
                external_id=str(item.get("id") or source_url),
                title=item.get("title") or "Untitled image",
                thumbnail_url=thumbnail_url,
                source_url=source_url,
                author=item.get("creator"),
                license=item.get("license"),
                license_version=item.get("license_version"),
                provider_display="Openverse",
            )
        )
    return results


def search_openverse_images(
    query: str,
    page: int,
    page_size: int,
    *,
    api_url: str,
    timeout: float,
    client_factory: ClientFactory = httpx.Client,
) -> list[schemas.ImageSearchResult]:
    try:
        with client_factory(timeout=timeout, follow_redirects=True) as client:
            response = client.get(
                api_url,
                params={"q": query, "page": page, "page_size": page_size},
                headers={"User-Agent": "Deckly/1.0"},
            )
            response.raise_for_status()
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Image search provider is unavailable") from error
    return normalize_openverse_results(response.json())


def download_external_image(
    source_url: str,
    *,
    timeout: float,
    redirect_limit: int,
    max_download_bytes: int,
    store_image: StoreImageFunc,
    client_factory: ClientFactory = httpx.Client,
    validate_url: ValidateUrlFunc = validate_external_image_url,
    ensure_redirect: EnsureRedirectFunc = ensure_redirect_allowed,
) -> str:
    current_url = validate_url(source_url)
    redirects_followed = 0

    try:
        with client_factory(timeout=timeout, follow_redirects=False) as client:
            while True:
                with client.stream("GET", current_url, headers={"User-Agent": "Deckly/1.0"}) as response:
                    if response.status_code in {301, 302, 303, 307, 308}:
                        location = response.headers.get("location")
                        if not location:
                            raise HTTPException(status_code=502, detail="Image provider returned an invalid redirect")
                        redirects_followed += 1
                        if redirects_followed > redirect_limit:
                            raise HTTPException(status_code=502, detail="Image provider redirected too many times")
                        current_url = ensure_redirect(current_url, location)
                        continue

                    response.raise_for_status()
                    content_type = response.headers.get("content-type", "")
                    if not content_type.startswith("image/"):
                        raise HTTPException(status_code=400, detail="The selected file is not an image")

                    content_length = response.headers.get("content-length")
                    if content_length and int(content_length) > max_download_bytes:
                        raise HTTPException(status_code=413, detail="The selected image is too large")

                    content = bytearray()
                    for chunk in response.iter_bytes():
                        content.extend(chunk)
                        if len(content) > max_download_bytes:
                            raise HTTPException(status_code=413, detail="The selected image is too large")

                    if not content:
                        raise HTTPException(status_code=400, detail="The selected image is empty")

                    detected_extension = detect_image_extension(bytes(content))
                    if not detected_extension:
                        raise HTTPException(status_code=400, detail="The selected file is not a supported image")

                    return store_image(bytes(content), detected_extension)
    except HTTPException:
        raise
    except httpx.HTTPError as error:
        raise HTTPException(status_code=502, detail="Failed to download the selected image") from error


def decode_uploaded_image(content_base64: str, *, max_upload_bytes: int) -> tuple[bytes, str]:
    try:
        content = base64.b64decode(content_base64, validate=True)
    except (binascii.Error, ValueError) as error:
        raise HTTPException(status_code=400, detail="Invalid image payload") from error
    if not content:
        raise HTTPException(status_code=400, detail="Image payload is empty")
    if len(content) > max_upload_bytes:
        raise HTTPException(status_code=413, detail="Image payload is too large")
    extension = detect_image_extension(content)
    if not extension:
        raise HTTPException(status_code=400, detail="Uploaded file is not a supported image")
    return content, extension
