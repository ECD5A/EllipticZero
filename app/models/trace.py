from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class TraceEvent(BaseModel):
    """Structured JSONL trace event."""

    model_config = ConfigDict(extra="forbid")

    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    session_id: str
    event_type: str
    agent: str
    hypothesis_id: str | None = None
    summary: str
    data: dict[str, Any] | None = None
