import hashlib
import hmac
import re

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_API_KEY_RE = re.compile(
    r"(?:\bBearer\s+[A-Za-z0-9._\-]{12,}|\b(?:sk|AIza|ghp|xox[baprs])[-_A-Za-z0-9]{8,})"
)
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?1[-.\s]?)?(?:\(\d{3}\)|\d{3})[-.\s]?\d{3}[-.\s]?\d{4}(?!\w)"
)


def redact_pii(text: str) -> tuple[str, list[str]]:
    """Deterministically scrub emails, phone numbers, SSNs, and API tokens from text."""
    if not text:
        return text, []

    categories: set[str] = set()
    redacted = text

    # Scrub API keys/tokens before phones to avoid partial digit collisions inside tokens.
    if _API_KEY_RE.search(redacted):
        redacted = _API_KEY_RE.sub("[REDACTED_TOKEN]", redacted)
        categories.add("API_KEY")

    if _EMAIL_RE.search(redacted):
        redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
        categories.add("EMAIL")

    if _SSN_RE.search(redacted):
        redacted = _SSN_RE.sub("[REDACTED_SSN]", redacted)
        categories.add("SSN")

    if _PHONE_RE.search(redacted):
        redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
        categories.add("PHONE")

    return redacted, sorted(categories)


def verify_webhook_signature(
    payload: bytes,
    signature_header: str | None,
    secret: str,
) -> bool:
    """Verify HMAC-SHA256 carrier webhook signature when a signing secret is configured."""
    if not secret:
        return True
    if not signature_header:
        return False

    candidate = signature_header.strip()
    if candidate.lower().startswith("sha256="):
        candidate = candidate[7:].strip()

    expected = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(candidate.lower(), expected.lower())
