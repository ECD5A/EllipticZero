from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import ECCCurvePayload
from app.tools.base import BaseTool
from app.tools.ecc_utils import resolve_ecc_domain


class ECCCurveParameterTool(BaseTool):
    """Return normalized ECC domain metadata for supported named curves."""

    name = "ecc_curve_parameter_tool"
    category = "ecc_curve_analysis"
    description = "Return normalized ECC domain parameters and metadata from the central curve registry."
    version = "0.8.0"
    input_schema_hint = "ECCCurvePayload"
    output_schema_hint = "Normalized ECC curve/domain metadata result"
    payload_model = ECCCurvePayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        requested = str(payload["curve_name"]).strip()
        domain = resolve_ecc_domain(requested)

        if domain is None:
            return self.make_result(
                status="not_recognized",
                conclusion="Curve or domain input was not recognized by the ECC domain layer.",
                notes=["Use a supported named curve alias from the central registry."],
                result_data={
                    "recognized": False,
                    "requested_curve": requested,
                    "curve_name": requested,
                    "supported": False,
                },
            )

        return self.make_result(
            status="ok",
            conclusion=f"Recognized ECC domain metadata for {domain.canonical_curve_name}.",
            notes=[domain.notes],
            result_data={
                "recognized": True,
                "requested_curve": requested,
                "curve_name": domain.canonical_curve_name,
                "aliases": domain.aliases,
                "family": domain.family,
                "usage_category": domain.usage_category,
                "field_type": domain.field_type,
                "field_modulus_hex": domain.field_modulus_hex,
                "a_hex": domain.a_hex,
                "b_hex": domain.b_hex,
                "generator_present": bool(domain.generator_x_hex and domain.generator_y_hex),
                "order_present": bool(domain.order_hex),
                "cofactor": domain.cofactor,
                "supports_on_curve_check": domain.supports_on_curve_check,
                "supported": True,
            },
        )
