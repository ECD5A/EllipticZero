from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class CurveMetadataPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curve_name: str

    @field_validator("curve_name")
    @classmethod
    def validate_curve_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("curve_name cannot be empty.")
        return stripped


class SmartContractAuditPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_code: str
    language: str | None = None
    source_label: str | None = None
    contract_root: str | None = None

    @field_validator("contract_code")
    @classmethod
    def validate_contract_code(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("contract_code cannot be empty.")
        if len(stripped) > 20_000:
            raise ValueError("contract_code is too large for bounded local smart-contract auditing.")
        return stripped

    @field_validator("language")
    @classmethod
    def validate_language(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip().lower()
        if stripped not in {"solidity", "vyper"}:
            raise ValueError("language must be solidity or vyper.")
        return stripped

    @field_validator("source_label")
    @classmethod
    def normalize_source_label(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("contract_root")
    @classmethod
    def normalize_contract_root(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class SmartContractInventoryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    root_path: str
    max_files: int = 64

    @field_validator("root_path")
    @classmethod
    def validate_root_path(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("root_path cannot be empty.")
        return stripped

    @field_validator("max_files")
    @classmethod
    def validate_max_files(cls, value: int) -> int:
        if value < 1 or value > 256:
            raise ValueError("max_files must remain between 1 and 256.")
        return value


class SmartContractTestbedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    testbed_name: str
    case_limit: int = 8

    @field_validator("testbed_name")
    @classmethod
    def validate_testbed_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("testbed_name cannot be empty.")
        return stripped

    @field_validator("case_limit")
    @classmethod
    def validate_case_limit(cls, value: int) -> int:
        if value < 1 or value > 16:
            raise ValueError("case_limit must remain between 1 and 16.")
        return value


class PointDescriptorPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: str | None = None
    y: str | None = None
    coordinates: list[str] | None = None
    point_text: str | None = None

    @field_validator("x", "y", "point_text")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        return normalized or None


class SymbolicCheckPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expression: str

    @field_validator("expression")
    @classmethod
    def validate_expression(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("expression cannot be empty.")
        return stripped


class PropertyInvariantPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    left_expression: str
    right_expression: str
    variables: list[str] | None = None
    domain_min: int = -8
    domain_max: int = 8
    max_examples: int = 24

    @field_validator("left_expression", "right_expression")
    @classmethod
    def validate_expression_pair(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("expression cannot be empty.")
        if len(stripped) > 512:
            raise ValueError("expression is too large for bounded local property checks.")
        return stripped

    @field_validator("variables")
    @classmethod
    def validate_variables(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        if len(normalized) > 3:
            raise ValueError("At most 3 variables are allowed for bounded local property checks.")
        return normalized or None

    @field_validator("domain_max")
    @classmethod
    def validate_domain_max(cls, value: int, info) -> int:
        domain_min = info.data.get("domain_min", -8)
        if value < domain_min:
            raise ValueError("domain_max must be >= domain_min.")
        if value - domain_min > 64:
            raise ValueError("The bounded property domain is too large.")
        return value

    @field_validator("max_examples")
    @classmethod
    def validate_max_examples(cls, value: int) -> int:
        if value < 1 or value > 128:
            raise ValueError("max_examples must remain between 1 and 128.")
        return value


class FormalConstraintPayload(PropertyInvariantPayload):
    pass


class FuzzMutationPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_kind: str
    seed_input: str
    mutations: int = 12
    curve_name: str | None = None

    @field_validator("target_kind")
    @classmethod
    def validate_target_kind(cls, value: str) -> str:
        stripped = value.strip().lower()
        if stripped not in {"point_hex", "curve_name"}:
            raise ValueError("target_kind must be point_hex or curve_name.")
        return stripped

    @field_validator("seed_input")
    @classmethod
    def validate_seed_input(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("seed_input cannot be empty.")
        if len(stripped) > 256:
            raise ValueError("seed_input is too large for bounded local mutation probes.")
        return stripped

    @field_validator("curve_name")
    @classmethod
    def normalize_curve_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("mutations")
    @classmethod
    def validate_mutations(cls, value: int) -> int:
        if value < 1 or value > 32:
            raise ValueError("mutations must remain between 1 and 32.")
        return value


class ECCTestbedPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    testbed_name: str
    case_limit: int = 8

    @field_validator("testbed_name")
    @classmethod
    def validate_testbed_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("testbed_name cannot be empty.")
        return stripped

    @field_validator("case_limit")
    @classmethod
    def validate_case_limit(cls, value: int) -> int:
        if value < 1 or value > 16:
            raise ValueError("case_limit must remain between 1 and 16.")
        return value


class DeterministicExperimentPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    experiment_type: str = "normalize_text"
    value: str | dict[str, Any]
    repeats: int = 3

    @field_validator("experiment_type")
    @classmethod
    def validate_experiment_type(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("experiment_type cannot be empty.")
        return stripped

    @field_validator("repeats")
    @classmethod
    def validate_repeats(cls, value: int) -> int:
        if value < 1:
            raise ValueError("repeats must be >= 1.")
        return value


class FiniteFieldCheckPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    modulus: int
    left: int
    right: int
    operation: str = "equivalent_mod"

    @field_validator("modulus")
    @classmethod
    def validate_modulus(cls, value: int) -> int:
        if value <= 1:
            raise ValueError("modulus must be > 1.")
        if value > 1_000_000_000:
            raise ValueError("modulus is too large for bounded local checking.")
        return value

    @field_validator("left", "right")
    @classmethod
    def validate_operands(cls, value: int) -> int:
        if abs(value) > 1_000_000_000_000:
            raise ValueError("operand is too large for bounded local checking.")
        return value

    @field_validator("operation")
    @classmethod
    def validate_operation(cls, value: str) -> str:
        stripped = value.strip()
        if stripped != "equivalent_mod":
            raise ValueError("operation must be equivalent_mod.")
        return stripped


class ECCCurvePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    curve_name: str

    @field_validator("curve_name")
    @classmethod
    def validate_curve_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("curve_name cannot be empty.")
        return stripped


class ECCPointPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_key_hex: str | None = None
    x: str | None = None
    y: str | None = None
    coordinates: list[str] | None = None
    point_text: str | None = None
    curve_name: str | None = None

    @field_validator("public_key_hex", "x", "y", "point_text", "curve_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [item.strip() for item in value if item.strip()]
        return normalized or None


class ECCConsistencyPayload(ECCPointPayload):
    check_on_curve: bool = False
