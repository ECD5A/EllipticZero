from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models.job import ComputeJob
from app.models.math_workspace import MathWorkspace


class MathArtifactStore:
    """Local JSON artifact store for bounded advanced math workspaces."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def create_workspace(
        self,
        *,
        session_id: str,
        experiment_type: str,
        tool_name: str,
        notes: list[str] | None = None,
    ) -> MathWorkspace:
        workspace = MathWorkspace(
            session_id=session_id,
            experiment_type=experiment_type,
            tool_name=tool_name,
            notes=notes or [],
        )
        self.path_for_workspace(workspace).mkdir(parents=True, exist_ok=True)
        return workspace

    def path_for_workspace(self, workspace: MathWorkspace) -> Path:
        return self.directory / workspace.session_id / workspace.workspace_id

    def write_execution_artifact(
        self,
        *,
        workspace: MathWorkspace,
        job: ComputeJob,
        payload: dict[str, Any],
    ) -> str:
        workspace_dir = self.path_for_workspace(workspace)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = workspace_dir / f"{job.job_id}.json"
        artifact_path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        stored_path = str(artifact_path)
        if stored_path not in workspace.artifact_paths:
            workspace.artifact_paths.append(stored_path)
        return stored_path
