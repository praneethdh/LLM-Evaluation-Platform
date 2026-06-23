"""
Provider registry — maps provider names to their implementation classes.
"""

from backend.providers.groq_provider import GroqProvider
from backend.providers.openrouter_provider import OpenRouterProvider
from backend.providers.gemini_provider import GeminiJudgeProvider

PROVIDERS = {
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
}

# Gemini is NOT in the provider map — it's the judge, not an evaluated model.
JUDGE_PROVIDER = GeminiJudgeProvider


def get_provider(name: str):
    """Get a provider class by name. Raises KeyError if not found."""
    if name not in PROVIDERS:
        raise KeyError(f"Unknown provider '{name}'. Available: {list(PROVIDERS.keys())}")
    return PROVIDERS[name]()
