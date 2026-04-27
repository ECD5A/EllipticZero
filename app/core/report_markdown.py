from __future__ import annotations

import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.core.replay_loader import LoadedReplaySource
from app.models.report import ResearchReport
from app.models.run_manifest import RunManifest
from app.models.session import ResearchSession

REDACTED = "[REDACTED]"

_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{12,}"),
    re.compile(r"(?i)\b(sk|sk-or|sk-ant|ghp|github_pat)_[A-Za-z0-9_]{12,}"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
)

_ENV_ASSIGNMENT_PATTERNS = tuple(
    re.compile(rf"(?i)\b{re.escape(name)}\s*=\s*([^\s,;]+)")
    for name in (
        "ANTHROPIC_API_KEY",
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
    )
)


REPORT_SECTIONS: tuple[tuple[str, str], ...] = (
    ("contract_triage_snapshot", "Smart-Contract Triage Snapshot"),
    ("remediation_delta_summary", "Remediation Delta Summary"),
    ("ecc_triage_snapshot", "ECC Triage Snapshot"),
    ("confidence_rationale", "Confidence Rationale"),
    ("contract_overview", "Contract Overview"),
    ("contract_finding_cards", "Finding Cards"),
    ("ecc_benchmark_summary", "ECC Benchmark Summary"),
    ("evidence_profile", "Evidence Profile"),
    ("evidence_coverage_summary", "Evidence Coverage"),
    ("validation_posture", "Validation Posture"),
    ("shared_follow_up", "Shared Follow-Up"),
    ("calibration_blockers", "Calibration Blockers"),
    ("reproducibility_summary", "Reproducibility Summary"),
    ("quality_gates", "Quality Gates"),
    ("hardening_summary", "Hardening Summary"),
    ("toolchain_fingerprint_summary", "Toolchain Fingerprint"),
    ("secret_redaction_summary", "Secret Redaction"),
    ("ecc_benchmark_posture", "ECC Benchmark Posture"),
    ("ecc_family_coverage", "ECC Family Coverage"),
    ("ecc_coverage_matrix", "ECC Coverage Matrix"),
    ("ecc_benchmark_case_summaries", "ECC Benchmark Case Summaries"),
    ("ecc_review_focus", "ECC Review Focus"),
    ("ecc_residual_risk", "ECC Residual Risk"),
    ("ecc_signal_consensus", "ECC Signal Consensus"),
    ("ecc_validation_matrix", "ECC Validation Matrix"),
    ("ecc_comparison_focus", "ECC Comparison Focus"),
    ("ecc_benchmark_delta", "ECC Benchmark Delta"),
    ("ecc_regression_summary", "ECC Regression Summary"),
    ("ecc_review_queue", "ECC Review Queue"),
    ("ecc_exit_criteria", "ECC Exit Criteria"),
    ("contract_inventory_summary", "Contract Inventory"),
    ("contract_protocol_map", "Contract Protocol Map"),
    ("contract_protocol_invariants", "Contract Protocol Invariants"),
    ("contract_signal_consensus", "Contract Signal Consensus"),
    ("contract_validation_matrix", "Contract Validation Matrix"),
    ("contract_benchmark_posture", "Contract Benchmark Posture"),
    ("contract_benchmark_pack_summary", "Contract Benchmark Pack Summary"),
    ("contract_benchmark_case_summaries", "Contract Benchmark Case Summaries"),
    ("contract_repo_priorities", "Contract Repo Priorities"),
    ("contract_repo_triage", "Contract Repo Triage"),
    ("contract_casebook_coverage", "Contract Casebook Coverage"),
    ("contract_casebook_coverage_matrix", "Contract Casebook Coverage Matrix"),
    ("contract_casebook_case_studies", "Contract Casebook Case Studies"),
    ("contract_casebook_priority_cases", "Contract Casebook Priority Cases"),
    ("contract_casebook_gaps", "Contract Casebook Gaps"),
    ("contract_casebook_benchmark_support", "Contract Casebook Benchmark Support"),
    ("contract_casebook_triage", "Contract Casebook Triage"),
    ("contract_toolchain_alignment", "Contract Toolchain Alignment"),
    ("contract_review_queue", "Contract Review Queue"),
    ("contract_compile_summary", "Contract Compile Summary"),
    ("contract_surface_summary", "Contract Surface Summary"),
    ("contract_priority_findings", "Contract Priority Findings"),
    ("contract_static_findings", "Contract Static Findings"),
    ("contract_testbed_findings", "Contract Testbed Findings"),
    ("contract_remediation_validation", "Contract Remediation Validation"),
    ("contract_review_focus", "Contract Review Focus"),
    ("contract_remediation_guidance", "Contract Remediation Guidance"),
    ("contract_remediation_follow_up", "Contract Remediation Follow-Up"),
    ("contract_residual_risk", "Contract Residual Risk"),
    ("contract_exit_criteria", "Contract Exit Criteria"),
    ("contract_manual_review_items", "Contract Manual Review Items"),
    ("before_after_comparison", "Before/After Comparison"),
    ("regression_flags", "Regression Flags"),
    ("agent_contributions", "Agent Contributions"),
    ("local_experiment_summary", "Local Experiment Summary"),
    ("local_signal_summary", "Local Signal Summary"),
    ("dead_end_summary", "Dead-End Summary"),
    ("next_defensive_leads", "Next Defensive Leads"),
    ("tested_hypotheses", "Tested Hypotheses"),
    ("tool_usage_summary", "Tool Usage"),
    ("comparative_findings", "Comparative Findings"),
    ("exploratory_findings", "Exploratory Findings"),
    ("anomalies", "Anomalies"),
    ("recommendations", "Recommendations"),
    ("manual_review_items", "Manual Review Items"),
)


