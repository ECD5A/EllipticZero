from __future__ import annotations

from app.config import AppConfig
from app.main import build_orchestrator
from app.tools.builtin import (
    ECCConsistencyCheckTool,
    ECCPointFormatTool,
)
from app.tools.ecc_utils import resolve_ecc_domain
from app.types import make_id


def test_ecc_domain_lookup_normalization() -> None:
    domain = resolve_ecc_domain("P-256")

    assert domain is not None
    assert domain.canonical_curve_name == "secp256r1"
    assert domain.a_hex is not None
    assert domain.b_hex is not None
    assert domain.supports_on_curve_check is True


def test_ecc_point_format_classification_and_malformed_handling() -> None:
    tool = ECCPointFormatTool()

    compressed = tool.run(
        tool.validate_payload(
            {
                "public_key_hex": "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
            }
        )
    )
    malformed = tool.run(tool.validate_payload({"public_key_hex": "04zz"}))
    bad_prefix = tool.run(
        tool.validate_payload(
            {
                "public_key_hex": "0579BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
                "curve_name": "secp256k1",
            }
        )
    )

    assert compressed["result_data"]["encoding"] == "compressed"
    assert compressed["result_data"]["format_recognized"] is True
    assert compressed["result_data"]["likely_curve_family"] == "secp"
    assert compressed["result_data"]["prefix_valid"] is True
    assert compressed["result_data"]["expected_coordinate_hex_length"] == 64
    assert malformed["result_data"]["input_kind"] == "malformed"
    assert malformed["result_data"]["format_recognized"] is False
    assert bad_prefix["result_data"]["prefix_valid"] is False
    assert bad_prefix["result_data"]["issues"]


def test_ecc_consistency_tool_supported_on_curve_case() -> None:
    tool = ECCConsistencyCheckTool()
    payload = tool.validate_payload(
        {
            "curve_name": "secp256k1",
            "x": "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
            "y": "483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8",
            "check_on_curve": True,
        }
    )
    result = tool.run(payload)

    assert result["status"] == "ok"
    assert result["result_data"]["format_consistent"] is True
    assert result["result_data"]["on_curve_checked"] is True
    assert result["result_data"]["on_curve"] is True
    assert result["result_data"]["field_bounds_checked"] is True
    assert result["result_data"]["x_in_field_range"] is True
    assert result["result_data"]["y_in_field_range"] is True


def test_ecc_consistency_tool_reports_coordinate_mismatch_issue() -> None:
    tool = ECCConsistencyCheckTool()
    payload = tool.validate_payload(
        {
            "curve_name": "secp256k1",
            "x": "79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798",
            "y": "483ADA7726A3C4655DA4FBFC0E1108A8",
            "check_on_curve": False,
        }
    )
    result = tool.run(payload)

    assert result["status"] == "observed_issue"
    assert result["result_data"]["coordinate_length_match"] is False
    assert result["result_data"]["format_consistent"] is False
    assert result["result_data"]["issues"]


def test_orchestrator_routes_ecc_point_format_seed() -> None:
    run_root = f".test_runs/{make_id('ecc')}"
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
        seed_text=(
            "Inspect whether this compressed public key format looks well-formed: "
            "0279BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798"
        ),
        author="ecc-test",
    )

    assert session.jobs
    assert session.jobs[0].tool_name == "ecc_point_format_tool"
    assert session.evidence
    assert session.evidence[0].tool_name == "ecc_point_format_tool"
    assert any("encoding=compressed" in note for note in session.evidence[0].notes)


