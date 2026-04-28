from __future__ import annotations

from pathlib import Path

from app.core.replay_loader import LoadedReplaySource
from app.core.report_markdown import (
    build_saved_run_report_markdown,
    write_report_markdown_file,
)
from app.core.seed_parsing import build_smart_contract_seed
from app.main import build_parser
from app.models.report import ResearchReport
from app.models.run_manifest import RunManifest
from app.models.seed import ResearchSeed
from app.models.session import ResearchSession
from app.types import ConfidenceLevel


def _saved_contract_run() -> LoadedReplaySource:
    seed_text = build_smart_contract_seed(
        idea_text="Review vault permission lanes.",
        contract_code="pragma solidity ^0.8.20; contract Vault {}",
        source_label="contracts/Vault.sol",
    )
    report = ResearchReport(
        session_id="session_markdown",
        seed_text=seed_text,
        summary="Bounded smart-contract review.",
        contract_finding_cards=[
            "Potential finding: externally reachable value-flow lane requires review."
        ],
        contract_manual_review_items=[
            "Manual review: confirm admin role assumptions before deployment."
        ],
        quality_gates=[
            "Evidence gate: local tool output must be inspected before escalation."
        ],
        confidence=ConfidenceLevel.MANUAL_REVIEW_REQUIRED,
    )
    session = ResearchSession(
        session_id="session_markdown",
        seed=ResearchSeed(raw_text=seed_text),
        report=report,
        selected_pack_name="vault_permission_benchmark_pack",
        session_file_path="artifacts/sessions/session_markdown.json",
        trace_file_path="artifacts/traces/session_markdown.jsonl",
        bundle_dir="artifacts/bundles/session_markdown",
    )
    return LoadedReplaySource(
        source_type="bundle",
        source_path="artifacts/bundles/session_markdown",
        session=session,
        original_session_id="session_markdown",
        tool_names=["contract_parser_tool", "contract_surface_tool"],
        experiment_types=["smart_contract_parse", "smart_contract_surface"],
        selected_pack_name="vault_permission_benchmark_pack",
    )


def test_saved_run_markdown_report_avoids_embedded_contract_code(tmp_path: Path) -> None:
    loaded = _saved_contract_run()

    markdown = build_saved_run_report_markdown(loaded_source=loaded)

    assert markdown.startswith("# EllipticZero Report")
    assert "Bounded smart-contract review." in markdown
    assert "## Review Snapshot" in markdown
    assert "Primary signal" in markdown
    assert "Next review step" in markdown
    assert "Evidence posture" in markdown
    assert "## Finding Cards" in markdown
    assert "externally reachable value-flow" in markdown
    assert "## Evidence Boundary" in markdown
    assert "Seed hash" in markdown
    assert "pragma solidity" not in markdown
    assert "contract Vault" not in markdown

    output_path = write_report_markdown_file(
        loaded_source=loaded,
        output_path=tmp_path / "session_markdown.md",
    )

    assert output_path.read_text(encoding="utf-8") == markdown


def test_manifest_only_markdown_report_uses_snapshot_sections() -> None:
    manifest = RunManifest(
        session_id="session_manifest_only",
        seed_hash="abc123",
        session_hash=None,
        session_file_path="artifacts/sessions/session_manifest_only.json",
        trace_file_path=None,
        comparative_report_path=None,
        export_policy_summary=["Export policy: approved roots only."],
        session_export_ready=False,
        trace_export_ready=False,
        comparative_export_ready=False,
        artifact_count=0,
        filtered_artifact_count=0,
        artifacts=[],
        tool_names=["contract_parser_tool"],
        experiment_types=["smart_contract_parse"],
        local_experiment_summary=[],
        report_focus_summary=["Focus on vault permission lanes."],
        report_snapshot_summary=["Snapshot: manual review required."],
        report_snapshot_count=1,
        quality_gate_summary=["Quality gate: inspect local evidence."],
        quality_gate_count=1,
        hardening_summary=[],
        hardening_summary_count=0,
        evidence_coverage_summary={"evidence_count": 1},
        toolchain_fingerprint={},
        secret_redaction_summary=[],
        environment_summary={},
        approved_export_roots=[],
        notes=[],
        is_replay=False,
        replay_source_type=None,
        replay_source_path=None,
        original_session_id=None,
        replay_mode=None,
        comparison_ready=False,
        comparison_baseline_session_id=None,
        comparison_baseline_source_type=None,
        comparison_baseline_source_path=None,
        research_mode="default",
        exploration_profile=None,
        sandbox_id=None,
        selected_pack_name="vault_permission_benchmark_pack",
        recommended_pack_names=[],
        executed_pack_steps=[],
        exploratory_rounds_executed=0,
        research_target_kind=None,
        research_target_reference=None,
        research_target_origin=None,
        synthetic_target_name=None,
        research_target_profile=None,
        confidence="manual_review_required",
        report_summary="Manifest-only saved-run summary.",
    )
    loaded = LoadedReplaySource(
        source_type="manifest",
        source_path="artifacts/bundles/session_manifest_only/manifest.json",
        manifest=manifest,
    )

    markdown = build_saved_run_report_markdown(loaded_source=loaded)

    assert markdown.startswith("# EllipticZero Saved-Run Snapshot")
    assert "Manifest-only saved-run summary." in markdown
    assert "## Report Snapshot" in markdown
    assert "Snapshot: manual review required." in markdown


def test_parser_supports_saved_run_markdown_export() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--replay-bundle",
            "artifacts/bundles/session_markdown",
            "--export-report-md",
            "artifacts/reports/session_markdown.md",
        ]
    )

    assert args.replay_bundle == "artifacts/bundles/session_markdown"
    assert args.export_report_md == "artifacts/reports/session_markdown.md"
