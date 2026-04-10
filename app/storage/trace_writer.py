from __future__ import annotations

import json
from pathlib import Path

from app.models.trace import TraceEvent


class TraceWriter:
    """Append-only JSONL trace writer for research sessions."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path_for_session(self, session_id: str) -> Path:
        return self.directory / f"{session_id}.jsonl"

    def append(self, event: TraceEvent) -> Path:
        path = self.path_for_session(event.session_id)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False))
            handle.write("\n")
        return path
