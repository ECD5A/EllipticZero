from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.core.manifest_helpers import build_run_manifest
from app.main import build_orchestrator
from app.models import Evidence, ResearchReport, ResearchSeed, ResearchSession
from app.storage.fingerprints import hash_text
from app.storage.reproducibility_bundle import ReproducibilityBundleStore
from app.types import ConfidenceLevel, make_id


def test_seed_hashing_is_stable() -> None:
    seed = "Investigate reproducible local curve metadata inspection."
    assert hash_text(seed) == hash_text(seed)
    assert hash_text(seed) != hash_text(seed + " changed")


def test_manifest_and_bundle_export_without_advanced_artifacts() -> None:
    run_root = Path(".test_runs") / make_id("bundle")
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
        seed_text="Inspect whether secp256k1 metadata labels remain consistent across local reasoning and tool output.",
        author="bundle-test",
    )

    assert session.session_file_path is not None
    assert session.trace_file_path is not None
    assert session.manifest_file_path is not None
    assert session.bundle_dir is not None

    manifest_path = Path(session.manifest_file_path)
    bundle_dir = Path(session.bundle_dir)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert bundle_dir.exists()
    assert (bundle_dir / "session.json").exists()
    assert (bundle_dir / "trace.jsonl").exists()
    assert (bundle_dir / "manifest.json").exists()
    assert (bundle_dir / "comparative_report.json").exists()
    assert (bundle_dir / "overview.json").exists()
    assert manifest["session_id"] == session.session_id
    assert manifest["seed_hash"] == hash_text(session.seed.raw_text)
    assert manifest["session_file_path"] == session.session_file_path
    assert manifest["trace_file_path"] == session.trace_file_path
    assert manifest["comparative_report_path"] == session.comparative_report_file_path
    assert manifest["artifact_count"] == len(manifest["artifacts"])
    assert manifest["comparison_ready"] is False
    assert manifest["report_focus_summary"]
    assert manifest["quality_gate_count"] == len(manifest["quality_gate_summary"])
    assert manifest["hardening_summary_count"] == len(manifest["hardening_summary"])
    assert manifest["quality_gate_summary"]
    assert manifest["hardening_summary"]
    assert "curve_metadata_tool" in manifest["tool_names"]
    assert manifest["local_experiment_summary"]

    overview = json.loads((bundle_dir / "overview.json").read_text(encoding="utf-8"))
    assert overview["session_id"] == session.session_id
    assert overview["tool_count"] == len(manifest["tool_names"])
    assert overview["comparison_ready"] is False
    assert overview["focus_summary"]
    assert overview["quality_gate_count"] == manifest["quality_gate_count"]
    assert overview["hardening_summary_count"] == manifest["hardening_summary_count"]
    assert overview["quality_gate_summary"]
    assert overview["hardening_summary"]


def test_bundle_includes_advanced_math_artifact_references() -> None:
    run_root = Path(".test_runs") / make_id("bundleadv")
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
        author="bundle-advanced-test",
    )

    assert session.manifest_file_path is not None
    assert session.bundle_dir is not None
    manifest = json.loads(Path(session.manifest_file_path).read_text(encoding="utf-8"))
    bundle_dir = Path(session.bundle_dir)

    assert manifest["artifacts"]
    assert manifest["experiment_types"] == ["finite_field_check"]
    assert manifest["local_experiment_summary"]
    assert manifest["artifacts"][0]["generating_tool"] == "finite_field_check_tool"
    assert manifest["artifacts"][0]["workspace_id"] is not None
    assert (bundle_dir / "artifacts").exists()
    assert any(path.is_file() for path in (bundle_dir / "artifacts").iterdir())


def test_manifest_filters_artifacts_outside_local_storage_roots() -> None:
    run_root = Path(".test_runs") / make_id("bundlefilter")
    external_root = Path(".test_runs") / make_id("bundleexternal")
    allowed_root = run_root / "math"
    allowed_root.mkdir(parents=True, exist_ok=True)
    external_root.mkdir(parents=True, exist_ok=True)
    allowed_artifact = allowed_root / "allowed.json"
    external_artifact = external_root / "external.json"
    allowed_artifact.write_text('{"ok": true}', encoding="utf-8")
    external_artifact.write_text('{"secret": true}', encoding="utf-8")

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
                "math_artifacts_dir": str(allowed_root),
                "bundles_dir": str(run_root / "bundles"),
            },
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    session = ResearchSession(
        seed=ResearchSeed(raw_text="Check reproducibility export filtering."),
        evidence=[
            Evidence(
                hypothesis_id="hyp_filter",
                source="finite_field_check_tool",
                summary="Local artifact references were recorded.",
                tool_name="finite_field_check_tool",
                experiment_type="finite_field_check",
                workspace_id="workspace_filter",
                artifact_paths=[str(allowed_artifact), str(external_artifact)],
                raw_result={"result": {"status": "ok", "result_data": {}}},
            )
        ],
    )
    session.report = ResearchReport(
        session_id=session.session_id,
        seed_text=session.seed.raw_text,
        summary="Filtered reproducibility export.",
        confidence=ConfidenceLevel.LOW,
    )
    session_dir = run_root / "sessions"
    trace_dir = run_root / "traces"
    session_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    session.session_file_path = str(session_dir / f"{session.session_id}.json")
    Path(session.session_file_path).write_text("{}", encoding="utf-8")
    session.trace_file_path = str(trace_dir / f"{session.session_id}.jsonl")
    Path(session.trace_file_path).write_text("", encoding="utf-8")

    manifest = build_run_manifest(
        session=session,
        config=config,
        plugin_metadata=[],
        session_path_fallback=Path(session.session_file_path),
    )
    bundle_store = ReproducibilityBundleStore(config.storage.bundles_dir)
    bundle_dir = bundle_store.export(session=session, manifest=manifest)
    manifest_payload = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))

    assert manifest_payload["artifact_count"] == 1
    assert len(manifest_payload["artifacts"]) == 1
    assert manifest_payload["artifacts"][0]["artifact_path"] == str(allowed_artifact)
    copied_files = list((bundle_dir / "artifacts").iterdir())
    assert len(copied_files) == 1
    assert copied_files[0].name.endswith("allowed.json")
