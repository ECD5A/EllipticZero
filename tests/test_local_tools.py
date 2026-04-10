from __future__ import annotations

import json
import subprocess

import app.compute.runners.contract_compile_runner as compile_runner_module
import app.compute.runners.echidna_runner as echidna_runner_module
import app.compute.runners.foundry_runner as foundry_runner_module
import app.compute.runners.slither_runner as slither_runner_module
from app.compute.runners import (
    ContractCompileRunner,
    ContractTestbedRunner,
    ECCTestbedRunner,
    EchidnaRunner,
    FormalRunner,
    FoundryRunner,
    FuzzRunner,
    PropertyRunner,
    SageRunner,
    SlitherRunner,
    SympyRunner,
)
from app.compute.runners.toolchain_utils import select_best_solc_version
from app.config import AppConfig
from app.main import build_orchestrator
from app.tools.builtin import (
    ContractCompileTool,
    ContractInventoryTool,
    ContractParserTool,
    ContractPatternCheckTool,
    ContractSurfaceTool,
    ContractTestbedTool,
    CurveMetadataTool,
    DeterministicExperimentTool,
    ECCConsistencyCheckTool,
    ECCCurveParameterTool,
    ECCPointFormatTool,
    ECCTestbedTool,
    EchidnaAuditTool,
    FiniteFieldCheckTool,
    FormalConstraintTool,
    FoundryAuditTool,
    FuzzMutationTool,
    PlaceholderMathTool,
    PointDescriptorTool,
    PropertyInvariantTool,
    SageSymbolicTool,
    SlitherAuditTool,
    SymbolicCheckTool,
)
from app.tools.curve_registry import CURVE_REGISTRY
from app.tools.registry import ToolRegistry
from app.types import make_id


def test_curve_registry_lookup_and_alias_resolution() -> None:
    secp = CURVE_REGISTRY.resolve("secp256k1")
    p256 = CURVE_REGISTRY.resolve("P-256")
    x25519 = CURVE_REGISTRY.resolve("curve25519")

    assert secp is not None and secp.canonical_name == "secp256k1"
    assert p256 is not None and p256.canonical_name == "secp256r1"
    assert x25519 is not None and x25519.canonical_name == "x25519"


def test_registry_metadata_listing() -> None:
    registry = ToolRegistry()
    registry.register(ContractCompileTool(runner=ContractCompileRunner(enabled=False)))
    registry.register(ContractInventoryTool())
    registry.register(SlitherAuditTool(runner=SlitherRunner(enabled=False)))
    registry.register(EchidnaAuditTool(runner=EchidnaRunner(enabled=False)))
    registry.register(FoundryAuditTool(runner=FoundryRunner(enabled=False)))
    registry.register(ContractParserTool())
    registry.register(ContractSurfaceTool())
    registry.register(ContractPatternCheckTool())
    registry.register(CurveMetadataTool())
    registry.register(ECCCurveParameterTool())
    registry.register(ECCPointFormatTool())
    registry.register(ECCConsistencyCheckTool())
    registry.register(PointDescriptorTool())
    registry.register(SageSymbolicTool(runner=SageRunner(enabled=False)))
    registry.register(SymbolicCheckTool(runner=SympyRunner(enabled=True)))
    registry.register(PropertyInvariantTool(runner=PropertyRunner(enabled=True, max_examples=12)))
    registry.register(FormalConstraintTool(runner=FormalRunner(enabled=True)))
    registry.register(FiniteFieldCheckTool())
    registry.register(FuzzMutationTool(runner=FuzzRunner(enabled=True)))
    registry.register(ECCTestbedTool(runner=ECCTestbedRunner(enabled=True)))
    registry.register(DeterministicExperimentTool())
    registry.register(PlaceholderMathTool())

    names = registry.names()
    metadata = registry.list_metadata()

    assert "contract_compile_tool" in names
    assert "contract_inventory_tool" in names
    assert "slither_audit_tool" in names
    assert "echidna_audit_tool" in names
    assert "foundry_audit_tool" in names
    assert "contract_parser_tool" in names
    assert "contract_surface_tool" in names
    assert "contract_pattern_check_tool" in names
    assert "curve_metadata_tool" in names
    assert "ecc_curve_parameter_tool" in names
    assert "ecc_point_format_tool" in names
    assert "ecc_consistency_check_tool" in names
    assert "point_descriptor_tool" in names
    assert "sage_symbolic_tool" in names
    assert "symbolic_check_tool" in names
    assert "property_invariant_tool" in names
    assert "formal_constraint_tool" in names
    assert "finite_field_check_tool" in names
    assert "fuzz_mutation_tool" in names
    assert "ecc_testbed_tool" in names
    assert "deterministic_experiment_tool" in names
    assert any(item.name == "curve_metadata_tool" and item.deterministic for item in metadata)


