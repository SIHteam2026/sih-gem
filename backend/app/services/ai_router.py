"""Resilient AI Router Module for Groq API Key Pool & Fallback Routing.

Provides round-robin load distribution and automatic fault-tolerant failover
across multiple Groq API keys (GROQ_KEY_1 to GROQ_KEY_6) using the
openai/gpt-oss-120b model.
"""

import asyncio
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Ensure project root and backend paths are available for imports
_current_file = Path(__file__).resolve()
_backend_dir = _current_file.parent.parent.parent
_root_dir = _backend_dir.parent
for _p in [str(_root_dir), str(_backend_dir), str(_current_file.parent.parent)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from dotenv import find_dotenv, load_dotenv
from fastapi import HTTPException, status
import httpx

try:
    from groq import AsyncGroq, Groq, APIError, RateLimitError, APIConnectionError
except ImportError:
    AsyncGroq = None  # type: ignore
    Groq = None  # type: ignore
    APIError = Exception  # type: ignore
    RateLimitError = Exception  # type: ignore
    APIConnectionError = Exception  # type: ignore

# Load environment variables
load_dotenv(find_dotenv(usecwd=True))

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "openai/gpt-oss-120b"
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"


class AIRouterError(Exception):
    """Exception raised when all Groq keys in the pool fail."""
    pass


class AIRouter:
    """Manages a pool of Groq API keys with thread-safe round-robin selection
    and automatic fallback failover upon rate limits (429) or failures.
    """

    def __init__(self, default_model: str = DEFAULT_MODEL):
        self.default_model = default_model
        self._current_index = 0
        self._lock = asyncio.Lock()
        self._sync_lock_index = 0

    def get_api_keys(self) -> List[str]:
        """Loads and returns all configured Groq API keys from environment variables.

        Scans for GROQ_KEY_1 through GROQ_KEY_6, as well as GROQ_API_KEY_1..6,
        GROQ_API_KEY, and GROQ_KEY.
        """
        # Re-read dotenv in case of runtime modifications
        load_dotenv(find_dotenv(usecwd=True))

        keys: List[str] = []
        seen = set()

        # Primary pattern: GROQ_KEY_1 through GROQ_KEY_6
        for i in range(1, 7):
            val = os.getenv(f"GROQ_KEY_{i}")
            if val and val.strip() and val.strip() not in seen:
                clean_key = val.strip()
                keys.append(clean_key)
                seen.add(clean_key)

        # Alternative patterns: GROQ_API_KEY_1 through GROQ_API_KEY_6
        for i in range(1, 7):
            val = os.getenv(f"GROQ_API_KEY_{i}")
            if val and val.strip() and val.strip() not in seen:
                clean_key = val.strip()
                keys.append(clean_key)
                seen.add(clean_key)

        # Single key fallbacks
        for env_var in ["GROQ_API_KEY", "GROQ_KEY"]:
            val = os.getenv(env_var)
            if val and val.strip() and val.strip() not in seen:
                clean_key = val.strip()
                keys.append(clean_key)
                seen.add(clean_key)

        return keys

    async def _get_next_key_indices(self) -> List[int]:
        """Returns key indices ordered starting from the current round-robin cursor."""
        keys = self.get_api_keys()
        if not keys:
            return []

        async with self._lock:
            start = self._current_index % len(keys)
            self._current_index = (self._current_index + 1) % len(keys)

        # Return list of indices starting from current round-robin position
        return [(start + i) % len(keys) for i in range(len(keys))]

    def _get_next_key_indices_sync(self) -> List[int]:
        """Synchronous version to get ordered key indices starting from current cursor."""
        keys = self.get_api_keys()
        if not keys:
            return []

        start = self._sync_lock_index % len(keys)
        self._sync_lock_index = (self._sync_lock_index + 1) % len(keys)
        return [(start + i) % len(keys) for i in range(len(keys))]

    async def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = 4096,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Asynchronously generates completion text using Groq with multi-key round-robin fallback.

        Args:
            prompt: User prompt content.
            system_prompt: Optional system prompt instructions.
            model: Target model (defaults to openai/gpt-oss-120b).
            temperature: Sampling temperature.
            max_tokens: Maximum output tokens.
            response_format: Optional response format (e.g. {"type": "json_object"}).

        Returns:
            str: Generated text completion.

        Raises:
            HTTPException: If all Groq keys fail or no keys are configured.
        """
        keys = self.get_api_keys()
        if not keys:
            logger.error("No Groq API keys configured in environment (checked GROQ_KEY_1..6, GROQ_API_KEY).")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No Groq API keys configured in environment variables.",
            )

        target_model = model or self.default_model
        ordered_indices = await self._get_next_key_indices()
        last_exception = None

        messages: List[Dict[str, str]] = []
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": prompt})

        for attempt_idx, key_idx in enumerate(ordered_indices, start=1):
            key = keys[key_idx]
            masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"

            try:
                logger.debug(
                    "Executing Groq query with key #%d (%s) [Attempt %d/%d, model=%s]",
                    key_idx + 1,
                    masked_key,
                    attempt_idx,
                    len(keys),
                    target_model,
                )

                if AsyncGroq is not None:
                    client = AsyncGroq(api_key=key)
                    kwargs: Dict[str, Any] = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                    if max_tokens:
                        kwargs["max_tokens"] = max_tokens
                    if response_format:
                        kwargs["response_format"] = response_format

                    response = await client.chat.completions.create(**kwargs)
                    if response.choices and len(response.choices) > 0:
                        content = response.choices[0].message.content or ""
                        return content.strip()
                    else:
                        raise ValueError("Received empty choices array from Groq API.")
                else:
                    # Direct HTTP fallback using httpx
                    headers = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    }
                    payload: Dict[str, Any] = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                    if max_tokens:
                        payload["max_tokens"] = max_tokens
                    if response_format:
                        payload["response_format"] = response_format

                    async with httpx.AsyncClient(timeout=60.0) as http_client:
                        resp = await http_client.post(GROQ_API_URL, headers=headers, json=payload)
                        if resp.status_code == 429:
                            raise HTTPException(
                                status_code=429,
                                detail=f"Rate limit exceeded on key {masked_key}",
                            )
                        resp.raise_for_status()
                        data = resp.json()
                        content = data["choices"][0]["message"]["content"]
                        return content.strip()

            except Exception as exc:
                last_exception = exc
                err_msg = str(exc)
                logger.warning(
                    "Groq key #%d (%s) failed on attempt %d/%d: %s. Initiating automatic fallback to next key...",
                    key_idx + 1,
                    masked_key,
                    attempt_idx,
                    len(keys),
                    err_msg[:160],
                )
                continue

        logger.error("All %d Groq API keys in pool failed: %s", len(keys), last_exception)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"All Groq API keys failed: {str(last_exception)}",
        )

    async def generate_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Union[Dict[str, Any], List[Any]]:
        """Asynchronously generates completion and parses JSON output with automatic sanitization.

        Args:
            prompt: User prompt content.
            system_prompt: Optional system instructions.
            model: Target model (defaults to openai/gpt-oss-120b).
            temperature: Sampling temperature.

        Returns:
            dict or list: Parsed JSON structure.
        """
        raw_text = await self.generate_text(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )

        return self._extract_json(raw_text)

    def generate_text_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: Optional[int] = 4096,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Synchronous generation using Groq multi-key fallback."""
        keys = self.get_api_keys()
        if not keys:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="No Groq API keys configured in environment variables.",
            )

        target_model = model or self.default_model
        ordered_indices = self._get_next_key_indices_sync()
        last_exception = None

        messages: List[Dict[str, str]] = []
        if system_prompt and system_prompt.strip():
            messages.append({"role": "system", "content": system_prompt.strip()})
        messages.append({"role": "user", "content": prompt})

        for attempt_idx, key_idx in enumerate(ordered_indices, start=1):
            key = keys[key_idx]
            masked_key = f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "***"

            try:
                if Groq is not None:
                    client = Groq(api_key=key)
                    kwargs: Dict[str, Any] = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                    if max_tokens:
                        kwargs["max_tokens"] = max_tokens
                    if response_format:
                        kwargs["response_format"] = response_format

                    response = client.chat.completions.create(**kwargs)
                    if response.choices and len(response.choices) > 0:
                        content = response.choices[0].message.content or ""
                        return content.strip()
                    else:
                        raise ValueError("Received empty choices array from Groq API.")
                else:
                    headers = {
                        "Authorization": f"Bearer {key}",
                        "Content-Type": "application/json",
                    }
                    payload: Dict[str, Any] = {
                        "model": target_model,
                        "messages": messages,
                        "temperature": temperature,
                    }
                    if max_tokens:
                        payload["max_tokens"] = max_tokens
                    if response_format:
                        payload["response_format"] = response_format

                    with httpx.Client(timeout=60.0) as http_client:
                        resp = http_client.post(GROQ_API_URL, headers=headers, json=payload)
                        if resp.status_code == 429:
                            raise HTTPException(
                                status_code=429,
                                detail=f"Rate limit exceeded on key {masked_key}",
                            )
                        resp.raise_for_status()
                        data = resp.json()
                        return data["choices"][0]["message"]["content"].strip()

            except Exception as exc:
                last_exception = exc
                logger.warning(
                    "Groq sync key #%d (%s) failed on attempt %d/%d: %s. Retrying next key...",
                    key_idx + 1,
                    masked_key,
                    attempt_idx,
                    len(keys),
                    str(exc)[:160],
                )
                continue

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"All Groq API keys failed: {str(last_exception)}",
        )

    def generate_json_sync(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Union[Dict[str, Any], List[Any]]:
        """Synchronously generates and parses JSON output."""
        raw_text = self.generate_text_sync(
            prompt=prompt,
            system_prompt=system_prompt,
            model=model,
            temperature=temperature,
            response_format={"type": "json_object"},
        )
        return self._extract_json(raw_text)

    def _extract_json(self, raw_text: str) -> Union[Dict[str, Any], List[Any]]:
        """Cleans and parses raw JSON or Markdown-fenced JSON text."""
        cleaned = raw_text.strip()

        # Remove markdown code block fences if present
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]

        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            # Attempt regex extraction if there are surrounding comments
            json_match = re.search(r"(\{.*\}|\[.*\])", cleaned, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group(0))
                except json.JSONDecodeError:
                    pass
            logger.error("Failed to parse JSON from AI response: %s", raw_text[:300])
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI returned malformed or non-JSON output.",
            )


# Global singleton router instance
ai_router = AIRouter()

# Convenience functional exports
call_groq = ai_router.generate_text
call_groq_json = ai_router.generate_json
call_groq_sync = ai_router.generate_text_sync
call_groq_json_sync = ai_router.generate_json_sync
