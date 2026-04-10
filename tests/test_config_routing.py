from __future__ import annotations

from app.config import AppConfig
from app.llm.router import ModelRouter


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
