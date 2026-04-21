from __future__ import annotations

import platform
import shutil
import sys
from importlib import metadata as importlib_metadata
from pathlib import Path
from typing import Any

from app.config import AppConfig
from app.core.reporting_helpers import (
    build_local_experiment_summary,
    build_manifest_focus_summary,
    build_report_snapshot_summary,
    collect_artifact_references,
    ordered_unique,
    unique_metadata_snapshots,
)
from app.models.plugin_metadata import PluginMetadata
from app.models.run_manifest import RunArtifactReference, RunManifest
from app.models.session import ResearchSession
from app.storage.fingerprints import hash_file, hash_text
from app.storage.redaction import redaction_summary


def build_run_manifest(
    *,
    session: ResearchSession,
    config: AppConfig,
    plugin_metadata: list[PluginMetadata],
    session_path_fallback: Path,
) -> RunManifest:
    raw_artifact_references = collect_artifact_references(session)
    allowed_export_roots = [
        Path(config.storage.artifacts_dir),
        Path(config.storage.math_artifacts_dir),
        Path(config.storage.sessions_dir),
        Path(config.storage.traces_dir),
    ]
    normalized_export_roots = _normalized_export_roots(allowed_export_roots)
    artifact_references = _filter_safe_artifact_references(
        raw_artifact_references,
        allowed_roots=allowed_export_roots,
    )
    session_path = Path(session.session_file_path or session_path_fallback)
    trace_path = Path(session.trace_file_path) if session.trace_file_path else None
    safe_session_export = _is_safe_export_file(
        session_path,
        allowed_roots=normalized_export_roots,
    )
    safe_trace_export = _is_safe_export_file(
        trace_path,
        allowed_roots=normalized_export_roots,
    )
    filtered_artifact_count = max(0, len(raw_artifact_references) - len(artifact_references))
    comparative_export_ready = bool(session.comparative_report is not None)
    tool_metadata_snapshots = unique_metadata_snapshots(session)
    evidence_coverage_summary = _build_evidence_coverage_summary(
        session=session,
        artifact_references=artifact_references,
        filtered_artifact_count=filtered_artifact_count,
    )
    toolchain_fingerprint = _build_toolchain_fingerprint(
        session=session,
        config=config,
        plugin_metadata=plugin_metadata,
        tool_metadata_snapshots=tool_metadata_snapshots,
    )
    report_snapshot_summary = build_report_snapshot_summary(session)

    return RunManifest(
        session_id=session.session_id,
        seed_hash=hash_text(session.seed.raw_text),
        session_hash=hash_file(session_path) if session_path.exists() else None,
        session_file_path=str(session_path),
        trace_file_path=str(trace_path) if trace_path is not None else None,
        comparative_report_path=session.comparative_report_file_path,
        approved_export_roots=[str(root) for root in normalized_export_roots],
        export_policy_summary=[
            "Export policy: only approved local storage roots are eligible for bundle copy operations.",
            "Secret redaction policy: session, trace, manifest, comparative-report, and overview JSON are redacted before export.",
            f"Session export readiness: {'ready' if safe_session_export else 'skipped'}",
            f"Trace export readiness: {'ready' if safe_trace_export else 'skipped'}",
            f"Artifact export filtering: kept={len(artifact_references)} filtered={filtered_artifact_count}",
            f"Comparative export readiness: {'ready' if comparative_export_ready else 'not available'}",
        ],
        filtered_artifact_count=filtered_artifact_count,
        session_export_ready=safe_session_export,
        trace_export_ready=safe_trace_export,
        comparative_export_ready=comparative_export_ready,
        artifact_paths=[item.artifact_path for item in artifact_references],
        artifacts=artifact_references,
        artifact_count=len(artifact_references),
        tool_names=ordered_unique(
            job.tool_name for job in session.jobs if job.tool_name
        ),
        tool_metadata_snapshots=tool_metadata_snapshots,
        experiment_types=ordered_unique(
            evidence.experiment_type for evidence in session.evidence if evidence.experiment_type
        ),
        local_experiment_summary=build_local_experiment_summary(session),
        report_focus_summary=build_manifest_focus_summary(session),
        report_snapshot_summary=report_snapshot_summary,
        report_snapshot_count=len(report_snapshot_summary),
        quality_gate_summary=list(session.report.quality_gates) if session.report is not None else [],
        quality_gate_count=len(session.report.quality_gates) if session.report is not None else 0,
        hardening_summary=list(session.report.hardening_summary) if session.report is not None else [],
        hardening_summary_count=len(session.report.hardening_summary) if session.report is not None else 0,
        evidence_coverage_summary=evidence_coverage_summary,
        toolchain_fingerprint=toolchain_fingerprint,
        secret_redaction_summary=redaction_summary(),
        research_mode=session.research_mode.value,
        exploration_profile=(
            session.sandbox_spec.exploration_profile.value
            if session.sandbox_spec is not None
            else None
        ),
        sandbox_id=session.sandbox_spec.sandbox_id if session.sandbox_spec is not None else None,
        selected_pack_name=session.selected_pack_name,
        recommended_pack_names=list(session.recommended_pack_names),
        executed_pack_steps=list(session.executed_pack_steps),
        exploratory_rounds_executed=session.exploratory_rounds_executed,
        research_target_kind=(
            session.research_target.target_kind if session.research_target is not None else None
        ),
        research_target_reference=(
            session.research_target.target_reference if session.research_target is not None else None
        ),
        research_target_origin=(
            session.research_target.target_origin if session.research_target is not None else None
        ),
        synthetic_target_name=(
            session.research_target.synthetic_target_name if session.research_target is not None else None
        ),
        research_target_profile=(
            session.research_target.target_profile if session.research_target is not None else None
        ),
        confidence=session.report.confidence.value if session.report is not None else None,
        report_summary=session.report.summary if session.report is not None else None,
        comparison_ready=bool(
            session.comparative_report is not None
            and session.comparative_report.cross_session_comparison is not None
        ),
        environment_summary={
            "python_version": sys.version.split()[0],
            "ellipticzero_version": str(toolchain_fingerprint.get("ellipticzero_version", "unknown")),
            "platform": platform.platform(),
            "llm_provider": config.llm.default_provider,
            "default_model": config.llm.default_model,
            "is_replay": str(session.is_replay).lower(),
            "research_mode": session.research_mode.value,
            "loaded_plugins": ",".join(
                item.plugin_name
                for item in plugin_metadata
                if item.load_status == "loaded"
            )
            or "none",
            "failed_plugins": ",".join(
                item.plugin_name
                for item in plugin_metadata
                if item.load_status != "loaded"
            )
            or "none",
        },
        notes=[
            "Folder-based reproducibility bundle exported locally.",
            f"evidence_count={len(session.evidence)}",
            f"workspace_count={len(session.math_workspaces)}",
            f"plugin_count={len(plugin_metadata)}",
            f"artifact_reference_count={len(artifact_references)}",
            f"filtered_artifact_reference_count={filtered_artifact_count}",
            f"tool_backed_evidence_count={evidence_coverage_summary['tool_backed_evidence_count']}",
            f"unique_tool_count={evidence_coverage_summary['unique_tool_count']}",
            f"experiment_type_count={evidence_coverage_summary['experiment_type_count']}",
            f"session_export_ready={str(safe_session_export).lower()}",
            f"trace_export_ready={str(safe_trace_export).lower()}",
            f"comparative_export_ready={str(comparative_export_ready).lower()}",
            f"explored_branch_count={len(session.explored_hypothesis_ids)}",
            f"exploratory_round_count={session.exploratory_rounds_executed}",
            (
                f"exploration_profile={session.sandbox_spec.exploration_profile.value}"
                if session.sandbox_spec is not None
                else "exploration_profile=none"
            ),
            f"selected_pack_name={session.selected_pack_name or 'none'}",
            f"comparative_analysis_generated={str(bool(session.comparative_report and session.comparative_report.analysis_generated)).lower()}",
            f"comparison_baseline_session_id={session.comparison_baseline_session_id or 'none'}",
        ]
        + list(session.replay_notes),
        is_replay=session.is_replay,
        replay_source_type=session.replay_source_type,
        replay_source_path=session.replay_source_path,
        original_session_id=session.original_session_id,
        replay_mode=session.replay_mode,
        comparison_baseline_session_id=session.comparison_baseline_session_id,
        comparison_baseline_source_type=session.comparison_baseline_source_type,
        comparison_baseline_source_path=session.comparison_baseline_source_path,
    )


