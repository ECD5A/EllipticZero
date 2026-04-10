from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import DeterministicExperimentPayload
from app.tools.base import BaseTool


class DeterministicExperimentTool(BaseTool):
    """Run bounded deterministic consistency experiments on structured input."""

    name = "deterministic_experiment_tool"
    category = "deterministic_experiment"
    description = "Run repeatable normalization and consistency checks on structured payloads."
    input_schema_hint = "experiment_type plus structured payload"
    output_schema_hint = (
        "status, conclusion, deterministic, notes, result_data"
    )
    payload_model = DeterministicExperimentPayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        experiment_type = str(payload.get("experiment_type", "normalize_text")).strip()
        repeats = max(1, min(int(payload.get("repeats", 3)), 10))

        if experiment_type == "normalize_text":
            source_text = str(payload.get("value", ""))
            outputs = [self._normalize_text(source_text) for _ in range(repeats)]
        elif experiment_type == "canonical_json":
            sample = payload.get("value", {})
            outputs = [json.dumps(sample, sort_keys=True, separators=(",", ":")) for _ in range(repeats)]
        else:
            return self.make_result(
                status="unsupported_experiment",
                conclusion="Requested deterministic experiment type is not supported.",
                notes=["Experiment type is not supported by the deterministic tool."],
                result_data={
                    "experiment_type": experiment_type,
                    "result": "unsupported_experiment",
                    "repeatability": False,
                    "normalized_outputs": [],
                },
            )

        repeatable = len(set(outputs)) == 1
        return self.make_result(
            status="ok",
            conclusion="Deterministic local experiment completed with bounded repeatability checks.",
            notes=["Experiment executed with bounded deterministic local logic."],
            result_data={
                "experiment_type": experiment_type,
                "result": outputs[0] if outputs else None,
                "repeatability": repeatable,
                "normalized_outputs": outputs,
            },
        )

    def _normalize_text(self, value: str) -> str:
        return " ".join(value.lower().split())
