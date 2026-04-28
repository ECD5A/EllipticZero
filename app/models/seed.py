from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.types import make_id


class ResearchSeed(BaseModel):
    """Original user-provided research idea preserved as session anchor."""

    model_config = ConfigDict(extra="forbid")

    seed_id: str = Field(default_factory=lambda: make_id("seed"))
    raw_text: str
    author: str | None = None
    domain: str | None = None

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Research seed cannot be empty.")
        return stripped

    @field_validator("author")
    @classmethod
    def normalize_author(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("domain")
    @classmethod
    def normalize_domain(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().lower()
        if not normalized:
            return None
        if normalized not in {"ecc_research", "smart_contract_audit"}:
            raise ValueError("Research seed domain must be ecc_research or smart_contract_audit.")
        return normalized