def build_saved_run_report_markdown(*, loaded_source: LoadedReplaySource) -> str:
    """Build a human-readable Markdown report from a saved replay source."""

    session = loaded_source.session
    manifest = loaded_source.manifest
    if session is not None and session.report is not None:
        return build_session_report_markdown(
            session=session,
            manifest=manifest,
            source_type=loaded_source.source_type,
            source_path=loaded_source.source_path,
        )
    if manifest is not None:
        return build_manifest_report_markdown(
            manifest=manifest,
            source_type=loaded_source.source_type,
            source_path=loaded_source.source_path,
        )
    raise ValueError("Saved source does not contain a report or manifest snapshot.")


def build_session_report_markdown(
    *,
    session: ResearchSession,
    manifest: RunManifest | None = None,
    source_type: str = "session",
    source_path: str | None = None,
) -> str:
    """Build a Markdown report without embedding the full seed or contract source."""

    if session.report is None:
        raise ValueError("Session does not contain a report.")

    report = session.report
    lines = [
        "# EllipticZero Report",
        "",
        _metadata_table(
            _session_metadata(
                session=session,
                report=report,
                manifest=manifest,
                source_type=source_type,
                source_path=source_path,
            )
        ),
        "",
        "## Summary",
        "",
        report.summary,
        "",
        "## Confidence",
        "",
        f"`{report.confidence.value}`",
    ]

    for field_name, title in REPORT_SECTIONS:
        items = _string_items(getattr(report, field_name, []))
        if not items:
            continue
        lines.extend(["", f"## {title}", ""])
        lines.extend(f"- {item}" for item in items)

    lines.extend(
        [
            "",
            "## Evidence Boundary",
            "",
            (
                "Model output is interpretation. Local tool outputs, saved session data, "
                "traces, manifests, bundles, and human review carry the evidence trail."
            ),
            "",
        ]
    )
    return _redact_text("\n".join(lines)).rstrip() + "\n"


