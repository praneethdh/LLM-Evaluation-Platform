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
        4. Fallback manual regex extraction for malformed JSON with unescaped quotes
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

        # Fallback regex extraction for nested schema when unescaped quotes break json.loads
        try:
            scores_dict = {}
            for key in ["correctness", "relevance", "coherence", "tone", "hallucination_resistance"]:
                val_match = re.search(rf'"{key}"\s*:\s*(\d+)', text)
                if val_match:
                    scores_dict[key] = int(val_match.group(1))

            reasoning_dict = {}
            for key in ["correctness", "relevance", "coherence", "tone", "hallucination_resistance"]:
                val_match = re.search(rf'"{key}"\s*:\s*"(.*)"\s*(?:,|\n|}})', text)
                if val_match:
                    reasoning_dict[key] = val_match.group(1)

            devil_match = re.search(r'"devil_advocate"\s*:\s*"(.*)"\s*(?:,|\n|}})', text)
            devil_advocate = devil_match.group(1) if devil_match else "N/A"

            if scores_dict:
                return {
                    "devil_advocate": devil_advocate,
                    "reasoning": reasoning_dict,
                    "scores": scores_dict
                }
        except Exception:
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

        judge_prompt = f"""You are a strict, calibrated evaluator. Your bias is toward lower scores.
A score of 9-10 means the output is nearly perfect with no room for improvement.
Most outputs score between 4 and 7.

You MUST follow this exact JSON structure — reasoning BEFORE scores:

{{
  "devil_advocate": "<one sentence: what is the strongest argument that this output is wrong or incomplete>",
  "reasoning": {{
    "correctness": "<evaluate factual accuracy against reference — cite specific errors if any>",
    "relevance": "<does it answer exactly what was asked, nothing more, nothing less>",
    "coherence": "<logical flow, structure, clarity>",
    "tone": "<appropriateness for context>",
    "hallucination_resistance": "<any invented facts, numbers, or claims not in the input>"
  }},
  "scores": {{
    "correctness": <1-10>,
    "relevance": <1-10>,
    "coherence": <1-10>,
    "tone": <1-10>,
    "hallucination_resistance": <1-10>
  }}
}}

Scoring anchors (apply to ALL dimensions):
1-3: Clearly wrong, missing, or harmful
4-5: Partially meets criteria, notable gaps
6-7: Adequate, meets basic criteria, minor issues
8:   Good, only small improvements possible
9-10: Reserved for outputs that could not realistically be improved

Input: {input_text}
Reference answer: {expected_output or "None provided"}
Model output: {actual_output}

Return ONLY the JSON. No preamble.
IMPORTANT: If you quote strings from the model output in your reasoning or devil's advocate fields, you MUST use single quotes (e.g., 'mutable') to avoid breaking JSON formatting."""

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
                parsed = self._extract_json(raw_text)

                # Extract and validate scores
                scores_dict = parsed.get("scores", {})
                final_scores = {}
                required = ["correctness", "relevance", "coherence", "tone", "hallucination_resistance"]
                for field in required:
                    val = scores_dict.get(field)
                    if val is None:
                        raise ValueError(f"Missing score field: {field}")
                    final_scores[field] = max(1, min(10, int(val)))

                # Extract and compile reasoning
                reasoning_dict = parsed.get("reasoning", {})
                reasoning_lines = []
                for field in required:
                    field_reason = reasoning_dict.get(field, "No detail provided.")
                    reasoning_lines.append(f"- **{field.replace('_', ' ').capitalize()}**: {field_reason}")

                devil_advocate = parsed.get("devil_advocate", "")
                full_reasoning = f"**Devil's Advocate:** {devil_advocate}\n\n" + "\n".join(reasoning_lines)
                final_scores["reasoning"] = full_reasoning

                return final_scores

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
