import os
from pathlib import Path

from .config import load_local_env
from .rate_limits import InMemoryRateLimitStore

load_local_env()

MEDIA_DIR = Path(__file__).resolve().parent.parent / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)

OPENVERSE_API_URL = os.getenv("OPENVERSE_API_URL", "https://api.openverse.org/v1/images/")
IMAGE_SEARCH_TIMEOUT = 15.0
MAX_IMAGE_DOWNLOAD_BYTES = int(os.getenv("MAX_IMAGE_DOWNLOAD_BYTES", str(5 * 1024 * 1024)))
MAX_IMAGE_UPLOAD_BYTES = int(os.getenv("MAX_IMAGE_UPLOAD_BYTES", str(5 * 1024 * 1024)))
IMAGE_REDIRECT_LIMIT = int(os.getenv("IMAGE_REDIRECT_LIMIT", "3"))
LOGIN_RATE_LIMIT = int(os.getenv("LOGIN_RATE_LIMIT", "5"))
DECK_ACCESS_RATE_LIMIT = int(os.getenv("DECK_ACCESS_RATE_LIMIT", "5"))
RATE_LIMIT_WINDOW_SECONDS = int(os.getenv("RATE_LIMIT_WINDOW_SECONDS", "600"))

RATE_LIMIT_STORE = InMemoryRateLimitStore()
FAILED_ATTEMPTS = RATE_LIMIT_STORE.attempts
