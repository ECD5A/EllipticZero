from __future__ import annotations

import platform
import sys
from pathlib import Path

from app.config import AppConfig
from app.core.reporting_helpers import (
    build_local_experiment_summary,
    build_manifest_focus_summary,
    collect_artifact_references,
    ordered_unique,
    unique_metadata_snapshots,
)
from app.models.plugin_metadata import PluginMetadata
from app.models.run_manifest import RunArtifactReference, RunManifest
from app.models.session import ResearchSession
from app.storage.fingerprints import hash_file, hash_text


def build_run_manifest(
    *,
    session: ResearchSession,
    config: AppConfig,
    plugin_metadata: list[PluginMetadata],
    session_path_fallback: Path,
) -> RunManifest:
    raw_artifact_references = collect_artifact_references(session)
    allowed_artifact_roots = [
        Path(config.storage.artifacts_dir),
        Path(config.storage.math_artifacts_dir),
        Path(config.storage.sessions_dir),
        Path(config.storage.traces_dir),
    ]
    artifact_references = _filter_safe_artifact_references(
        raw_artifact_references,
        allowed_roots=allowed_artifact_roots,
    )
    session_path = Path(session.session_file_path or session_path_fallback)
    trace_path = Path(session.trace_file_path) if session.trace_file_path else None

    return RunManifest(
        session_id=session.session_id,
        seed_hash=hash_text(session.seed.raw_text),
        session_hash=hash_file(session_path) if session_path.exists() else None,
        session_file_path=str(session_path),
        trace_file_path=str(trace_path) if trace_path is not None else None,
        comparative_report_path=session.comparative_report_file_path,
        artifact_paths=[item.artifact_path for item in artifact_references],
        artifacts=artifact_references,
        artifact_count=len(artifact_references),
        tool_names=ordered_unique(
            job.tool_name for job in session.jobs if job.tool_name
        ),
        tool_metadata_snapshots=unique_metadata_snapshots(session),
        experiment_types=ordered_unique(
            evidence.experiment_type for evidence in session.evidence if evidence.experiment_type
        ),
        local_experiment_summary=build_local_experiment_summary(session),
        report_focus_summary=build_manifest_focus_summary(session),
        quality_gate_summary=list(session.report.quality_gates) if session.report is not None else [],
        quality_gate_count=len(session.report.quality_gates) if session.report is not None else 0,
        hardening_summary=list(session.report.hardening_summary) if session.report is not None else [],
        hardening_summary_count=len(session.report.hardening_summary) if session.report is not None else 0,
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
            f"filtered_artifact_reference_count={max(0, len(raw_artifact_references) - len(artifact_references))}",
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


def _filter_safe_artifact_references(
    references: list[RunArtifactReference],
    *,
    allowed_roots: list[Path],
) -> list[RunArtifactReference]:
    normalized_roots = [_safe_resolve(root) for root in allowed_roots if root]
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
