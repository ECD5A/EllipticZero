from __future__ import annotations

from pathlib import Path

from app.compute.runners import SageRunner
from app.config import AppConfig
from app.main import build_orchestrator
from app.tools.builtin import FiniteFieldCheckTool, SageSymbolicTool
from app.types import make_id


def test_sage_symbolic_tool_graceful_unavailable_behavior() -> None:
    tool = SageSymbolicTool(
        runner=SageRunner(enabled=True, binary="definitely-not-installed-sage", timeout_seconds=5)
    )
    payload = tool.validate_payload({"expression": "x^2 - x"})
    result = tool.run(payload)

    assert result["status"] == "unavailable"
    assert result["deterministic"] is True
    assert result["result_data"]["sage_available"] is False
    assert result["result_data"]["execution_performed"] is False


def test_finite_field_check_tool_basic_behavior() -> None:
    tool = FiniteFieldCheckTool()
    payload = tool.validate_payload(
        {"modulus": 7, "left": 10, "right": 3, "operation": "equivalent_mod"}
    )
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["consistent"] is True
    assert result["result_data"]["left_mod"] == 3
    assert result["result_data"]["right_mod"] == 3
    assert result["result_data"]["difference_mod"] == 0


def test_orchestrator_symbolic_fallback_and_math_workspace() -> None:
    run_root = Path(".test_runs") / make_id("adv")
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
            "storage": {
                "artifacts_dir": str(run_root),
                "sessions_dir": str(run_root / "sessions"),
                "traces_dir": str(run_root / "traces"),
                "math_artifacts_dir": str(run_root / "math"),
                "bundles_dir": str(run_root / "bundles"),
            },
            "sage": {
                "enabled": True,
                "binary": "definitely-not-installed-sage",
                "timeout_seconds": 5,
            },
            "advanced_math_enabled": True,
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Check whether x^2 - x + x simplifies consistently under bounded symbolic analysis.",
        author="advanced-test",
    )

    assert session.jobs
    assert session.jobs[0].tool_name == "sage_symbolic_tool"
    assert session.jobs[-1].tool_name == "symbolic_check_tool"
    assert session.evidence
    assert session.evidence[0].tool_name == "symbolic_check_tool"
    assert any("Fallback executed" in note for note in session.evidence[0].notes)
    assert session.math_workspaces == []


def test_orchestrator_finite_field_path_records_math_workspace() -> None:
    run_root = Path(".test_runs") / make_id("field")
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
            "storage": {
                "artifacts_dir": str(run_root),
                "sessions_dir": str(run_root / "sessions"),
                "traces_dir": str(run_root / "traces"),
                "math_artifacts_dir": str(run_root / "math"),
                "bundles_dir": str(run_root / "bundles"),
            },
            "sage": {
                "enabled": False,
                "binary": "sage",
                "timeout_seconds": 5,
            },
            "advanced_math_enabled": True,
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Check whether 10 and 3 are equivalent mod 7 under a finite field consistency test.",
        author="field-test",
    )

    assert session.jobs
    assert session.jobs[0].tool_name == "finite_field_check_tool"
    assert session.evidence
    assert session.evidence[0].tool_name == "finite_field_check_tool"
    assert session.evidence[0].experiment_type == "finite_field_check"
    assert session.evidence[0].workspace_id is not None
    assert session.evidence[0].artifact_paths
    assert session.math_workspaces
    assert session.math_workspaces[0].artifact_paths
