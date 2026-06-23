"""
Pydantic schemas for API request/response validation.
"""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


# ── Test Cases ──────────────────────────────────────────────

class TestCaseCreate(BaseModel):
    input_text: str = Field(..., min_length=1)
    expected_output: str = ""
    tags: str = ""


class TestCaseResponse(BaseModel):
    id: int
    suite_id: int
    input_text: str
    expected_output: str
    tags: str
    created_at: datetime

    class Config:
        from_attributes = True


# ── Test Suites ─────────────────────────────────────────────

class TestSuiteCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""
    test_cases: list[TestCaseCreate] = []


class TestSuiteUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class TestSuiteResponse(BaseModel):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime
    case_count: int = 0
    test_cases: list[TestCaseResponse] = []

    class Config:
        from_attributes = True


class TestSuiteListItem(BaseModel):
    id: int
    name: str
    description: str
    case_count: int
    created_at: datetime

    class Config:
        from_attributes = True


# ── Eval Results ────────────────────────────────────────────

class EvalResultResponse(BaseModel):
    id: int
    case_id: int
    input_text: str = ""
    expected_output: str = ""
    actual_output: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    from_cache: bool
    correctness: Optional[float]
    relevance: Optional[float]
    coherence: Optional[float]
    tone: Optional[float]
    hallucination_resistance: Optional[float]
    rouge_l: Optional[float]
    semantic_similarity: Optional[float]
    similarity_method: Optional[str]
    judge_reasoning: str

    class Config:
        from_attributes = True


# ── Eval Runs ───────────────────────────────────────────────

class EvalRunCreate(BaseModel):
    suite_id: int
    provider: str = Field(..., pattern=r"^(groq|openrouter)$")
    model_id: str = Field(..., min_length=1)
    system_prompt: str = ""


class EvalRunResponse(BaseModel):
    id: int
    suite_id: int
    provider: str
    model_id: str
    system_prompt: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    total_cases: int
    completed_cases: int
    avg_correctness: Optional[float]
    avg_relevance: Optional[float]
    avg_coherence: Optional[float]
    avg_tone: Optional[float]
    avg_hallucination_resistance: Optional[float]
    avg_rouge_l: Optional[float]
    avg_similarity: Optional[float]
    avg_latency_ms: Optional[float]
    total_input_tokens: int
    total_output_tokens: int
    estimated_cost_usd: float
    cache_hits: int
    error_message: Optional[str]
    results: list[EvalResultResponse] = []

    class Config:
        from_attributes = True


class EvalRunListItem(BaseModel):
    id: int
    suite_id: int
    suite_name: str = ""
    provider: str
    model_id: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime]
    total_cases: int
    completed_cases: int
    avg_correctness: Optional[float]
    avg_relevance: Optional[float]
    avg_coherence: Optional[float]
    avg_tone: Optional[float]
    avg_hallucination_resistance: Optional[float]
    avg_rouge_l: Optional[float]
    avg_similarity: Optional[float]
    avg_latency_ms: Optional[float]
    estimated_cost_usd: float
    cache_hits: int

    class Config:
        from_attributes = True


class RunProgress(BaseModel):
    id: int
    status: str
    total_cases: int
    completed_cases: int
    error_message: Optional[str]


# ── Comparison ──────────────────────────────────────────────

class DimensionDelta(BaseModel):
    dimension: str
    run_a_score: Optional[float]
    run_b_score: Optional[float]
    delta: Optional[float]  # b - a (positive = improvement)
    delta_pct: Optional[float]
    is_regression: bool = False


class CaseComparison(BaseModel):
    case_id: int
    input_text: str
    run_a_output: str
    run_b_output: str
    run_a_avg_score: Optional[float]
    run_b_avg_score: Optional[float]
    delta: Optional[float]


class ComparisonResponse(BaseModel):
    run_a_id: int
    run_b_id: int
    run_a_model: str
    run_b_model: str
    run_a_prompt: str
    run_b_prompt: str
    dimensions: list[DimensionDelta]
    case_comparisons: list[CaseComparison]
    has_regression: bool
    regression_summary: str


# ── Quota Estimate ──────────────────────────────────────────

class QuotaEstimateRequest(BaseModel):
    suite_id: int
    provider: str
    model_id: str
    system_prompt: str = ""


class QuotaEstimateResponse(BaseModel):
    total_cases: int
    cache_hits: int
    model_calls_needed: int
    judge_calls_needed: int
    total_api_calls: int
    estimated_time_seconds: int
    estimated_cost_usd: float


# ── Models & Health ─────────────────────────────────────────

class ModelInfo(BaseModel):
    provider: str
    model_id: str
    display_name: str
    description: str


class ProviderStatus(BaseModel):
    name: str
    configured: bool
    status: str  # "ok" | "error" | "not_configured"


class HealthResponse(BaseModel):
    status: str
    providers: list[ProviderStatus]
