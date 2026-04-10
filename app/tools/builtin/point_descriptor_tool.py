from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import PointDescriptorPayload
from app.tools.base import BaseTool


class PointDescriptorTool(BaseTool):
    """Describe point-like payloads without making cryptographic claims."""

    name = "point_descriptor_tool"
    category = "point_analysis"
    description = "Validate basic point payload shape and describe coordinate form."
    input_schema_hint = "x/y strings, coordinates list, or point_text"
    output_schema_hint = (
        "status, conclusion, deterministic, notes, result_data"
    )
    payload_model = PointDescriptorPayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        x_value, y_value = self._extract_coordinates(payload)
        notes: list[str] = []
        issues: list[str] = []

        if x_value is None or y_value is None:
            issues.append("Point payload does not contain both x and y coordinates.")
            return self.make_result(
                status="invalid_input",
                conclusion="Point payload was not sufficiently formed for local coordinate description.",
                notes=notes + issues,
                result_data={
                    "well_formed": False,
                    "coordinate_format": "missing",
                    "x_length": 0,
                    "y_length": 0,
                    "issues": issues,
                },
            )

        x_clean = self._normalize_coordinate(x_value)
        y_clean = self._normalize_coordinate(y_value)

        if not x_clean or not y_clean:
            issues.append("One or more coordinates became empty after normalization.")

        x_hex = self._looks_hex(x_clean)
        y_hex = self._looks_hex(y_clean)
        if x_hex and y_hex:
            notes.append("Coordinates look hex-like after normalization.")
        else:
            notes.append("Coordinates are treated as generic strings rather than strict hex values.")

        if len(x_clean) != len(y_clean):
            issues.append("Coordinate lengths differ, which may indicate malformed input.")

        coordinate_length_match = len(x_clean) == len(y_clean)
        common_curve_width = 64 if x_hex and y_hex and coordinate_length_match and len(x_clean) == 64 else None
        well_formed = len(issues) == 0
        return self.make_result(
            status="ok" if well_formed else "observed_issue",
            conclusion="Point payload was described locally without cryptographic interpretation.",
            notes=notes + issues,
            result_data={
                "well_formed": well_formed,
                "coordinate_format": "hex_like" if x_hex and y_hex else "generic",
                "coordinate_length_match": coordinate_length_match,
                "expected_coordinate_hex_length": common_curve_width,
                "x_length": len(x_clean),
                "y_length": len(y_clean),
                "x_prefix": x_clean[:12],
                "y_prefix": y_clean[:12],
                "issues": issues,
            },
        )

    def _extract_coordinates(self, payload: Mapping[str, Any]) -> tuple[str | None, str | None]:
        if "x" in payload and "y" in payload:
            return str(payload.get("x")), str(payload.get("y"))

        coordinates = payload.get("coordinates")
        if isinstance(coordinates, list) and len(coordinates) >= 2:
            return str(coordinates[0]), str(coordinates[1])

        point_text = str(payload.get("point_text", ""))
        x_match = re.search(r"x\s*[:=]\s*([0-9a-fA-Fx]+)", point_text)
        y_match = re.search(r"y\s*[:=]\s*([0-9a-fA-Fx]+)", point_text)
        if x_match and y_match:
            return x_match.group(1), y_match.group(1)
        return None, None

    def _normalize_coordinate(self, value: str) -> str:
        normalized = value.strip().lower()
        if normalized.startswith("0x"):
            return normalized[2:]
        return normalized

    def _looks_hex(self, value: str) -> bool:
        return bool(value) and all(char in "0123456789abcdef" for char in value)
