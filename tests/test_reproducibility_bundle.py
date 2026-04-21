from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.core.manifest_helpers import build_run_manifest
from app.main import build_orchestrator
from app.models import Evidence, ResearchReport, ResearchSeed, ResearchSession
from app.models.trace import TraceEvent
from app.storage.fingerprints import hash_text
from app.storage.redaction import REDACTED, redact_sensitive_data
from app.storage.reproducibility_bundle import ReproducibilityBundleStore
from app.storage.trace_writer import TraceWriter
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
    assert manifest["approved_export_roots"]
    assert manifest["export_policy_summary"]
    assert manifest["filtered_artifact_count"] == 0
    assert manifest["session_export_ready"] is True
    assert manifest["trace_export_ready"] is True
    assert manifest["comparative_export_ready"] is True
    assert manifest["artifact_count"] == len(manifest["artifacts"])
    assert manifest["comparison_ready"] is False
    assert manifest["report_focus_summary"]
    assert manifest["report_snapshot_summary"]
    assert manifest["report_snapshot_count"] == len(manifest["report_snapshot_summary"])
    assert manifest["quality_gate_count"] == len(manifest["quality_gate_summary"])
    assert manifest["hardening_summary_count"] == len(manifest["hardening_summary"])
    assert manifest["quality_gate_summary"]
    assert manifest["hardening_summary"]
    assert manifest["evidence_coverage_summary"]["evidence_count"] == len(session.evidence)
    assert manifest["toolchain_fingerprint"]["python_version"]
    assert manifest["secret_redaction_summary"]
    assert "curve_metadata_tool" in manifest["tool_names"]
    assert manifest["local_experiment_summary"]

    overview = json.loads((bundle_dir / "overview.json").read_text(encoding="utf-8"))
    assert overview["session_id"] == session.session_id
    assert overview["tool_count"] == len(manifest["tool_names"])
    assert overview["comparison_ready"] is False
    assert overview["focus_summary"]
    assert overview["report_snapshot_summary"] == manifest["report_snapshot_summary"]
    assert overview["report_snapshot_count"] == manifest["report_snapshot_count"]
    assert overview["filtered_artifact_count"] == 0
    assert overview["export_policy_summary"]
    assert overview["approved_export_roots"]
    assert overview["outputs"]["session_json"] is True
    assert overview["outputs"]["trace_jsonl"] is True
    assert overview["outputs"]["comparative_report_json"] is True
    assert overview["quality_gate_count"] == manifest["quality_gate_count"]
    assert overview["hardening_summary_count"] == manifest["hardening_summary_count"]
    assert overview["quality_gate_summary"]
    assert overview["hardening_summary"]
    assert overview["evidence_coverage_summary"]["evidence_count"] == len(session.evidence)
    assert overview["toolchain_fingerprint"]["python_version"]
    assert overview["secret_redaction_summary"]


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
    assert manifest_payload["filtered_artifact_count"] == 1
    assert manifest_payload["session_export_ready"] is True
    assert manifest_payload["trace_export_ready"] is True
    assert manifest_payload["artifacts"][0]["artifact_path"] == str(allowed_artifact)
    copied_files = list((bundle_dir / "artifacts").iterdir())
    assert len(copied_files) == 1
    assert copied_files[0].name.endswith("allowed.json")
    overview = json.loads((bundle_dir / "overview.json").read_text(encoding="utf-8"))
    assert overview["filtered_artifact_count"] == 1
    assert overview["outputs"]["session_json"] is True
    assert overview["outputs"]["trace_jsonl"] is True


