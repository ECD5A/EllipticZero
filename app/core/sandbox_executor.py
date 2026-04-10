from __future__ import annotations

from typing import Any

from app.compute.executor import ComputeExecutor
from app.core.research_targets import ResearchTargetRegistry
from app.models import ComputeJob, SandboxExecutionRequest, SandboxExecutionResult


class SandboxExecutor:
    """Bounded execution wrapper for sandboxed exploratory sessions."""

    def __init__(
        self,
        *,
        executor: ComputeExecutor,
        target_registry: ResearchTargetRegistry,
        max_job_timeout_seconds: int = 30,
        property_max_examples: int = 24,
        fuzz_max_mutations: int = 12,
        formal_timeout_seconds: int = 5,
        max_testbed_cases: int = 8,
    ) -> None:
        self.executor = executor
        self.target_registry = target_registry
        self.max_job_timeout_seconds = max(1, max_job_timeout_seconds)
        self.property_max_examples = max(1, property_max_examples)
        self.fuzz_max_mutations = max(1, fuzz_max_mutations)
        self.formal_timeout_seconds = max(1, formal_timeout_seconds)
        self.max_testbed_cases = max(1, max_testbed_cases)

    def execute(
        self,
        *,
        request: SandboxExecutionRequest,
        job: ComputeJob,
    ) -> SandboxExecutionResult:
        if not (request.local_only and request.reversible and request.bounded):
            raise ValueError(
                "Sandbox execution requires local_only, reversible, and bounded policies to remain enabled."
            )
        if job.tool_name != request.tool_name:
            raise ValueError(
                "Sandbox execution request and compute job disagree about the selected tool."
            )
        if request.tool_name not in request.approved_tool_names:
            raise ValueError(
                f"Sandbox execution rejected unapproved tool: {request.tool_name}"
            )

        profile, notes = self.target_registry.validate_target(request.research_target)
        if request.tool_name not in profile.allowed_tool_names:
            raise ValueError(
                f"Sandbox target profile {profile.profile_name} does not allow tool {request.tool_name}."
            )

        bounded_job, policy_notes = self._apply_job_policy(job)
        raw_result = self.executor.execute(bounded_job)
        raw_result["sandbox"] = {
            "request_id": request.request_id,
            "sandbox_id": request.sandbox_id,
            "research_mode": request.research_mode.value,
            "target_profile": profile.profile_name,
            "notes": notes + policy_notes + [
                f"tool_allowed_for_profile={profile.profile_name}",
                "execution_path=sandbox_executor",
            ],
        }
        return SandboxExecutionResult(
            request_id=request.request_id,
            sandbox_id=request.sandbox_id,
            allowed=True,
            executed=True,
            target_profile=profile.profile_name,
            notes=list(raw_result["sandbox"]["notes"]),
            raw_result=raw_result,
        )

    def _apply_job_policy(self, job: ComputeJob) -> tuple[ComputeJob, list[str]]:
        adjusted_job = job.model_copy(deep=True)
        notes: list[str] = []

        original_timeout = adjusted_job.timeout_seconds
        adjusted_job.timeout_seconds = min(
            adjusted_job.timeout_seconds,
            self.max_job_timeout_seconds,
        )
        if adjusted_job.timeout_seconds != original_timeout:
            notes.append(
                f"timeout_clamped={original_timeout}->{adjusted_job.timeout_seconds}"
            )

        if adjusted_job.tool_name == "formal_constraint_tool":
            formal_timeout = adjusted_job.timeout_seconds
            adjusted_job.timeout_seconds = min(
                adjusted_job.timeout_seconds,
                self.formal_timeout_seconds,
            )
            if adjusted_job.timeout_seconds != formal_timeout:
                notes.append(
                    f"formal_timeout_clamped={formal_timeout}->{adjusted_job.timeout_seconds}"
                )

        payload = dict(adjusted_job.payload)
        payload_notes = self._apply_payload_limits(
            tool_name=adjusted_job.tool_name,
            payload=payload,
            timeout_seconds=adjusted_job.timeout_seconds,
        )
        adjusted_job.payload = payload
        return adjusted_job, notes + payload_notes

    def _apply_payload_limits(
        self,
        *,
        tool_name: str,
        payload: dict[str, Any],
        timeout_seconds: int,
    ) -> list[str]:
        notes: list[str] = []

        if tool_name == "property_invariant_tool" and "max_examples" in payload:
            original = int(payload["max_examples"])
            payload["max_examples"] = min(original, self.property_max_examples)
            if payload["max_examples"] != original:
                notes.append(
                    f"property_max_examples_clamped={original}->{payload['max_examples']}"
                )

        if tool_name == "fuzz_mutation_tool" and "mutations" in payload:
            original = int(payload["mutations"])
            payload["mutations"] = min(original, self.fuzz_max_mutations)
            if payload["mutations"] != original:
                notes.append(
                    f"fuzz_mutations_clamped={original}->{payload['mutations']}"
                )

        if tool_name == "formal_constraint_tool":
            if "domain_min" in payload and "domain_max" in payload:
                span = int(payload["domain_max"]) - int(payload["domain_min"])
                if span > 32:
                    midpoint = (int(payload["domain_max"]) + int(payload["domain_min"])) // 2
                    payload["domain_min"] = midpoint - 16
                    payload["domain_max"] = midpoint + 16
                    notes.append("formal_domain_span_clamped_to_32")

        if tool_name in {"ecc_testbed_tool", "contract_testbed_tool"} and "case_limit" in payload:
            original = int(payload["case_limit"])
            payload["case_limit"] = min(original, self.max_testbed_cases)
            if payload["case_limit"] != original:
                notes.append(
                    f"testbed_case_limit_clamped={original}->{payload['case_limit']}"
                )

        return notes
