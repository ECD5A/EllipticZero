from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.http_utils import post_json


class AnthropicProvider(BaseLLMProvider):
    """Anthropic hosted provider implementation via the official Messages API."""

    provider_name = "anthropic"
    endpoint = "https://api.anthropic.com/v1/messages"
    api_version = "2023-06-01"

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
        del metadata
        if not self.api_key:
            raise RuntimeError(
                "AnthropicProvider selected, but the configured Anthropic API key is not available."
            )
        response = post_json(
            url=self.endpoint,
            payload={
                "model": model,
                "max_tokens": max(1, max_request_tokens),
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            headers={
                "X-Api-Key": self.api_key,
                "Anthropic-Version": self.api_version,
            },
            timeout_seconds=timeout_seconds,
        )
        text = self._extract_text(response)
        if not text:
            raise RuntimeError("AnthropicProvider returned an empty text response.")
        return text

    def _extract_text(self, payload: Mapping[str, Any]) -> str:
        content = payload.get("content")
        if isinstance(content, list):
            fragments = [
                block.get("text", "").strip()
                for block in content
                if isinstance(block, Mapping)
                and block.get("type") == "text"
                and isinstance(block.get("text"), str)
                and block.get("text", "").strip()
            ]
            if fragments:
                return "\n".join(fragments)
        return ""
