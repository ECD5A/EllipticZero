from __future__ import annotations

from app.compute.executor import ComputeExecutor
from app.compute.runners import ECCTestbedRunner, FormalRunner, PropertyRunner
from app.core.research_targets import ResearchTargetRegistry
from app.core.sandbox_executor import SandboxExecutor
from app.models import ComputeJob, ResearchMode, ResearchTarget, SandboxExecutionRequest
from app.tools.builtin import (
    ECCTestbedTool,
    FiniteFieldCheckTool,
    FormalConstraintTool,
    PlaceholderMathTool,
    PropertyInvariantTool,
)
from app.tools.registry import ToolRegistry


def test_research_target_registry_validates_profile_and_reference_bounds() -> None:
    registry = ResearchTargetRegistry()
    target = ResearchTarget(
        target_kind="symbolic",
        target_reference="x + y - y",
    )

    profile, notes = registry.validate_target(target)

    assert profile.profile_name == "symbolic_expression_target"
    assert any(note.startswith("target_profile=") for note in notes)
    assert any(note.startswith("target_reference_length=") for note in notes)


def test_sandbox_executor_rejects_tool_outside_target_profile() -> None:
    registry = ToolRegistry()
    registry.register(PlaceholderMathTool())
    registry.register(FiniteFieldCheckTool())
    executor = ComputeExecutor(registry=registry)
    sandbox_executor = SandboxExecutor(
        executor=executor,
        target_registry=ResearchTargetRegistry(),
    )
    request = SandboxExecutionRequest(
        session_id="session_test",
        hypothesis_id="hyp_test",
        sandbox_id="sandbox_test",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        tool_name="placeholder_math_tool",
        research_target=ResearchTarget(
            target_kind="finite_field",
            target_reference="left=10, right=3, modulus=7",
        ),
        approved_tool_names=["placeholder_math_tool", "finite_field_check_tool"],
    )
    job = ComputeJob(
        hypothesis_id="hyp_test",
        tool_name="placeholder_math_tool",
        payload={},
    )

    try:
        sandbox_executor.execute(request=request, job=job)
    except ValueError as exc:
        assert "does not allow tool" in str(exc)
    else:
        raise AssertionError("Sandbox executor should reject tools outside the target profile.")


def test_sandbox_executor_clamps_runner_budgets_for_bounded_execution() -> None:
    registry = ToolRegistry()
    registry.register(PropertyInvariantTool(runner=PropertyRunner(enabled=True, max_examples=24)))
    registry.register(FormalConstraintTool(runner=FormalRunner(enabled=False, timeout_seconds=5)))
    registry.register(ECCTestbedTool(runner=ECCTestbedRunner(enabled=True)))
    executor = ComputeExecutor(registry=registry)
    sandbox_executor = SandboxExecutor(
        executor=executor,
        target_registry=ResearchTargetRegistry(),
        max_job_timeout_seconds=30,
        property_max_examples=24,
        formal_timeout_seconds=5,
        max_testbed_cases=8,
    )

    property_request = SandboxExecutionRequest(
        session_id="session_test",
        hypothesis_id="hyp_test",
        sandbox_id="sandbox_test",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
        tool_name="property_invariant_tool",
        research_target=ResearchTarget(
            target_kind="symbolic",
            target_reference="x + 1 = 1 + x",
        ),
        approved_tool_names=["property_invariant_tool", "formal_constraint_tool", "ecc_testbed_tool"],
    )
    property_job = ComputeJob(
        hypothesis_id="hyp_test",
        tool_name="property_invariant_tool",
        timeout_seconds=45,
        payload={
            "left_expression": "x + 1",
            "right_expression": "1 + x",
            "max_examples": 120,
        },
    )

    property_result = sandbox_executor.execute(request=property_request, job=property_job)
    assert property_result.raw_result is not None
    assert property_result.raw_result["timeout_seconds"] == 30
    assert property_result.raw_result["validated_payload"]["max_examples"] == 24
    assert any("timeout_clamped=45->30" in note for note in property_result.notes)
    assert any("property_max_examples_clamped=120->24" in note for note in property_result.notes)

    formal_request = property_request.model_copy(
        update={
            "tool_name": "formal_constraint_tool",
            "research_target": ResearchTarget(
                target_kind="symbolic",
                target_reference="x^2 = x*x",
            ),
        }
    )
    formal_job = ComputeJob(
        hypothesis_id="hyp_test",
        tool_name="formal_constraint_tool",
        timeout_seconds=20,
        payload={
            "left_expression": "x^2",
            "right_expression": "x*x",
            "domain_min": -40,
            "domain_max": 40,
        },
    )
    formal_result = sandbox_executor.execute(request=formal_request, job=formal_job)
    assert formal_result.raw_result is not None
    assert formal_result.raw_result["timeout_seconds"] == 5
    assert formal_result.raw_result["validated_payload"]["domain_min"] == -16
    assert formal_result.raw_result["validated_payload"]["domain_max"] == 16
    assert any("formal_timeout_clamped=20->5" in note for note in formal_result.notes)
    assert any("formal_domain_span_clamped_to_32" in note for note in formal_result.notes)

    testbed_request = property_request.model_copy(
        update={
            "tool_name": "ecc_testbed_tool",
            "research_target": ResearchTarget(
                target_kind="testbed",
                target_reference="point_anomaly_corpus",
            ),
        }
    )
    testbed_job = ComputeJob(
        hypothesis_id="hyp_test",
        tool_name="ecc_testbed_tool",
        payload={
            "testbed_name": "point_anomaly_corpus",
            "case_limit": 14,
        },
    )
    testbed_result = sandbox_executor.execute(request=testbed_request, job=testbed_job)
    assert testbed_result.raw_result is not None
    assert testbed_result.raw_result["validated_payload"]["case_limit"] == 8
    assert any("testbed_case_limit_clamped=14->8" in note for note in testbed_result.notes)
