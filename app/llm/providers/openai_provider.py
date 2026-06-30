# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

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
        if not self.api_key:
            raise RuntimeError(
                "OpenAIProvider selected, but the configured OpenAI API key is not available."
            )
        request_metadata = self._request_metadata(metadata)
        payload: dict[str, Any] = {
            "model": model,
            "instructions": system_prompt,
            "input": user_prompt,
            "max_output_tokens": max(1, max_request_tokens),
            "store": False,
        }
        if request_metadata:
            payload["metadata"] = request_metadata
        response = post_json(
            url=self.endpoint,
            payload=payload,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout_seconds=timeout_seconds,
        )
        text = self._extract_text(response)
        if not text:
            raise RuntimeError("OpenAIProvider returned an empty text response.")
        return text

    def _request_metadata(self, metadata: Mapping[str, Any] | None) -> dict[str, str]:
        """Keep API metadata small and free of code, evidence, or secrets."""
        allowed_keys = {"agent", "domain", "round_index", "variant_index"}
        result: dict[str, str] = {}
        for key, value in (metadata or {}).items():
            if key not in allowed_keys or value is None:
                continue
            rendered = str(value).strip()
            if rendered:
                result[key] = rendered[:500]
        return result

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