def build_manifest_report_markdown(
    *,
    manifest: RunManifest,
    source_type: str = "manifest",
    source_path: str | None = None,
) -> str:
    lines = [
        "# EllipticZero Saved-Run Snapshot",
        "",
        _metadata_table(
            {
                "Session ID": manifest.session_id,
                "Source type": source_type,
                "Source path": source_path,
                "Research mode": manifest.research_mode,
                "Selected pack": manifest.selected_pack_name,
                "Confidence": manifest.confidence,
                "Seed hash": manifest.seed_hash,
                "Tool count": str(len(manifest.tool_names)),
                "Artifact count": str(manifest.artifact_count),
            }
        ),
    ]
    if manifest.report_summary:
        lines.extend(["", "## Summary", "", manifest.report_summary])
    _extend_section(lines, "Report Snapshot", manifest.report_snapshot_summary)
    _extend_section(lines, "Focus Summary", manifest.report_focus_summary)
    _extend_section(lines, "Quality Gates", manifest.quality_gate_summary)
    _extend_section(lines, "Hardening Summary", manifest.hardening_summary)
    _extend_section(lines, "Export Policy", manifest.export_policy_summary)
    lines.extend(
        [
            "",
            "## Evidence Boundary",
            "",
            (
                "This Markdown file is a compact snapshot. Review the original session, "
                "trace, manifest, bundle, and local tool outputs before treating any "
                "signal as confirmed."
            ),
            "",
        ]
    )
    return _redact_text("\n".join(lines)).rstrip() + "\n"


def write_report_markdown_file(
    *,
    loaded_source: LoadedReplaySource,
    output_path: str | Path,
) -> Path:
    markdown = build_saved_run_report_markdown(loaded_source=loaded_source)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(markdown, encoding="utf-8")
    return destination


def render_report_markdown_export_result(*, output_path: Path, language: str) -> str:
    if language == "ru":
        return "\n".join(
            [
                "Markdown report export complete",
                f"- Файл: {output_path}",
                "- Назначение: человекочитаемый saved-run отчёт для review, обмена и архива.",
                "- Граница: Markdown не заменяет session/trace/manifest/bundle и ручную проверку.",
            ]
        )
    return "\n".join(
        [
            "Markdown report export complete",
            f"- File: {output_path}",
            "- Purpose: human-readable saved-run report for review, sharing, and archive.",
            "- Boundary: Markdown does not replace session/trace/manifest/bundle evidence or review.",
        ]
    )


def _session_metadata(
    *,
    session: ResearchSession,
    report: ResearchReport,
    manifest: RunManifest | None,
    source_type: str,
    source_path: str | None,
) -> dict[str, str | None]:
    return {
        "Session ID": session.session_id,
        "Original session ID": session.original_session_id,
        "Source type": source_type,
        "Source path": source_path,
        "Research mode": report.research_mode or session.research_mode.value,
        "Research target": report.research_target,
        "Selected pack": report.selected_pack_name or session.selected_pack_name,
        "Exploration profile": report.exploration_profile,
        "Seed hash": _hash_text(session.seed.raw_text),
        "Session JSON": session.session_file_path,
        "Trace JSONL": session.trace_file_path,
        "Manifest": session.manifest_file_path,
        "Bundle": session.bundle_dir,
        "Comparative report": session.comparative_report_file_path,
        "Tool count": str(len(manifest.tool_names)) if manifest is not None else str(len(session.jobs)),
        "Artifact count": (
            str(manifest.artifact_count)
            if manifest is not None
            else str(sum(len(evidence.artifact_paths) for evidence in session.evidence))
        ),
    }


def _metadata_table(items: dict[str, Any]) -> str:
    lines = ["| Field | Value |", "| --- | --- |"]
    for key, value in items.items():
        rendered = _table_value(value)
        if not rendered:
            continue
        lines.append(f"| {_escape_table_cell(key)} | {_escape_table_cell(rendered)} |")
    return "\n".join(lines)


def _table_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    return str(value)


def _escape_table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", "<br>")


def _extend_section(lines: list[str], title: str, items: list[str]) -> None:
    clean_items = _string_items(items)
    if not clean_items:
        return
    lines.extend(["", f"## {title}", ""])
    lines.extend(f"- {item}" for item in clean_items)


def _string_items(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]


def _hash_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _redact_text(value: str) -> str:
    redacted = value
    for pattern in _ENV_ASSIGNMENT_PATTERNS:
        redacted = pattern.sub(
            lambda match: match.group(0).split("=")[0].rstrip() + "=" + REDACTED,
            redacted,
        )
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(REDACTED, redacted)
    return redacted
