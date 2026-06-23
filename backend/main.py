"""
EvalForge — FastAPI application.
All API routes + static file serving for the frontend.
Eval runs execute in background threads to avoid HTTP timeouts.
"""

import os
import logging
import threading

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from dotenv import load_dotenv

# Load environment variables BEFORE importing providers
load_dotenv()

from backend.database import get_db, init_db
from backend.models import TestSuite, TestCase, EvalRun, EvalResult
from backend.schemas import (
    TestSuiteCreate, TestSuiteUpdate, TestSuiteResponse, TestSuiteListItem,
    TestCaseCreate, TestCaseResponse,
    EvalRunCreate, EvalRunResponse, EvalRunListItem, RunProgress,
    EvalResultResponse,
    ComparisonResponse,
    QuotaEstimateRequest, QuotaEstimateResponse,
    ModelInfo, ProviderStatus, HealthResponse,
)
from backend.providers import get_provider, JUDGE_PROVIDER, PROVIDERS
from backend.evaluation.runner import run_evaluation
from backend.evaluation.comparator import compare_runs, check_regression_vs_previous
from backend.evaluation.cache import count_cache_hits

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize FastAPI
app = FastAPI(
    title="EvalForge",
    description="LLM Evaluation & Observability Platform",
    version="1.0.0",
)

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    """Initialize database on server start."""
    init_db()
    logger.info("EvalForge started — database initialized")


# ═══════════════════════════════════════════════════════════════
# TEST SUITE ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/api/suites", response_model=TestSuiteResponse)
def create_suite(data: TestSuiteCreate, db: Session = Depends(get_db)):
    """Create a test suite with optional inline test cases."""
    # Check for duplicate name
    existing = db.query(TestSuite).filter(TestSuite.name == data.name).first()
    if existing:
        raise HTTPException(400, f"Suite '{data.name}' already exists")

    suite = TestSuite(name=data.name, description=data.description)
    db.add(suite)
    db.flush()  # Get the suite ID

    for tc in data.test_cases:
        case = TestCase(
            suite_id=suite.id,
            input_text=tc.input_text,
            expected_output=tc.expected_output,
            tags=tc.tags,
        )
        db.add(case)

    db.commit()
    db.refresh(suite)

    return _suite_to_response(suite)


@app.get("/api/suites", response_model=list[TestSuiteListItem])
def list_suites(db: Session = Depends(get_db)):
    """List all test suites with case counts."""
    suites = db.query(TestSuite).order_by(TestSuite.created_at.desc()).all()
    return [
        TestSuiteListItem(
            id=s.id,
            name=s.name,
            description=s.description,
            case_count=len(s.test_cases),
            created_at=s.created_at,
        )
        for s in suites
    ]


@app.get("/api/suites/{suite_id}", response_model=TestSuiteResponse)
def get_suite(suite_id: int, db: Session = Depends(get_db)):
    """Get a test suite with all its test cases."""
    suite = db.query(TestSuite).get(suite_id)
    if not suite:
        raise HTTPException(404, "Suite not found")
    return _suite_to_response(suite)


@app.put("/api/suites/{suite_id}", response_model=TestSuiteResponse)
def update_suite(suite_id: int, data: TestSuiteUpdate, db: Session = Depends(get_db)):
    """Update suite name/description."""
    suite = db.query(TestSuite).get(suite_id)
    if not suite:
        raise HTTPException(404, "Suite not found")

    if data.name is not None:
        suite.name = data.name
    if data.description is not None:
        suite.description = data.description

    db.commit()
    db.refresh(suite)
    return _suite_to_response(suite)


@app.delete("/api/suites/{suite_id}")
def delete_suite(suite_id: int, db: Session = Depends(get_db)):
    """Delete a suite and all associated cases, runs, and results."""
    suite = db.query(TestSuite).get(suite_id)
    if not suite:
        raise HTTPException(404, "Suite not found")

    db.delete(suite)
    db.commit()
    return {"status": "deleted", "id": suite_id}


