"""
Semantic similarity with graceful fallback chain:
  1. sentence-transformers (best, but requires 90MB download)
  2. difflib.SequenceMatcher (stdlib, zero download, always available)
Never crashes. Always returns a score.
"""

import logging
import difflib

logger = logging.getLogger(__name__)

# Lazy-loaded singleton — None until first use
_st_model = None
_st_available = None  # None = untested, True/False after first check


def _try_load_sentence_transformers():
    """Attempt to load sentence-transformers model. Caches result."""
    global _st_model, _st_available

    if _st_available is not None:
        return _st_available

    try:
        from sentence_transformers import SentenceTransformer
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
        _st_available = True
        logger.info("sentence-transformers loaded successfully (all-MiniLM-L6-v2)")
        return True
    except ImportError:
        _st_available = False
        logger.info("sentence-transformers not installed — falling back to difflib")
        return False
    except Exception as e:
        _st_available = False
        logger.warning(f"sentence-transformers failed to load: {e} — falling back to difflib")
        return False


def compute_similarity(expected: str, actual: str) -> tuple[float, str]:
    """
    Compute semantic similarity between expected and actual output.

    Returns:
        (score, method_used) where:
        - score: float 0.0-1.0
        - method_used: "sentence-transformers" or "difflib"
    """
    if not expected or not actual:
        return (0.0, "difflib")

    # Level 1: Try sentence-transformers (best quality)
    if _try_load_sentence_transformers():
        try:
            from sentence_transformers import util
            embeddings = _st_model.encode([expected, actual], convert_to_tensor=True)
            score = util.cos_sim(embeddings[0], embeddings[1]).item()
            # Clamp to 0-1 range (cosine sim can be slightly negative)
            score = max(0.0, min(1.0, score))
            return (round(score, 4), "sentence-transformers")
        except Exception as e:
            logger.warning(f"sentence-transformers scoring failed: {e}")

    # Level 2: difflib.SequenceMatcher (stdlib, always available)
    score = difflib.SequenceMatcher(None, expected.lower(), actual.lower()).ratio()
    return (round(score, 4), "difflib")
