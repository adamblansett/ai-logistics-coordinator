import base64
import hashlib
import hmac
import json
import secrets
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import Depends, HTTPException, Request, status

from app.core.config import Settings, get_runtime_settings

VALID_ROLES = {"VIEWER", "WAREHOUSE", "DISPATCHER", "WEBHOOK_INGESTOR", "ADMIN"}
_PBKDF2_ITERATIONS = 120_000


def _b64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64url_decode(token_part: str) -> bytes:
    padding = "=" * (-len(token_part) % 4)
    return base64.urlsafe_b64decode(token_part + padding)


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-HMAC-SHA256 and a random 16-byte salt."""
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt),
        _PBKDF2_ITERATIONS,
    )
    return f"pbkdf2_sha256${_PBKDF2_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a plaintext password against a stored PBKDF2-HMAC-SHA256 hash."""
    parts = stored_hash.split("$")
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
        salt = bytes.fromhex(parts[2])
        expected = bytes.fromhex(parts[3])
    except ValueError:
        return False

    candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return hmac.compare_digest(candidate, expected)


def create_access_token(
    *,
    subject: str,
    role: str,
    secret: str,
    ttl_minutes: int,
) -> str:
    """Mint an HS256 JWT access token."""
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + max(1, ttl_minutes) * 60,
    }
    signing_input = ".".join(
        [
            _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
            _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
        ]
    )
    sig = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64url_encode(sig)}"


def decode_access_token(token: str, secret: str) -> dict[str, Any]:
    """Verify and decode an HS256 JWT access token, raising ValueError on failure."""
    parts = token.strip().split(".")
    if len(parts) != 3:
        raise ValueError("Malformed bearer token.")
    header_b64, payload_b64, sig_b64 = parts
    signing_input = f"{header_b64}.{payload_b64}"
    expected_sig = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    try:
        provided_sig = _b64url_decode(sig_b64)
    except Exception as exc:
        raise ValueError("Invalid token signature encoding.") from exc

    if not hmac.compare_digest(provided_sig, expected_sig):
        raise ValueError("Invalid token signature.")

    try:
        header = json.loads(_b64url_decode(header_b64).decode("utf-8"))
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))
    except Exception as exc:
        raise ValueError("Invalid token payload.") from exc

    if header.get("alg") != "HS256":
        raise ValueError("Unsupported token algorithm.")
    exp = payload.get("exp")
    if not isinstance(exp, int | float) or int(time.time()) >= int(exp):
        raise ValueError("Token has expired.")
    if not payload.get("sub") or not payload.get("role"):
        raise ValueError("Token missing subject or role.")
    return dict(payload)


def parse_api_keys(raw: str) -> dict[str, tuple[str, str]]:
    """Parse comma-separated `key:ROLE:name` entries into `{key: (role, name)}`."""
    parsed: dict[str, tuple[str, str]] = {}
    for entry in raw.split(","):
        item = entry.strip()
        if not item:
            continue
        parts = [p.strip() for p in item.split(":")]
        if len(parts) < 2 or not parts[0]:
            continue
        key = parts[0]
        role = parts[1].upper() if parts[1].upper() in VALID_ROLES else "VIEWER"
        name = parts[2] if len(parts) >= 3 and parts[2] else f"api-key-{role.lower()}"
        parsed[key] = (role, name)
    return parsed


@dataclass(slots=True)
class Principal:
    username: str
    role: str
    auth_method: Literal["jwt", "api_key", "dev_anonymous"]
    authenticated: bool


async def get_current_principal(
    request: Request,
    settings: Settings = Depends(get_runtime_settings),
) -> Principal:
    """Resolve the active caller via JWT Bearer token, X-API-Key, or dev bypass."""
    auth_header = request.headers.get("authorization", "").strip()
    if auth_header:
        if not auth_header.lower().startswith("bearer "):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authorization header must use Bearer scheme.",
            )
        token = auth_header[7:].strip()
        try:
            claims = decode_access_token(token, settings.auth_secret_key)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=str(exc),
            ) from exc
        return Principal(
            username=str(claims["sub"]),
            role=str(claims["role"]).upper(),
            auth_method="jwt",
            authenticated=True,
        )

    api_key_header = request.headers.get("x-api-key", "").strip()
    if api_key_header:
        configured = parse_api_keys(settings.auth_api_keys)
        for key, (role, name) in configured.items():
            if hmac.compare_digest(api_key_header, key):
                return Principal(
                    username=name,
                    role=role,
                    auth_method="api_key",
                    authenticated=True,
                )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid X-API-Key credential.",
        )

    if settings.auth_enabled:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )

    return Principal(
        username="dev-admin",
        role="ADMIN",
        auth_method="dev_anonymous",
        authenticated=False,
    )


def require_roles(*allowed_roles: str) -> Callable[..., Awaitable[Principal]]:
    """FastAPI dependency factory enforcing RBAC role membership (ADMIN always permitted)."""
    allowed = {role.upper() for role in allowed_roles} | {"ADMIN"}

    async def _guard(principal: Principal = Depends(get_current_principal)) -> Principal:
        if principal.role.upper() not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Role '{principal.role}' lacks required permission ({sorted(allowed)}).",
            )
        return principal

    return _guard


def resolve_actor(principal: Principal, fallback_actor: str) -> str:
    """Return verified caller identity when authenticated, else client fallback label."""
    if principal.authenticated:
        return principal.username
    return fallback_actor.strip() or principal.username
