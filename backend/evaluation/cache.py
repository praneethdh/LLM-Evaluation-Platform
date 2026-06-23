"""
Result cache — avoids redundant API calls when re-running the same
(model + prompt + input) combination.

Cache key = SHA-256 hash of (model_id, system_prompt, input_text).
Checks the EvalResult table for existing cached outputs.
"""

import hashlib
import logging

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def make_cache_key(model_id: str, system_prompt: str, input_text: str) -> str:
    """
    Deterministic hash of the triplet that uniquely identifies a model call.
    If any of the three change, the cache key changes → cache miss.
    """
    raw = f"{model_id}::{system_prompt}::{input_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def check_cache(db: Session, cache_key: str):
    """
    Look up a cached result by output_hash.
    Returns the first matching EvalResult or None.
    """
    from backend.models import EvalResult

    result = db.query(EvalResult).filter(
        EvalResult.output_hash == cache_key
    ).first()

    if result:
        logger.debug(f"Cache hit for key {cache_key[:12]}...")
    return result


def count_cache_hits(db: Session, model_id: str, system_prompt: str, input_texts: list[str]) -> int:
    """
    Count how many of the given inputs would be cache hits.
    Used by the quota estimator to predict API call count.
    """
    from backend.models import EvalResult

    hits = 0
    for input_text in input_texts:
        key = make_cache_key(model_id, system_prompt, input_text)
        exists = db.query(EvalResult.id).filter(
            EvalResult.output_hash == key
        ).first()
        if exists:
            hits += 1

    return hits
