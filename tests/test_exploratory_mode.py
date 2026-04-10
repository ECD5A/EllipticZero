from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.core.replay_loader import ReplayLoader
from app.core.replay_planner import ReplayPlanner
from app.main import build_orchestrator
from app.models.replay_request import ReplayRequest
from app.models.sandbox import ExplorationProfile, ResearchMode
from app.types import make_id


def _exploratory_config(run_root: Path) -> AppConfig:
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
                "max_exploratory_rounds": 2,
                "max_jobs_per_session": 4,
                "require_manual_review_for_exploratory": True,
            },
            "advanced_math_enabled": True,
            "log_level": "INFO",
            "max_hypotheses": 3,
            "tool_timeout_seconds": 15,
        }
    )


def test_sandboxed_exploratory_mode_records_bounded_branch_provenance() -> None:
    run_root = Path(".test_runs") / make_id("explore")
    config = _exploratory_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text=(
            "Explore whether secp256k1 compressed public key parsing and on-curve checks "
            "produce multiple bounded defensive research leads under local analysis."
        ),
        author="exploratory-test",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
    )

    assert session.research_mode == ResearchMode.SANDBOXED_EXPLORATORY
    assert session.sandbox_spec is not None
    assert session.research_target is not None
    assert session.sandbox_spec.mode == ResearchMode.SANDBOXED_EXPLORATORY
    assert session.sandbox_spec.exploration_profile == ExplorationProfile.CAUTIOUS
    assert session.sandbox_spec.approved_tool_names
    assert session.research_target.target_profile is not None
    assert session.exploratory_rounds_executed >= 2
    assert session.exploratory_round_summaries
    assert 2 <= len(session.explored_hypothesis_ids) <= config.research.max_jobs_per_session
    assert len(session.jobs) >= len(session.explored_hypothesis_ids)
    assert all(
        hypothesis_id in {hypothesis.hypothesis_id for hypothesis in session.hypotheses}
        for hypothesis_id in session.explored_hypothesis_ids
    )
    assert session.evidence
    assert all(
        evidence.sandbox_id == session.sandbox_spec.sandbox_id
        for evidence in session.evidence
    )
    assert all(
        evidence.research_target_reference == session.research_target.target_reference
        for evidence in session.evidence
    )
    assert all(
        evidence.target_profile == session.research_target.target_profile
        for evidence in session.evidence
    )
    assert session.report is not None
    assert session.report.research_mode == ResearchMode.SANDBOXED_EXPLORATORY.value
    assert session.report.research_target == session.research_target.target_reference
    assert session.report.exploratory_rounds_executed == session.exploratory_rounds_executed
    assert session.report.exploratory_findings
    assert session.report.local_signal_summary
    assert session.report.next_defensive_leads
    assert any("manual review" in item.lower() for item in session.report.manual_review_items)
    assert session.trace_file_path is not None
    trace_text = Path(session.trace_file_path).read_text(encoding="utf-8")
    assert "Defensive question to tighten:" in trace_text
    assert "Preserve null-control:" in trace_text

    assert session.manifest_file_path is not None
    manifest_payload = json.loads(Path(session.manifest_file_path).read_text(encoding="utf-8"))
    assert manifest_payload["research_mode"] == ResearchMode.SANDBOXED_EXPLORATORY.value
    assert manifest_payload["exploration_profile"] == ExplorationProfile.CAUTIOUS.value
    assert manifest_payload["sandbox_id"] == session.sandbox_spec.sandbox_id
    assert manifest_payload["research_target_kind"] == session.research_target.target_kind
    assert manifest_payload["research_target_reference"] == session.research_target.target_reference
    assert manifest_payload["research_target_profile"] == session.research_target.target_profile
    assert manifest_payload["exploratory_rounds_executed"] == session.exploratory_rounds_executed
    assert any(
        str(note).startswith("exploratory_round_count=") for note in manifest_payload["notes"]
    )


def test_aggressive_bounded_profile_expands_internal_sandbox_budget() -> None:
    run_root = Path(".test_runs") / make_id("exploreaggr")
    config = _exploratory_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text=(
            "Run an aggressive but bounded multi-round fuzz mutation and formal invariant testbed "
            "study for parser anomaly edge-case behavior in ECC validation."
        ),
        author="exploratory-aggressive-test",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
    )

    assert session.sandbox_spec is not None
    assert session.sandbox_spec.exploration_profile == ExplorationProfile.AGGRESSIVE_BOUNDED
    assert session.sandbox_spec.max_exploratory_branches > config.research.max_exploratory_branches
    assert session.sandbox_spec.max_exploratory_rounds > config.research.max_exploratory_rounds
    assert session.sandbox_spec.max_jobs_per_session >= config.research.max_jobs_per_session
    assert session.report is not None
    assert session.report.exploration_profile == ExplorationProfile.AGGRESSIVE_BOUNDED.value
    assert any(
        "Exploration profile: aggressive_bounded." in item
        for item in session.report.exploratory_findings
    )

    assert session.manifest_file_path is not None
    manifest_payload = json.loads(Path(session.manifest_file_path).read_text(encoding="utf-8"))
    assert manifest_payload["exploration_profile"] == ExplorationProfile.AGGRESSIVE_BOUNDED.value
    assert any(
        str(note).startswith("exploration_profile=aggressive_bounded")
        for note in manifest_payload["notes"]
    )