def test_orchestrator_builds_ecc_benchmark_focus_for_subgroup_seed() -> None:
    run_root = f".test_runs/{make_id('eccsubgroup')}"
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
        seed_text=(
            "Review subgroup, cofactor, and twist hygiene assumptions for x25519 and ed25519 inputs "
            "using bounded local ECC validation."
        ),
        author="ecc-subgroup-test",
    )

    assert session.report is not None
    assert session.report.ecc_benchmark_summary
    assert session.report.ecc_benchmark_posture
    assert session.report.ecc_family_coverage
    assert session.report.ecc_coverage_matrix
    assert session.report.ecc_benchmark_case_summaries
    assert session.report.ecc_review_focus
    assert session.report.ecc_residual_risk
    assert session.report.evidence_profile
    assert session.report.calibration_blockers
    assert session.report.reproducibility_summary
    assert session.report.quality_gates
    assert session.report.hardening_summary
    assert session.report.ecc_signal_consensus
    assert session.report.ecc_validation_matrix
    assert session.report.validation_posture
    assert session.report.shared_follow_up
    assert session.report.ecc_triage_snapshot
    assert session.report.ecc_review_queue
    assert session.report.ecc_exit_criteria
    assert any("benchmark" in line.lower() or "coverage" in line.lower() for line in session.report.ecc_benchmark_summary)
    assert any("overall=" in line.lower() or "coverage=" in line.lower() for line in session.report.ecc_benchmark_posture)
    assert any("family coverage" in line.lower() or "breadth=" in line.lower() for line in session.report.ecc_family_coverage)
    assert any("coverage matrix" in line.lower() and "baseline=" in line.lower() for line in session.report.ecc_coverage_matrix)
    assert any("benchmark case" in line.lower() and "anomaly-bearing=" in line.lower() for line in session.report.ecc_benchmark_case_summaries)
    assert any("25519" in line or "subgroup" in line.lower() for line in session.report.ecc_residual_risk)
    assert any("quality gate" in line.lower() for line in session.report.quality_gates)
    assert any("ecc coverage" in line.lower() for line in session.report.quality_gates)
    assert any("coverage posture" in line.lower() for line in session.report.validation_posture)
    assert any("ecc exit check" in line.lower() for line in session.report.shared_follow_up)
    assert any("hardening posture" in line.lower() for line in session.report.hardening_summary)
    assert any("subgroup/cofactor/twist" in line.lower() for line in session.report.ecc_signal_consensus)
    assert any("validation for subgroup/cofactor/twist" in line.lower() for line in session.report.ecc_validation_matrix)
    assert any("primary family" in line.lower() for line in session.report.ecc_triage_snapshot)
    assert any("next ecc check" in line.lower() for line in session.report.ecc_triage_snapshot)
    assert any("validation posture" in line.lower() or "posture=" in line.lower() for line in session.report.validation_posture)
    assert any(
        "follow-up" in line.lower() or "re-run" in line.lower() or "re-check" in line.lower()
        for line in session.report.shared_follow_up
    )
    assert any("subgroup" in line.lower() or "twist" in line.lower() for line in session.report.ecc_review_queue)
    assert any("subgroup" in line.lower() or "twist" in line.lower() for line in session.report.ecc_exit_criteria)


def test_orchestrator_builds_ecc_family_depth_focus_for_mixed_family_seed() -> None:
    run_root = f".test_runs/{make_id('eccfamilydepth')}"
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
        seed_text=(
            "Review Montgomery, Edwards, and short-Weierstrass family transition assumptions for bounded ECC handling."
        ),
        author="ecc-family-depth-test",
        experiment_pack_name="ecc_family_depth_benchmark_pack",
    )

    assert session.report is not None
    assert session.report.ecc_benchmark_summary
    assert session.report.ecc_benchmark_posture
    assert session.report.ecc_family_coverage
    assert session.report.ecc_coverage_matrix
    assert session.report.ecc_benchmark_case_summaries
    assert session.report.ecc_review_focus
    assert session.report.ecc_residual_risk
    assert session.report.ecc_signal_consensus
    assert session.report.ecc_validation_matrix
    assert session.report.ecc_triage_snapshot
    assert session.report.ecc_review_queue
    assert session.report.ecc_exit_criteria
    assert any("family-transition" in line.lower() or "family-depth" in line.lower() for line in session.report.ecc_benchmark_summary)
    assert any("family transitions" in line.lower() for line in session.report.ecc_benchmark_posture)
    assert any("family transitions" in line.lower() for line in session.report.ecc_family_coverage)
    assert any("family transitions" in line.lower() for line in session.report.ecc_coverage_matrix)
    assert any("montgomery" in line.lower() or "edwards" in line.lower() or "family" in line.lower() for line in session.report.ecc_review_focus)
    assert any("family transitions" in line.lower() for line in session.report.ecc_signal_consensus)
    assert any("validation for family transitions" in line.lower() for line in session.report.ecc_validation_matrix)
    assert any("family transitions" in line.lower() for line in session.report.ecc_triage_snapshot)


