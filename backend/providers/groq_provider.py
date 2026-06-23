"""
Groq provider — Llama 3.3 70B and Llama 3.1 8B via Groq's LPU inference.
Free tier: 14,400 req/day, 30 RPM.
"""

import os
import time
import logging

from backend.providers.base import LLMProvider, GenerateResult, ModelInfo, RateLimiter

logger = logging.getLogger(__name__)

# Groq paid-tier pricing (for cost estimation display)
GROQ_PRICING = {
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},  # per 1M tokens
    "llama-3.1-8b-instant": {"input": 0.05, "output": 0.08},
}

GROQ_MODELS = [
    ModelInfo(
        provider="groq",
        model_id="llama-3.3-70b-versatile",
        display_name="Llama 3.3 70B",
        description="Meta's flagship 70B model — best open-source quality, ~320 tok/s on Groq",
    ),
    ModelInfo(
        provider="groq",
        model_id="llama-3.1-8b-instant",
        display_name="Llama 3.1 8B",
        description="Lightweight 8B model — fast inference (~750 tok/s), good for speed comparisons",
    ),
]


class GroqProvider(LLMProvider):
    """Groq inference provider using official SDK."""

    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY", "")
        self.rate_limiter = RateLimiter.get("groq", min_delay_seconds=2.1)  # 30 RPM → ~2s

    def generate(self, prompt: str, system_prompt: str, model_id: str) -> GenerateResult:
        from groq import Groq

        if not self.api_key:
            raise ValueError("GROQ_API_KEY not set in environment")

        client = Groq(api_key=self.api_key)

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Rate limit before calling
        self.rate_limiter.wait()

        start = time.perf_counter()

        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = client.chat.completions.create(
                    model=model_id,
                    messages=messages,
                    temperature=0.7,
                    max_tokens=2048,
                )
                break
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "rate_limit" in error_str.lower():
                    logger.warning(f"Groq rate limit hit, attempt {attempt + 1}/{max_retries}")
                    self.rate_limiter.wait_with_backoff(attempt)
                    if attempt == max_retries - 1:
                        raise
                else:
                    raise

        elapsed_ms = (time.perf_counter() - start) * 1000

        text = response.choices[0].message.content or ""
        usage = response.usage
        input_tokens = usage.prompt_tokens if usage else 0
        output_tokens = usage.completion_tokens if usage else 0

        return GenerateResult(
            text=text,
            latency_ms=round(elapsed_ms, 2),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def get_models(self) -> list[ModelInfo]:
        return GROQ_MODELS

    def estimate_cost(self, input_tokens: int, output_tokens: int, model_id: str) -> float:
        pricing = GROQ_PRICING.get(model_id, {"input": 0.59, "output": 0.79})
        cost = (input_tokens / 1_000_000 * pricing["input"]) + \
               (output_tokens / 1_000_000 * pricing["output"])
        return round(cost, 6)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key != "your_groq_api_key_here")

    def check_health(self) -> str:
        if not self.is_configured():
            return "not_configured"
        try:
            from groq import Groq
            client = Groq(api_key=self.api_key)
            # Minimal call to verify connectivity
            client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return "ok"
        except Exception as e:
            return f"error: {str(e)[:100]}"
