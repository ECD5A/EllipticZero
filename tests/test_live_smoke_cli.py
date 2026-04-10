from __future__ import annotations

from app.config import AppConfig
from app.llm.live_smoke import resolve_live_smoke_model
from app.main import build_parser, run_live_provider_smoke


def test_parser_supports_live_smoke_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--live-provider-smoke",
            "anthropic",
            "--live-smoke-model",
            "claude-smoke",
        ]
    )

    assert args.live_provider_smoke == "anthropic"
    assert args.live_smoke_model == "claude-smoke"


def test_parser_supports_openrouter_live_smoke_provider() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--live-provider-smoke",
            "openrouter",
            "--live-smoke-model",
            "openai/gpt-4.1-mini",
        ]
    )

    assert args.live_provider_smoke == "openrouter"
    assert args.live_smoke_model == "openai/gpt-4.1-mini"


def test_run_live_provider_smoke_renders_result(monkeypatch) -> None:
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "anthropic",
                "default_model": "claude-test",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
        }
    )

    class _FakeProvider:
        def generate(self, **kwargs):
            assert kwargs["model"] == "claude-test"
            assert kwargs["max_request_tokens"] == 512
            return "LIVE SMOKE OK"

    class _FakeGateway:
        providers = {"anthropic": _FakeProvider()}

    monkeypatch.setattr("app.main.LLMGateway.from_config", lambda config: _FakeGateway())

    rendered = run_live_provider_smoke(
        config=config,
        provider_name="anthropic",
        model_name=None,
        language="en",
    )

    assert "Hosted Provider Smoke Test" in rendered
    assert "Provider: anthropic" in rendered
    assert "Timeout (s): 30" in rendered
    assert "Max request tokens: 512" in rendered
    assert "LIVE SMOKE OK" in rendered


def test_resolve_live_smoke_model_uses_openrouter_auto_by_default() -> None:
    assert (
        resolve_live_smoke_model(
            provider_name="openrouter",
            configured_default_model="some-default-model",
        )
        == "openrouter/auto"
    )


def test_run_live_provider_smoke_uses_openrouter_auto_default(monkeypatch) -> None:
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "openrouter",
                "default_model": "should-not-be-used",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
        }
    )

    class _FakeProvider:
        def generate(self, **kwargs):
            assert kwargs["model"] == "openrouter/auto"
            return "LIVE SMOKE OK"

    class _FakeGateway:
        providers = {"openrouter": _FakeProvider()}

    monkeypatch.setattr("app.main.LLMGateway.from_config", lambda config: _FakeGateway())

    rendered = run_live_provider_smoke(
        config=config,
        provider_name="openrouter",
        model_name=None,
        language="en",
    )

    assert "Provider: openrouter" in rendered
    assert "Model: openrouter/auto" in rendered
