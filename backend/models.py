"""
SQLAlchemy ORM models for EvalForge.
Four tables: TestSuite, TestCase, EvalRun, EvalResult.
"""

from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timezone

from backend.database import Base


class TestSuite(Base):
    __tablename__ = "test_suites"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))

    test_cases = relationship("TestCase", back_populates="suite", cascade="all, delete-orphan")
    eval_runs = relationship("EvalRun", back_populates="suite", cascade="all, delete-orphan")


class TestCase(Base):
    __tablename__ = "test_cases"

    id = Column(Integer, primary_key=True, autoincrement=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False)
    input_text = Column(Text, nullable=False)
    expected_output = Column(Text, default="")  # Optional — some evals are open-ended
    tags = Column(String(500), default="")  # Comma-separated labels
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    suite = relationship("TestSuite", back_populates="test_cases")
    results = relationship("EvalResult", back_populates="test_case", cascade="all, delete-orphan")


class EvalRun(Base):
    __tablename__ = "eval_runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    suite_id = Column(Integer, ForeignKey("test_suites.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)  # "groq" | "openrouter"
    model_id = Column(String(200), nullable=False)  # e.g., "llama-3.3-70b-versatile"
    system_prompt = Column(Text, default="")  # Snapshot of prompt used for this run
    status = Column(String(20), default="pending")  # pending | running | completed | failed
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)

    # Progress tracking
    total_cases = Column(Integer, default=0)
    completed_cases = Column(Integer, default=0)

    # Aggregate scores (computed on completion)
    avg_correctness = Column(Float, nullable=True)
    avg_relevance = Column(Float, nullable=True)
    avg_coherence = Column(Float, nullable=True)
    avg_tone = Column(Float, nullable=True)
    avg_hallucination_resistance = Column(Float, nullable=True)
    avg_rouge_l = Column(Float, nullable=True)
    avg_similarity = Column(Float, nullable=True)  # null if sentence-transformers unavailable

    # Performance metrics
    avg_latency_ms = Column(Float, nullable=True)
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    estimated_cost_usd = Column(Float, default=0.0)

    # Cache stats
    cache_hits = Column(Integer, default=0)

    # Error info
    error_message = Column(Text, nullable=True)

    suite = relationship("TestSuite", back_populates="eval_runs")
    results = relationship("EvalResult", back_populates="run", cascade="all, delete-orphan")


class EvalResult(Base):
    __tablename__ = "eval_results"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(Integer, ForeignKey("eval_runs.id", ondelete="CASCADE"), nullable=False)
    case_id = Column(Integer, ForeignKey("test_cases.id", ondelete="CASCADE"), nullable=False)

    # Model output
    actual_output = Column(Text, default="")
    latency_ms = Column(Float, default=0.0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    from_cache = Column(Boolean, default=False)

    # LLM Judge scores (1-10 scale)
    correctness = Column(Float, nullable=True)
    relevance = Column(Float, nullable=True)
    coherence = Column(Float, nullable=True)
    tone = Column(Float, nullable=True)
    hallucination_resistance = Column(Float, nullable=True)

    # Automated metrics (0-1 scale)
    rouge_l = Column(Float, nullable=True)
    semantic_similarity = Column(Float, nullable=True)
    similarity_method = Column(String(50), nullable=True)  # "sentence-transformers" | "difflib"

    # Judge explanation
    judge_reasoning = Column(Text, default="")

    # Cache key for lookup
    output_hash = Column(String(64), nullable=True, index=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    run = relationship("EvalRun", back_populates="results")
    test_case = relationship("TestCase", back_populates="results")
