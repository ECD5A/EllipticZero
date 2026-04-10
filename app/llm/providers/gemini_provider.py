from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import quote

from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.http_utils import post_json


class GeminiProvider(BaseLLMProvider):
    """Gemini hosted provider implementation via the official generateContent API."""

    provider_name = "gemini"

    def __init__(self, *, api_key: str | None) -> None:
        self.api_key = api_key

    def generate(
        self,
        *,
        model: str,
        timeout_seconds: int,
        max_request_tokens: int,
        system_prompt: str,
        user_prompt: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        del max_request_tokens, metadata
        if not self.api_key:
            raise RuntimeError(
                "GeminiProvider selected, but the configured Gemini API key is not available."
            )
        response = post_json(
            url=(
                "https://generativelanguage.googleapis.com/v1beta/models/"
                f"{quote(model, safe='')}:generateContent?key={quote(self.api_key, safe='')}"
            ),
            payload={
                "system_instruction": {"parts": [{"text": system_prompt}]},
                "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
            },
            headers={},
            timeout_seconds=timeout_seconds,
        )
        text = self._extract_text(response)
        if not text:
            raise RuntimeError("GeminiProvider returned an empty text response.")
        return text

    def _extract_text(self, payload: Mapping[str, Any]) -> str:
        candidates = payload.get("candidates")
        if isinstance(candidates, list):
            for candidate in candidates:
                if not isinstance(candidate, Mapping):
                    continue
                content = candidate.get("content")
                if not isinstance(content, Mapping):
                    continue
                parts = content.get("parts")
                if not isinstance(parts, list):
                    continue
                fragments = [
                    part.get("text", "").strip()
                    for part in parts
                    if isinstance(part, Mapping) and isinstance(part.get("text"), str) and part.get("text", "").strip()
                ]
                if fragments:
                    return "\n".join(fragments)
        prompt_feedback = payload.get("promptFeedback")
        if isinstance(prompt_feedback, Mapping):
            block_reason = prompt_feedback.get("blockReason")
            if isinstance(block_reason, str) and block_reason.strip():
                raise RuntimeError(f"GeminiProvider blocked the request: {block_reason.strip()}")
        return ""
