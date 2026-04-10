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

    def generate(
        self,
        *,
        agent_name: str,
        system_prompt: str,
        user_prompt: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        route = self.router.select(agent_name)
        try:
            return self._call_provider(route.provider, route, system_prompt, user_prompt, metadata)
        except Exception:
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
        return provider.generate(
            model=route.model,
            timeout_seconds=route.budget.timeout_seconds,
            max_request_tokens=route.budget.max_request_tokens,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            metadata=metadata,
        )