def test_contract_compile_tool_reports_unavailable_without_local_compiler(monkeypatch) -> None:
    monkeypatch.setattr(compile_runner_module, "resolve_local_binary", lambda _: None)
    monkeypatch.setattr(compile_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    runner = ContractCompileRunner(enabled=True)
    tool = ContractCompileTool(runner=runner)

    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.8.20; contract Vault {}",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "unavailable"
    assert result["result_data"]["compiler_binary"] is None
    assert "solc" in result["conclusion"].lower()


def test_contract_compile_tool_reports_success_with_fake_local_compiler(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        return "solc" if binary == "solc" else None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        if "--standard-json" in args:
            payload = {
                "contracts": {
                    "Contract.sol": {
                        "Vault": {
                            "abi": [],
                            "evm": {"bytecode": {"object": "0x60"}},
                        }
                    }
                },
                "sources": {"Contract.sol": {"ast": {"nodeType": "SourceUnit"}}},
                "errors": [
                    {
                        "severity": "warning",
                        "type": "Warning",
                        "component": "general",
                        "message": "floating pragma",
                    }
                ],
            }
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(compile_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(compile_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(compile_runner_module.subprocess, "run", fake_run)

    runner = ContractCompileRunner(enabled=True)
    tool = ContractCompileTool(runner=runner)
    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.8.20; contract Vault {}",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["compile_succeeded"] is True
    assert result["result_data"]["compiled_contract_names"] == ["Vault"]
    assert result["result_data"]["warning_count"] == 1
    assert result["result_data"]["ast_present"] is True
    assert result["result_data"]["compiler_binary"] == "solc"


def test_slither_audit_tool_reports_unavailable_without_local_binaries(monkeypatch) -> None:
    monkeypatch.setattr(slither_runner_module, "resolve_local_binary", lambda _: None)
    monkeypatch.setattr(slither_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    runner = SlitherRunner(enabled=True)
    tool = SlitherAuditTool(runner=runner)

    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.8.20; contract Vault {}",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "unavailable"
    assert result["result_data"]["analyzer_binary"] is None


def test_foundry_audit_tool_reports_unavailable_without_local_binaries(monkeypatch) -> None:
    monkeypatch.setattr(foundry_runner_module, "resolve_local_binary", lambda _: None)
    monkeypatch.setattr(foundry_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    runner = FoundryRunner(enabled=True)
    tool = FoundryAuditTool(runner=runner)

    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.8.20; contract Vault {}",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "unavailable"
    assert result["result_data"]["forge_binary"] is None


def test_echidna_audit_tool_reports_unavailable_without_local_binaries(monkeypatch) -> None:
    monkeypatch.setattr(echidna_runner_module, "resolve_local_binary", lambda _: None)
    monkeypatch.setattr(echidna_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    runner = EchidnaRunner(enabled=True)
    tool = EchidnaAuditTool(runner=runner)

    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.8.20; contract VaultHarness { function echidna_invariant() public returns (bool) { return true; } }",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "unavailable"
    assert result["result_data"]["analyzer_binary"] is None


def test_slither_audit_tool_reports_findings_with_fake_local_analyzer(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        if binary == "slither":
            return "slither"
        if binary == "solc":
            return "solc"
        return None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            if args[0] == "solc":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="0.11.5",
                stderr="",
            )
        if "--json" in args:
            payload = {
                "success": True,
                "results": {
                    "detectors": [
                        {
                            "check": "reentrancy-eth",
                            "impact": "High",
                            "confidence": "Medium",
                            "description": "Reentrancy risk in withdraw",
                        },
                        {
                            "check": "tx-origin",
                            "impact": "Medium",
                            "confidence": "High",
                            "description": "tx.origin usage in auth path",
                        },
                    ]
                },
            }
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(slither_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(slither_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(slither_runner_module.subprocess, "run", fake_run)

    runner = SlitherRunner(enabled=True)
    tool = SlitherAuditTool(runner=runner)
    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.8.20; contract Vault {}",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "observed_issue"
    assert result["result_data"]["analysis_succeeded"] is True
    assert result["result_data"]["finding_count"] == 2
    assert result["result_data"]["detector_name_counts"]["reentrancy-eth"] == 1
    assert result["result_data"]["impact_counts"]["high"] == 1
    assert result["result_data"]["high_severity_present"] is True


def test_foundry_audit_tool_reports_success_with_fake_local_analyzer(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        if binary == "forge":
            return "forge"
        if binary == "solc":
            return "solc"
        return None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            if args[0] == "forge":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="forge 1.0.0",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        if len(args) >= 2 and args[1] == "build":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="build completed",
                stderr="",
            )
        if len(args) >= 4 and args[1] == "inspect" and args[3] == "methodIdentifiers":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"ping()": "5c36b186"}),
                stderr="",
            )
        if len(args) >= 4 and args[1] == "inspect" and args[3] == "storageLayout":
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps({"storage": [{"slot": "0", "label": "owner"}]}),
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(foundry_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(foundry_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(foundry_runner_module.subprocess, "run", fake_run)

    runner = FoundryRunner(enabled=True)
    tool = FoundryAuditTool(runner=runner)
    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.8.20; contract Vault { function ping() external pure returns (uint256) { return 1; } }",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["build_succeeded"] is True
    assert result["result_data"]["inspect_contracts_succeeded"] == 1
    assert result["result_data"]["method_identifier_counts"]["Vault"] == 1
    assert result["result_data"]["storage_entry_counts"]["Vault"] == 1
    assert result["result_data"]["storage_layout_present"] is True


def test_echidna_audit_tool_reports_failing_checks_with_fake_local_analyzer(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        if binary == "echidna":
            return "echidna"
        if binary == "solc":
            return "solc"
        return None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            if args[0] == "echidna":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="echidna 2.2.2",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        return subprocess.CompletedProcess(
            args=args,
            returncode=1,
            stdout=json.dumps(
                {
                    "success": False,
                    "tests": [
                        {"name": "echidna_owner_is_not_zero", "status": "passed"},
                        {"name": "echidna_only_owner_can_set", "status": "solved"},
                    ],
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(echidna_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(echidna_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(echidna_runner_module.subprocess, "run", fake_run)

    runner = EchidnaRunner(enabled=True)
    tool = EchidnaAuditTool(runner=runner)
    payload = tool.validate_payload(
        {
            "contract_code": (
                "pragma solidity ^0.8.20; contract VaultHarness { "
                "function echidna_owner_is_not_zero() public returns (bool) { return true; } "
                "function echidna_only_owner_can_set() public returns (bool) { return false; } }"
            ),
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "observed_issue"
    assert result["result_data"]["analysis_mode"] == "property"
    assert result["result_data"]["analysis_applicable"] is True
    assert result["result_data"]["failing_test_count"] == 1
    assert result["result_data"]["failing_tests"] == ["echidna_only_owner_can_set"]


def test_contract_compile_tool_uses_managed_solc_when_path_binary_is_unavailable(monkeypatch) -> None:
    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        if "--standard-json" in args:
            payload = {
                "contracts": {"Contract.sol": {"Vault": {"abi": []}}},
                "sources": {"Contract.sol": {"ast": {"nodeType": "SourceUnit"}}},
                "errors": [],
            }
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout=json.dumps(payload),
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(compile_runner_module, "resolve_local_binary", lambda _: None)
    monkeypatch.setattr(
        compile_runner_module,
        "resolve_managed_solc_binary",
        lambda **_: ("C:/managed/solc.exe", "0.8.20"),
    )
    monkeypatch.setattr(compile_runner_module.subprocess, "run", fake_run)

    runner = ContractCompileRunner(enabled=True)
    tool = ContractCompileTool(runner=runner)
    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.8.20; contract Vault {}",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["compiler_binary"] == "C:/managed/solc.exe"


def test_select_best_solc_version_prefers_highest_matching_pragma() -> None:
    selected = select_best_solc_version(
        installed_versions=["0.8.20", "0.8.24", "0.8.25", "0.8.30"],
        preferred_version="0.8.20",
        pragma_spec="^0.8.24",
        require_pragma_match=True,
    )

    assert selected == "0.8.30"


def test_select_best_solc_version_prefers_exact_pragma_match() -> None:
    selected = select_best_solc_version(
        installed_versions=["0.8.20", "0.8.24", "0.8.25", "0.8.30"],
        preferred_version="0.8.20",
        pragma_spec="0.8.24",
        require_pragma_match=True,
    )

    assert selected == "0.8.24"


def test_select_best_solc_version_returns_none_when_strict_pragma_has_no_match() -> None:
    selected = select_best_solc_version(
        installed_versions=["0.8.20", "0.8.24"],
        preferred_version="0.8.20",
        pragma_spec="^0.9.0",
        require_pragma_match=True,
    )

    assert selected is None


def test_contract_compile_tool_reports_unavailable_when_no_pragma_matching_compiler_exists(monkeypatch) -> None:
    monkeypatch.setattr(compile_runner_module, "resolve_local_binary", lambda _: None)
    monkeypatch.setattr(compile_runner_module, "list_managed_solc_versions", lambda _: ["0.8.20", "0.8.24"])
    monkeypatch.setattr(compile_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))

    runner = ContractCompileRunner(enabled=True)
    tool = ContractCompileTool(runner=runner)
    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.9.0; contract FutureVault {}",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "unavailable"
    assert result["result_data"]["pragma_spec"] == "^0.9.0"
    assert any("required_pragma=^0.9.0" in note for note in result["notes"])


def test_slither_audit_tool_reports_unavailable_when_no_pragma_matching_compiler_exists(monkeypatch) -> None:
    monkeypatch.setattr(slither_runner_module, "resolve_local_binary", lambda binary: "slither" if binary == "slither" else None)
    monkeypatch.setattr(slither_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="0.11.5",
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(slither_runner_module.subprocess, "run", fake_run)

    runner = SlitherRunner(enabled=True)
    tool = SlitherAuditTool(runner=runner)
    payload = tool.validate_payload(
        {
            "contract_code": "pragma solidity ^0.9.0; contract FutureVault {}",
            "language": "solidity",
        }
    )
    result = tool.run(payload)

    assert result["status"] == "unavailable"
    assert result["result_data"]["pragma_spec"] == "^0.9.0"
    assert any("required_pragma=^0.9.0" in note for note in result["notes"])


def test_curve_metadata_tool_basic_behavior() -> None:
    tool = CurveMetadataTool()
    payload = tool.validate_payload({"curve_name": "P-256"})
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["recognized"] is True
    assert result["result_data"]["curve_name"] == "secp256r1"


def test_point_descriptor_tool_basic_behavior() -> None:
    tool = PointDescriptorTool()
    payload = tool.validate_payload({"x": "0x1234abcd", "y": "0x5678ef00"})
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["well_formed"] is True
    assert result["result_data"]["coordinate_format"] == "hex_like"
    assert result["result_data"]["x_length"] == 8
    assert result["result_data"]["y_length"] == 8


def test_symbolic_check_tool_basic_behavior() -> None:
    tool = SymbolicCheckTool(runner=SympyRunner(enabled=True))
    payload = tool.validate_payload({"expression": "x + x - y"})
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["parsed"] is True
    assert result["result_data"]["normalized_form"] is not None
    assert result["result_data"]["errors"] == []


def test_property_and_formal_tools_basic_behavior() -> None:
    property_tool = PropertyInvariantTool(runner=PropertyRunner(enabled=True, max_examples=12))
    property_payload = property_tool.validate_payload(
        {
            "left_expression": "x + 1",
            "right_expression": "1 + x",
            "max_examples": 12,
        }
    )
    property_result = property_tool.run(property_payload)

    formal_tool = FormalConstraintTool(runner=FormalRunner(enabled=True))
    formal_payload = formal_tool.validate_payload(
        {
            "left_expression": "x + 1",
            "right_expression": "1 + x",
        }
    )
    formal_result = formal_tool.run(formal_payload)

    assert property_result["status"] in {"ok", "unavailable"}
    assert "property_holds" in property_result["result_data"]
    assert formal_result["status"] in {"ok", "unavailable"}
    assert "property_holds" in formal_result["result_data"]


def test_fuzz_and_testbed_tools_basic_behavior() -> None:
    fuzz_tool = FuzzMutationTool(runner=FuzzRunner(enabled=True))
    fuzz_payload = fuzz_tool.validate_payload(
        {
            "target_kind": "point_hex",
            "seed_input": "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
            "mutations": 4,
            "curve_name": "secp256k1",
        }
    )
    fuzz_result = fuzz_tool.run(fuzz_payload)

    testbed_tool = ECCTestbedTool(runner=ECCTestbedRunner(enabled=True))
    testbed_payload = testbed_tool.validate_payload({"testbed_name": "point_anomaly_corpus", "case_limit": 4})
    testbed_result = testbed_tool.run(testbed_payload)

    assert fuzz_result["status"] in {"ok", "observed_issue"}
    assert fuzz_result["result_data"]["mutations_generated"] == 4
    assert testbed_result["status"] in {"ok", "observed_issue"}
    assert testbed_result["result_data"]["case_count"] == 4
    assert "anomaly_case_ids" in testbed_result["result_data"]
    assert "issue_type_counts" in testbed_result["result_data"]


def test_curve_domain_testbed_reports_bounded_registry_completeness_gaps() -> None:
    testbed_tool = ECCTestbedTool(runner=ECCTestbedRunner(enabled=True))
    testbed_payload = testbed_tool.validate_payload({"testbed_name": "curve_domain_corpus", "case_limit": 6})
    testbed_result = testbed_tool.run(testbed_payload)

    assert testbed_result["status"] in {"ok", "observed_issue"}
    assert testbed_result["result_data"]["testbed_name"] == "curve_domain_corpus"
    assert testbed_result["result_data"]["case_count"] == 6
    assert "secp384r1" in testbed_result["result_data"]["anomaly_case_ids"]
    assert any(
        "Short-Weierstrass registry entry is missing bounded domain fields:"
        in issue
        for issue in testbed_result["result_data"]["issue_type_counts"]
    )


def test_ecc_testbeds_report_encoding_and_subgroup_review_signals() -> None:
    testbed_tool = ECCTestbedTool(runner=ECCTestbedRunner(enabled=True))

    encoding_payload = testbed_tool.validate_payload({"testbed_name": "encoding_edge_corpus", "case_limit": 6})
    encoding_result = testbed_tool.run(encoding_payload)
    assert encoding_result["status"] in {"ok", "observed_issue"}
    assert encoding_result["result_data"]["testbed_name"] == "encoding_edge_corpus"
    assert "x25519_like_public_key" in encoding_result["result_data"]["anomaly_case_ids"]
    assert any(
        "Point-like input did not match a supported bounded point encoding." in issue
        or "Input contains malformed hexadecimal or coordinate data." in issue
        for issue in encoding_result["result_data"]["issue_type_counts"]
    )

    subgroup_payload = testbed_tool.validate_payload({"testbed_name": "subgroup_cofactor_corpus", "case_limit": 6})
    subgroup_result = testbed_tool.run(subgroup_payload)
    assert subgroup_result["status"] in {"ok", "observed_issue"}
    assert subgroup_result["result_data"]["testbed_name"] == "subgroup_cofactor_corpus"
    assert "x25519" in subgroup_result["result_data"]["anomaly_case_ids"]
    assert any(
        "subgroup" in issue.lower() or "cofactor" in issue.lower() or "25519-family" in issue
        for issue in subgroup_result["result_data"]["issue_type_counts"]
    )

    family_payload = testbed_tool.validate_payload({"testbed_name": "curve_family_corpus", "case_limit": 5})
    family_result = testbed_tool.run(family_payload)
    assert family_result["status"] in {"ok", "observed_issue"}
    assert family_result["result_data"]["testbed_name"] == "curve_family_corpus"
    assert "x25519" in family_result["result_data"]["anomaly_case_ids"]
    assert any(
        "Curve family requires non-short-Weierstrass handling" in issue
        or "Alias form resolved correctly" in issue
        for issue in family_result["result_data"]["issue_type_counts"]
    )


def test_contract_testbed_reports_upgrade_and_entropy_review_signals() -> None:
    testbed_tool = ContractTestbedTool(runner=ContractTestbedRunner(enabled=True))

    upgrade_payload = testbed_tool.validate_payload({"testbed_name": "upgrade_surface_corpus", "case_limit": 4})
    upgrade_result = testbed_tool.run(upgrade_payload)
    assert upgrade_result["status"] in {"ok", "observed_issue"}
    assert upgrade_result["result_data"]["testbed_name"] == "upgrade_surface_corpus"
    assert "unguarded_upgrade_to" in upgrade_result["result_data"]["anomaly_case_ids"]
    assert any(
        "unguarded_upgrade_surface:upgradeTo" in issue
        for issue in upgrade_result["result_data"]["issue_type_counts"]
    )

    entropy_payload = testbed_tool.validate_payload({"testbed_name": "time_entropy_corpus", "case_limit": 4})
    entropy_result = testbed_tool.run(entropy_payload)
    assert entropy_result["status"] in {"ok", "observed_issue"}
    assert entropy_result["result_data"]["testbed_name"] == "time_entropy_corpus"
    assert "timestamp_entropy_lottery" in entropy_result["result_data"]["anomaly_case_ids"]
    assert any(
        "entropy_source_review_required:pickWinner" in issue
        or "entropy_source_review_required:draw" in issue
        for issue in entropy_result["result_data"]["issue_type_counts"]
    )


def test_contract_testbed_reports_token_and_assembly_review_signals() -> None:
    testbed_tool = ContractTestbedTool(runner=ContractTestbedRunner(enabled=True))

    token_payload = testbed_tool.validate_payload({"testbed_name": "token_interaction_corpus", "case_limit": 4})
    token_result = testbed_tool.run(token_payload)
    assert token_result["status"] in {"ok", "observed_issue"}
    assert token_result["result_data"]["testbed_name"] == "token_interaction_corpus"
    assert "unchecked_token_sweep" in token_result["result_data"]["anomaly_case_ids"]
    assert "arbitrary_from_transfer" in token_result["result_data"]["anomaly_case_ids"]
    assert any(
        "unchecked_token_transfer_surface:sweep" in issue
        or "unchecked_token_transfer_from_surface:rescue" in issue
        or "arbitrary_from_transfer_surface:rescue" in issue
        for issue in token_result["result_data"]["issue_type_counts"]
    )

    assembly_payload = testbed_tool.validate_payload({"testbed_name": "assembly_review_corpus", "case_limit": 4})
    assembly_result = testbed_tool.run(assembly_payload)
    assert assembly_result["status"] in {"ok", "observed_issue"}
    assert assembly_result["result_data"]["testbed_name"] == "assembly_review_corpus"
    assert "assembly_storage_write" in assembly_result["result_data"]["anomaly_case_ids"]
    assert any(
        "assembly_review_required:setOwner" in issue
        or "assembly_review_required:route" in issue
        for issue in assembly_result["result_data"]["issue_type_counts"]
    )


def test_contract_testbed_reports_approval_validation_and_state_machine_signals() -> None:
    testbed_tool = ContractTestbedTool(runner=ContractTestbedRunner(enabled=True))

    approval_payload = testbed_tool.validate_payload({"testbed_name": "approval_review_corpus", "case_limit": 4})
    approval_result = testbed_tool.run(approval_payload)
    assert approval_result["status"] in {"ok", "observed_issue"}
    assert approval_result["result_data"]["testbed_name"] == "approval_review_corpus"
    assert "unchecked_direct_approve" in approval_result["result_data"]["anomaly_case_ids"]
    assert any(
        "unchecked_approve_surface:approveSpender" in issue
        or "approve_race_review_required:approveSpender" in issue
        for issue in approval_result["result_data"]["issue_type_counts"]
    )

    validation_payload = testbed_tool.validate_payload({"testbed_name": "upgrade_validation_corpus", "case_limit": 4})
    validation_result = testbed_tool.run(validation_payload)
    assert validation_result["status"] in {"ok", "observed_issue"}
    assert validation_result["result_data"]["testbed_name"] == "upgrade_validation_corpus"
    assert "upgrade_without_zero_or_code_check" in validation_result["result_data"]["anomaly_case_ids"]
    assert any(
        "missing_zero_address_validation:upgradeTo" in issue
        or "unvalidated_implementation_target:upgradeTo" in issue
        for issue in validation_result["result_data"]["issue_type_counts"]
    )

    state_payload = testbed_tool.validate_payload({"testbed_name": "state_machine_corpus", "case_limit": 4})
    state_result = testbed_tool.run(state_payload)
    assert state_result["status"] in {"ok", "observed_issue"}
    assert state_result["result_data"]["testbed_name"] == "state_machine_corpus"
    assert "status_update_after_external_call" in state_result["result_data"]["anomaly_case_ids"]
    assert any(
        "state_transition_after_external_call:execute" in issue
        for issue in state_result["result_data"]["issue_type_counts"]
    )


def test_contract_testbed_reports_signature_oracle_and_loop_signals() -> None:
    testbed_tool = ContractTestbedTool(runner=ContractTestbedRunner(enabled=True))

    signature_payload = testbed_tool.validate_payload({"testbed_name": "signature_review_corpus", "case_limit": 4})
    signature_result = testbed_tool.run(signature_payload)
    assert signature_result["status"] in {"ok", "observed_issue"}
    assert signature_result["result_data"]["testbed_name"] == "signature_review_corpus"
    assert "permit_without_nonce_or_deadline" in signature_result["result_data"]["anomaly_case_ids"]
    assert any(
        "signature_replay_review_required:permitAction" in issue
        for issue in signature_result["result_data"]["issue_type_counts"]
    )

    oracle_payload = testbed_tool.validate_payload({"testbed_name": "oracle_review_corpus", "case_limit": 4})
    oracle_result = testbed_tool.run(oracle_payload)
    assert oracle_result["status"] in {"ok", "observed_issue"}
    assert oracle_result["result_data"]["testbed_name"] == "oracle_review_corpus"
    assert "price_feed_without_staleness_check" in oracle_result["result_data"]["anomaly_case_ids"]
    assert any(
        "oracle_staleness_review_required:quote" in issue
        for issue in oracle_result["result_data"]["issue_type_counts"]
    )

    loop_payload = testbed_tool.validate_payload({"testbed_name": "loop_payout_corpus", "case_limit": 4})
    loop_result = testbed_tool.run(loop_payload)
    assert loop_result["status"] in {"ok", "observed_issue"}
    assert loop_result["result_data"]["testbed_name"] == "loop_payout_corpus"
    assert "batch_payout_external_call_loop" in loop_result["result_data"]["anomaly_case_ids"]
    assert any(
        "external_call_in_loop:distribute" in issue
        for issue in loop_result["result_data"]["issue_type_counts"]
    )


def test_contract_testbed_reports_repo_casebook_signals() -> None:
    testbed_tool = ContractTestbedTool(runner=ContractTestbedRunner(enabled=True))

    upgrade_payload = testbed_tool.validate_payload({"testbed_name": "repo_upgrade_casebook", "case_limit": 4})
    upgrade_result = testbed_tool.run(upgrade_payload)
    assert upgrade_result["status"] in {"ok", "observed_issue"}
    assert upgrade_result["result_data"]["testbed_name"] == "repo_upgrade_casebook"
    assert upgrade_result["result_data"]["repo_case_count"] == 3
    assert upgrade_result["result_data"]["matched_review_lane_count"] >= 1
    assert upgrade_result["result_data"]["matched_risk_family_lane_count"] >= 1
    assert upgrade_result["result_data"]["matched_function_priority_count"] >= 1
    assert upgrade_result["result_data"]["matched_case_count"] >= 1
    assert upgrade_result["result_data"]["matched_case_ids"]
    assert upgrade_result["result_data"]["validation_group_count"] >= 1
    assert upgrade_result["result_data"]["validated_group_count"] >= 1
    assert any(
        "coverage=" in item.lower() and "repo_upgrade_casebook" in item
        for item in upgrade_result["result_data"]["repo_casebook_coverage"]
    )
    assert "proxy_delegatecall_upgrade_lane" in upgrade_result["result_data"]["anomaly_case_ids"]
    assert any(
        "repo-scale proxy and upgrade lanes" in item.lower()
        or "guarded_proxy_upgrade_lane" in item
        for item in upgrade_result["result_data"]["remediation_validation"]
    )
    assert any(
        "proxy_fallback_delegatecall_review_required:fallback" in issue
        or "storage_slot_write_review_required:setAddress" in issue
        for issue in upgrade_result["result_data"]["issue_type_counts"]
    )

    oracle_payload = testbed_tool.validate_payload({"testbed_name": "repo_oracle_casebook", "case_limit": 4})
    oracle_result = testbed_tool.run(oracle_payload)
    assert oracle_result["status"] in {"ok", "observed_issue"}
    assert oracle_result["result_data"]["testbed_name"] == "repo_oracle_casebook"
    assert oracle_result["result_data"]["repo_case_count"] == 3
    assert oracle_result["result_data"]["matched_review_lane_count"] >= 1
    assert oracle_result["result_data"]["matched_case_count"] >= 1
    assert oracle_result["result_data"]["matched_case_ids"]
    assert "stale_oracle_liquidation_lane" in oracle_result["result_data"]["anomaly_case_ids"]
    assert any(
        "coverage=" in item.lower() and "repo_oracle_casebook" in item
        for item in oracle_result["result_data"]["repo_casebook_coverage"]
    )
    assert any(
        "oracle freshness" in item.lower()
        or "fresh_oracle_liquidation_lane" in item
        for item in oracle_result["result_data"]["remediation_validation"]
    )
    assert any(
        "oracle_staleness_review_required:quote" in issue
        for issue in oracle_result["result_data"]["issue_type_counts"]
    )


def test_deterministic_experiment_tool_basic_behavior() -> None:
    tool = DeterministicExperimentTool()
    payload = tool.validate_payload(
        {"experiment_type": "normalize_text", "value": "  A   Test   Value  ", "repeats": 3}
    )
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["repeatability"] is True
    assert result["result_data"]["result"] == "a test value"
    assert len(result["result_data"]["normalized_outputs"]) == 3


def test_orchestrator_planning_and_payload_validation() -> None:
    run_root = f".test_runs/{make_id('plan')}"
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
            "storage": {
                "artifacts_dir": run_root,
                "sessions_dir": f"{run_root}/sessions",
                "traces_dir": f"{run_root}/traces",
                "bundles_dir": f"{run_root}/bundles",
            },
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    session = orchestrator.run_session(
        seed_text="Inspect whether P-256 metadata and named-curve references stay consistent.",
        author="tool-test",
    )

    assert session.jobs
    job = session.jobs[0]
    assert job.tool_plan is not None
    assert job.experiment_spec is not None
    assert job.experiment_spec.target_kind == "curve"
    assert job.tool_plan.tool_name == "curve_metadata_tool"
    assert "CryptographyAgent" in job.tool_plan.selected_by_roles

    assert session.evidence
    evidence = session.evidence[0]
    assert evidence.tool_metadata_snapshot is not None
    assert evidence.experiment_type == "curve_metadata_math_check"
    assert "CryptographyAgent" in evidence.selected_by_roles
    assert session.report is not None
    assert any(
        "CryptographyAgent -> curve_metadata_tool [curve_metadata_math_check]" in item
        for item in session.report.local_experiment_summary
    )
    assert evidence.target_kind == "curve"
