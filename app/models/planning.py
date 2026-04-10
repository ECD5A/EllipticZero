from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ExperimentType(str, Enum):
    SMART_CONTRACT_INVENTORY_CHECK = "smart_contract_inventory_check"
    SMART_CONTRACT_COMPILE_CHECK = "smart_contract_compile_check"
    SMART_CONTRACT_STATIC_ANALYZER_CHECK = "smart_contract_static_analyzer_check"
    SMART_CONTRACT_FUZZ_CHECK = "smart_contract_fuzz_check"
    SYMBOLIC_SIMPLIFICATION = "symbolic_simplification"
    PROPERTY_INVARIANT_CHECK = "property_invariant_check"
    FORMAL_CONSTRAINT_CHECK = "formal_constraint_check"
    FINITE_FIELD_CHECK = "finite_field_check"
    SMART_CONTRACT_PARSE = "smart_contract_parse"
    SMART_CONTRACT_SURFACE_CHECK = "smart_contract_surface_check"
    SMART_CONTRACT_PATTERN_CHECK = "smart_contract_pattern_check"
    SMART_CONTRACT_TESTBED_SWEEP = "smart_contract_testbed_sweep"
    ECC_CURVE_PARAMETER_CHECK = "ecc_curve_parameter_check"
    ECC_POINT_FORMAT_CHECK = "ecc_point_format_check"
    ECC_CONSISTENCY_CHECK = "ecc_consistency_check"
    FUZZ_MUTATION_SCAN = "fuzz_mutation_scan"
    ECC_TESTBED_SWEEP = "ecc_testbed_sweep"
    CURVE_METADATA_MATH_CHECK = "curve_metadata_math_check"
    POINT_STRUCTURE_CHECK = "point_structure_check"
    DETERMINISTIC_REPEAT_CHECK = "deterministic_repeat_check"
    PLACEHOLDER_SIGNAL_SCAN = "placeholder_signal_scan"


class ToolPlan(BaseModel):
    """Structured plan describing why a specific local tool should run."""

    model_config = ConfigDict(extra="forbid")

    tool_name: str
    reason: str
    priority: int = 1
    expected_output: str
    deterministic_expected: bool = True
    selected_by_roles: list[str] = Field(default_factory=list)

    @field_validator("tool_name", "reason", "expected_output")
    @classmethod
    def validate_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ToolPlan text fields cannot be empty.")
        return stripped

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ToolPlan priority must be >= 1.")
        return value


class ExperimentSpec(BaseModel):
    """Structured specification for a bounded local experiment or inspection."""

    model_config = ConfigDict(extra="forbid")

    experiment_type: ExperimentType
    target_kind: str
    target_reference: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    repeat_count: int = 1
    deterministic_required: bool = True

    @field_validator("target_kind", "target_reference")
    @classmethod
    def validate_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("ExperimentSpec text fields cannot be empty.")
        return stripped

    @field_validator("repeat_count")
    @classmethod
    def validate_repeat_count(cls, value: int) -> int:
        if value < 1:
            raise ValueError("ExperimentSpec repeat_count must be >= 1.")
        return value
