from __future__ import annotations

import json
from pathlib import Path

from app.cli.text_rendering import render_evaluation_summary
from app.config import AppConfig
from app.core.experiment_packs import ExperimentPackRegistry
from app.core.golden_cases import list_golden_cases, prepare_golden_case_run, render_golden_cases
from app.core.research_targets import ResearchTargetRegistry
from app.core.seed_parsing import build_smart_contract_seed, extract_contract_root
from app.llm.providers.mock_provider import MockLLMProvider
from app.main import build_orchestrator, build_parser
from app.models.sandbox import ResearchTarget
from app.tools.builtin import (
    ContractInventoryTool,
    ContractParserTool,
    ContractPatternCheckTool,
    ContractSurfaceTool,
)
from app.types import make_id

GOLDEN_ROOT = Path("examples") / "golden_cases"
GOLDEN_MANIFEST = GOLDEN_ROOT / "golden_manifest.json"


def _load_manifest() -> dict:
    return json.loads(GOLDEN_MANIFEST.read_text(encoding="utf-8"))


def _make_config(run_root: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
            "storage": {
                "artifacts_dir": str(run_root),
                "sessions_dir": str(run_root / "sessions"),
                "traces_dir": str(run_root / "traces"),
                "math_artifacts_dir": str(run_root / "math"),
                "bundles_dir": str(run_root / "bundles"),
            },
            "plugins": {
                "enabled": True,
                "directory": "plugins",
                "allow_local_plugins": True,
            },
            "sage": {
                "enabled": False,
                "binary": "sage",
                "timeout_seconds": 5,
            },
            "research": {
                "default_mode": "standard",
                "max_exploratory_branches": 2,
                "max_jobs_per_session": 2,
                "require_manual_review_for_exploratory": True,
            },
            "advanced_math_enabled": True,
            "log_level": "INFO",
            "max_hypotheses": 3,
            "tool_timeout_seconds": 15,
        }
    )


def test_golden_manifest_references_existing_inputs_and_known_packs() -> None:
    manifest = _load_manifest()
    registry = ExperimentPackRegistry()
    pack_names = set(registry.names())
    case_ids: set[str] = set()

    assert manifest["schema_version"] == 1
    assert manifest["cases"]

    for case in manifest["cases"]:
        case_id = case["case_id"]
        assert case_id not in case_ids
        case_ids.add(case_id)
        assert (GOLDEN_ROOT / case["input_file"]).is_file()
        assert case["recommended_pack"] in pack_names
        assert case["recommended_pack"] in case["sample_command"]
        assert case["expected_report_shape"]["must_include"]
        assert case["expected_report_shape"]["must_not_claim"]
        if fallback_pack := case.get("fallback_pack"):
            assert fallback_pack in pack_names
        if contract_root := case.get("contract_root"):
            assert (GOLDEN_ROOT / contract_root).is_dir()


def test_golden_cli_parser_and_renderer_expose_cases() -> None:
    parser = build_parser()
    args = parser.parse_args(["--golden-case", "contract-repo-scale-lending-protocol"])
    listed = list_golden_cases()
    rendered_en = render_golden_cases(language="en")
    rendered_ru = render_golden_cases(language="ru")

    assert args.golden_case == "contract-repo-scale-lending-protocol"
    assert parser.parse_args(["--list-golden-cases"]).list_golden_cases is True
    assert any(case["case_id"] == "contract-repo-scale-lending-protocol" for case in listed)
    assert "EllipticZero Golden Cases" in rendered_en
    assert "contract-repo-scale-lending-protocol" in rendered_en
    assert "Golden cases EllipticZero" in rendered_ru
    assert "contract-repo-scale-lending-protocol" in rendered_ru


def test_evaluation_summary_cli_parser_and_renderer_expose_eval_paths() -> None:
    parser = build_parser()
    args = parser.parse_args(["--evaluation-summary"])
    json_args = parser.parse_args(["--evaluation-summary", "--evaluation-summary-format", "json"])
    pack_names = ExperimentPackRegistry().names()
    cases = list_golden_cases()

    rendered_en = render_evaluation_summary(
        language="en",
        golden_cases=cases,
        pack_names=pack_names,
        provider_names=["mock", "openai", "openrouter"],
    )
    rendered_ru = render_evaluation_summary(
        language="ru",
        golden_cases=cases,
        pack_names=pack_names,
        provider_names=["mock", "openai", "openrouter"],
    )
    rendered_json = render_evaluation_summary(
        language="en",
        golden_cases=cases,
        pack_names=pack_names,
        provider_names=["mock", "openai", "openrouter"],
        output_format="json",
    )
    payload = json.loads(rendered_json)

    assert args.evaluation_summary is True
    assert json_args.evaluation_summary_format == "json"
    assert "EllipticZero Evaluation Summary" in rendered_en
    assert f"Golden cases: {len(cases)}" in rendered_en
    assert f"Experiment packs: {len(pack_names)}" in rendered_en
    assert "python -m app.main --doctor" in rendered_en
    assert "contract-repo-scale-lending-protocol" in rendered_en
    assert "Сводка оценки EllipticZero" in rendered_ru
    assert "Быстрая проверка без ключей" in rendered_ru
    assert "docs/ru/EVALUATION.ru.md" in rendered_ru
    assert payload["project"] == "EllipticZero"
    assert payload["golden_cases"]["count"] == len(cases)
    assert payload["experiment_packs"]["count"] == len(pack_names)
    assert "contract-repo-scale-lending-protocol" in payload["golden_cases"]["case_ids"]
    assert payload["license"]["current"] == "FSL-1.1-ALv2"


