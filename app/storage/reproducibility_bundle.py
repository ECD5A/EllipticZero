from __future__ import annotations

import json
from pathlib import Path
from shutil import copy2

from app.core.report_markdown import build_session_report_markdown
from app.models.run_manifest import RunManifest
from app.models.session import ResearchSession
from app.storage.redaction import redact_sensitive_data, redact_text


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

    def report_markdown_path_for_session(self, session_id: str) -> Path:
        return self.path_for_session(session_id) / "report.md"

    def export(self, *, session: ResearchSession, manifest: RunManifest) -> Path:
        bundle_dir = self.path_for_session(session.session_id)
        bundle_dir.mkdir(parents=True, exist_ok=True)

        copied_session = False
        copied_trace = False
        if manifest.session_export_ready and session.session_file_path:
            self._copy_redacted_json_snapshot(
                Path(session.session_file_path),
                bundle_dir / "session.json",
                jsonl=False,
            )
            copied_session = True
        if manifest.trace_export_ready and session.trace_file_path and Path(session.trace_file_path).exists():
            self._copy_redacted_json_snapshot(
                Path(session.trace_file_path),
                bundle_dir / "trace.jsonl",
                jsonl=True,
            )
            copied_trace = True

        self._copy_artifacts(manifest=manifest, bundle_dir=bundle_dir)

        manifest_path = bundle_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                redact_sensitive_data(manifest.model_dump(mode="json")),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        if session.comparative_report is not None:
            self.comparative_report_path_for_session(session.session_id).write_text(
                json.dumps(
                    redact_sensitive_data(session.comparative_report.model_dump(mode="json")),
                    indent=2,
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
        report_markdown_exported = False
        if session.report is not None:
            self.report_markdown_path_for_session(session.session_id).write_text(
                build_session_report_markdown(
                    session=session,
                    manifest=manifest,
                    source_type="bundle",
                    source_path=str(bundle_dir),
                ),
                encoding="utf-8",
            )
            report_markdown_exported = True
        self.overview_path_for_session(session.session_id).write_text(
            json.dumps(
                redact_sensitive_data(
                    self._bundle_overview(
                        session=session,
                        manifest=manifest,
                        copied_session=copied_session,
                        copied_trace=copied_trace,
                        report_markdown_exported=report_markdown_exported,
                    )
                ),
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (bundle_dir / "README.txt").write_text(
            self._bundle_notes(
                session=session,
                manifest=manifest,
                copied_session=copied_session,
                copied_trace=copied_trace,
                report_markdown_exported=report_markdown_exported,
            ),
            encoding="utf-8",
        )
        return bundle_dir

    def _copy_redacted_json_snapshot(self, source: Path, target: Path, *, jsonl: bool) -> None:
        text = source.read_text(encoding="utf-8")
        if jsonl:
            lines: list[str] = []
            for line in text.splitlines():
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError:
                    lines.append(redact_text(line))
                    continue
                lines.append(json.dumps(redact_sensitive_data(payload), ensure_ascii=False))
            target.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")
            return
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            target.write_text(redact_text(text), encoding="utf-8")
            return
        target.write_text(
            json.dumps(redact_sensitive_data(payload), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

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

    def _bundle_notes(
        self,
        *,
        session: ResearchSession,
        manifest: RunManifest,
        copied_session: bool,
        copied_trace: bool,
        report_markdown_exported: bool,
    ) -> str:
        lines = [
            "EllipticZero Reproducibility Bundle",
            f"Session ID: {session.session_id}",
            f"Confidence: {manifest.confidence or 'unavailable'}",
            f"Seed Hash: {manifest.seed_hash}",
            f"Replay Run: {'yes' if manifest.is_replay else 'no'}",
            "",
            "Contents:",
            "- overview.json: concise export overview with report snapshots, focus, confidence, comparison status, and quality/hardening counts",
            "- session.json: saved session snapshot when the source path stays inside approved local export roots",
            "- trace.jsonl: append-only execution trace when the source path stays inside approved local export roots",
            "- manifest.json: reproducibility manifest",
            "- comparative_report.json: machine-readable comparative reporting snapshot when available",
            "- report.md: Markdown report when a session report is available",
            "- artifacts/: copied local research artifacts when available and inside approved local export roots",
            "",
            "Export policy summary:",
        ]
        lines.extend(f"- {item}" for item in manifest.export_policy_summary)
        if manifest.secret_redaction_summary:
            lines.extend(["", "Secret redaction summary:"])
            lines.extend(f"- {item}" for item in manifest.secret_redaction_summary)
        lines.extend(
            [
                "",
                f"Copied session snapshot: {'yes' if copied_session else 'no'}",
                f"Copied trace snapshot: {'yes' if copied_trace else 'no'}",
                f"Exported Markdown report: {'yes' if report_markdown_exported else 'no'}",
            ]
        )
        return "\n".join(lines) + "\n"

    def _bundle_overview(
        self,
        *,
        session: ResearchSession,
        manifest: RunManifest,
        copied_session: bool,
        copied_trace: bool,
        report_markdown_exported: bool,
    ) -> dict[str, object]:
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
            "filtered_artifact_count": manifest.filtered_artifact_count,
            "tool_count": len(manifest.tool_names),
            "focus_summary": list(manifest.report_focus_summary),
            "report_snapshot_summary": list(manifest.report_snapshot_summary),
            "report_snapshot_count": manifest.report_snapshot_count,
            "export_policy_summary": list(manifest.export_policy_summary),
            "approved_export_roots": list(manifest.approved_export_roots),
            "quality_gate_count": manifest.quality_gate_count,
            "hardening_summary_count": manifest.hardening_summary_count,
            "quality_gate_summary": list(manifest.quality_gate_summary),
            "hardening_summary": list(manifest.hardening_summary),
            "evidence_coverage_summary": dict(manifest.evidence_coverage_summary),
            "toolchain_fingerprint": dict(manifest.toolchain_fingerprint),
            "secret_redaction_summary": list(manifest.secret_redaction_summary),
            "outputs": {
                "session_json": copied_session,
                "trace_jsonl": copied_trace,
                "comparative_report_json": manifest.comparative_export_ready,
                "report_markdown": report_markdown_exported,
                "artifacts_dir": bool(manifest.artifacts),
            },
        }
