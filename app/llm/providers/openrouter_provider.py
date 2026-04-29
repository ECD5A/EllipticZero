from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.http_utils import post_json


class OpenRouterProvider(BaseLLMProvider):
    """OpenRouter hosted provider via the OpenAI-compatible chat completions API."""

    provider_name = "openrouter"
    endpoint = "https://openrouter.ai/api/v1/chat/completions"
    referer = "https://github.com/ECD5A/EllipticZero"
    title = "EllipticZero Research Lab"

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
                "OpenRouterProvider selected, but the configured OpenRouter API key is not available."
            )
        response = post_json(
            url=self.endpoint,
            payload={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "max_tokens": max_request_tokens,
            },
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "HTTP-Referer": self.referer,
                "X-Title": self.title,
            },
            timeout_seconds=timeout_seconds,
        )
        text = self._extract_text(response)
        if not text:
            raise RuntimeError("OpenRouterProvider returned an empty text response.")
        return text

    def _extract_text(self, payload: Mapping[str, Any]) -> str:
        choices = payload.get("choices")
        if not isinstance(choices, list):
            return ""
        for choice in choices:
            if not isinstance(choice, Mapping):
                continue
            message = choice.get("message")
            if not isinstance(message, Mapping):
                continue
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content.strip()
            if isinstance(content, list):
                fragments: list[str] = []
                for item in content:
                    if not isinstance(item, Mapping):
                        continue
                    text = item.get("text")
                    if isinstance(text, str) and text.strip():
                        fragments.append(text.strip())
                if fragments:
                    return "\n".join(fragments).strip()
        return ""
