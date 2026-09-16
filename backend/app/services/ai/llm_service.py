"""
DispenseIQ — Bounded LLM Service

Handles external LLM communication (e.g. Google Gemini API via REST).
The LLM is strictly a supporting component, not the diagnostic authority.

Allowed uses:
- Symptom extraction assistance
- Natural-language explanation formatting
- Revision delta explanation
- End-of-case summarization

Explicitly forbidden:
- Inventing scores or overriding deterministic scores
- Inventing troubleshooting procedures or sources
- Declaring root causes confirmed automatically
- Declaring issues resolved automatically
- Crashing or corrupting diagnosis upon service failure
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.ai.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-1.5-flash"
DEFAULT_TIMEOUT_SECONDS = 10.0


class LLMService:
    """Manages bounded LLM calls with graceful fallback."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        api_base: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = (
            api_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("LLM_API_KEY")
            or settings.gemini_api_key
        )
        self.model_name = (
            model_name
            or os.environ.get("GEMINI_MODEL")
            or os.environ.get("LLM_MODEL")
            or settings.gemini_model
        )
        self.api_base = (
            api_base
            or os.environ.get("GEMINI_API_BASE")
            or os.environ.get("LLM_API_BASE")
            or settings.gemini_api_base
        ).rstrip("/")
        self.timeout = timeout if timeout != DEFAULT_TIMEOUT_SECONDS else settings.llm_timeout_seconds
        self.prompt_manager = prompt_manager or PromptManager()

    @property
    def is_available(self) -> bool:
        """True if an API key is configured."""
        return bool(self.api_key and self.api_key.strip())

    # -----------------------------------------------------------------------
    # Core generation methods
    # -----------------------------------------------------------------------

    def generate_text(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> str | None:
        """Generate text from LLM. Returns None on failure or if unconfigured."""
        if not self.is_available:
            logger.debug("LLMService: No API key configured; skipping LLM call.")
            return None

        try:
            url = f"{self.api_base}/models/{self.model_name}:generateContent"
            params = {"key": self.api_key}

            payload: dict[str, Any] = {
                "contents": [
                    {
                        "parts": [{"text": prompt}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 1024,
                },
            }

            if system_prompt:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_prompt}]
                }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, params=params, json=payload)
                response.raise_for_status()
                data = response.json()

            candidates = data.get("candidates", [])
            if not candidates:
                logger.warning("LLMService: Empty candidate list in response")
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return None

            return parts[0].get("text", "").strip()

        except httpx.TimeoutException:
            logger.warning(f"LLMService: Timeout after {self.timeout}s during text generation")
            return None
        except httpx.HTTPStatusError as e:
            logger.warning(f"LLMService: HTTP {e.response.status_code} from Gemini API: {e.response.text}")
            return None
        except Exception as e:
            logger.warning(f"LLMService: Unexpected error during text generation: {e}")
            return None

    def generate_structured(
        self,
        prompt: str,
        system_prompt: str | None = None,
    ) -> dict[str, Any] | None:
        """Generate structured JSON from LLM. Returns None on failure or invalid JSON."""
        if not self.is_available:
            logger.debug("LLMService: No API key configured; skipping structured LLM call.")
            return None

        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent"
            params = {"key": self.api_key}

            payload: dict[str, Any] = {
                "contents": [
                    {
                        "parts": [{"text": prompt}],
                    }
                ],
                "generationConfig": {
                    "temperature": 0.1,
                    "responseMimeType": "application/json",
                    "maxOutputTokens": 1024,
                },
            }

            if system_prompt:
                payload["systemInstruction"] = {
                    "parts": [{"text": system_prompt}]
                }

            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(url, params=params, json=payload)
                response.raise_for_status()
                data = response.json()

            candidates = data.get("candidates", [])
            if not candidates:
                return None

            parts = candidates[0].get("content", {}).get("parts", [])
            if not parts:
                return None

            raw_text = parts[0].get("text", "").strip()
            # Clean possible markdown code fences
            cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

            return json.loads(cleaned)

        except httpx.TimeoutException:
            logger.warning(f"LLMService: Timeout after {self.timeout}s during structured generation")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"LLMService: Malformed JSON output from LLM: {e}")
            return None
        except Exception as e:
            logger.warning(f"LLMService: Unexpected error during structured generation: {e}")
            return None

    # -----------------------------------------------------------------------
    # Domain-specific bounded actions
    # -----------------------------------------------------------------------

    def extract_symptoms(self, description: str) -> dict[str, Any] | None:
        """Extract observations and user hypotheses using bounded LLM.

        Validates output to ensure:
        1. It contains an 'observations' list.
        2. It does NOT cross into root-cause probabilities (e.g. 'air bubble 90%').
        """
        system_prompt, user_prompt = self.prompt_manager.get_symptom_extraction_prompt(description)
        result = self.generate_structured(user_prompt, system_prompt=system_prompt)
        if not result or not isinstance(result, dict):
            return None

        # Validation Rule §3.3: Reject if model returned root-cause probabilities or conclusions
        for obs in result.get("observations", []):
            val_str = str(obs.get("value", "")).lower()
            type_str = str(obs.get("type", "")).lower()

            # Detect diagnosis claims / percentages masquerading as observations
            if re.search(r"\b\d{1,3}%\b", val_str) or re.search(r"\b(probable|likelihood|confidence|probability)\b", val_str):
                logger.warning(f"LLMService: Rejected observation containing root-cause probability: {obs}")
                return None
            if "cause" in type_str or "diagnosis" in type_str:
                logger.warning(f"LLMService: Rejected diagnosis claim in extraction: {obs}")
                return None

        return result
