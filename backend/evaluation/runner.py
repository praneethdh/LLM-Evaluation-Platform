"""
Evaluation runner — the core orchestrator.
Runs test suites through models, scores with Gemini judge,
computes metrics, handles caching and rate limiting.

Runs in a background thread to avoid HTTP timeouts.
"""

import logging
import traceback
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.database import SessionLocal
from backend.models import TestSuite, TestCase, EvalRun, EvalResult
from backend.providers import get_provider, JUDGE_PROVIDER
from backend.evaluation.cache import make_cache_key, check_cache
from backend.evaluation.metrics import rouge_l
from backend.evaluation.similarity import compute_similarity

logger = logging.getLogger(__name__)


def run_evaluation(run_id: int):
    """
    Execute a full evaluation run. Called in a background thread.

    Pipeline per test case:
    1. Check cache → if hit, reuse output (skip model call)
    2. If miss → call target model, measure latency
    3. Send (input, expected, actual) to Gemini judge
    4. Compute ROUGE-L locally
    5. Compute semantic similarity (sentence-transformers or difflib)
    6. Store result in DB
    7. Update run progress

    On completion: compute aggregate scores, update run status.
    """
    db = SessionLocal()

    try:
        _execute_run(db, run_id)
    except Exception as e:
        logger.error(f"Run {run_id} failed: {traceback.format_exc()}")
        try:
            run = db.query(EvalRun).get(run_id)
            if run:
                run.status = "failed"
                err_str = str(e)
                if any(token in err_str.lower() for token in ["429", "rate_limit", "rate limit", "quota", "resource_exhausted", "resource exhausted"]):
                    run.error_message = "Daily API limit reached — resets in 24 hours. Try again tomorrow."
                else:
                    run.error_message = err_str[:500]
                run.completed_at = datetime.now(timezone.utc)
                db.commit()
        except Exception:
            pass
    finally:
        db.close()


def _execute_run(db: Session, run_id: int):
    """Internal run execution logic."""

    run = db.query(EvalRun).get(run_id)
    if not run:
        raise ValueError(f"Run {run_id} not found")

    # Mark as running
    run.status = "running"
    db.commit()

    # Load test suite and cases
    suite = db.query(TestSuite).get(run.suite_id)
    if not suite:
        raise ValueError(f"Suite {run.suite_id} not found")

    test_cases = db.query(TestCase).filter(TestCase.suite_id == suite.id).all()
    if not test_cases:
        raise ValueError(f"Suite '{suite.name}' has no test cases")

    run.total_cases = len(test_cases)
    run.completed_cases = 0
    db.commit()

    # Initialize providers
    model_provider = get_provider(run.provider)
    judge = JUDGE_PROVIDER()

    cache_hits = 0
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0

    for i, case in enumerate(test_cases):
        try:
            result = _evaluate_single_case(
                db=db,
                run=run,
                case=case,
                model_provider=model_provider,
                judge=judge,
            )

            if result.from_cache:
                cache_hits += 1

            total_input_tokens += result.input_tokens
            total_output_tokens += result.output_tokens
            total_cost += model_provider.estimate_cost(
                result.input_tokens, result.output_tokens, run.model_id
            )

        except Exception as e:
            logger.error(f"Case {case.id} failed: {e}")
            err_str = str(e)
            if any(token in err_str.lower() for token in ["429", "rate_limit", "rate limit", "quota", "resource_exhausted", "resource exhausted"]):
                friendly_error = "Daily API limit reached — resets in 24 hours. Try again tomorrow."
            else:
                friendly_error = f"[ERROR] {err_str[:300]}"
            
            # Store a failed result rather than crashing the whole run
            failed_result = EvalResult(
                run_id=run.id,
                case_id=case.id,
                actual_output=friendly_error,
                latency_ms=0,
                judge_reasoning=f"Evaluation failed: {friendly_error}",
                output_hash=make_cache_key(run.model_id, run.system_prompt, case.input_text),
            )
            db.add(failed_result)

        # Update progress
        run.completed_cases = i + 1
        db.commit()

    # Compute aggregates
    _compute_aggregates(db, run)
    run.cache_hits = cache_hits
    run.total_input_tokens = total_input_tokens
    run.total_output_tokens = total_output_tokens
    run.estimated_cost_usd = round(total_cost, 6)
    run.status = "completed"
    run.completed_at = datetime.now(timezone.utc)
    db.commit()

    logger.info(f"Run {run_id} completed: {len(test_cases)} cases, {cache_hits} cache hits")


