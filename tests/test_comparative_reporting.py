from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.core.comparison import (
    build_comparative_report,
    collect_manual_review_items,
    compare_hypotheses,
    compare_tool_outcomes,
    summarize_tested_hypotheses,
    summarize_tool_usage,
)
from app.main import build_orchestrator
from app.models import Evidence, Hypothesis, ResearchSeed, ResearchSession
from app.models.comparative_report import (
    BranchComparison,
    ComparativeReport,
    ComparativeReportSection,
    CrossSessionComparison,
    ToolComparison,
)
from app.types import ConfidenceLevel, HypothesisStatus, make_id


def test_comparative_report_models_creation() -> None:
    branch = BranchComparison(
        hypothesis_ids=["hyp_1", "hyp_2"],
        compared_aspects=["status", "score"],
        summary="Compared two bounded branches.",
        stronger_branch_ids=["hyp_1"],
        weaker_branch_ids=["hyp_2"],
        notes=["hyp_1 retained stronger bounded support."],
    )
    tool = ToolComparison(
        tool_names=["ecc_curve_parameter_tool", "symbolic_check_tool"],
        experiment_types=["ecc_curve_parameter_check", "symbolic_simplification"],
        consistency_summary="Tool outcomes were divergent but inspectable.",
        conflicting_signals=["ecc_curve_parameter_tool: recognized curve metadata"],
        notes=["tool_count=2"],
    )
    section = ComparativeReportSection(
        title="Comparative Findings",
        summary="Branch and tool comparisons were recorded.",
        findings=["Two bounded branches were compared."],
        recommendations=["Review divergent tool outputs manually."],
    )
    report = ComparativeReport(
        session_id="session_123",
        analysis_generated=True,
        summary="Comparative analysis produced branch and tool findings.",
        baseline_session_id="session_baseline",
        baseline_source_path="artifacts/sessions/baseline.json",
        branch_comparisons=[branch],
        tool_comparisons=[tool],
        cross_session_comparison=CrossSessionComparison(
            baseline_session_id="session_baseline",
            current_session_id="session_123",
            baseline_source_path="artifacts/sessions/baseline.json",
            summary="Before/after comparison remained bounded and inspectable.",
            improvements=["Coverage expanded from 1 to 2 evidence items."],
            regressions=[],
            stable_findings=["Tool-path set stayed consistent with the baseline session."],
        ),
        sections=[section],
        manual_review_items=["Tool outcomes should be reviewed manually."],
        notes=["Evidence-first comparison only."],
    )

    assert report.analysis_generated is True
    assert report.baseline_session_id == "session_baseline"
    assert report.branch_comparisons[0].stronger_branch_ids == ["hyp_1"]
    assert report.tool_comparisons[0].tool_names[0] == "ecc_curve_parameter_tool"