def test_bundle_skips_session_and_trace_outside_approved_roots() -> None:
    run_root = Path(".test_runs") / make_id("bundleunsafe")
    external_root = Path(".test_runs") / make_id("bundleunsafeexternal")
    allowed_root = run_root / "math"
    allowed_root.mkdir(parents=True, exist_ok=True)
    external_root.mkdir(parents=True, exist_ok=True)
    allowed_artifact = allowed_root / "allowed.json"
    allowed_artifact.write_text('{"ok": true}', encoding="utf-8")
    external_session = external_root / "session.json"
    external_trace = external_root / "trace.jsonl"
    external_session.write_text("{}", encoding="utf-8")
    external_trace.write_text("", encoding="utf-8")

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
        seed=ResearchSeed(raw_text="Check bundle export safety for session and trace paths."),
        evidence=[
            Evidence(
                hypothesis_id="hyp_export",
                source="finite_field_check_tool",
                summary="A safe local artifact was recorded.",
                tool_name="finite_field_check_tool",
                experiment_type="finite_field_check",
                workspace_id="workspace_export",
                artifact_paths=[str(allowed_artifact)],
                raw_result={"result": {"status": "ok", "result_data": {}}},
            )
        ],
    )
    session.report = ResearchReport(
        session_id=session.session_id,
        seed_text=session.seed.raw_text,
        summary="Bundle export safety.",
        confidence=ConfidenceLevel.LOW,
    )
    session.session_file_path = str(external_session)
    session.trace_file_path = str(external_trace)

    manifest = build_run_manifest(
        session=session,
        config=config,
        plugin_metadata=[],
        session_path_fallback=external_session,
    )
    bundle_store = ReproducibilityBundleStore(config.storage.bundles_dir)
    bundle_dir = bundle_store.export(session=session, manifest=manifest)
    overview = json.loads((bundle_dir / "overview.json").read_text(encoding="utf-8"))

    assert manifest.session_export_ready is False
    assert manifest.trace_export_ready is False
    assert not (bundle_dir / "session.json").exists()
    assert not (bundle_dir / "trace.jsonl").exists()
    assert overview["outputs"]["session_json"] is False
    assert overview["outputs"]["trace_jsonl"] is False
    assert overview["outputs"]["artifacts_dir"] is True


def test_redaction_masks_secrets_in_trace_and_bundle_snapshots() -> None:
    run_root = Path(".test_runs") / make_id("bundleredact")
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
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    session = ResearchSession(
        seed=ResearchSeed(raw_text="Check secret redaction in exported snapshots.")
    )
    session.report = ResearchReport(
        session_id=session.session_id,
        seed_text=session.seed.raw_text,
        summary="Secret redaction bundle export.",
        confidence=ConfidenceLevel.LOW,
    )
    session_dir = run_root / "sessions"
    trace_dir = run_root / "traces"
    session_dir.mkdir(parents=True, exist_ok=True)
    trace_dir.mkdir(parents=True, exist_ok=True)
    session.session_file_path = str(session_dir / f"{session.session_id}.json")
    Path(session.session_file_path).write_text(
        '{"api_key": "sk-testsecret1234567890", "safe": "ok"}',
        encoding="utf-8",
    )

    trace_writer = TraceWriter(str(trace_dir))
    trace_path = trace_writer.append(
        TraceEvent(
            session_id=session.session_id,
            event_type="provider_call",
            agent="test",
            summary="Trace event with sensitive data.",
            data={"Authorization": "Bearer abcdefghijklmnop", "safe": "ok"},
        )
    )
    session.trace_file_path = str(trace_path)

    manifest = build_run_manifest(
        session=session,
        config=config,
        plugin_metadata=[],
        session_path_fallback=Path(session.session_file_path),
    )
    bundle_store = ReproducibilityBundleStore(config.storage.bundles_dir)
    bundle_dir = bundle_store.export(session=session, manifest=manifest)

    trace_text = trace_path.read_text(encoding="utf-8")
    session_text = (bundle_dir / "session.json").read_text(encoding="utf-8")
    bundle_trace_text = (bundle_dir / "trace.jsonl").read_text(encoding="utf-8")

    assert "sk-testsecret1234567890" not in session_text
    assert "Bearer abcdefghijklmnop" not in trace_text
    assert "Bearer abcdefghijklmnop" not in bundle_trace_text
    assert REDACTED in session_text
    assert REDACTED in trace_text
    assert REDACTED in bundle_trace_text


def test_redaction_helper_recursively_masks_sensitive_data() -> None:
    payload = {
        "safe": "OPENAI_API_KEY is only an environment variable name",
        "nested": {
            "token": "raw-token-value",
            "notes": "OPENROUTER_API_KEY=sk-or-v1-testsecret1234567890",
        },
        "items": [{"password": "hunter2"}],
    }

    redacted = redact_sensitive_data(payload)

    assert redacted["safe"] == "OPENAI_API_KEY is only an environment variable name"
    assert redacted["nested"]["token"] == REDACTED
    assert redacted["nested"]["notes"] == f"OPENROUTER_API_KEY={REDACTED}"
    assert redacted["items"][0]["password"] == REDACTED