def _evaluate_single_case(
    db: Session,
    run: EvalRun,
    case: TestCase,
    model_provider,
    judge,
) -> EvalResult:
    """Evaluate a single test case — handles caching, model call, judging, metrics."""

    cache_key = make_cache_key(run.model_id, run.system_prompt, case.input_text)

    # Check cache
    cached = check_cache(db, cache_key)
    from_cache = False
    actual_output = ""
    latency_ms = 0.0
    input_tokens = 0
    output_tokens = 0

    if cached:
        # Cache hit — reuse model output, skip API call
        actual_output = cached.actual_output
        latency_ms = cached.latency_ms
        input_tokens = cached.input_tokens
        output_tokens = cached.output_tokens
        from_cache = True
        logger.debug(f"Cache hit for case {case.id}")
    else:
        # Cache miss — call the model
        gen_result = model_provider.generate(
            prompt=case.input_text,
            system_prompt=run.system_prompt,
            model_id=run.model_id,
        )
        actual_output = gen_result.text
        latency_ms = gen_result.latency_ms
        input_tokens = gen_result.input_tokens
        output_tokens = gen_result.output_tokens

    # Always re-run the judge (judging criteria might have changed)
    scores = judge.judge(
        input_text=case.input_text,
        expected_output=case.expected_output,
        actual_output=actual_output,
    )

    # Compute ROUGE-L (always available, pure Python)
    rouge_score = 0.0
    if case.expected_output:
        rouge_score = rouge_l(case.expected_output, actual_output)

    # Compute semantic similarity (sentence-transformers or difflib fallback)
    sim_score = None
    sim_method = None
    if case.expected_output:
        sim_score, sim_method = compute_similarity(case.expected_output, actual_output)

    # Store result
    result = EvalResult(
        run_id=run.id,
        case_id=case.id,
        actual_output=actual_output,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        from_cache=from_cache,
        correctness=scores.get("correctness"),
        relevance=scores.get("relevance"),
        coherence=scores.get("coherence"),
        tone=scores.get("tone"),
        hallucination_resistance=scores.get("hallucination_resistance"),
        rouge_l=rouge_score,
        semantic_similarity=sim_score,
        similarity_method=sim_method,
        judge_reasoning=scores.get("reasoning", ""),
        output_hash=cache_key,
    )
    db.add(result)
    db.commit()

    return result


def _compute_aggregates(db: Session, run: EvalRun):
    """Compute average scores across all results for a run."""
    results = db.query(EvalResult).filter(EvalResult.run_id == run.id).all()

    if not results:
        return

    def safe_avg(values):
        valid = [v for v in values if v is not None]
        return round(sum(valid) / len(valid), 2) if valid else None

    run.avg_correctness = safe_avg([r.correctness for r in results])
    run.avg_relevance = safe_avg([r.relevance for r in results])
    run.avg_coherence = safe_avg([r.coherence for r in results])
    run.avg_tone = safe_avg([r.tone for r in results])
    run.avg_hallucination_resistance = safe_avg([r.hallucination_resistance for r in results])
    run.avg_rouge_l = safe_avg([r.rouge_l for r in results])
    run.avg_similarity = safe_avg([r.semantic_similarity for r in results])
    run.avg_latency_ms = safe_avg([r.latency_ms for r in results])
