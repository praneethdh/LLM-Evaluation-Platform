"""
Gemini provider — used EXCLUSIVELY as the LLM-as-Judge scorer.
This is NOT an evaluated model. It scores outputs from other models.
Uses the new google-genai SDK (not the legacy google-generativeai).
"""

import os
import re
import json
import time
import logging

from backend.providers.base import RateLimiter

logger = logging.getLogger(__name__)


class GeminiJudgeProvider:
    """
    Gemini 2.5 Flash as the LLM judge.
    Handles the #1 failure mode: Gemini wrapping JSON in markdown code fences.
    """

    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY", "")
        self.model_id = "gemini-2.5-flash"
        self.rate_limiter = RateLimiter.get("gemini_judge", min_delay_seconds=4.1)  # conservative

    def _extract_json(self, text: str) -> dict:
        """
        Extract JSON from Gemini's response, handling:
        1. Clean JSON (ideal case)
        2. JSON wrapped in ```json ... ``` markdown fences
        3. JSON with preamble text before the first {
        """
        # Try direct parse first
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences
        fenced = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', text, re.DOTALL)
        if fenced:
            try:
                return json.loads(fenced.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Find first { ... } block
        brace_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', text, re.DOTALL)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract valid JSON from Gemini response: {text[:200]}")

    def judge(
        self,
        input_text: str,
        expected_output: str,
        actual_output: str,
    ) -> dict:
        """
        Score an LLM output on 5 dimensions using Gemini as judge.

        Returns dict with keys:
            correctness, relevance, coherence, tone,
            hallucination_resistance (all int 1-10),
            reasoning (str)
        """
        from google import genai

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set in environment")

        client = genai.Client(api_key=self.api_key)

        expected_section = ""
        if expected_output and expected_output.strip():
            expected_section = f"\nEXPECTED OUTPUT (reference answer):\n{expected_output}\n"

        judge_prompt = f"""You are an expert LLM output evaluator. Your job is to objectively score a model's response.

INPUT (the question/prompt given to the model):
{input_text}
{expected_section}
ACTUAL OUTPUT (the model's response to evaluate):
{actual_output}

Score the ACTUAL OUTPUT on these 5 dimensions, each from 1 to 10:

1. correctness: Does the output accurately and completely answer the question? (1=completely wrong, 10=perfect)
2. relevance: Is the output on-topic and directly addresses the input? (1=off-topic, 10=perfectly relevant)
3. coherence: Is the output well-structured, logical, and easy to follow? (1=incoherent, 10=perfectly structured)
4. tone: Is the tone appropriate — professional, clear, neither too casual nor too stiff? (1=inappropriate, 10=perfect tone)
5. hallucination_resistance: Does the output avoid fabricating facts or making unsupported claims? (1=full of hallucinations, 10=fully grounded)

Respond with ONLY a JSON object, no other text:
{{"correctness": <int>, "relevance": <int>, "coherence": <int>, "tone": <int>, "hallucination_resistance": <int>, "reasoning": "<2-3 sentence explanation of your scores>"}}"""

        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            self.rate_limiter.wait()

            try:
                response = client.models.generate_content(
                    model=self.model_id,
                    contents=judge_prompt,
                )
                raw_text = response.text or ""
                scores = self._extract_json(raw_text)

                # Validate all required fields exist and are in range
                required = ["correctness", "relevance", "coherence", "tone", "hallucination_resistance"]
                for field in required:
                    val = scores.get(field)
                    if val is None:
                        raise ValueError(f"Missing field: {field}")
                    scores[field] = max(1, min(10, int(val)))

                if "reasoning" not in scores:
                    scores["reasoning"] = "No reasoning provided by judge."

                return scores

            except Exception as e:
                last_error = e
                logger.warning(f"Judge attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(2)
                continue

        # All retries failed — return default low-confidence scores
        logger.error(f"Judge failed after {max_retries} attempts: {last_error}")
        return {
            "correctness": 5,
            "relevance": 5,
            "coherence": 5,
            "tone": 5,
            "hallucination_resistance": 5,
            "reasoning": f"Judge scoring failed after {max_retries} attempts. Default scores assigned. Error: {str(last_error)[:200]}",
        }

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key != "your_gemini_api_key_here")

    def check_health(self) -> str:
        if not self.is_configured():
            return "not_configured"
        try:
            from google import genai
            client = genai.Client(api_key=self.api_key)
            response = client.models.generate_content(
                model=self.model_id,
                contents="Reply with just the word 'ok'",
            )
            return "ok" if response.text else "error: empty response"
        except Exception as e:
            return f"error: {str(e)[:100]}"
