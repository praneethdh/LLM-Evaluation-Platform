"""
Comparator — side-by-side comparison of two evaluation runs
with delta scoring and regression detection.
"""

import logging
from sqlalchemy.orm import Session

from backend.models import EvalRun, EvalResult, TestCase
from backend.schemas import (
    ComparisonResponse,
    DimensionDelta,
    CaseComparison,
)

logger = logging.getLogger(__name__)

# Regression thresholds
DIMENSION_REGRESSION_THRESHOLD = 10.0  # % drop in any single dimension
OVERALL_REGRESSION_THRESHOLD = 5.0  # % drop in average across all dimensions


def compare_runs(db: Session, run_a_id: int, run_b_id: int) -> ComparisonResponse:
    """
    Compare two evaluation runs and detect regressions.

    Convention: Run A is the baseline (older), Run B is the new version.
    Positive delta = improvement, negative delta = regression.
    """
    run_a = db.query(EvalRun).get(run_a_id)
    run_b = db.query(EvalRun).get(run_b_id)

    if not run_a or not run_b:
        raise ValueError(f"Run not found: A={run_a_id}, B={run_b_id}")

    if run_a.status != "completed" or run_b.status != "completed":
        raise ValueError("Both runs must be completed before comparison")

    # Dimension-level comparison
    dimensions = _compare_dimensions(run_a, run_b)

    # Per-case comparison
    case_comparisons = _compare_cases(db, run_a, run_b)

    # Regression detection
    has_regression, regression_summary = _detect_regression(dimensions)

    return ComparisonResponse(
        run_a_id=run_a.id,
        run_b_id=run_b.id,
        run_a_model=f"{run_a.provider}/{run_a.model_id}",
        run_b_model=f"{run_b.provider}/{run_b.model_id}",
        run_a_prompt=run_a.system_prompt or "(no prompt)",
        run_b_prompt=run_b.system_prompt or "(no prompt)",
        dimensions=dimensions,
        case_comparisons=case_comparisons,
        has_regression=has_regression,
        regression_summary=regression_summary,
    )


def _compare_dimensions(run_a: EvalRun, run_b: EvalRun) -> list[DimensionDelta]:
    """Compare aggregate scores across all scoring dimensions."""
    dim_pairs = [
        ("correctness", run_a.avg_correctness, run_b.avg_correctness),
        ("relevance", run_a.avg_relevance, run_b.avg_relevance),
        ("coherence", run_a.avg_coherence, run_b.avg_coherence),
        ("tone", run_a.avg_tone, run_b.avg_tone),
        ("hallucination_resistance", run_a.avg_hallucination_resistance, run_b.avg_hallucination_resistance),
        ("rouge_l", run_a.avg_rouge_l, run_b.avg_rouge_l),
        ("similarity", run_a.avg_similarity, run_b.avg_similarity),
        ("latency_ms", run_a.avg_latency_ms, run_b.avg_latency_ms),
    ]

    dimensions = []
    for name, score_a, score_b in dim_pairs:
        delta = None
        delta_pct = None
        is_regression = False

        if score_a is not None and score_b is not None:
            delta = round(score_b - score_a, 2)

            if score_a != 0:
                delta_pct = round((delta / score_a) * 100, 1)

            # For latency, LOWER is better (regression = increase)
            if name == "latency_ms":
                is_regression = delta_pct is not None and delta_pct > DIMENSION_REGRESSION_THRESHOLD
            else:
                is_regression = delta_pct is not None and delta_pct < -DIMENSION_REGRESSION_THRESHOLD

        dimensions.append(DimensionDelta(
            dimension=name,
            run_a_score=score_a,
            run_b_score=score_b,
            delta=delta,
            delta_pct=delta_pct,
            is_regression=is_regression,
        ))

    return dimensions


def _compare_cases(db: Session, run_a: EvalRun, run_b: EvalRun) -> list[CaseComparison]:
    """Compare results per test case between two runs."""
    results_a = {r.case_id: r for r in db.query(EvalResult).filter(EvalResult.run_id == run_a.id).all()}
    results_b = {r.case_id: r for r in db.query(EvalResult).filter(EvalResult.run_id == run_b.id).all()}

    # Get all case IDs from both runs
    all_case_ids = set(results_a.keys()) | set(results_b.keys())
    comparisons = []

    for case_id in sorted(all_case_ids):
        case = db.query(TestCase).get(case_id)
        if not case:
            continue

        r_a = results_a.get(case_id)
        r_b = results_b.get(case_id)

        avg_a = _result_avg_score(r_a) if r_a else None
        avg_b = _result_avg_score(r_b) if r_b else None
        delta = round(avg_b - avg_a, 2) if avg_a is not None and avg_b is not None else None

        comparisons.append(CaseComparison(
            case_id=case_id,
            input_text=case.input_text[:200],
            run_a_output=(r_a.actual_output[:200] if r_a else "N/A"),
            run_b_output=(r_b.actual_output[:200] if r_b else "N/A"),
            run_a_avg_score=avg_a,
            run_b_avg_score=avg_b,
            delta=delta,
        ))

    return comparisons


def _result_avg_score(result: EvalResult) -> float:
    """Average of all judge dimensions for a single result."""
    scores = [
        result.correctness,
        result.relevance,
        result.coherence,
        result.tone,
        result.hallucination_resistance,
    ]
    valid = [s for s in scores if s is not None]
    return round(sum(valid) / len(valid), 2) if valid else 0.0


def _detect_regression(dimensions: list[DimensionDelta]) -> tuple[bool, str]:
    """
    Check if any dimension regressed significantly.

    Regression if:
    - Any single dimension drops by >10%
    - OR the average of judge dimensions drops by >5%
    """
    regressions = [d for d in dimensions if d.is_regression]
    if regressions:
        names = [d.dimension for d in regressions]
        return True, f"Regression detected in: {', '.join(names)}"

    # Check overall average
    judge_dims = [d for d in dimensions if d.dimension not in ("rouge_l", "similarity", "latency_ms")]
    deltas = [d.delta_pct for d in judge_dims if d.delta_pct is not None]

    if deltas:
        avg_delta = sum(deltas) / len(deltas)
        if avg_delta < -OVERALL_REGRESSION_THRESHOLD:
            return True, f"Overall regression: average score dropped by {abs(avg_delta):.1f}%"

    return False, "No regression detected"


def check_regression_vs_previous(db: Session, run_id: int) -> ComparisonResponse | None:
    """
    Compare a run against the most recent prior completed run
    on the same test suite. Returns None if no prior run exists.
    """
    run = db.query(EvalRun).get(run_id)
    if not run:
        return None

    # Find the most recent completed run on the same suite, before this one
    previous = (
        db.query(EvalRun)
        .filter(
            EvalRun.suite_id == run.suite_id,
            EvalRun.status == "completed",
            EvalRun.id < run.id,
        )
        .order_by(EvalRun.id.desc())
        .first()
    )

    if not previous:
        return None

    return compare_runs(db, previous.id, run.id)
