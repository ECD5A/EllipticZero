from __future__ import annotations

import pytest

from app.config import AppConfig
from app.llm.gateway import LLMGateway
from app.llm.providers.mock_provider import MockLLMProvider
from app.llm.router import ModelRouter
from app.platform_paths import platform_cache_tag


class _FailingProvider:
    def generate(self, **kwargs: object) -> str:
        del kwargs
        raise RuntimeError("primary timeout")


class _StaticProvider:
    def __init__(self) -> None:
        self.call_count = 0

    def generate(self, **kwargs: object) -> str:
        del kwargs
        self.call_count += 1
        return "fallback response"


def test_managed_solc_cache_is_platform_specific() -> None:
    config = AppConfig.model_validate(
        {"local_research": {"managed_solc_dir": "tooling/solcx/{platform}"}}
    )

    assert "{platform}" not in config.local_research.managed_solc_dir
    assert config.local_research.managed_solc_dir.endswith(platform_cache_tag())


def test_custom_managed_solc_cache_path_is_preserved() -> None:
    config = AppConfig.model_validate(
        {"local_research": {"managed_solc_dir": "custom/solc-cache"}}
    )

    assert config.local_research.managed_solc_dir == "custom/solc-cache"


def test_agent_specific_model_override() -> None:
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "fallback_provider": "mock",
                "fallback_model": "mock-fallback",
                "timeout_seconds": 45,
                "max_request_tokens": 1024,
                "max_total_requests_per_session": 8,
            },
            "agents": {
                "math_agent": {"provider": "mock", "model": "mock-math"},
                "hypothesis_agent": {"provider": "mock", "model": "mock-hypothesis"},
            },
        }
    )

    router = ModelRouter(config)
    math_route = router.select("math_agent")
    critic_route = router.select("critic_agent")

    assert math_route.provider == "mock"
    assert math_route.model == "mock-math"
    assert math_route.fallback_provider == "mock"
    assert math_route.fallback_model == "mock-fallback"
    assert math_route.budget.timeout_seconds == 45

    assert critic_route.provider == "mock"
    assert critic_route.model == "mock-default"


def test_gateway_enforces_and_resets_session_request_budget() -> None:
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "timeout_seconds": 45,
                "max_request_tokens": 1024,
                "max_total_requests_per_session": 1,
            }
        }
    )
    gateway = LLMGateway(
        router=ModelRouter(config),
        providers={"mock": MockLLMProvider()},
    )
    request = {
        "agent_name": "math_agent",
        "system_prompt": "system",
        "user_prompt": "seed",
        "metadata": {"agent": "math", "seed": "curve point"},
    }

    gateway.generate(**request)
    assert gateway.request_count == 1
    with pytest.raises(RuntimeError, match="request budget exhausted"):
        gateway.generate(**request)

    gateway.start_session()
    gateway.generate(**request)
    assert gateway.request_count == 1


def test_gateway_uses_fallback_within_session_budget() -> None:
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "openai",
                "default_model": "primary-model",
                "fallback_provider": "mock",
                "fallback_model": "fallback-model",
                "max_total_requests_per_session": 2,
            }
        }
    )
    fallback = _StaticProvider()
    gateway = LLMGateway(
        router=ModelRouter(config),
        providers={"openai": _FailingProvider(), "mock": fallback},
    )

    result = gateway.generate(
        agent_name="math_agent",
        system_prompt="system",
        user_prompt="seed",
    )

    assert result == "fallback response"
    assert fallback.call_count == 1
    assert gateway.request_count == 2


def test_gateway_skips_fallback_when_primary_consumes_last_request() -> None:
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "openai",
                "default_model": "primary-model",
                "fallback_provider": "mock",
                "fallback_model": "fallback-model",
                "max_total_requests_per_session": 1,
            }
        }
    )
    fallback = _StaticProvider()
    gateway = LLMGateway(
        router=ModelRouter(config),
        providers={"openai": _FailingProvider(), "mock": fallback},
    )

    with pytest.raises(RuntimeError, match="fallback was not attempted"):
        gateway.generate(
            agent_name="math_agent",
            system_prompt="system",
            user_prompt="seed",
        )

    assert fallback.call_count == 0
    assert gateway.request_count == 1
