import hashlib
import math
import re

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def embed_text(text: str, dimensions: int = 64) -> list[float]:
    """Generate a deterministic L2-normalized feature-hashing vector over unigrams and bigrams."""
    dims = max(8, dimensions)
    tokens = _TOKEN_RE.findall(text.lower())
    if not tokens:
        return [0.0] * dims

    features = list(tokens)
    for idx in range(len(tokens) - 1):
        features.append(f"{tokens[idx]}_{tokens[idx + 1]}")

    vec = [0.0] * dims
    for feat in features:
        digest = hashlib.sha256(feat.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % dims
        sign = 1.0 if (digest[4] & 1) == 0 else -1.0
        vec[bucket] += sign

    norm = math.sqrt(sum(v * v for v in vec))
    if norm == 0.0:
        return [0.0] * dims
    return [round(v / norm, 6) for v in vec]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Compute cosine similarity between two equal-dimension vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norm_a = math.sqrt(sum(a * a for a in left))
    norm_b = math.sqrt(sum(b * b for b in right))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return round(dot / (norm_a * norm_b), 6)
