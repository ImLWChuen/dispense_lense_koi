"""
DispenseIQ — Bounded LLM Service

Handles external LLM communication using OpenAI API.
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

from openai import OpenAI, OpenAIError, APITimeoutError
from app.core.config import get_settings
from app.services.ai.prompt_manager import PromptManager

logger = logging.getLogger(__name__)

DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT_SECONDS = 10.0


class LLMService:
    """Manages bounded LLM calls with graceful fallback."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        prompt_manager: PromptManager | None = None,
    ) -> None:
        settings = get_settings()
        self.api_key = (
            api_key
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("LLM_API_KEY")
            or settings.openai_api_key
        )
        self.model_name = (
            model_name
            or os.environ.get("OPENAI_MODEL")
            or os.environ.get("LLM_MODEL")
            or settings.openai_model
            or DEFAULT_OPENAI_MODEL
        )
        self.timeout = timeout if timeout != DEFAULT_TIMEOUT_SECONDS else settings.llm_timeout_seconds
        self.prompt_manager = prompt_manager or PromptManager()

        if self.is_available:
            self.client = OpenAI(api_key=self.api_key, timeout=self.timeout)
        else:
            self.client = None

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
        if not self.is_available or not self.client:
            logger.debug("LLMService: No API key configured; skipping LLM call.")
            return None

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.2,
                max_tokens=1024,
            )
            
            return response.choices[0].message.content.strip() if response.choices else None

        except APITimeoutError:
            logger.warning(f"LLMService: Timeout after {self.timeout}s during text generation")
            return None
        except OpenAIError as e:
            logger.warning(f"LLMService: OpenAI error during text generation: {e}")
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
        if not self.is_available or not self.client:
            logger.debug("LLMService: No API key configured; skipping structured LLM call.")
            return None

        try:
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})

            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
                response_format={ "type": "json_object" }
            )
            
            if not response.choices:
                return None

            raw_text = response.choices[0].message.content.strip()
            # Clean possible markdown code fences just in case
            cleaned = re.sub(r"^```json\s*", "", raw_text, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)

            return json.loads(cleaned)

        except APITimeoutError:
            logger.warning(f"LLMService: Timeout after {self.timeout}s during structured generation")
            return None
        except json.JSONDecodeError as e:
            logger.warning(f"LLMService: Malformed JSON output from LLM: {e}")
            return None
        except OpenAIError as e:
            logger.warning(f"LLMService: OpenAI error during structured generation: {e}")
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
