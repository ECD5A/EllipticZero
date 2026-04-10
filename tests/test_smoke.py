from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.main import build_orchestrator
from app.types import ConfidenceLevel, make_id


def test_smoke_flow() -> None:
    run_root = Path(".test_runs") / make_id("smoke")
    session_dir = run_root / "sessions"
    trace_dir = run_root / "traces"
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
                "sessions_dir": str(session_dir),
                "traces_dir": str(trace_dir),
                "bundles_dir": str(run_root / "bundles"),
            },
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text=(
            "Investigate whether secp256k1 point parsing inconsistencies in a "
            "custom implementation indicate a real anomaly or underspecified input handling."
        ),
        author="test",
    )

    assert session.report is not None
    assert session.math_result is not None
    assert session.cryptography_result is not None
    assert session.strategy_result is not None
    assert session.hypothesis_result is not None
    assert session.critic_result is not None
    assert session.report_result is not None
    assert session.hypotheses
    assert session.evidence
    assert session.jobs
    assert isinstance(session.math_workspaces, list)
    assert isinstance(session.plugin_metadata, list)
    assert session.hypothesis_result.branches
    assert session.trace_file_path is not None
    assert session.session_file_path is not None
    assert session.manifest_file_path is not None
    assert session.bundle_dir is not None
    assert session.comparative_report is not None
    assert session.comparative_report_file_path is not None
    assert session.jobs[0].tool_plan is not None
    assert session.jobs[0].experiment_spec is not None
    assert session.evidence[0].tool_name is not None
    assert session.evidence[0].conclusion is not None
    assert isinstance(session.evidence[0].notes, list)
    assert session.evidence[0].experiment_type is not None
    assert session.evidence[0].target_kind is not None
    assert isinstance(session.evidence[0].selected_by_roles, list)

    session_path = session_dir / f"{session.session_id}.json"
    trace_path = Path(session.trace_file_path)
    manifest_path = Path(session.manifest_file_path)
    bundle_dir = Path(session.bundle_dir)
    comparative_report_path = Path(session.comparative_report_file_path)

    assert session_path.exists()
    assert trace_path.exists()
    assert manifest_path.exists()
    assert bundle_dir.exists()
    assert comparative_report_path.exists()
    assert (bundle_dir / "session.json").exists()
    assert (bundle_dir / "trace.jsonl").exists()
    assert (bundle_dir / "manifest.json").exists()
    assert (bundle_dir / "comparative_report.json").exists()

    session_payload = json.loads(session_path.read_text(encoding="utf-8"))
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    trace_lines = trace_path.read_text(encoding="utf-8").strip().splitlines()

    assert session_payload["seed"]["raw_text"]
    assert session_payload["trace_file_path"] == str(trace_path)
    assert session_payload["session_file_path"] == str(session_path)
    assert session_payload["manifest_file_path"] == str(manifest_path)
    assert session_payload["bundle_dir"] == str(bundle_dir)
    assert session_payload["comparative_report_file_path"] == str(comparative_report_path)
    assert "math_workspaces" in session_payload
    assert manifest_payload["session_id"] == session.session_id
    assert manifest_payload["session_file_path"] == str(session_path)
    assert manifest_payload["trace_file_path"] == str(trace_path)
    assert manifest_payload["comparative_report_path"] == str(comparative_report_path)
    assert "loaded_plugins" in manifest_payload["environment_summary"]
    assert session_payload["evidence"][0]["tool_name"] == session.evidence[0].tool_name
    assert session_payload["jobs"][0]["tool_plan"]["tool_name"] == session.jobs[0].tool_plan.tool_name
    assert session_payload["report"]["tested_hypotheses"]
    assert session_payload["report"]["local_experiment_summary"]
    assert session_payload["report"]["local_signal_summary"]
    assert session_payload["cryptography_result"]["surface_summary"]
    assert session_payload["strategy_result"]["strategy_summary"]
    assert session_payload["report"]["agent_contributions"]
    assert "dead_end_summary" in session_payload["report"]
    assert "next_defensive_leads" in session_payload["report"]
    assert "local_experiment_summary" in manifest_payload
    assert "comparative_report" in session_payload
    assert len(trace_lines) >= 8
    assert session.report.confidence in {
        ConfidenceLevel.LOW,
        ConfidenceLevel.INCONCLUSIVE,
        ConfidenceLevel.MEDIUM,
        ConfidenceLevel.HIGH,
        ConfidenceLevel.MANUAL_REVIEW_REQUIRED,
    }
