from __future__ import annotations

import logging
from typing import Any

from app.models.job import ComputeJob
from app.tools.registry import ToolRegistry


class ComputeExecutor:
    """Execute approved compute jobs through the tool registry only."""

    def __init__(self, *, registry: ToolRegistry) -> None:
        self.registry = registry
        self.logger = logging.getLogger(self.__class__.__name__)

    def execute(self, job: ComputeJob) -> dict[str, Any]:
        tool = self.registry.get(job.tool_name)
        validated_payload = tool.validate_payload(job.payload)
        self.logger.info(
            "Executing compute job %s with tool %s",
            job.job_id,
            job.tool_name,
        )
        result = tool.run(validated_payload)
        return {
            "job_id": job.job_id,
            "hypothesis_id": job.hypothesis_id,
            "tool_name": tool.name,
            "tool_version": tool.version,
            "tool_metadata": tool.metadata.model_dump(mode="json"),
            "deterministic": bool(result.get("deterministic", tool.deterministic)),
            "validated_payload": validated_payload,
            "tool_plan": (
                job.tool_plan.model_dump(mode="json") if job.tool_plan is not None else None
            ),
            "experiment_spec": (
                job.experiment_spec.model_dump(mode="json")
                if job.experiment_spec is not None
                else None
            ),
            "timeout_seconds": job.timeout_seconds,
            "result": result,
        }
