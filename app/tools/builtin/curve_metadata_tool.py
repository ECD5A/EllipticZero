from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import CurveMetadataPayload
from app.tools.base import BaseTool
from app.tools.curve_registry import CURVE_REGISTRY


class CurveMetadataTool(BaseTool):
    """Inspect known curve metadata using deterministic local lookup."""

    name = "curve_metadata_tool"
    category = "curve_metadata"
    description = "Return structured metadata for recognized named elliptic curves."
    input_schema_hint = "curve_name string or alias"
    output_schema_hint = (
        "status, conclusion, deterministic, notes, result_data"
    )
    payload_model = CurveMetadataPayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        requested = str(payload.get("curve_name", "")).strip().lower()
        curve = CURVE_REGISTRY.resolve(requested)

        if curve is None:
            return self.make_result(
                status="not_recognized",
                conclusion="Curve input was not recognized by the central local curve registry.",
                notes=["Use a supported named curve or extend the central registry carefully."],
                result_data={
                    "recognized": False,
                    "requested_curve": requested or "unknown",
                    "curve_name": requested or "unknown",
                    "field_type": "unknown",
                    "short_description": "Curve name not recognized by the local metadata table.",
                },
            )

        return self.make_result(
            status="ok",
            conclusion=f"Recognized curve metadata for {curve.canonical_name}.",
            notes=[curve.notes],
            result_data={
                "recognized": True,
                "requested_curve": requested or curve.canonical_name,
                "curve_name": curve.canonical_name,
                "aliases": curve.aliases,
                "family": curve.family,
                "usage_category": curve.usage_category,
                "field_type": curve.field_type,
                "short_description": curve.short_description,
            },
        )
