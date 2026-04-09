import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request, status


class InMemoryRateLimitStore:
    def __init__(self) -> None:
        self._attempts: dict[str, dict[str, list[float]]] = defaultdict(dict)
        self._lock = Lock()

    @property
    def attempts(self) -> dict[str, dict[str, list[float]]]:
        return self._attempts

    def build_key(self, scope: str, identifier: str, request: Request | None) -> str:
        client_host = request.client.host if request and request.client else "unknown"
        return f"{scope}:{client_host}:{identifier.strip().lower()}"

    def enforce(
        self,
        scope: str,
        identifier: str,
        request: Request | None,
        limit: int,
        window_seconds: int,
    ) -> str:
        key = self.build_key(scope, identifier, request)
        now = time.time()
        with self._lock:
            attempts = self._pruned_attempts(scope, key, now, window_seconds)
            if len(attempts) >= limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Слишком много неудачных попыток. Попробуйте позже",
                )
        return key

    def record_failure(self, scope: str, key: str, window_seconds: int) -> None:
        now = time.time()
        with self._lock:
            attempts = self._pruned_attempts(scope, key, now, window_seconds)
            attempts.append(now)
            self._attempts[scope][key] = attempts

    def clear_failures(self, scope: str, key: str) -> None:
        with self._lock:
            self._attempts[scope].pop(key, None)

    def _pruned_attempts(self, scope: str, key: str, now: float, window_seconds: int) -> list[float]:
        attempts = [
            timestamp
            for timestamp in self._attempts[scope].get(key, [])
            if now - timestamp < window_seconds
        ]
        self._attempts[scope][key] = attempts
        return attempts
