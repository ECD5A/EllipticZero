from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.types import make_id

DoctorStatus = Literal["ok", "warning", "error", "info"]


class DoctorCheck(BaseModel):
    """Single self-check result for the runtime environment."""

    model_config = ConfigDict(extra="forbid")

    check_id: str = Field(default_factory=lambda: make_id("doctor_check"))
    status: DoctorStatus
    title: str
    summary: str
    details: list[str] = Field(default_factory=list)
    context: dict[str, str] = Field(default_factory=dict)


class DoctorReport(BaseModel):
    """Aggregate self-check report for EllipticZero runtime readiness."""

    model_config = ConfigDict(extra="forbid")

    report_id: str = Field(default_factory=lambda: make_id("doctor"))
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    overall_status: DoctorStatus
    summary: str
    checks: list[DoctorCheck] = Field(default_factory=list)