def _build_evidence_coverage_summary(
    *,
    session: ResearchSession,
    artifact_references: list[RunArtifactReference],
    filtered_artifact_count: int,
) -> dict[str, Any]:
    tool_names = ordered_unique(
        (evidence.tool_name or evidence.source) for evidence in session.evidence
    )
    experiment_types = ordered_unique(
        evidence.experiment_type for evidence in session.evidence if evidence.experiment_type
    )
    report = session.report
    return {
        "evidence_count": len(session.evidence),
        "tool_backed_evidence_count": sum(1 for evidence in session.evidence if evidence.tool_name),
        "unique_tool_count": len(tool_names),
        "experiment_type_count": len(experiment_types),
        "experiment_types": experiment_types,
        "artifact_reference_count": len(artifact_references),
        "filtered_artifact_reference_count": filtered_artifact_count,
        "finding_card_count": len(report.contract_finding_cards) if report is not None else 0,
        "manual_review_item_count": len(report.manual_review_items) if report is not None else 0,
        "quality_gate_count": len(report.quality_gates) if report is not None else 0,
        "before_after_ready": bool(
            session.comparative_report is not None
            and session.comparative_report.cross_session_comparison is not None
        ),
    }


def _build_toolchain_fingerprint(
    *,
    session: ResearchSession,
    config: AppConfig,
    plugin_metadata: list[PluginMetadata],
    tool_metadata_snapshots: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "ellipticzero_version": _package_version(),
        "python_version": sys.version.split()[0],
        "python_implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "llm": {
            "default_provider": config.llm.default_provider,
            "default_model": config.llm.default_model,
            "fallback_provider": config.llm.fallback_provider,
            "fallback_model": config.llm.fallback_model,
            "timeout_seconds": config.llm.timeout_seconds,
            "max_request_tokens": config.llm.max_request_tokens,
            "max_total_requests_per_session": config.llm.max_total_requests_per_session,
        },
        "provider_auth_env_names": _provider_auth_env_names(config),
        "local_research": {
            "sage_enabled": config.sage.enabled,
            "sympy_enabled": config.local_research.sympy_enabled,
            "smart_contract_compile_enabled": (
                config.local_research.smart_contract_compile_enabled
            ),
            "slither_enabled": config.local_research.slither_enabled,
            "echidna_enabled": config.local_research.echidna_enabled,
            "foundry_enabled": config.local_research.foundry_enabled,
            "formal_backend": config.local_research.formal_backend,
        },
        "external_tools": _external_tool_availability(config),
        "registered_tool_metadata": tool_metadata_snapshots,
        "plugin_fingerprint": [
            {
                "plugin_name": item.plugin_name,
                "load_status": item.load_status,
                "tool_count": len(item.tools),
            }
            for item in plugin_metadata
        ],
        "session_mode": {
            "is_replay": session.is_replay,
            "research_mode": session.research_mode.value,
            "selected_pack_name": session.selected_pack_name,
        },
    }