# ── Test Case sub-endpoints ────────────────────────────────

@app.post("/api/suites/{suite_id}/cases", response_model=TestCaseResponse)
def add_test_case(suite_id: int, data: TestCaseCreate, db: Session = Depends(get_db)):
    """Add a single test case to a suite."""
    suite = db.query(TestSuite).get(suite_id)
    if not suite:
        raise HTTPException(404, "Suite not found")

    case = TestCase(
        suite_id=suite_id,
        input_text=data.input_text,
        expected_output=data.expected_output,
        tags=data.tags,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


@app.delete("/api/cases/{case_id}")
def delete_test_case(case_id: int, db: Session = Depends(get_db)):
    """Delete a single test case."""
    case = db.query(TestCase).get(case_id)
    if not case:
        raise HTTPException(404, "Test case not found")

    db.delete(case)
    db.commit()
    return {"status": "deleted", "id": case_id}


# ═══════════════════════════════════════════════════════════════
# EVALUATION RUN ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/api/runs", response_model=RunProgress)
def start_run(data: EvalRunCreate, db: Session = Depends(get_db)):
    """
    Start an evaluation run. Returns immediately with a run ID.
    The actual evaluation runs in a background thread.
    """
    # Validate suite exists
    suite = db.query(TestSuite).get(data.suite_id)
    if not suite:
        raise HTTPException(404, "Suite not found")

    if not suite.test_cases:
        raise HTTPException(400, "Suite has no test cases")

    # Validate provider
    try:
        provider = get_provider(data.provider)
    except KeyError as e:
        raise HTTPException(400, str(e))

    if not provider.is_configured():
        raise HTTPException(400, f"Provider '{data.provider}' API key not configured")

    # Create the run record
    run = EvalRun(
        suite_id=data.suite_id,
        provider=data.provider,
        model_id=data.model_id,
        system_prompt=data.system_prompt,
        status="pending",
        total_cases=len(suite.test_cases),
        completed_cases=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    # Launch background thread
    thread = threading.Thread(
        target=run_evaluation,
        args=(run.id,),
        daemon=True,
        name=f"eval-run-{run.id}",
    )
    thread.start()
    logger.info(f"Started eval run {run.id} in background thread")

    return RunProgress(
        id=run.id,
        status="pending",
        total_cases=run.total_cases,
        completed_cases=0,
        error_message=None,
    )


@app.get("/api/runs", response_model=list[EvalRunListItem])
def list_runs(
    suite_id: int | None = Query(None),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """List all runs, optionally filtered by suite or status."""
    query = db.query(EvalRun).order_by(EvalRun.created_at.desc())

    if suite_id is not None:
        query = query.filter(EvalRun.suite_id == suite_id)
    if status is not None:
        query = query.filter(EvalRun.status == status)

    runs = query.all()
    result = []
    for r in runs:
        suite = db.query(TestSuite).get(r.suite_id)
        result.append(EvalRunListItem(
            id=r.id,
            suite_id=r.suite_id,
            suite_name=suite.name if suite else "Deleted Suite",
            provider=r.provider,
            model_id=r.model_id,
            status=r.status,
            created_at=r.created_at,
            completed_at=r.completed_at,
            total_cases=r.total_cases,
            completed_cases=r.completed_cases,
            avg_correctness=r.avg_correctness,
            avg_relevance=r.avg_relevance,
            avg_coherence=r.avg_coherence,
            avg_tone=r.avg_tone,
            avg_hallucination_resistance=r.avg_hallucination_resistance,
            avg_rouge_l=r.avg_rouge_l,
            avg_similarity=r.avg_similarity,
            avg_latency_ms=r.avg_latency_ms,
            estimated_cost_usd=r.estimated_cost_usd,
            cache_hits=r.cache_hits,
        ))
    return result


@app.get("/api/runs/{run_id}", response_model=EvalRunResponse)
def get_run(run_id: int, db: Session = Depends(get_db)):
    """Get a run with all its per-case results."""
    run = db.query(EvalRun).get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    results = db.query(EvalResult).filter(EvalResult.run_id == run.id).all()

    result_responses = []
    for r in results:
        case = db.query(TestCase).get(r.case_id)
        result_responses.append(EvalResultResponse(
            id=r.id,
            case_id=r.case_id,
            input_text=case.input_text if case else "",
            expected_output=case.expected_output if case else "",
            actual_output=r.actual_output,
            latency_ms=r.latency_ms,
            input_tokens=r.input_tokens,
            output_tokens=r.output_tokens,
            from_cache=r.from_cache,
            correctness=r.correctness,
            relevance=r.relevance,
            coherence=r.coherence,
            tone=r.tone,
            hallucination_resistance=r.hallucination_resistance,
            rouge_l=r.rouge_l,
            semantic_similarity=r.semantic_similarity,
            similarity_method=r.similarity_method,
            judge_reasoning=r.judge_reasoning,
        ))

    return EvalRunResponse(
        id=run.id,
        suite_id=run.suite_id,
        provider=run.provider,
        model_id=run.model_id,
        system_prompt=run.system_prompt,
        status=run.status,
        created_at=run.created_at,
        completed_at=run.completed_at,
        total_cases=run.total_cases,
        completed_cases=run.completed_cases,
        avg_correctness=run.avg_correctness,
        avg_relevance=run.avg_relevance,
        avg_coherence=run.avg_coherence,
        avg_tone=run.avg_tone,
        avg_hallucination_resistance=run.avg_hallucination_resistance,
        avg_rouge_l=run.avg_rouge_l,
        avg_similarity=run.avg_similarity,
        avg_latency_ms=run.avg_latency_ms,
        total_input_tokens=run.total_input_tokens,
        total_output_tokens=run.total_output_tokens,
        estimated_cost_usd=run.estimated_cost_usd,
        cache_hits=run.cache_hits,
        error_message=run.error_message,
        results=result_responses,
    )


@app.get("/api/runs/{run_id}/progress", response_model=RunProgress)
def get_run_progress(run_id: int, db: Session = Depends(get_db)):
    """Get run progress — polled by frontend during evaluation."""
    run = db.query(EvalRun).get(run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    return RunProgress(
        id=run.id,
        status=run.status,
        total_cases=run.total_cases,
        completed_cases=run.completed_cases,
        error_message=run.error_message,
    )


# ═══════════════════════════════════════════════════════════════
# COMPARISON & REGRESSION ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.get("/api/compare", response_model=ComparisonResponse)
def compare(
    run_a: int = Query(..., description="Baseline run ID"),
    run_b: int = Query(..., description="New run ID"),
    db: Session = Depends(get_db),
):
    """Compare two evaluation runs side by side."""
    try:
        return compare_runs(db, run_a, run_b)
    except ValueError as e:
        raise HTTPException(400, str(e))


@app.get("/api/runs/{run_id}/regression", response_model=ComparisonResponse | None)
def check_regression(run_id: int, db: Session = Depends(get_db)):
    """Check if a run regressed vs. the most recent prior run on the same suite."""
    result = check_regression_vs_previous(db, run_id)
    if result is None:
        raise HTTPException(404, "No previous run found for comparison")
    return result


# ═══════════════════════════════════════════════════════════════
# QUOTA & SYSTEM ENDPOINTS
# ═══════════════════════════════════════════════════════════════

@app.post("/api/quota/estimate", response_model=QuotaEstimateResponse)
def estimate_quota(data: QuotaEstimateRequest, db: Session = Depends(get_db)):
    """Estimate API calls needed before starting a run."""
    suite = db.query(TestSuite).get(data.suite_id)
    if not suite:
        raise HTTPException(404, "Suite not found")

    cases = db.query(TestCase).filter(TestCase.suite_id == data.suite_id).all()
    total_cases = len(cases)

    # Count cache hits
    input_texts = [c.input_text for c in cases]
    cache_hits = count_cache_hits(db, data.model_id, data.system_prompt, input_texts)

    model_calls = total_cases - cache_hits
    judge_calls = total_cases  # Always re-judge

    # Estimate time based on rate limits
    provider_delay = 3.0 if data.provider == "openrouter" else 2.1
    judge_delay = 4.1
    estimated_time = int((model_calls * provider_delay) + (judge_calls * judge_delay))

    # Estimate cost
    try:
        provider = get_provider(data.provider)
        avg_input = 500  # rough estimate tokens per call
        avg_output = 300
        cost = provider.estimate_cost(
            avg_input * model_calls, avg_output * model_calls, data.model_id
        )
    except Exception:
        cost = 0.0

    return QuotaEstimateResponse(
        total_cases=total_cases,
        cache_hits=cache_hits,
        model_calls_needed=model_calls,
        judge_calls_needed=judge_calls,
        total_api_calls=model_calls + judge_calls,
        estimated_time_seconds=estimated_time,
        estimated_cost_usd=cost,
    )


@app.get("/api/models", response_model=list[ModelInfo])
def list_models():
    """List all available models across all providers."""
    models = []
    for name, cls in PROVIDERS.items():
        try:
            provider = cls()
            for m in provider.get_models():
                models.append(ModelInfo(
                    provider=m.provider,
                    model_id=m.model_id,
                    display_name=m.display_name,
                    description=m.description,
                ))
        except Exception:
            continue
    return models


@app.get("/api/health", response_model=HealthResponse)
def health_check():
    """Health check with provider connectivity status."""
    providers_status = []

    # Check evaluated model providers
    for name, cls in PROVIDERS.items():
        try:
            provider = cls()
            if not provider.is_configured():
                status = "not_configured"
            else:
                status = "ok"  # Skip actual health check to avoid rate limit usage
        except Exception as e:
            status = f"error: {str(e)[:100]}"

        providers_status.append(ProviderStatus(
            name=name,
            configured=status != "not_configured",
            status=status,
        ))

    # Check Gemini judge
    try:
        judge = JUDGE_PROVIDER()
        if not judge.is_configured():
            judge_status = "not_configured"
        else:
            judge_status = "ok"
    except Exception as e:
        judge_status = f"error: {str(e)[:100]}"

    providers_status.append(ProviderStatus(
        name="gemini (judge)",
        configured=judge_status != "not_configured",
        status=judge_status,
    ))

    all_ok = all(p.status == "ok" for p in providers_status)
    return HealthResponse(
        status="ok" if all_ok else "degraded",
        providers=providers_status,
    )


# ═══════════════════════════════════════════════════════════════
# STATIC FILE SERVING (Frontend)
# ═══════════════════════════════════════════════════════════════

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "frontend")

# Mount static directories
if os.path.isdir(os.path.join(FRONTEND_DIR, "css")):
    app.mount("/css", StaticFiles(directory=os.path.join(FRONTEND_DIR, "css")), name="css")
if os.path.isdir(os.path.join(FRONTEND_DIR, "js")):
    app.mount("/js", StaticFiles(directory=os.path.join(FRONTEND_DIR, "js")), name="js")


@app.get("/")
def serve_frontend():
    """Serve the SPA index.html."""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found. Place index.html in /frontend/"}


# ═══════════════════════════════════════════════════════════════

def _suite_to_response(suite: TestSuite) -> TestSuiteResponse:
    """Helper to convert a TestSuite ORM object to a response schema."""
    return TestSuiteResponse(
        id=suite.id,
        name=suite.name,
        description=suite.description,
        created_at=suite.created_at,
        updated_at=suite.updated_at,
        case_count=len(suite.test_cases),
        test_cases=[
            TestCaseResponse(
                id=tc.id,
                suite_id=tc.suite_id,
                input_text=tc.input_text,
                expected_output=tc.expected_output,
                tags=tc.tags,
                created_at=tc.created_at,
            )
            for tc in suite.test_cases
        ],
    )


# ═══════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
