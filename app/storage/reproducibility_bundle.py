from __future__ import annotations

import json
from pathlib import Path
from shutil import copy2

from app.models.run_manifest import RunManifest
from app.models.session import ResearchSession


class ReproducibilityBundleStore:
    """Export inspectable folder-based reproducibility bundles."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path_for_session(self, session_id: str) -> Path:
        return self.directory / session_id

    def manifest_path_for_session(self, session_id: str) -> Path:
        return self.path_for_session(session_id) / "manifest.json"

    def comparative_report_path_for_session(self, session_id: str) -> Path:
        return self.path_for_session(session_id) / "comparative_report.json"

    def overview_path_for_session(self, session_id: str) -> Path:
        return self.path_for_session(session_id) / "overview.json"

    def export(self, *, session: ResearchSession, manifest: RunManifest) -> Path:
        bundle_dir = self.path_for_session(session.session_id)
        bundle_dir.mkdir(parents=True, exist_ok=True)

        if session.session_file_path:
            copy2(session.session_file_path, bundle_dir / "session.json")
        if session.trace_file_path and Path(session.trace_file_path).exists():
            copy2(session.trace_file_path, bundle_dir / "trace.jsonl")

        self._copy_artifacts(manifest=manifest, bundle_dir=bundle_dir)

        manifest_path = bundle_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest.model_dump(mode="json"), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        if session.comparative_report is not None:
            self.comparative_report_path_for_session(session.session_id).write_text(
                json.dumps(session.comparative_report.model_dump(mode="json"), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        self.overview_path_for_session(session.session_id).write_text(
            json.dumps(self._bundle_overview(session=session, manifest=manifest), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        (bundle_dir / "README.txt").write_text(
            self._bundle_notes(session=session, manifest=manifest),
            encoding="utf-8",
        )
        return bundle_dir

    def _copy_artifacts(self, *, manifest: RunManifest, bundle_dir: Path) -> None:
        artifacts_dir = bundle_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        copied: set[Path] = set()
        for index, artifact in enumerate(manifest.artifacts, start=1):
            source = Path(artifact.artifact_path)
            if not source.exists() or not source.is_file() or source in copied:
                continue
            copied.add(source)
            target_name = f"{artifact.workspace_id or 'artifact'}_{index}_{source.name}"
            copy2(source, artifacts_dir / target_name)

    def _bundle_notes(self, *, session: ResearchSession, manifest: RunManifest) -> str:
        lines = [
            "EllipticZero Reproducibility Bundle",
            f"Session ID: {session.session_id}",
            f"Confidence: {manifest.confidence or 'unavailable'}",
            f"Seed Hash: {manifest.seed_hash}",
            f"Replay Run: {'yes' if manifest.is_replay else 'no'}",
            "",
            "Contents:",
            "- overview.json: concise export overview with focus, confidence, comparison status, and quality/hardening counts",
            "- session.json: saved session snapshot",
            "- trace.jsonl: append-only execution trace when available",
            "- manifest.json: reproducibility manifest",
            "- comparative_report.json: machine-readable comparative reporting snapshot when available",
            "- artifacts/: copied local research artifacts when available",
        ]
        return "\n".join(lines) + "\n"

    def _bundle_overview(self, *, session: ResearchSession, manifest: RunManifest) -> dict[str, object]:
        return {
            "session_id": session.session_id,
            "confidence": manifest.confidence,
            "report_summary": manifest.report_summary,
            "selected_pack_name": manifest.selected_pack_name,
            "research_mode": manifest.research_mode,
            "research_target_kind": manifest.research_target_kind,
            "research_target_reference": manifest.research_target_reference,
            "comparison_ready": manifest.comparison_ready,
            "comparison_baseline_session_id": manifest.comparison_baseline_session_id,
            "artifact_count": manifest.artifact_count,
            "tool_count": len(manifest.tool_names),
            "focus_summary": list(manifest.report_focus_summary),
            "quality_gate_count": manifest.quality_gate_count,
            "hardening_summary_count": manifest.hardening_summary_count,
            "quality_gate_summary": list(manifest.quality_gate_summary),
            "hardening_summary": list(manifest.hardening_summary),
            "outputs": {
                "session_json": bool(session.session_file_path),
                "trace_jsonl": bool(session.trace_file_path),
                "comparative_report_json": bool(session.comparative_report is not None),
                "artifacts_dir": True,
            },
        }
