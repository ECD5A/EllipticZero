from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import ECCPointPayload
from app.tools.base import BaseTool
from app.tools.ecc_utils import analyze_ecc_shape_invariants, describe_ecc_point_input


class ECCPointFormatTool(BaseTool):
    """Describe ECC point/public-key-like inputs in a bounded deterministic way."""

    name = "ecc_point_format_tool"
    category = "ecc_point_analysis"
    description = "Classify compressed, uncompressed, coordinate, or malformed ECC point-like inputs."
    version = "0.8.0"
    input_schema_hint = "ECCPointPayload"
    output_schema_hint = "Normalized ECC point/public-key descriptor"
    payload_model = ECCPointPayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        descriptor = describe_ecc_point_input(payload)
        invariants, invariant_notes = analyze_ecc_shape_invariants(
            descriptor=descriptor,
            curve_name=str(payload.get("curve_name", "")).strip() or None,
        )
        recognized = descriptor.input_kind in {"public_key_hex", "coordinate_payload"}
        issues = list(invariants.get("issues", []))
        notes = list(dict.fromkeys([*descriptor.notes, *invariant_notes]))

        return self.make_result(
            status="ok" if recognized and not issues else "observed_issue",
            conclusion="ECC point-like input was described locally without cryptographic interpretation.",
            notes=notes,
            result_data={
                "input_kind": descriptor.input_kind,
                "encoding": descriptor.encoding,
                "hex_length": descriptor.hex_length,
                "coordinate_presence": descriptor.coordinate_presence,
                "likely_curve_family": descriptor.likely_curve_family,
                "x_hex": descriptor.x_hex,
                "y_hex": descriptor.y_hex,
                "format_recognized": recognized,
                "supported": recognized,
                "prefix": invariants.get("prefix"),
                "prefix_valid": invariants.get("prefix_valid"),
                "expected_coordinate_hex_length": invariants.get("expected_coordinate_hex_length"),
                "coordinate_length_match": invariants.get("coordinate_length_match"),
                "expected_length_match": invariants.get("expected_length_match"),
                "x_hex_length": invariants.get("x_hex_length"),
                "y_hex_length": invariants.get("y_hex_length"),
                "issues": issues,
            },
        )
