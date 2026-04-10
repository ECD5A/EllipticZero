from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ECCPointDescriptor(BaseModel):
    """Normalized description of a point-like or public-key-like ECC input."""

    model_config = ConfigDict(extra="forbid")

    input_kind: str
    encoding: str
    hex_length: int | None = None
    coordinate_presence: str
    likely_curve_family: str | None = None
    normalized_public_key_hex: str | None = None
    x_hex: str | None = None
    y_hex: str | None = None
    notes: list[str] = Field(default_factory=list)

    @field_validator("input_kind", "encoding", "coordinate_presence")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ECC point descriptor text fields cannot be empty.")
        return stripped

    @field_validator("likely_curve_family", "normalized_public_key_hex", "x_hex", "y_hex")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
