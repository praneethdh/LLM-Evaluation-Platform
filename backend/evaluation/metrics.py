"""
Pure Python token-overlap metrics — zero external dependencies.
ROUGE-L: Longest Common Subsequence based metric.
"""


def _lcs_length(x: list[str], y: list[str]) -> int:
    """Compute length of Longest Common Subsequence between two token lists."""
    m, n = len(x), len(y)
    if m == 0 or n == 0:
        return 0

    # Space-optimized DP — only keep two rows
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)

    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if x[i - 1] == y[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = max(prev[j], curr[j - 1])
        prev, curr = curr, [0] * (n + 1)

    return prev[n]


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer."""
    import re
    return re.findall(r'\b\w+\b', text.lower())


def rouge_l(reference: str, hypothesis: str) -> float:
    """
    Compute ROUGE-L F1 score between reference and hypothesis.

    ROUGE-L uses LCS (Longest Common Subsequence) to measure
    how much of the reference appears in order within the hypothesis.

    Returns float 0.0 - 1.0
    """
    if not reference or not hypothesis:
        return 0.0

    ref_tokens = _tokenize(reference)
    hyp_tokens = _tokenize(hypothesis)

    if not ref_tokens or not hyp_tokens:
        return 0.0

    lcs = _lcs_length(ref_tokens, hyp_tokens)

    precision = lcs / len(hyp_tokens) if hyp_tokens else 0
    recall = lcs / len(ref_tokens) if ref_tokens else 0

    if precision + recall == 0:
        return 0.0

    # F1 score
    f1 = (2 * precision * recall) / (precision + recall)
    return round(f1, 4)
