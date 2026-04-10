from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import FiniteFieldCheckPayload
from app.tools.base import BaseTool


class FiniteFieldCheckTool(BaseTool):
    """Deterministic bounded finite-field style consistency checker."""

    name = "finite_field_check_tool"
    description = (
        "Perform deterministic modular arithmetic consistency checks for bounded research experiments."
    )
    version = "0.6.0"
    category = "advanced_math"
    input_schema_hint = "FiniteFieldCheckPayload"
    output_schema_hint = "Normalized modular consistency result"
    payload_model = FiniteFieldCheckPayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        modulus = int(payload["modulus"])
        left = int(payload["left"])
        right = int(payload["right"])
        left_mod = left % modulus
        right_mod = right % modulus
        difference_mod = (left - right) % modulus
        consistent = left_mod == right_mod

        return self.make_result(
            status="ok",
            conclusion=(
                "The provided values are congruent modulo the specified modulus."
                if consistent
                else "The provided values are not congruent modulo the specified modulus."
            ),
            notes=[
                "This tool performs bounded deterministic modular arithmetic only.",
                "No cryptographic strength or exploitation claim is implied.",
            ],
            result_data={
                "operation": payload["operation"],
                "modulus": modulus,
                "left": left,
                "right": right,
                "left_mod": left_mod,
                "right_mod": right_mod,
                "difference_mod": difference_mod,
                "consistent": consistent,
            },
        )
