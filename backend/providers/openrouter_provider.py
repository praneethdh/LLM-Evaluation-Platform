"""
OpenRouter provider — access 20+ free models through OpenAI-compatible API.
Free tier: 200 req/day per model, 20 RPM.
"""

import os
import time
import logging

from backend.providers.base import LLMProvider, GenerateResult, ModelInfo, RateLimiter

logger = logging.getLogger(__name__)

OPENROUTER_MODELS = [
    ModelInfo(
        provider="openrouter",
        model_id="qwen/qwen3-coder:free",
        display_name="Qwen 3 Coder (Free)",
        description="Alibaba's coding-optimized model — strong for code generation tasks",
    ),
    ModelInfo(
        provider="openrouter",
        model_id="openrouter/free",
        display_name="OpenRouter Auto-Free Router",
        description="Dynamically routes to an active free model on OpenRouter",
    ),
    ModelInfo(
        provider="openrouter",
        model_id="meta-llama/llama-3.3-70b-instruct:free",
        display_name="Llama 3.3 70B Instruct (Free)",
        description="Meta's 70B instruct model via OpenRouter — compare with Groq's version",
    ),
    ModelInfo(
        provider="openrouter",
        model_id="mistralai/mistral-small-3.1-24b-instruct:free",
        display_name="Mistral Small 3.1 24B (Free)",
        description="Mistral's efficient 24B model — good balance of speed and quality",
    ),
]

# Estimated pricing if user were paying (for cost estimation display)
OPENROUTER_PRICING = {
    "default": {"input": 0.15, "output": 0.60},  # per 1M tokens, rough average
}


class OpenRouterProvider(LLMProvider):
    """OpenRouter provider using OpenAI-compatible SDK."""

    def __init__(self):
        self.api_key = os.getenv("OPENROUTER_API_KEY", "")
        self.base_url = "https://openrouter.ai/api/v1"
        self.rate_limiter = RateLimiter.get("openrouter", min_delay_seconds=3.1)  # 20 RPM → ~3s

    def generate(self, prompt: str, system_prompt: str, model_id: str) -> GenerateResult:
        from openai import OpenAI

        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment")

        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            default_headers={
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "EvalForge",
            },
        )

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
                if "429" in error_str or "rate" in error_str.lower():
                    logger.warning(f"OpenRouter rate limit hit, attempt {attempt + 1}/{max_retries}")
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
        return OPENROUTER_MODELS

    def estimate_cost(self, input_tokens: int, output_tokens: int, model_id: str) -> float:
        pricing = OPENROUTER_PRICING.get(model_id, OPENROUTER_PRICING["default"])
        cost = (input_tokens / 1_000_000 * pricing["input"]) + \
               (output_tokens / 1_000_000 * pricing["output"])
        return round(cost, 6)

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key != "your_openrouter_api_key_here")

    def check_health(self) -> str:
        if not self.is_configured():
            return "not_configured"
        try:
            from openai import OpenAI
            client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
                default_headers={
                    "HTTP-Referer": "http://localhost:8000",
                    "X-Title": "EvalForge",
                },
            )
            client.chat.completions.create(
                model="qwen/qwen3-coder:free",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5,
            )
            return "ok"
        except Exception as e:
            return f"error: {str(e)[:100]}"
