"""
Abstract base for all LLM providers.
Defines the interface every provider must implement.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
import threading
import time


@dataclass
class GenerateResult:
    """Return type from a model generation call."""
    text: str
    latency_ms: float
    input_tokens: int
    output_tokens: int


@dataclass
class ModelInfo:
    """Metadata about an available model."""
    provider: str
    model_id: str
    display_name: str
    description: str


class RateLimiter:
    """
    Thread-safe per-provider rate limiter.
    Uses a global lock per provider so concurrent eval runs
    can't 429 each other by exceeding the same rate limit pool.
    """

    _instances: dict[str, "RateLimiter"] = {}
    _creation_lock = threading.Lock()

    def __init__(self, provider_name: str, min_delay_seconds: float):
        self.provider_name = provider_name
        self.min_delay = min_delay_seconds
        self._lock = threading.Lock()
        self._last_call_time = 0.0

    @classmethod
    def get(cls, provider_name: str, min_delay_seconds: float) -> "RateLimiter":
        """Get or create a singleton rate limiter for a provider."""
        with cls._creation_lock:
            if provider_name not in cls._instances:
                cls._instances[provider_name] = cls(provider_name, min_delay_seconds)
            return cls._instances[provider_name]

    def wait(self):
        """Block until it's safe to make the next API call."""
        with self._lock:
            now = time.time()
            elapsed = now - self._last_call_time
            if elapsed < self.min_delay:
                sleep_time = self.min_delay - elapsed
                time.sleep(sleep_time)
            self._last_call_time = time.time()

    def wait_with_backoff(self, attempt: int):
        """Exponential backoff for retries after a 429."""
        base_delay = 5.0
        max_delay = 60.0
        import random
        delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
        time.sleep(delay)


class LLMProvider(ABC):
    """Abstract base class for LLM inference providers."""

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str, model_id: str) -> GenerateResult:
        """
        Generate a response from the model.
        Must measure latency internally and return it in the result.
        """
        ...

    @abstractmethod
    def get_models(self) -> list[ModelInfo]:
        """Return list of available models for this provider."""
        ...

    @abstractmethod
    def estimate_cost(self, input_tokens: int, output_tokens: int, model_id: str) -> float:
        """Estimate USD cost based on paid-tier pricing (for display purposes)."""
        ...

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if API key is set for this provider."""
        ...

    @abstractmethod
    def check_health(self) -> str:
        """Quick connectivity check. Returns 'ok' or error message."""
        ...