def _provider_auth_env_names(config: AppConfig) -> dict[str, str | None]:
    return {
        provider_name: provider_settings.get("api_key_env")
        for provider_name, provider_settings in config.providers.model_dump().items()
        if isinstance(provider_settings, dict)
    }


def _external_tool_availability(config: AppConfig) -> dict[str, dict[str, str | bool]]:
    configured = {
        "sage": config.sage.binary,
        "solc": config.local_research.solc_binary,
        "solcjs": config.local_research.solcjs_binary,
        "slither": config.local_research.slither_binary,
        "echidna": config.local_research.echidna_binary,
        "forge": config.local_research.forge_binary,
    }
    availability: dict[str, dict[str, str | bool]] = {}
    for tool_name, binary in configured.items():
        resolved = shutil.which(binary)
        availability[tool_name] = {
            "configured_binary": binary,
            "available": resolved is not None,
            "resolved_path": resolved or "",
        }
    return availability


def _package_version() -> str:
    try:
        return importlib_metadata.version("ellipticzero")
    except importlib_metadata.PackageNotFoundError:
        return "0.1.0"


def _filter_safe_artifact_references(
    references: list[RunArtifactReference],
    *,
    allowed_roots: list[Path],
) -> list[RunArtifactReference]:
    normalized_roots = _normalized_export_roots(allowed_roots)
    if not normalized_roots:
        return []

    safe_references: list[RunArtifactReference] = []
    for item in references:
        artifact_path = Path(item.artifact_path)
        resolved = _safe_resolve(artifact_path)
        if resolved is None or not artifact_path.exists() or not artifact_path.is_file():
            continue
        if not any(_is_relative_to(resolved, root) for root in normalized_roots):
            continue
        safe_references.append(item)
    return safe_references


def _normalized_export_roots(roots: list[Path]) -> list[Path]:
    return [resolved for root in roots if root for resolved in [_safe_resolve(root)] if resolved is not None]


def _is_safe_export_file(path: Path | None, *, allowed_roots: list[Path]) -> bool:
    if path is None or not allowed_roots or not path.exists() or not path.is_file():
        return False
    resolved = _safe_resolve(path)
    if resolved is None:
        return False
    return any(_is_relative_to(resolved, root) for root in allowed_roots)


def _safe_resolve(path: Path) -> Path | None:
    try:
        return path.resolve(strict=False)
    except OSError:
        return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
