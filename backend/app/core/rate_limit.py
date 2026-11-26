import json
import time
from collections import defaultdict, deque

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.config import Settings

_HEALTH_EXEMPT_SUFFIXES = (
    "/health",
    "/health/live",
    "/health/ready",
)


class RateLimitMiddleware:
    """Pure ASGI sliding-window per-IP rate limiter for API routes."""

    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _client_key(self, scope: Scope) -> str:
        for key, value in scope.get("headers") or []:
            if key.decode("latin-1").lower() == "x-forwarded-for":
                first_hop = value.decode("latin-1", errors="ignore").split(",")[0].strip()
                if first_hop:
                    return first_hop
        client = scope.get("client")
        if isinstance(client, tuple | list) and client:
            return str(client[0])
        return "unknown"

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or not self.settings.rate_limit_enabled:
            await self.app(scope, receive, send)
            return

        path = str(scope.get("path") or "")
        if any(path.endswith(suffix) for suffix in _HEALTH_EXEMPT_SUFFIXES):
            await self.app(scope, receive, send)
            return

        limit = max(1, self.settings.rate_limit_requests_per_minute)
        now = time.monotonic()
        cutoff = now - 60.0
        client_ip = self._client_key(scope)
        bucket = self._hits[client_ip]

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(60 - (now - bucket[0])) + 1)
            body = json.dumps({"detail": "Rate limit exceeded. Retry shortly."}).encode("utf-8")
            await send(
                {
                    "type": "http.response.start",
                    "status": 429,
                    "headers": [
                        (b"content-type", b"application/json"),
                        (b"retry-after", str(retry_after).encode("ascii")),
                        (b"x-ratelimit-limit", str(limit).encode("ascii")),
                        (b"x-ratelimit-remaining", b"0"),
                    ],
                }
            )
            await send({"type": "http.response.body", "body": body})
            return

        bucket.append(now)
        remaining = max(0, limit - len(bucket))

        async def send_wrapper(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers") or [])
                existing = {k.lower() for k, _ in headers}
                if b"x-ratelimit-limit" not in existing:
                    headers.append((b"x-ratelimit-limit", str(limit).encode("ascii")))
                if b"x-ratelimit-remaining" not in existing:
                    headers.append((b"x-ratelimit-remaining", str(remaining).encode("ascii")))
                message = {**message, "headers": headers}
            await send(message)

        await self.app(scope, receive, send_wrapper)