def test_role_informed_mapping_can_shift_exploratory_follow_up_tools() -> None:
    run_root = Path(".test_runs") / make_id("exploremap")
    config = _exploratory_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text=(
            "Explore whether malformed point prefix parsing and parser anomaly handling "
            "produce bounded defensive leads under local ECC analysis."
        ),
        author="exploratory-mapping-test",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
    )

    selected_role_sets = [
        tuple(job.tool_plan.selected_by_roles)
        for job in session.jobs
        if job.tool_plan is not None and job.tool_plan.selected_by_roles
    ]
    tool_names = [job.tool_name for job in session.jobs]

    assert selected_role_sets
    assert any(
        tool_name in {"point_descriptor_tool", "ecc_testbed_tool", "fuzz_mutation_tool"}
        for tool_name in tool_names
    )
    assert any(
        "CryptographyAgent" in role_set or "StrategyAgent" in role_set
        for role_set in selected_role_sets
    )
    assert any(
        evidence.selected_by_roles
        for evidence in session.evidence
    )
    assert session.cryptography_result is not None
    assert "ecc_testbed_tool" in session.cryptography_result.preferred_local_tools
    assert "fuzz_mutation_tool" in session.cryptography_result.preferred_local_tools
    assert session.strategy_result is not None
    assert "ecc_consistency_check_tool" in session.strategy_result.escalation_local_tools


def test_role_guided_mapping_diversifies_parser_anomaly_experiments() -> None:
    run_root = Path(".test_runs") / make_id("explorediverse")
    config = _exploratory_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text=(
            "Run an aggressive but bounded parser anomaly exploration for malformed compressed point "
            "prefix handling, mutation behavior, and testbed-style validation drift in local ECC analysis."
        ),
        author="exploratory-diversify-test",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
    )

    tool_names = [job.tool_name for job in session.jobs]

    assert "ecc_testbed_tool" in tool_names
    assert "fuzz_mutation_tool" in tool_names
    assert len(set(tool_names)) >= 2
    assert any(
        job.tool_plan is not None
        and "CryptographyAgent" in job.tool_plan.selected_by_roles
        and job.tool_name in {"ecc_testbed_tool", "fuzz_mutation_tool"}
        for job in session.jobs
    )


def test_role_guided_mapping_can_push_symbolic_formal_and_property_paths() -> None:
    run_root = Path(".test_runs") / make_id("exploresymbolic")
    config = _exploratory_config(run_root)
    orchestrator = build_orchestrator(config)

    session = orchestrator.run_session(
        seed_text=(
            "Explore a bounded symbolic invariant and counterexample check for whether x + 1 = 1 + x "
            "remains solver-consistent under local sandboxed research."
        ),
        author="exploratory-symbolic-test",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
    )

    tool_names = [job.tool_name for job in session.jobs]

    assert session.strategy_result is not None
    assert "formal_constraint_tool" in session.strategy_result.escalation_local_tools
    assert "property_invariant_tool" in session.strategy_result.escalation_local_tools
    assert any(tool_name in {"formal_constraint_tool", "property_invariant_tool"} for tool_name in tool_names)
    assert any(
        job.tool_plan is not None
        and "StrategyAgent" in job.tool_plan.selected_by_roles
        and job.tool_name in {"formal_constraint_tool", "property_invariant_tool"}
        for job in session.jobs
    )


def test_replay_preserves_exploratory_research_mode() -> None:
    run_root = Path(".test_runs") / make_id("explorereplay")
    config = _exploratory_config(run_root)
    orchestrator = build_orchestrator(config)

    source_session = orchestrator.run_session(
        seed_text=(
            "Explore whether modular consistency and symbolic normalization jointly surface "
            "bounded defensive leads for elliptic-curve validation logic."
        ),
        author="exploratory-replay-source",
        research_mode=ResearchMode.SANDBOXED_EXPLORATORY,
    )
    assert source_session.session_file_path is not None

    request = ReplayRequest(
        source_type="session",
        source_path=source_session.session_file_path,
        dry_run=False,
        reexecute=True,
        preserve_original_seed=True,
    )
    loader = ReplayLoader()
    planner = ReplayPlanner()
    loaded = loader.load(request)
    plan = planner.build_plan(
        loaded_source=loaded,
        available_tools=orchestrator.executor.registry.names(),
        preserve_original_seed=request.preserve_original_seed,
    )
    result = planner.execute(
        request=request,
        plan=plan,
        orchestrator=build_orchestrator(config),
        author="exploratory-replay",
    )

    assert plan.research_mode == ResearchMode.SANDBOXED_EXPLORATORY.value
    assert plan.exploration_profile is not None
    assert result.success is True
    assert result.generated_session_path is not None
    replay_payload = json.loads(Path(result.generated_session_path).read_text(encoding="utf-8"))
    assert replay_payload["research_mode"] == ResearchMode.SANDBOXED_EXPLORATORY.value
    assert replay_payload["sandbox_spec"] is not None
    assert replay_payload["report"]["exploration_profile"] == plan.exploration_profile
    assert replay_payload["exploratory_rounds_executed"] >= 2
    assert replay_payload["research_target"]["target_profile"] is not None
    assert replay_payload["report"]["research_mode"] == ResearchMode.SANDBOXED_EXPLORATORY.value
    assert replay_payload["report"]["exploratory_rounds_executed"] >= 2
