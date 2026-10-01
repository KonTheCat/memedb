"""Calibrated relevance bucketing for search results.

Cosmos DB's RANK RRF(VectorDistance(...), FullTextScore(...)) can only be used
in ORDER BY - it can't be projected as a combined score - so the only signals
available per result are the raw vector cosine (projected separately as
`similarity`) and, for text queries, lexical overlap with the query that we
compute ourselves. Both are compared against fixed thresholds calibrated per
embedding model version (see scripts/calibrate_thresholds.py), not rescaled
within a single result set, since relative rescaling would show high
confidence for a result set that's uniformly bad.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

TEXT_BUCKETS = ("weak", "possible", "strong")
IMAGE_BUCKETS = ("weak", "loose", "similar", "near_duplicate")

_STOPWORDS = {
    "a", "an", "the", "of", "in", "on", "at", "to", "for", "and", "or", "is",
    "are", "was", "were", "be", "been", "with", "this", "that", "it", "its",
    "as", "from", "by", "me", "my", "i",
}

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_SUFFIXES = ("'s", "ing", "ed", "es", "s")


def _stem(token: str) -> str:
    for suffix in _SUFFIXES:
        if len(token) > len(suffix) + 2 and token.endswith(suffix):
            return token[: -len(suffix)]
    return token


def tokenize(text: str) -> set[str]:
    raw = _TOKEN_RE.findall(text.lower())
    return {_stem(t) for t in raw if t not in _STOPWORDS}


def lexical_coverage(query_tokens: set[str], doc_tokens: set[str]) -> tuple[float, list[str]]:
    if not query_tokens:
        return 0.0, []
    matched = sorted(query_tokens & doc_tokens)
    return len(matched) / len(query_tokens), matched


@dataclass(frozen=True)
class TextThresholds:
    mid: float
    high: float


@dataclass(frozen=True)
class ImageThresholds:
    mid: float
    high: float
    dup: float


# Keyed by embedding model version (Settings.vision_model_version). The
# cosine ranges below are tied to that specific model's embedding space, so
# an upgrade needs a new entry from scripts/calibrate_thresholds.py rather
# than overwriting the old one - add, don't replace, so historical runs stay
# interpretable.
TEXT_THRESHOLDS: dict[str, TextThresholds] = {}
IMAGE_THRESHOLDS: dict[str, ImageThresholds] = {}

# PROVISIONAL - not derived from labeled data. Placeholders so the feature is
# usable before calibration; replace by running scripts/calibrate_thresholds.py
# and adding a real entry to TEXT_THRESHOLDS / IMAGE_THRESHOLDS above.
_PROVISIONAL_TEXT = TextThresholds(mid=0.30, high=0.36)
_PROVISIONAL_IMAGE = ImageThresholds(mid=0.55, high=0.75, dup=0.92)

_warned: set[tuple[str, str]] = set()


def _warn_once(mode: str, model_version: str) -> None:
    key = (mode, model_version)
    if key in _warned:
        return
    _warned.add(key)
    logger.warning(
        "No calibrated %s relevance thresholds for vision model %r; using "
        "provisional, uncalibrated placeholders. Run "
        "scripts/calibrate_thresholds.py and add an entry to %s_THRESHOLDS.",
        mode,
        model_version,
        mode.upper(),
    )


def is_provisional(mode: str, model_version: str) -> bool:
    table = TEXT_THRESHOLDS if mode == "text" else IMAGE_THRESHOLDS
    return model_version not in table


def get_text_thresholds(model_version: str) -> TextThresholds:
    thresholds = TEXT_THRESHOLDS.get(model_version)
    if thresholds is None:
        _warn_once("text", model_version)
        return _PROVISIONAL_TEXT
    return thresholds


def get_image_thresholds(model_version: str) -> ImageThresholds:
    thresholds = IMAGE_THRESHOLDS.get(model_version)
    if thresholds is None:
        _warn_once("image", model_version)
        return _PROVISIONAL_IMAGE
    return thresholds


def _bucket_text(cosine: float, coverage: float, thresholds: TextThresholds) -> str:
    if cosine >= thresholds.high or (coverage >= 0.5 and cosine >= thresholds.mid):
        return "strong"
    if coverage > 0 or cosine >= thresholds.mid:
        return "possible"
    return "weak"


def _bucket_image(cosine: float, thresholds: ImageThresholds) -> str:
    if cosine >= thresholds.dup:
        return "near_duplicate"
    if cosine >= thresholds.high:
        return "similar"
    if cosine >= thresholds.mid:
        return "loose"
    return "weak"


def _cap_non_increasing(buckets: list[str], order: tuple[str, ...]) -> list[str]:
    index = {name: i for i, name in enumerate(order)}
    ceiling = len(order) - 1
    capped = []
    for bucket in buckets:
        level = min(index[bucket], ceiling)
        ceiling = level
        capped.append(order[level])
    return capped


def bucket_text_results(cosine_coverage_pairs: list[tuple[float, float]], model_version: str) -> tuple[list[str], bool]:
    """Returns (bucket per result, non-increasing down the list), no_strong_matches)."""
    thresholds = get_text_thresholds(model_version)
    raw = [_bucket_text(cosine, coverage, thresholds) for cosine, coverage in cosine_coverage_pairs]
    capped = _cap_non_increasing(raw, TEXT_BUCKETS)
    no_strong_matches = "strong" not in capped
    return capped, no_strong_matches


def bucket_image_results(cosines: list[float], model_version: str) -> tuple[list[str], bool]:
    thresholds = get_image_thresholds(model_version)
    raw = [_bucket_image(cosine, thresholds) for cosine in cosines]
    capped = _cap_non_increasing(raw, IMAGE_BUCKETS)
    no_strong_matches = not any(b in ("similar", "near_duplicate") for b in capped)
    return capped, no_strong_matches
