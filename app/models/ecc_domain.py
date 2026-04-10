from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ECCDomainParameters(BaseModel):
    """Normalized ECC domain metadata derived from the central curve registry."""

    model_config = ConfigDict(extra="forbid")

    canonical_curve_name: str
    aliases: list[str] = Field(default_factory=list)
    family: str
    usage_category: list[str] = Field(default_factory=list)
    field_type: str
    field_modulus_hex: str | None = None
    a_hex: str | None = None
    b_hex: str | None = None
    generator_x_hex: str | None = None
    generator_y_hex: str | None = None
    order_hex: str | None = None
    cofactor: int | None = None
    short_description: str
    notes: str
    supports_on_curve_check: bool = False

    @field_validator("canonical_curve_name", "family", "field_type", "short_description", "notes")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ECC domain text fields cannot be empty.")
        return stripped