def test_orchestrator_builds_ecc_domain_completeness_focus_for_metadata_seed() -> None:
    run_root = f".test_runs/{make_id('eccdomainfocus')}"
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
        seed_text=(
            "Audit generator, order, cofactor, and registry completeness assumptions before stronger ECC domain conclusions."
        ),
        author="ecc-domain-focus-test",
        experiment_pack_name="ecc_domain_completeness_benchmark_pack",
    )

    assert session.report is not None
    assert session.report.ecc_benchmark_summary
    assert session.report.ecc_benchmark_posture
    assert session.report.ecc_family_coverage
    assert session.report.ecc_coverage_matrix
    assert session.report.ecc_benchmark_case_summaries
    assert session.report.ecc_review_focus
    assert session.report.ecc_residual_risk
    assert session.report.ecc_signal_consensus
    assert session.report.ecc_validation_matrix
    assert session.report.ecc_triage_snapshot
    assert session.report.ecc_review_queue
    assert session.report.ecc_exit_criteria
    assert any("domain" in line.lower() or "registry" in line.lower() for line in session.report.ecc_review_focus)
    assert any("domain completeness" in line.lower() for line in session.report.ecc_benchmark_posture)
    assert any("domain completeness" in line.lower() for line in session.report.ecc_family_coverage)
    assert any("domain completeness" in line.lower() for line in session.report.ecc_coverage_matrix)
    assert any("domain" in line.lower() or "metadata" in line.lower() for line in session.report.ecc_residual_risk)
    assert any("domain completeness" in line.lower() for line in session.report.ecc_signal_consensus)
    assert any("validation for domain completeness" in line.lower() for line in session.report.ecc_validation_matrix)
    assert any("domain completeness" in line.lower() for line in session.report.ecc_triage_snapshot)


def test_ecc_before_after_comparison_populates_ecc_comparison_focus() -> None:
    run_root = f".test_runs/{make_id('ecccomparefocus')}"
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

    baseline = orchestrator.run_session(
        seed_text="Review subgroup, cofactor, and twist hygiene assumptions for x25519 and ed25519 inputs using bounded local ECC validation.",
        author="ecc-baseline",
    )
    compared = orchestrator.run_session(
        seed_text="Review subgroup, cofactor, and twist hygiene assumptions for x25519 and ed25519 inputs using bounded local ECC validation.",
        author="ecc-compared",
        comparison_baseline=baseline,
        comparison_baseline_source_type="session",
        comparison_baseline_source_path=baseline.session_file_path,
    )

    assert compared.report is not None
    assert compared.report.before_after_comparison
    assert compared.report.regression_flags
    assert compared.report.evidence_profile
    assert compared.report.calibration_blockers
    assert compared.report.reproducibility_summary
    assert compared.report.ecc_comparison_focus
    assert compared.report.ecc_benchmark_delta
    assert compared.report.ecc_regression_summary
    assert compared.report.ecc_coverage_matrix
    assert compared.report.quality_gates
    assert compared.report.hardening_summary
    assert compared.report.validation_posture
    assert compared.report.shared_follow_up
    assert compared.report.shared_follow_up
    assert compared.report.ecc_review_queue
    assert compared.report.ecc_exit_criteria
    assert compared.report.ecc_triage_snapshot
    assert compared.report.remediation_delta_summary
    assert any("baseline session" in line.lower() for line in compared.report.ecc_comparison_focus)
    assert any("benchmark delta" in line.lower() for line in compared.report.ecc_benchmark_delta)
    assert any("before/after delta" in line.lower() or "baseline=" in line.lower() for line in compared.report.ecc_triage_snapshot)
    assert any("before/after posture" in line.lower() for line in compared.report.remediation_delta_summary)
    assert any("regression summary" in line.lower() or "regression watch" in line.lower() for line in compared.report.ecc_regression_summary)
    assert any("comparison:" in line.lower() or "baseline=" in line.lower() for line in compared.report.quality_gates)
    assert any("before/after" in line.lower() or "baseline" in line.lower() for line in compared.report.hardening_summary)
    assert any("baseline" in line.lower() or "comparison" in line.lower() for line in compared.report.validation_posture)
    assert any(
        "baseline" in line.lower() or "follow-up" in line.lower() or "re-run" in line.lower()
        for line in compared.report.shared_follow_up
    )
