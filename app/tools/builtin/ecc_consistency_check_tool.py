from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import ECCConsistencyPayload
from app.tools.base import BaseTool
from app.tools.ecc_utils import (
    analyze_ecc_shape_invariants,
    bounded_field_range_check,
    describe_ecc_point_input,
    resolve_ecc_domain,
    short_weierstrass_on_curve_check,
)


class ECCConsistencyCheckTool(BaseTool):
    """Perform bounded deterministic ECC consistency and shape checks."""

    name = "ecc_consistency_check_tool"
    category = "ecc_consistency"
    description = "Perform bounded ECC format and optional short-Weierstrass on-curve consistency checks."
    version = "0.8.0"
    input_schema_hint = "ECCConsistencyPayload"
    output_schema_hint = "Normalized ECC consistency result"
    payload_model = ECCConsistencyPayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        descriptor = describe_ecc_point_input(payload)
        curve_name = str(payload.get("curve_name", "")).strip() or None
        domain = resolve_ecc_domain(curve_name) if curve_name else None

        notes = list(descriptor.notes)
        invariants, invariant_notes = analyze_ecc_shape_invariants(
            descriptor=descriptor,
            curve_name=curve_name,
        )
        notes.extend(invariant_notes)
        issues = list(invariants.get("issues", []))
        format_recognized = descriptor.input_kind in {"public_key_hex", "coordinate_payload"}
        format_consistent = False

        if descriptor.encoding == "compressed":
            format_consistent = bool(
                descriptor.hex_length == 66 and invariants.get("prefix_valid") is True
            )
        elif descriptor.encoding == "uncompressed":
            format_consistent = bool(
                descriptor.hex_length == 130 and invariants.get("prefix_valid") is True
            )
        elif descriptor.encoding == "coordinates":
            format_consistent = bool(
                descriptor.x_hex
                and descriptor.y_hex
                and invariants.get("coordinate_length_match") is True
            )

        field_range_data, field_range_notes = bounded_field_range_check(
            curve_name=domain.canonical_curve_name if domain is not None else curve_name,
            x_hex=descriptor.x_hex,
            y_hex=descriptor.y_hex,
        )
        notes.extend(field_range_notes)
        if (
            field_range_data.get("field_bounds_checked") is True
            and (
                field_range_data.get("x_in_field_range") is False
                or field_range_data.get("y_in_field_range") is False
            )
        ):
            issues.append("One or more coordinates exceed the bounded field modulus range.")

        on_curve: bool | None = None
        on_curve_checked = False
        if bool(payload.get("check_on_curve", False)) and curve_name:
            on_curve, on_curve_notes = short_weierstrass_on_curve_check(
                curve_name=curve_name,
                x_hex=descriptor.x_hex,
                y_hex=descriptor.y_hex,
            )
            on_curve_checked = on_curve is not None
            notes.extend(on_curve_notes)
        elif curve_name and domain is not None and domain.supports_on_curve_check and descriptor.y_hex:
            notes.append("On-curve checking was available but not requested explicitly.")

        supported = format_recognized and (curve_name is None or domain is not None)
        if on_curve_checked and on_curve is False:
            issues.append("Bounded on-curve verification failed for the supplied coordinates.")
        notes = list(dict.fromkeys(notes))
        return self.make_result(
            status="ok" if supported and not issues else "observed_issue",
            conclusion=(
                "Bounded ECC consistency checks completed without implying cryptographic validity."
            ),
            notes=notes,
            result_data={
                "curve_name": domain.canonical_curve_name if domain is not None else curve_name,
                "input_kind": descriptor.input_kind,
                "encoding": descriptor.encoding,
                "format_recognized": format_recognized,
                "format_consistent": format_consistent,
                "consistency_check_performed": True,
                "supported": supported,
                "prefix": invariants.get("prefix"),
                "prefix_valid": invariants.get("prefix_valid"),
                "expected_coordinate_hex_length": invariants.get("expected_coordinate_hex_length"),
                "coordinate_length_match": invariants.get("coordinate_length_match"),
                "expected_length_match": invariants.get("expected_length_match"),
                "x_hex_length": invariants.get("x_hex_length"),
                "y_hex_length": invariants.get("y_hex_length"),
                "field_bounds_checked": field_range_data.get("field_bounds_checked"),
                "x_in_field_range": field_range_data.get("x_in_field_range"),
                "y_in_field_range": field_range_data.get("y_in_field_range"),
                "on_curve_checked": on_curve_checked,
                "on_curve": on_curve,
                "issues": issues,
            },
        )
