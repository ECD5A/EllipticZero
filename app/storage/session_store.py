from __future__ import annotations

import json
from pathlib import Path

from app.models.session import ResearchSession
from app.storage.redaction import redact_sensitive_data


class SessionStore:
    """Very small JSON-backed store for research sessions."""

    def __init__(self, directory: str) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def path_for_session(self, session_id: str) -> Path:
        return self.directory / f"{session_id}.json"

    def save_session(self, session: ResearchSession) -> Path:
        path = self.path_for_session(session.session_id)
        payload = redact_sensitive_data(session.model_dump(mode="json"))
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return path

    def load_session(self, session_id: str) -> ResearchSession:
        path = self.path_for_session(session_id)
        return ResearchSession.model_validate_json(path.read_text(encoding="utf-8"))