def test_comparison_logic_for_multiple_hypotheses_and_tools() -> None:
    session = ResearchSession(
        seed=ResearchSeed(raw_text="Compare ECC metadata and symbolic branch outcomes."),
    )
    strong = Hypothesis(
        source_agent="HypothesisAgent",
        summary="Curve metadata branch",
        rationale="Use recognized curve metadata as a bounded signal.",
        planned_test="Inspect secp256k1 registry metadata.",
        score=0.92,
        status=HypothesisStatus.VALIDATED,
    )
    weak = Hypothesis(
        source_agent="HypothesisAgent",
        summary="Symbolic side branch",
        rationale="Try symbolic normalization on a malformed expression.",
        planned_test="Normalize malformed symbolic text.",
        score=0.14,
        status=HypothesisStatus.REJECTED,
    )
    session.hypotheses = [strong, weak]
    session.evidence = [
        Evidence(
            hypothesis_id=strong.hypothesis_id,
            source="ecc_curve_parameter_tool",
            summary="Recognized canonical secp256k1 metadata was returned.",
            tool_name="ecc_curve_parameter_tool",
            experiment_type="ecc_curve_parameter_check",
            target_kind="curve",
            deterministic=True,
            conclusion="Recognized canonical secp256k1 metadata.",
            raw_result={"result": {"status": "success"}},
        ),
        Evidence(
            hypothesis_id=weak.hypothesis_id,
            source="symbolic_check_tool",
            summary="Malformed symbolic expression remained inconclusive.",
            tool_name="symbolic_check_tool",
            experiment_type="symbolic_simplification",
            target_kind="symbolic",
            deterministic=True,
            conclusion="Malformed symbolic expression remained inconclusive.",
            notes=["Manual review required because symbolic parsing failed cleanly but inconclusively."],
            raw_result={"result": {"status": "invalid_input"}},
        ),
    ]
    baseline_session = ResearchSession(
        seed=ResearchSeed(raw_text="Compare ECC metadata and symbolic branch outcomes."),
        hypotheses=[strong],
        evidence=[session.evidence[0]],
    )

    branch_comparison = compare_hypotheses(session)
    tool_comparison = compare_tool_outcomes(session)
    comparative_report = build_comparative_report(
        session,
        baseline_session=baseline_session,
        baseline_source_path="artifacts/sessions/baseline.json",
    )
    manual_review = collect_manual_review_items(session, tool_comparison)

    assert branch_comparison.stronger_branch_ids == [strong.hypothesis_id]
    assert weak.hypothesis_id in branch_comparison.weaker_branch_ids
    assert tool_comparison.tool_names == ["ecc_curve_parameter_tool", "symbolic_check_tool"]
    assert tool_comparison.conflicting_signals
    assert comparative_report.analysis_generated is True
    assert comparative_report.cross_session_comparison is not None
    assert comparative_report.cross_session_comparison.baseline_session_id == baseline_session.session_id
    assert any("coverage expanded" in item.lower() for item in comparative_report.cross_session_comparison.improvements)
    assert any("manual review" in item.lower() for item in manual_review)
    assert len(summarize_tested_hypotheses(session)) == 2
    assert summarize_tool_usage(session) == []


def test_comparative_report_export_and_single_path_flow() -> None:
    run_root = Path(".test_runs") / make_id("comparative")
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
            "advanced_math_enabled": True,
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text="Inspect whether secp256k1 metadata labels remain consistent across local reasoning and tool output.",
        author="comparative-test",
    )

    assert session.report is not None
    assert session.comparative_report is not None
    assert session.comparative_report_file_path is not None

    comparative_path = Path(session.comparative_report_file_path)
    assert comparative_path.exists()
    payload = json.loads(comparative_path.read_text(encoding="utf-8"))

    assert payload["session_id"] == session.session_id
    assert "sections" in payload
    assert (Path(session.bundle_dir) / "comparative_report.json").exists()
    assert session.report.confidence in {
        ConfidenceLevel.LOW,
        ConfidenceLevel.INCONCLUSIVE,
        ConfidenceLevel.MEDIUM,
        ConfidenceLevel.HIGH,
        ConfidenceLevel.MANUAL_REVIEW_REQUIRED,
    }


def test_direct_session_can_attach_before_after_comparison() -> None:
    run_root = Path(".test_runs") / make_id("compareattach")
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
            "advanced_math_enabled": True,
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    baseline = orchestrator.run_session(
        seed_text="Inspect bounded secp256k1 metadata consistency for replay-safe local comparison.",
        author="baseline-run",
    )
    compared = orchestrator.run_session(
        seed_text="Inspect bounded secp256k1 metadata consistency for replay-safe local comparison.",
        author="compared-run",
        comparison_baseline=baseline,
        comparison_baseline_source_type="session",
        comparison_baseline_source_path=baseline.session_file_path,
    )

    assert compared.comparative_report is not None
    assert compared.comparative_report.cross_session_comparison is not None
    assert compared.report is not None
    assert compared.report.before_after_comparison
    assert compared.report.regression_flags
    assert compared.report.remediation_delta_summary
    assert compared.report.quality_gates
    assert compared.report.hardening_summary
    assert any("before/after posture" in item.lower() for item in compared.report.remediation_delta_summary)
    assert compared.manifest_file_path is not None
    manifest = json.loads(Path(compared.manifest_file_path).read_text(encoding="utf-8"))
    assert manifest["comparison_ready"] is True
    assert manifest["report_focus_summary"]
    assert manifest["quality_gate_count"] == len(manifest["quality_gate_summary"])
    assert manifest["hardening_summary_count"] == len(manifest["hardening_summary"])