def test_prepare_golden_case_run_builds_ecc_and_contract_sessions() -> None:
    ecc_run = prepare_golden_case_run("ecc-secp256k1-point-format-edge")
    repo_run = prepare_golden_case_run("contract-repo-scale-lending-protocol")

    assert ecc_run.domain == "ecc_research"
    assert ecc_run.experiment_pack_name == "point_format_inspection_pack"
    assert ecc_run.synthetic_target_name == "toy_secp256k1_bad_prefix_compressed"
    assert "Recommended pack: point_format_inspection_pack" in ecc_run.seed_text

    assert repo_run.domain == "smart_contract_audit"
    assert repo_run.experiment_pack_name == "lending_protocol_benchmark_pack"
    assert repo_run.synthetic_target_name is None
    assert repo_run.contract_root is not None
    assert repo_run.contract_root.is_dir()
    assert extract_contract_root(repo_run.seed_text) == str(repo_run.contract_root)
    assert "contract LendingPool" in repo_run.seed_text


def test_mock_provider_keeps_ecc_library_wording_out_of_contract_mode() -> None:
    provider = MockLLMProvider()
    ecc_run = prepare_golden_case_run("ecc-secp256k1-point-format-edge")
    contract_run = prepare_golden_case_run("contract-vault-permission-lane")

    assert provider._is_smart_contract_seed(ecc_run.seed_text) is False
    assert provider._is_smart_contract_seed(contract_run.seed_text) is True


def test_golden_ecc_cases_recommend_expected_benchmark_packs() -> None:
    manifest = _load_manifest()
    registry = ExperimentPackRegistry()
    target_registry = ResearchTargetRegistry()

    for case in manifest["cases"]:
        if case["domain"] != "ecc_research":
            continue
        seed_text = (GOLDEN_ROOT / case["input_file"]).read_text(encoding="utf-8")
        target = target_registry.build_synthetic_target(case["synthetic_target"])
        recommended = registry.recommend(seed_text=seed_text, research_target=target)
        recommended_names = [item.pack_name for item in recommended]

        assert case["recommended_pack"] in recommended_names


def test_golden_smart_contract_cases_recommend_expected_benchmark_packs() -> None:
    manifest = _load_manifest()
    registry = ExperimentPackRegistry()

    for case in manifest["cases"]:
        if case["domain"] != "smart_contract_audit":
            continue
        source_path = GOLDEN_ROOT / case["input_file"]
        contract_root = GOLDEN_ROOT / case["contract_root"] if case.get("contract_root") else source_path.parent
        contract_code = source_path.read_text(encoding="utf-8")
        seed = build_smart_contract_seed(
            idea_text=case["sample_command"],
            contract_code=contract_code,
            language="solidity",
            source_label=str(source_path),
            contract_root=str(contract_root),
        )
        target = ResearchTarget(target_kind="smart_contract", target_reference=contract_code)

        recommended = registry.recommend(seed_text=seed, research_target=target)
        recommended_names = [item.pack_name for item in recommended]

        assert case["recommended_pack"] in recommended_names


def test_golden_contract_fixtures_parse_and_expose_expected_review_lanes() -> None:
    parser = ContractParserTool()
    surface_tool = ContractSurfaceTool()
    pattern_tool = ContractPatternCheckTool()

    expectations = {
        "SyntheticVault.sol": {
            "contract_name": "SyntheticVault",
            "functions": {
                "deposit",
                "redeem",
                "permitStyleApprove",
                "approveSpender",
                "recoverPermitSigner",
                "sweep",
                "setOwner",
            },
            "surface_fields": {
                "payable_functions": {"deposit"},
                "call_with_value_functions": {"redeem", "sweep"},
                "share_accounting_functions": {"redeem"},
                "approve_functions": {"approveSpender"},
                "signature_validation_functions": {"recoverPermitSigner"},
            },
        },
        "SyntheticGovernanceTimelock.sol": {
            "contract_name": "SyntheticGovernanceTimelock",
            "functions": {"queueUpgrade", "executeUpgrade", "emergencyPause", "setGuardian", "setDelay"},
            "surface_fields": {
                "delegatecall_functions": {"executeUpgrade"},
                "timestamp_functions": {"queueUpgrade", "executeUpgrade"},
                "pause_control_functions": {"emergencyPause", "emergencyUnpause"},
                "implementation_reference_functions": {"queueUpgrade", "executeUpgrade"},
            },
        },
    }

    for filename, expected in expectations.items():
        path = GOLDEN_ROOT / "contracts" / filename
        code = path.read_text(encoding="utf-8")
        payload = {"contract_code": code, "language": "solidity", "source_label": str(path)}

        parser_result = parser.run(parser.validate_payload(payload))
        assert parser_result["status"] == "ok"
        assert expected["contract_name"] in parser_result["result_data"]["contract_names"]
        assert expected["functions"].issubset(set(parser_result["result_data"]["function_names"]))

        surface_result = surface_tool.run(surface_tool.validate_payload(payload))
        assert surface_result["result_data"]["recognized"] is True
        for field_name, expected_functions in expected["surface_fields"].items():
            assert expected_functions.issubset(set(surface_result["result_data"][field_name]))

        pattern_result = pattern_tool.run(pattern_tool.validate_payload(payload))
        assert pattern_result["result_data"]["recognized"] is True
        assert pattern_result["result_data"]["bounded_static_analysis"] is True


