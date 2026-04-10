from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.models.replay_request import ReplayRequest
from app.models.run_manifest import RunManifest
from app.models.session import ResearchSession


@dataclass
class LoadedReplaySource:
    source_type: str
    source_path: str
    session: ResearchSession | None = None
    manifest: RunManifest | None = None
    bundle_dir: str | None = None
    recovered_seed: str | None = None
    original_session_id: str | None = None
    tool_names: list[str] = field(default_factory=list)
    experiment_types: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    trace_file_path: str | None = None
    research_mode: str | None = None
    exploration_profile: str | None = None
    selected_pack_name: str | None = None
    notes: list[str] = field(default_factory=list)


class ReplayLoader:
    """Load replayable session state from session, manifest, or bundle sources."""

    def load(self, request: ReplayRequest) -> LoadedReplaySource:
        if request.source_type == "session":
            return self._load_session_source(Path(request.source_path))
        if request.source_type == "manifest":
            return self._load_manifest_source(Path(request.source_path))
        if request.source_type == "bundle":
            return self._load_bundle_source(Path(request.source_path))
        raise ValueError(f"Unsupported replay source type: {request.source_type}")

    def _load_session_source(self, path: Path) -> LoadedReplaySource:
        session = self._read_session(path)
        return LoadedReplaySource(
            source_type="session",
            source_path=str(path),
            session=session,
            recovered_seed=session.seed.raw_text,
            original_session_id=session.original_session_id or session.session_id,
            tool_names=[job.tool_name for job in session.jobs],
            experiment_types=[
                evidence.experiment_type for evidence in session.evidence if evidence.experiment_type
            ],
            artifact_paths=[
                artifact
                for evidence in session.evidence
                for artifact in evidence.artifact_paths
            ],
            trace_file_path=session.trace_file_path,
            research_mode=session.research_mode.value,
            exploration_profile=(
                session.sandbox_spec.exploration_profile.value
                if session.sandbox_spec is not None
                else None
            ),
            selected_pack_name=session.selected_pack_name,
            notes=["Loaded replay source from saved session JSON."],
        )

    def _load_manifest_source(self, path: Path) -> LoadedReplaySource:
        manifest = self._read_manifest(path)
        session = self._resolve_session_from_manifest(manifest=manifest, manifest_path=path)
        return LoadedReplaySource(
            source_type="manifest",
            source_path=str(path),
            session=session,
            manifest=manifest,
            recovered_seed=session.seed.raw_text if session is not None else None,
            original_session_id=(
                session.original_session_id
                if session is not None and session.original_session_id
                else manifest.original_session_id or manifest.session_id
            ),
            tool_names=manifest.tool_names,
            experiment_types=manifest.experiment_types,
            artifact_paths=manifest.artifact_paths,
            trace_file_path=manifest.trace_file_path,
            research_mode=(
                session.research_mode.value
                if session is not None
                else manifest.research_mode
            ),
            exploration_profile=(
                session.sandbox_spec.exploration_profile.value
                if session is not None and session.sandbox_spec is not None
                else manifest.exploration_profile
            ),
            selected_pack_name=(
                session.selected_pack_name
                if session is not None
                else manifest.selected_pack_name
            ),
            notes=[
                "Loaded replay source from run manifest.",
                (
                    "Recovered session JSON through the manifest."
                    if session is not None
                    else "Session JSON could not be recovered from the manifest path."
                ),
            ],
        )

    def _load_bundle_source(self, path: Path) -> LoadedReplaySource:
        if not path.exists() or not path.is_dir():
            raise ValueError(f"Replay bundle directory not found: {path}")

        session_path = path / "session.json"
        manifest_path = path / "manifest.json"
        trace_path = path / "trace.jsonl"

        session = self._read_session(session_path) if session_path.exists() else None
        manifest = self._read_manifest(manifest_path) if manifest_path.exists() else None
        if session is None and manifest is None:
            raise ValueError("Bundle does not contain a readable session.json or manifest.json.")

        tool_names = manifest.tool_names if manifest is not None else [job.tool_name for job in session.jobs]
        experiment_types = (
            manifest.experiment_types
            if manifest is not None
            else [evidence.experiment_type for evidence in session.evidence if evidence.experiment_type]
        )
        artifact_paths = manifest.artifact_paths if manifest is not None else [
            artifact for evidence in session.evidence for artifact in evidence.artifact_paths
        ]

        return LoadedReplaySource(
            source_type="bundle",
            source_path=str(path),
            session=session,
            manifest=manifest,
            bundle_dir=str(path),
            recovered_seed=session.seed.raw_text if session is not None else None,
            original_session_id=(
                session.original_session_id
                if session is not None and session.original_session_id
                else (manifest.original_session_id if manifest is not None else None)
                or (session.session_id if session is not None else None)
                or (manifest.session_id if manifest is not None else None)
            ),
            tool_names=tool_names,
            experiment_types=experiment_types,
            artifact_paths=artifact_paths,
            trace_file_path=(
                str(trace_path)
                if trace_path.exists()
                else (manifest.trace_file_path if manifest is not None else None)
            ),
            research_mode=(
                session.research_mode.value
                if session is not None
                else (manifest.research_mode if manifest is not None else None)
            ),
            exploration_profile=(
                session.sandbox_spec.exploration_profile.value
                if session is not None and session.sandbox_spec is not None
                else (manifest.exploration_profile if manifest is not None else None)
            ),
            selected_pack_name=(
                session.selected_pack_name
                if session is not None
                else (manifest.selected_pack_name if manifest is not None else None)
            ),
            notes=["Loaded replay source from reproducibility bundle directory."],
        )

    def _resolve_session_from_manifest(
        self,
        *,
        manifest: RunManifest,
        manifest_path: Path,
    ) -> ResearchSession | None:
        candidates = [Path(manifest.session_file_path)]
        sibling_session = manifest_path.parent / "session.json"
        if sibling_session not in candidates:
            candidates.append(sibling_session)
        for candidate in candidates:
            if candidate.exists():
                try:
                    return self._read_session(candidate)
                except ValueError:
                    continue
        return None

    def _read_session(self, path: Path) -> ResearchSession:
        if not path.exists() or not path.is_file():
            raise ValueError(f"Replay session file not found: {path}")
        try:
            return ResearchSession.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise ValueError(f"Replay session file is malformed: {path}") from exc

    def _read_manifest(self, path: Path) -> RunManifest:
        if not path.exists() or not path.is_file():
            raise ValueError(f"Replay manifest file not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return RunManifest.model_validate(payload)
        except Exception as exc:
            raise ValueError(f"Replay manifest file is malformed: {path}") from exc
