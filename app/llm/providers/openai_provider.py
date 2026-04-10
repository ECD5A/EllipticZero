from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.http_utils import post_json


class OpenAIProvider(BaseLLMProvider):
    """OpenAI hosted provider implementation via the official Responses API."""

    provider_name = "openai"
    endpoint = "https://api.openai.com/v1/responses"

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
        del max_request_tokens
        if not self.api_key:
            raise RuntimeError(
                "OpenAIProvider selected, but the configured OpenAI API key is not available."
            )
        response = post_json(
            url=self.endpoint,
            payload={
                "model": model,
                "instructions": system_prompt,
                "input": user_prompt,
                "metadata": dict(metadata or {}),
            },
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout_seconds=timeout_seconds,
        )
        text = self._extract_text(response)
        if not text:
            raise RuntimeError("OpenAIProvider returned an empty text response.")
        return text

    def _extract_text(self, payload: Mapping[str, Any]) -> str:
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()

        fragments: list[str] = []
        for item in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
            if not isinstance(item, Mapping):
                continue
            content = item.get("content")
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, Mapping):
                    continue
                text = block.get("text")
                if isinstance(text, str) and text.strip():
                    fragments.append(text.strip())
        return "\n".join(fragments).strip()