def test_golden_repo_scale_fixture_builds_inventory_lanes() -> None:
    manifest = _load_manifest()
    repo_case = next(case for case in manifest["cases"] if case["case_id"] == "contract-repo-scale-lending-protocol")
    contracts_root = GOLDEN_ROOT / repo_case["contract_root"]
    tool = ContractInventoryTool()

    result = tool.run(tool.validate_payload({"root_path": str(contracts_root)}))
    data = result["result_data"]

    assert result["status"] == "ok"
    assert data["recognized"] is True
    assert data["file_count"] == 3
    assert data["first_party_file_count"] == 3
    assert data["dependency_file_count"] == 0
    assert any(item.endswith("LendingPool.sol") for item in data["entrypoint_candidates"])
    assert any("local import edges=2" in item for item in data["import_graph_summary"])
    assert any("LendingPool.sol" in item and "OracleAdapter.sol" in item for item in data["entrypoint_flow_summaries"])
    assert any("LendingPool.sol" in item and "collateral" in item for item in data["risk_family_lane_summaries"])
    assert any(
        "LendingPool.sol" in item and "fee/reserve/debt" in item
        for item in data["entrypoint_function_family_priorities"]
    )


def test_golden_ecc_case_executes_expected_pack_shape() -> None:
    run_root = Path(".test_runs") / make_id("goldenecc")
    orchestrator = build_orchestrator(_make_config(run_root))
    seed_text = (GOLDEN_ROOT / "ecc" / "secp256k1_metadata_seed.txt").read_text(encoding="utf-8")

    session = orchestrator.run_session(
        seed_text=seed_text,
        author="golden-ecc-test",
        experiment_pack_name="ecc_domain_completeness_benchmark_pack",
        synthetic_target_name="toy_curve_secp256k1",
    )

    assert session.selected_pack_name == "ecc_domain_completeness_benchmark_pack"
    assert "ecc_domain_completeness_benchmark_pack:curve_parameters" in session.executed_pack_steps
    assert "ecc_domain_completeness_benchmark_pack:domain_completeness_benchmark" in session.executed_pack_steps
    assert session.report is not None
    assert session.report.selected_pack_name == session.selected_pack_name
    assert session.report.executed_pack_steps == session.executed_pack_steps
    assert session.report.confidence_rationale


def test_golden_repo_scale_case_executes_expected_pack_shape() -> None:
    run_root = Path(".test_runs") / make_id("goldenrepo")
    orchestrator = build_orchestrator(_make_config(run_root))
    source_path = GOLDEN_ROOT / "protocols" / "SyntheticLendingProtocol" / "contracts" / "LendingPool.sol"
    contracts_root = source_path.parent
    seed = build_smart_contract_seed(
        idea_text="Benchmark the scoped lending protocol for collateral, liquidation, reserve, fee, and debt-accounting review lanes.",
        contract_code=source_path.read_text(encoding="utf-8"),
        language="solidity",
        source_label=str(source_path),
        contract_root=str(contracts_root),
    )

    session = orchestrator.run_session(
        seed_text=seed,
        author="golden-repo-test",
        experiment_pack_name="lending_protocol_benchmark_pack",
    )

    assert session.selected_pack_name == "lending_protocol_benchmark_pack"
    assert "lending_protocol_benchmark_pack:lending_inventory_scope" in session.executed_pack_steps
    assert "lending_protocol_benchmark_pack:lending_casebook_match" in session.executed_pack_steps
    assert any(job.tool_name == "contract_inventory_tool" for job in session.jobs)
    assert any(job.tool_name == "contract_testbed_tool" for job in session.jobs)
    assert session.report is not None
    assert session.report.contract_benchmark_pack_summary
    assert session.report.contract_benchmark_case_summaries
    assert session.report.confidence_rationale


def test_expected_report_shape_docs_cover_every_manifest_case() -> None:
    manifest = _load_manifest()
    english = (GOLDEN_ROOT / "EXPECTED_REPORT_SHAPES.md").read_text(encoding="utf-8")
    russian = (GOLDEN_ROOT / "EXPECTED_REPORT_SHAPES.ru.md").read_text(encoding="utf-8")

    for case in manifest["cases"]:
        assert case["case_id"] in english
        assert case["case_id"] in russian
