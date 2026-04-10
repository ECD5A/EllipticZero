from __future__ import annotations

from app.config import AppConfig
from app.llm.router import build_route_overview, summarize_route_mode
from app.main import build_parser, render_routing_summary


def _base_config_payload(run_root: str) -> dict[str, object]:
    return {
        "llm": {
            "default_provider": "mock",
            "default_model": "mock-default",
            "timeout_seconds": 30,
            "max_request_tokens": 2048,
            "max_total_requests_per_session": 16,
        },
        "storage": {
            "artifacts_dir": run_root,
            "sessions_dir": f"{run_root}/sessions",
            "traces_dir": f"{run_root}/traces",
            "math_artifacts_dir": f"{run_root}/math",
            "bundles_dir": f"{run_root}/bundles",
        },
    }


def test_parser_supports_routing_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--show-routing",
            "--model",
            "gpt-test",
            "--math-provider",
            "openai",
            "--math-model",
            "gpt-math",
        ]
    )

    assert args.show_routing is True
    assert args.model == "gpt-test"
    assert args.math_agent_provider == "openai"
    assert args.math_agent_model == "gpt-math"


def test_route_overview_defaults_to_shared_and_summary_renders() -> None:
    payload = _base_config_payload(".test_runs/routing")
    payload["agents"] = {
        "math_agent": {"provider": None, "model": None},
        "cryptography_agent": {"provider": None, "model": None},
        "strategy_agent": {"provider": None, "model": None},
        "hypothesis_agent": {"provider": None, "model": None},
        "critic_agent": {"provider": None, "model": None},
        "report_agent": {"provider": None, "model": None},
    }
    config = AppConfig.model_validate(payload)

    rows = build_route_overview(config)
    summary = render_routing_summary(config, language="en")

    assert summarize_route_mode(config) == "shared-default"
    assert rows
    assert all(row.mode == "shared" for row in rows)
    assert "LLM Routing" in summary
    assert "shared-default" in summary


def test_route_overview_detects_override() -> None:
    payload = _base_config_payload(".test_runs/routing_override")
    payload["agents"] = {
        "math_agent": {"provider": "openai", "model": "gpt-math"},
    }
    config = AppConfig.model_validate(payload)

    rows = build_route_overview(config)
    math_row = next(row for row in rows if row.agent_name == "math_agent")

    assert math_row.mode == "override"
    assert summarize_route_mode(config).startswith("mixed")
    assert "gpt-math" in render_routing_summary(config, language="en")
