# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.config import AppConfig
from app.llm.providers.anthropic_provider import AnthropicProvider
from app.llm.providers.base import BaseLLMProvider
from app.llm.providers.gemini_provider import GeminiProvider
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.providers.openai_provider import OpenAIProvider
from app.llm.providers.openrouter_provider import OpenRouterProvider
from app.llm.router import ModelRouter, RouteDecision


class LLMGateway:
    """Config-routed gateway for bounded agent reasoning."""

    def __init__(
        self,
        *,
        router: ModelRouter,
        providers: dict[str, BaseLLMProvider],
    ) -> None:
        self.router = router
        self.providers = providers
        self._request_count = 0

    @classmethod
    def from_config(cls, config: AppConfig) -> "LLMGateway":
        providers: dict[str, BaseLLMProvider] = {
            "mock": MockLLMProvider(),
            "openai": OpenAIProvider(api_key=config.provider_api_key("openai")),
            "openrouter": OpenRouterProvider(api_key=config.provider_api_key("openrouter")),
            "gemini": GeminiProvider(api_key=config.provider_api_key("gemini")),
            "anthropic": AnthropicProvider(api_key=config.provider_api_key("anthropic")),
        }
        return cls(router=ModelRouter(config), providers=providers)

    @property
    def request_count(self) -> int:
        return self._request_count

    def start_session(self) -> None:
        self._request_count = 0

    def generate(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        route = self.router.select(agent_name)
        self._ensure_request_budget(route)
        try:
            return self._call_provider(route.provider, route, system_prompt, user_prompt, metadata)
        except Exception as primary_error:
            if not route.fallback_provider:
                raise
            if (
                route.fallback_provider == route.provider
                and route.fallback_model == route.model
            ):
                raise
            fallback_route = RouteDecision(
                provider=route.fallback_provider,
                model=route.fallback_model or route.model,
                fallback_provider=None,
                fallback_model=None,
                budget=route.budget,
            )
            if self._request_count >= fallback_route.budget.max_total_requests_per_session:
                raise RuntimeError(
                    f"Primary route {route.provider}/{route.model} failed; fallback "
                    "was not attempted because the session request budget is exhausted."
                ) from primary_error
            try:
                return self._call_provider(
                    fallback_route.provider,
                    fallback_route,
                    system_prompt,
                    user_prompt,
                    metadata,
                )
            except Exception as fallback_error:
                raise RuntimeError(
                    f"Primary route {route.provider}/{route.model} failed and fallback "
                    f"{fallback_route.provider}/{fallback_route.model} also failed."
                ) from fallback_error

    def _call_provider(
        self,
        provider_name: str,
        route: RouteDecision,
        system_prompt: str,
        user_prompt: str,
        metadata: Mapping[str, Any] | None,
    ) -> str:
        provider = self.providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Unsupported LLM provider: {provider_name}")
        self._ensure_request_budget(route)
        self._request_count += 1
        return provider.generate(
            model=route.model,
            timeout_seconds=route.budget.timeout_seconds,
            max_request_tokens=route.budget.max_request_tokens,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            metadata=metadata,
        )

    def _ensure_request_budget(self, route: RouteDecision) -> None:
        if self._request_count >= route.budget.max_total_requests_per_session:
            raise RuntimeError(
                "LLM request budget exhausted for this session "
                f"({route.budget.max_total_requests_per_session} requests)."
            )
