from __future__ import annotations

import logging

from app.agents.critic_agent import CriticAgent
from app.agents.cryptography_agent import CryptographyAgent
from app.agents.hypothesis_agent import HypothesisAgent
from app.agents.math_agent import MathAgent
from app.agents.report_agent import ReportAgent
from app.agents.strategy_agent import StrategyAgent
from app.compute.executor import ComputeExecutor
from app.config import AppConfig
from app.core.comparison import (
    build_comparative_report,
    collect_manual_review_items,
    summarize_tested_hypotheses,
    summarize_tool_usage,
)
from app.core.experiment_packs import ExperimentPackRegistry
from app.core.filtering import validate_seed_text
from app.core.lifecycle import transition_hypothesis
from app.core.manifest_helpers import build_run_manifest
from app.core.planning_helpers import (
    build_experiment_spec,
    build_pack_experiment_spec,
    build_pack_tool_plan,
    build_standard_smart_contract_tool_plans,
    build_tool_payload,
    build_tool_plan,
    choose_role_guided_candidate,
    determine_target_kind,
    normalize_tool_hint,
    normalized_role_tool_hints,
    normalized_testbed_hints,
    normalized_tool_family_hints,
    resolve_tool_name_for_hypothesis,
    strategy_guidance_text,
    target_reference_for_kind,
    tool_name_for_target_kind,
)
from app.core.reporting_helpers import (
    append_result_note,
    build_before_after_comparison,
    build_calibration_blockers,
    build_confidence_rationale,
    build_contract_benchmark_case_summaries,
    build_contract_benchmark_pack_summary,
    build_contract_benchmark_posture,
    build_contract_casebook_benchmark_support,
    build_contract_casebook_case_studies,
    build_contract_casebook_coverage,
    build_contract_casebook_coverage_matrix,
    build_contract_casebook_gaps,
    build_contract_casebook_priority_cases,
    build_contract_casebook_triage,
    build_contract_compile_summary,
    build_contract_exit_criteria,
    build_contract_inventory_summary,
    build_contract_manual_review_items,
    build_contract_overview,
    build_contract_priority_findings,
    build_contract_protocol_invariants,
    build_contract_protocol_map,
    build_contract_remediation_follow_up,
    build_contract_remediation_guidance,
    build_contract_remediation_validation,
    build_contract_repo_priorities,
    build_contract_repo_triage,
    build_contract_residual_risk,
    build_contract_review_focus,
    build_contract_review_queue,
    build_contract_signal_consensus,
    build_contract_static_findings,
    build_contract_surface_summary,
    build_contract_testbed_findings,
    build_contract_toolchain_alignment,
    build_contract_validation_matrix,
    build_dead_end_summary,
    build_ecc_benchmark_case_summaries,
    build_ecc_benchmark_delta,
    build_ecc_benchmark_posture,
    build_ecc_benchmark_summary,
    build_ecc_comparison_focus,
    build_ecc_coverage_matrix,
    build_ecc_exit_criteria,
    build_ecc_family_coverage,
    build_ecc_regression_summary,
    build_ecc_residual_risk,
    build_ecc_review_focus,
    build_ecc_review_queue,
    build_ecc_signal_consensus,
    build_ecc_validation_matrix,
    build_evidence_conclusion,
    build_evidence_profile,
    build_evidence_summary,
    build_exploratory_findings,
    build_hardening_summary,
    build_job_trace_data,
    build_local_experiment_summary,
    build_local_signal_summary,
    build_next_defensive_leads,
    build_quality_gates,
    build_regression_flags,
    build_reproducibility_summary,
    build_shared_follow_up,
    build_validation_posture,
    compose_evidence_summary,
    extract_evidence_notes,
    ordered_unique,
    should_fallback_from_sage,
)
from app.core.research_targets import ResearchTargetRegistry
from app.core.sandbox_executor import SandboxExecutor
from app.core.scoring import score_hypothesis
from app.core.seed_parsing import extract_curve_name
from app.models import (
    ComputeJob,
    CriticAgentResult,
    CryptographyAgentResult,
    Evidence,
    ExperimentPack,
    ExperimentPackRecommendation,
    ExperimentPackStep,
    ExperimentSpec,
    ExperimentType,
    ExplorationProfile,
    Hypothesis,
    HypothesisAgentResult,
    MathAgentResult,
    MathWorkspace,
    PluginMetadata,
    ResearchMode,
    ResearchSeed,
    ResearchSession,
    ResearchTarget,
    RunManifest,
    SandboxExecutionRequest,
    SandboxSpec,
    StrategyAgentResult,
    ToolPlan,
)
from app.models.trace import TraceEvent
from app.storage.math_artifacts import MathArtifactStore
from app.storage.reproducibility_bundle import ReproducibilityBundleStore
from app.storage.session_store import SessionStore
from app.storage.trace_writer import TraceWriter
from app.types import BranchType, HypothesisStatus
from app.validation.confidence import infer_confidence


class ResearchOrchestrator:
    """Central controller that keeps the session aligned and bounded."""

    def __init__(
        self,
        *,
        config: AppConfig,
        math_agent: MathAgent,
        cryptography_agent: CryptographyAgent,
        strategy_agent: StrategyAgent,
        hypothesis_agent: HypothesisAgent,
        critic_agent: CriticAgent,
        report_agent: ReportAgent,
        executor: ComputeExecutor,
        sandbox_executor: SandboxExecutor,
        math_artifact_store: MathArtifactStore,
        bundle_store: ReproducibilityBundleStore,
        session_store: SessionStore,
        trace_writer: TraceWriter,
        target_registry: ResearchTargetRegistry,
        experiment_pack_registry: ExperimentPackRegistry,
        plugin_metadata: list[PluginMetadata] | None = None,
    ) -> None:
        self.config = config
        self.math_agent = math_agent
        self.cryptography_agent = cryptography_agent
        self.strategy_agent = strategy_agent
        self.hypothesis_agent = hypothesis_agent
        self.critic_agent = critic_agent
        self.report_agent = report_agent
        self.executor = executor
        self.sandbox_executor = sandbox_executor
        self.math_artifact_store = math_artifact_store
        self.bundle_store = bundle_store
        self.session_store = session_store
        self.trace_writer = trace_writer
        self.target_registry = target_registry
        self.experiment_pack_registry = experiment_pack_registry
        self.plugin_metadata = plugin_metadata or []
        self.logger = logging.getLogger(self.__class__.__name__)

    def run_session(
        self,
        *,
        seed_text: str,
        author: str | None = None,
        research_mode: ResearchMode | str | None = None,
        synthetic_target_name: str | None = None,
        experiment_pack_name: str | None = None,
        replay_source_type: str | None = None,
        replay_source_path: str | None = None,
        original_session_id: str | None = None,
        replay_mode: str | None = None,
        replay_notes: list[str] | None = None,
        comparison_baseline: ResearchSession | None = None,
        comparison_baseline_source_type: str | None = None,
        comparison_baseline_source_path: str | None = None,
    ) -> ResearchSession:
        return self._run_session_internal(
            seed_text=seed_text,
            author=author,
            research_mode=research_mode,
            synthetic_target_name=synthetic_target_name,
            experiment_pack_name=experiment_pack_name,
            replay_source_type=replay_source_type,
            replay_source_path=replay_source_path,
            original_session_id=original_session_id,
            replay_mode=replay_mode,
            replay_notes=replay_notes,
            comparison_baseline=comparison_baseline,
            comparison_baseline_source_type=comparison_baseline_source_type,
            comparison_baseline_source_path=comparison_baseline_source_path,
        )

    def _run_session_internal(
        self,
        *,
        seed_text: str,
        author: str | None = None,
        research_mode: ResearchMode | str | None = None,
        synthetic_target_name: str | None = None,
        experiment_pack_name: str | None = None,
        replay_source_type: str | None = None,
        replay_source_path: str | None = None,
        original_session_id: str | None = None,
        replay_mode: str | None = None,
        replay_notes: list[str] | None = None,
        comparison_baseline: ResearchSession | None = None,
        comparison_baseline_source_type: str | None = None,
        comparison_baseline_source_path: str | None = None,
    ) -> ResearchSession:
        normalized_seed = validate_seed_text(seed_text)
        seed = ResearchSeed(raw_text=normalized_seed, author=author)
        resolved_research_mode = self._resolve_research_mode(research_mode)
        sandbox_spec = self._build_sandbox_spec(
            research_mode=resolved_research_mode,
            seed_text=seed.raw_text,
        )
        session = ResearchSession(
            seed=seed,
            research_mode=resolved_research_mode,
            sandbox_spec=sandbox_spec,
        )
        session.plugin_metadata = list(self.plugin_metadata)
        session.is_replay = replay_source_type is not None
        session.replay_source_type = replay_source_type
        session.replay_source_path = replay_source_path
        session.original_session_id = original_session_id
        session.replay_mode = replay_mode
        session.replay_notes = list(replay_notes or [])
        session.comparison_baseline_session_id = (
            comparison_baseline.session_id if comparison_baseline is not None else None
        )
        session.comparison_baseline_source_type = comparison_baseline_source_type
        session.comparison_baseline_source_path = comparison_baseline_source_path
        session.trace_file_path = str(self.trace_writer.path_for_session(session.session_id))

        self.logger.info("Created research session %s", session.session_id)
        self._trace(
            session=session,
            event_type="session_created",
            agent="orchestrator",
            summary="Research session created from validated user seed.",
            data={
                "author": author,
                "is_replay": session.is_replay,
                "replay_source_type": session.replay_source_type,
                "replay_source_path": session.replay_source_path,
                "original_session_id": session.original_session_id,
                "replay_mode": session.replay_mode,
                "comparison_baseline_session_id": session.comparison_baseline_session_id,
                "comparison_baseline_source_type": session.comparison_baseline_source_type,
                "comparison_baseline_source_path": session.comparison_baseline_source_path,
                "research_mode": session.research_mode.value,
                "sandbox_id": session.sandbox_spec.sandbox_id if session.sandbox_spec else None,
                "exploration_profile": (
                    session.sandbox_spec.exploration_profile.value
                    if session.sandbox_spec is not None
                    else None
                ),
            },
        )
        if session.sandbox_spec is not None:
            self._trace(
                session=session,
                event_type="sandbox_initialized",
                agent="orchestrator",
                summary="Sandboxed exploratory mode initialized with bounded local execution limits.",
                data=session.sandbox_spec.model_dump(mode="json"),
            )
        if session.plugin_metadata:
            self._trace(
                session=session,
                event_type="plugins_loaded",
                agent="PluginLoader",
                summary="Local plugins were inspected and loaded before session execution.",
                data={
                    "plugins": [item.model_dump(mode="json") for item in session.plugin_metadata],
                },
            )

        (
            math_result,
            cryptography_result,
            strategy_result,
            hypothesis_result,
            critic_result,
            initial_hypotheses,
        ) = self._run_agent_round(
            session=session,
            seed=seed,
            round_index=1,
        )
        session.math_result = math_result
        session.cryptography_result = cryptography_result
        session.strategy_result = strategy_result
        session.hypothesis_result = hypothesis_result
        session.critic_result = critic_result
        session.hypotheses = list(initial_hypotheses)

        session.research_target = self._build_research_target(
            session=session,
            seed_text=seed.raw_text,
            formalization=math_result.formalization_summary,
            hypotheses=session.hypotheses,
            synthetic_target_name=synthetic_target_name,
        )
        if session.research_target is not None:
            self._trace(
                session=session,
                event_type="research_target_built",
                agent="orchestrator",
                summary="Bounded research target normalized from the seed and formalized branches.",
                data=session.research_target.model_dump(mode="json"),
            )

        selected_pack, pack_recommendations = self._resolve_experiment_pack(
            seed_text=seed.raw_text,
            research_target=session.research_target,
            explicit_pack_name=experiment_pack_name,
        )
        session.selected_pack_name = selected_pack.pack_name if selected_pack is not None else None
        session.pack_recommendations = list(pack_recommendations)
        session.recommended_pack_names = [
            item.pack_name for item in pack_recommendations
        ]
        if selected_pack is not None or session.recommended_pack_names:
            self._trace(
                session=session,
                event_type="experiment_pack_resolved",
                agent="orchestrator",
                summary=(
                    f"Selected bounded experiment pack {selected_pack.pack_name}."
                    if selected_pack is not None
                    else "Generated bounded experiment pack recommendations for the current seed."
                ),
                data={
                    "selected_pack_name": session.selected_pack_name,
                    "recommended_pack_names": session.recommended_pack_names,
                    "recommendations": [
                        item.model_dump(mode="json") for item in session.pack_recommendations
                    ],
                },
            )

        if session.research_mode == ResearchMode.SANDBOXED_EXPLORATORY:
            self._run_exploratory_rounds(
                session=session,
                seed=seed,
                initial_math_result=math_result,
                selected_pack=selected_pack,
            )
        else:
            selected_hypotheses = self._select_hypotheses(
                session,
                selected_pack=selected_pack,
            )
            self._trace_branch_selection(
                session=session,
                hypotheses=selected_hypotheses,
            )
            self._execute_selected_hypotheses(
                session=session,
                seed=seed,
                math_formalization=math_result.formalization_summary,
                hypotheses=selected_hypotheses,
                research_target=session.research_target,
                selected_pack=selected_pack,
            )

        confidence = infer_confidence(session)
        evidence_summary = compose_evidence_summary(session)
        report_result, report = self.report_agent.run(
            session=session,
            evidence_summary=evidence_summary,
            confidence=confidence,
        )
        session.report_result = report_result
        session.report = report
        session.report.exploration_profile = (
            session.sandbox_spec.exploration_profile.value
            if session.sandbox_spec is not None
            else None
        )
        session.report.tested_hypotheses = summarize_tested_hypotheses(session)
        session.report.tool_usage_summary = summarize_tool_usage(session)
        session.report.local_experiment_summary = build_local_experiment_summary(session)
        session.report.local_signal_summary = build_local_signal_summary(session)
        session.report.ecc_benchmark_summary = build_ecc_benchmark_summary(session)
        session.report.ecc_benchmark_posture = build_ecc_benchmark_posture(session)
        session.report.ecc_family_coverage = build_ecc_family_coverage(session)
        session.report.ecc_coverage_matrix = build_ecc_coverage_matrix(session)
        session.report.ecc_benchmark_case_summaries = build_ecc_benchmark_case_summaries(session)
        session.report.ecc_review_focus = build_ecc_review_focus(session)
        session.report.ecc_residual_risk = build_ecc_residual_risk(session)
        session.report.contract_overview = build_contract_overview(session)
        session.report.contract_inventory_summary = build_contract_inventory_summary(session)
        session.report.contract_protocol_map = build_contract_protocol_map(session)
        session.report.contract_protocol_invariants = build_contract_protocol_invariants(session)
        session.report.contract_signal_consensus = build_contract_signal_consensus(session)
        session.report.contract_validation_matrix = build_contract_validation_matrix(session)
        session.report.contract_benchmark_posture = build_contract_benchmark_posture(session)
        session.report.contract_benchmark_pack_summary = build_contract_benchmark_pack_summary(session)
        session.report.contract_benchmark_case_summaries = build_contract_benchmark_case_summaries(session)
        session.report.contract_repo_priorities = build_contract_repo_priorities(session)
        session.report.contract_repo_triage = build_contract_repo_triage(session)
        session.report.contract_casebook_coverage = build_contract_casebook_coverage(session)
        session.report.contract_casebook_coverage_matrix = build_contract_casebook_coverage_matrix(session)
        session.report.contract_casebook_case_studies = build_contract_casebook_case_studies(session)
        session.report.contract_casebook_priority_cases = build_contract_casebook_priority_cases(session)
        session.report.contract_casebook_gaps = build_contract_casebook_gaps(session)
        session.report.contract_casebook_benchmark_support = build_contract_casebook_benchmark_support(session)
        session.report.contract_casebook_triage = build_contract_casebook_triage(session)
        session.report.contract_toolchain_alignment = build_contract_toolchain_alignment(session)
        session.report.contract_review_queue = build_contract_review_queue(session)
        session.report.contract_compile_summary = build_contract_compile_summary(session)
        session.report.contract_surface_summary = build_contract_surface_summary(session)
        session.report.contract_priority_findings = build_contract_priority_findings(session)
        session.report.contract_static_findings = build_contract_static_findings(session)
        session.report.contract_testbed_findings = build_contract_testbed_findings(session)
        session.report.contract_remediation_validation = build_contract_remediation_validation(session)
        session.report.contract_review_focus = build_contract_review_focus(session)
        session.report.contract_remediation_guidance = build_contract_remediation_guidance(session)
        session.report.contract_remediation_follow_up = build_contract_remediation_follow_up(session)
        session.report.contract_residual_risk = build_contract_residual_risk(session)
        session.report.contract_exit_criteria = build_contract_exit_criteria(session)
        session.report.contract_manual_review_items = build_contract_manual_review_items(session)
        session.report.agent_contributions = self._build_agent_contributions(session)
        session.comparative_report = build_comparative_report(
            session,
            baseline_session=comparison_baseline,
            baseline_source_path=comparison_baseline_source_path,
        )
        session.report.before_after_comparison = build_before_after_comparison(session)
        session.report.regression_flags = build_regression_flags(session)
        session.report.evidence_profile = build_evidence_profile(session)
        session.report.reproducibility_summary = build_reproducibility_summary(session)
        session.report.ecc_regression_summary = build_ecc_regression_summary(session)
        session.report.ecc_signal_consensus = build_ecc_signal_consensus(session)
        session.report.ecc_validation_matrix = build_ecc_validation_matrix(session)
        session.report.ecc_comparison_focus = build_ecc_comparison_focus(session)
        session.report.ecc_benchmark_delta = build_ecc_benchmark_delta(session)
        session.report.ecc_review_queue = build_ecc_review_queue(session)
        session.report.ecc_exit_criteria = build_ecc_exit_criteria(session)
        session.report.calibration_blockers = build_calibration_blockers(session)
        session.report.validation_posture = build_validation_posture(session)
        session.report.shared_follow_up = build_shared_follow_up(session)
        session.report.quality_gates = build_quality_gates(session)
        session.report.hardening_summary = build_hardening_summary(session)
        session.report.confidence_rationale = build_confidence_rationale(session)
        session.report.comparative_findings = [
            session.comparative_report.summary,
            *(
                [session.comparative_report.cross_session_comparison.summary]
                if session.comparative_report.cross_session_comparison is not None
                else []
            ),
            *[
                item.summary
                for item in session.comparative_report.branch_comparisons
            ],
            *[
                item.consistency_summary
                for item in session.comparative_report.tool_comparisons
            ],
        ]
        session.report.selected_pack_name = session.selected_pack_name
        session.report.recommended_pack_names = list(session.recommended_pack_names)
        session.report.executed_pack_steps = list(session.executed_pack_steps)
        session.report.exploratory_rounds_executed = session.exploratory_rounds_executed
        session.report.exploratory_findings = build_exploratory_findings(session)
        session.report.dead_end_summary = build_dead_end_summary(session)
        session.report.next_defensive_leads = build_next_defensive_leads(session)
        session.report.manual_review_items = collect_manual_review_items(
            session,
            session.comparative_report.tool_comparisons[0]
            if session.comparative_report.tool_comparisons
            else None,
        )
        session.report.manual_review_items = ordered_unique(
            [
                *session.report.contract_manual_review_items,
                *session.report.manual_review_items,
            ]
        )
        if (
            session.research_mode == ResearchMode.SANDBOXED_EXPLORATORY
            and self.config.research.require_manual_review_for_exploratory
        ):
            exploratory_note = (
                "Sandboxed exploratory findings remain bounded defensive research leads and require manual review before stronger conclusions."
            )
            if exploratory_note not in session.report.manual_review_items:
                session.report.manual_review_items.append(exploratory_note)
        self._trace(
            session=session,
            event_type="report_generated",
            agent="ReportAgent",
            summary=report.summary,
            data={"confidence": report.confidence.value},
        )
        self._trace(
            session=session,
            event_type="comparative_report_generated",
            agent="orchestrator",
            summary=session.comparative_report.summary,
            data={
                "analysis_generated": session.comparative_report.analysis_generated,
                "branch_comparison_count": len(session.comparative_report.branch_comparisons),
                "tool_comparison_count": len(session.comparative_report.tool_comparisons),
                "manual_review_item_count": len(session.comparative_report.manual_review_items),
            },
        )
        session.session_file_path = str(self.session_store.path_for_session(session.session_id))
        session.manifest_file_path = str(self.bundle_store.manifest_path_for_session(session.session_id))
        session.bundle_dir = str(self.bundle_store.path_for_session(session.session_id))
        session.comparative_report_file_path = str(
            self.bundle_store.comparative_report_path_for_session(session.session_id)
        )
        saved_path = self.session_store.save_session(session)
        self._trace(
            session=session,
            event_type="session_saved",
            agent="SessionStore",
            summary="Research session persisted to local JSON storage.",
            data={
                "path": str(saved_path),
                "trace_file_path": session.trace_file_path,
                "manifest_file_path": session.manifest_file_path,
                "bundle_dir": session.bundle_dir,
                "comparative_report_file_path": session.comparative_report_file_path,
            },
        )
        manifest = self._build_run_manifest(session)
        self.bundle_store.export(session=session, manifest=manifest)
        return session

    def _materialize_hypotheses(
        self,
        hypothesis_result: HypothesisAgentResult,
        *,
        parent_id: str | None = None,
    ) -> list[Hypothesis]:
        hypotheses: list[Hypothesis] = []
        for branch in hypothesis_result.branches:
            hypothesis = Hypothesis(
                parent_id=parent_id,
                source_agent=self.hypothesis_agent.name,
                summary=branch.summary,
                rationale=branch.rationale,
                planned_test=branch.planned_test,
                branch_type=branch.branch_type,
                priority=branch.priority,
            )
            transition_hypothesis(hypothesis, HypothesisStatus.FORMALIZED)
            transition_hypothesis(hypothesis, HypothesisStatus.EXPANDED)
            hypothesis.score = score_hypothesis(hypothesis)
            hypotheses.append(hypothesis)
        return hypotheses

    def _run_agent_round(
        self,
        *,
        session: ResearchSession,
        seed: ResearchSeed,
        round_index: int,
        follow_up_context: str | None = None,
        parent_hypothesis_id: str | None = None,
    ) -> tuple[
        MathAgentResult,
        CryptographyAgentResult,
        StrategyAgentResult,
        HypothesisAgentResult,
        CriticAgentResult,
        list[Hypothesis],
    ]:
        math_result = self.math_agent.run(
            seed,
            round_index=round_index,
            follow_up_context=follow_up_context,
        )
        self._trace(
            session=session,
            event_type="math_formalized",
            agent="MathAgent",
            summary=math_result.formalization_summary,
            data={
                "round_index": round_index,
                "follow_up_context": follow_up_context,
                "key_objects": math_result.key_objects,
                "testable_elements": math_result.testable_elements,
            },
        )

        cryptography_result = self.cryptography_agent.run(
            seed=seed,
            math_formalization=math_result,
            round_index=round_index,
            follow_up_context=follow_up_context,
        )
        self._trace(
            session=session,
            event_type="cryptography_profiled",
            agent="CryptographyAgent",
            summary=cryptography_result.surface_summary,
            data={
                "round_index": round_index,
                "follow_up_context": follow_up_context,
                "focus_areas": cryptography_result.focus_areas,
                "preferred_tool_families": cryptography_result.preferred_tool_families,
                "defensive_questions": cryptography_result.defensive_questions,
            },
        )

        strategy_result = self.strategy_agent.run(
            seed=seed,
            math_formalization=math_result,
            cryptography_profile=cryptography_result,
            round_index=round_index,
            follow_up_context=follow_up_context,
        )
        self._trace(
            session=session,
            event_type="strategy_shaped",
            agent="StrategyAgent",
            summary=strategy_result.strategy_summary,
            data={
                "round_index": round_index,
                "follow_up_context": follow_up_context,
                "primary_checks": strategy_result.primary_checks,
                "null_controls": strategy_result.null_controls,
                "stop_conditions": strategy_result.stop_conditions,
            },
        )

        hypothesis_result = self.hypothesis_agent.run(
            seed=seed,
            math_formalization=math_result,
            cryptography_profile=cryptography_result,
            strategy_profile=strategy_result,
            max_hypotheses=self.config.max_hypotheses,
            round_index=round_index,
            follow_up_context=follow_up_context,
        )
        hypotheses = self._materialize_hypotheses(
            hypothesis_result,
            parent_id=parent_hypothesis_id,
        )
        self._trace(
            session=session,
            event_type="hypotheses_expanded",
            agent="HypothesisAgent",
            summary=f"Expanded {len(hypotheses)} bounded hypothesis branches for round {round_index}.",
            data={
                "round_index": round_index,
                "follow_up_context": follow_up_context,
                "parent_hypothesis_id": parent_hypothesis_id,
                "hypothesis_ids": [hypothesis.hypothesis_id for hypothesis in hypotheses],
                "branch_types": [hypothesis.branch_type.value for hypothesis in hypotheses],
            },
        )

        critic_result = self.critic_agent.run(
            seed=seed,
            math_formalization=math_result,
            hypothesis_result=hypothesis_result,
            cryptography_profile=cryptography_result,
            strategy_profile=strategy_result,
            round_index=round_index,
            follow_up_context=follow_up_context,
        )
        self._apply_critic_result(
            session=session,
            hypotheses=hypotheses,
            critic_result=critic_result,
        )
        return (
            math_result,
            cryptography_result,
            strategy_result,
            hypothesis_result,
            critic_result,
            hypotheses,
        )

    def _apply_critic_result(
        self,
        *,
        session: ResearchSession,
        hypotheses: list[Hypothesis],
        critic_result: CriticAgentResult,
    ) -> None:
        if critic_result is None:
            return

        rejected_ids: list[str] = []

        for branch_index, hypothesis in enumerate(hypotheses):
            if branch_index in critic_result.rejected_branches:
                transition_hypothesis(hypothesis, HypothesisStatus.REJECTED)
                rejected_ids.append(hypothesis.hypothesis_id)
                continue
            if branch_index in critic_result.accepted_branches:
                transition_hypothesis(hypothesis, HypothesisStatus.PLANNED)
                hypothesis.rationale = (
                    f"{hypothesis.rationale}\n\nCritic note: {critic_result.critique_summary}"
                )

        if rejected_ids:
            self._trace(
                session=session,
                event_type="hypotheses_rejected",
                agent="CriticAgent",
                summary="One or more hypothesis branches were rejected after critique.",
                data={
                    "rejected_hypothesis_ids": rejected_ids,
                    "rejection_reasons": critic_result.rejection_reasons,
                },
            )

    def _select_hypothesis(self, hypotheses: list[Hypothesis]) -> Hypothesis | None:
        candidates = [
            hypothesis
            for hypothesis in hypotheses
            if hypothesis.status == HypothesisStatus.PLANNED
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda hypothesis: hypothesis.score)

    def _select_hypotheses(
        self,
        session: ResearchSession,
        *,
        selected_pack: ExperimentPack | None = None,
        hypotheses: list[Hypothesis] | None = None,
        branch_budget: int | None = None,
    ) -> list[Hypothesis]:
        candidate_pool = hypotheses if hypotheses is not None else session.hypotheses
        if selected_pack is not None:
            selected = self._select_hypothesis(candidate_pool)
            return [selected] if selected is not None else []

        if session.research_mode != ResearchMode.SANDBOXED_EXPLORATORY:
            selected = self._select_hypothesis(candidate_pool)
            return [selected] if selected is not None else []

        candidates = [
            hypothesis
            for hypothesis in candidate_pool
            if hypothesis.status == HypothesisStatus.PLANNED
        ]
        if not candidates:
            return []

        sandbox_spec = session.sandbox_spec
        branch_limit = min(
            sandbox_spec.max_exploratory_branches if sandbox_spec is not None else self.config.research.max_exploratory_branches,
            sandbox_spec.max_jobs_per_session if sandbox_spec is not None else self.config.research.max_jobs_per_session,
        )
        if branch_budget is not None:
            branch_limit = min(branch_limit, branch_budget)
        prioritized = sorted(
            candidates,
            key=lambda hypothesis: (
                0 if hypothesis.branch_type == BranchType.EXPLORATORY else 1,
                -hypothesis.score,
                hypothesis.priority,
                hypothesis.hypothesis_id,
            ),
        )
        return prioritized[:branch_limit]

    def _trace_branch_selection(
        self,
        *,
        session: ResearchSession,
        hypotheses: list[Hypothesis],
        round_index: int | None = None,
    ) -> None:
        if not hypotheses:
            return
        summary = "Selected the strongest planned branch for local execution."
        if session.research_mode == ResearchMode.SANDBOXED_EXPLORATORY:
            summary = "Selected bounded exploratory branches for local execution."
            if round_index is not None:
                summary = f"Selected bounded exploratory branches for round {round_index} local execution."
        self._trace(
            session=session,
            event_type="branches_selected",
            agent="orchestrator",
            summary=summary,
            data={
                "round_index": round_index,
                "hypothesis_ids": [hypothesis.hypothesis_id for hypothesis in hypotheses],
                "branch_types": [hypothesis.branch_type.value for hypothesis in hypotheses],
                "branch_count": len(hypotheses),
            },
        )

    def _execute_selected_hypotheses(
        self,
        *,
        session: ResearchSession,
        seed: ResearchSeed,
        math_formalization: str,
        hypotheses: list[Hypothesis],
        research_target: ResearchTarget | None,
        selected_pack: ExperimentPack | None = None,
    ) -> None:
        for selected in hypotheses:
            if selected.hypothesis_id not in session.explored_hypothesis_ids:
                session.explored_hypothesis_ids.append(selected.hypothesis_id)
            self._execute_hypothesis_branch(
                session=session,
                seed=seed,
                math_formalization=math_formalization,
                hypothesis=selected,
                research_target=research_target,
                selected_pack=selected_pack,
            )

    def _run_exploratory_rounds(
        self,
        *,
        session: ResearchSession,
        seed: ResearchSeed,
        initial_math_result: MathAgentResult,
        selected_pack: ExperimentPack | None = None,
    ) -> None:
        if session.sandbox_spec is None:
            return

        round_index = 1
        candidate_hypotheses = list(session.hypotheses)
        current_math_result = initial_math_result

        while round_index <= session.sandbox_spec.max_exploratory_rounds:
            remaining_job_budget = self._remaining_job_budget(session)
            if remaining_job_budget is not None and remaining_job_budget <= 0:
                break

            selected_hypotheses = self._select_hypotheses(
                session,
                selected_pack=selected_pack,
                hypotheses=candidate_hypotheses,
                branch_budget=remaining_job_budget,
            )
            if not selected_hypotheses:
                break

            self._trace(
                session=session,
                event_type="exploratory_round_started",
                agent="orchestrator",
                summary=f"Started bounded exploratory round {round_index}.",
                data={
                    "round_index": round_index,
                    "remaining_job_budget": remaining_job_budget,
                    "candidate_hypothesis_count": len(candidate_hypotheses),
                },
            )
            self._trace_branch_selection(
                session=session,
                hypotheses=selected_hypotheses,
                round_index=round_index,
            )

            evidence_start = len(session.evidence)
            job_start = len(session.jobs)
            self._execute_selected_hypotheses(
                session=session,
                seed=seed,
                math_formalization=current_math_result.formalization_summary,
                hypotheses=selected_hypotheses,
                research_target=session.research_target,
                selected_pack=selected_pack,
            )

            round_evidence = session.evidence[evidence_start:]
            round_summary = self._build_exploratory_round_summary(
                round_index=round_index,
                hypotheses=selected_hypotheses,
                evidence=round_evidence,
            )
            session.exploratory_rounds_executed = round_index
            session.exploratory_round_summaries.append(round_summary)
            self._trace(
                session=session,
                event_type="exploratory_round_completed",
                agent="orchestrator",
                summary=round_summary,
                data={
                    "round_index": round_index,
                    "jobs_executed_this_round": len(session.jobs) - job_start,
                    "evidence_count_this_round": len(round_evidence),
                    "selected_hypothesis_ids": [
                        hypothesis.hypothesis_id for hypothesis in selected_hypotheses
                    ],
                },
            )

            if round_index >= session.sandbox_spec.max_exploratory_rounds:
                break

            remaining_job_budget = self._remaining_job_budget(session)
            if remaining_job_budget is not None and remaining_job_budget <= 0:
                break

            follow_up_context = self._derive_follow_up_context(
                session=session,
                round_index=round_index,
                hypotheses=selected_hypotheses,
                evidence=round_evidence,
            )
            if not follow_up_context:
                break

            self._trace(
                session=session,
                event_type="exploratory_round_followup_generated",
                agent="orchestrator",
                summary=f"Generated bounded follow-up context for exploratory round {round_index + 1}.",
                data={
                    "round_index": round_index + 1,
                    "parent_hypothesis_ids": [
                        hypothesis.hypothesis_id for hypothesis in selected_hypotheses
                    ],
                    "follow_up_context": follow_up_context,
                },
            )

            (
                next_math_result,
                next_cryptography_result,
                next_strategy_result,
                next_hypothesis_result,
                next_critic_result,
                next_hypotheses,
            ) = self._run_agent_round(
                session=session,
                seed=seed,
                round_index=round_index + 1,
                follow_up_context=follow_up_context,
                parent_hypothesis_id=selected_hypotheses[0].hypothesis_id,
            )
            deduped_hypotheses = self._dedupe_hypotheses(
                existing_hypotheses=session.hypotheses,
                new_hypotheses=next_hypotheses,
            )
            if not deduped_hypotheses:
                break

            session.math_result = next_math_result
            session.cryptography_result = next_cryptography_result
            session.strategy_result = next_strategy_result
            session.hypothesis_result = next_hypothesis_result
            session.critic_result = next_critic_result
            session.hypotheses.extend(deduped_hypotheses)
            candidate_hypotheses = deduped_hypotheses
            current_math_result = next_math_result
            round_index += 1

    def _build_agent_contributions(self, session: ResearchSession) -> list[str]:
        contributions: list[str] = []
        if session.math_result is not None:
            contributions.append(
                f"Mathematical formalization: {session.math_result.formalization_summary}"
            )
        if session.cryptography_result is not None:
            tool_families = ", ".join(session.cryptography_result.preferred_tool_families)
            local_tools = ", ".join(session.cryptography_result.preferred_local_tools)
            contributions.append(
                "Cryptographic surface profile: "
                f"{session.cryptography_result.surface_summary}"
                + (f" Preferred tool families: {tool_families}." if tool_families else "")
                + (f" Preferred local tools: {local_tools}." if local_tools else "")
            )
        if session.strategy_result is not None:
            primary_checks = ", ".join(session.strategy_result.primary_checks)
            escalation_tools = ", ".join(session.strategy_result.escalation_local_tools)
            contributions.append(
                "Research strategy: "
                f"{session.strategy_result.strategy_summary}"
                + (f" Primary checks: {primary_checks}." if primary_checks else "")
                + (f" Escalation tools: {escalation_tools}." if escalation_tools else "")
            )
        if session.critic_result is not None:
            contributions.append(
                f"Critical review: {session.critic_result.critique_summary}"
            )
        return contributions

    def _build_exploratory_round_summary(
        self,
        *,
        round_index: int,
        hypotheses: list[Hypothesis],
        evidence: list[Evidence],
    ) -> str:
        tool_names = ordered_unique(
            evidence_item.tool_name or evidence_item.source
            for evidence_item in evidence
        )
        role_guided_tools = ordered_unique(
            f"{' + '.join(evidence_item.selected_by_roles)} -> {evidence_item.tool_name or evidence_item.source}"
            for evidence_item in evidence
            if evidence_item.selected_by_roles
        )
        return (
            f"Round {round_index} explored {len(hypotheses)} branch(es), recorded "
            f"{len(evidence)} evidence item(s), and used tools: {', '.join(tool_names) or 'none'}."
            + (
                f" Role-guided local tools: {', '.join(role_guided_tools)}."
                if role_guided_tools
                else ""
            )
        )

    def _derive_follow_up_context(
        self,
        *,
        session: ResearchSession,
        round_index: int,
        hypotheses: list[Hypothesis],
        evidence: list[Evidence],
    ) -> str | None:
        if not evidence:
            return None

        strongest_branches = [
            hypothesis.summary.strip()
            for hypothesis in hypotheses
            if hypothesis.status in {
                HypothesisStatus.OBSERVED_SIGNAL,
                HypothesisStatus.NEEDS_MANUAL_REVIEW,
                HypothesisStatus.VALIDATED,
                HypothesisStatus.CLOSED,
            }
        ]
        evidence_signals = [
            (item.conclusion or item.summary).strip()
            for item in evidence
            if (item.conclusion or item.summary).strip()
        ]
        if not strongest_branches and not evidence_signals:
            return None

        leading_branch = strongest_branches[0] if strongest_branches else hypotheses[0].summary.strip()
        role_guided_evidence = next(
            (
                item
                for item in evidence
                if item.selected_by_roles and (item.conclusion or item.summary).strip()
            ),
            None,
        )
        leading_signal = (
            (role_guided_evidence.conclusion or role_guided_evidence.summary).strip()
            if role_guided_evidence is not None
            else (evidence_signals[0] if evidence_signals else evidence[0].summary.strip())
        )
        role_guided_summary = None
        if role_guided_evidence is not None:
            role_guided_summary = (
                f"{' + '.join(role_guided_evidence.selected_by_roles)} drove "
                f"{role_guided_evidence.tool_name or role_guided_evidence.source}"
            )
        defensive_question = (
            session.cryptography_result.defensive_questions[0].strip()
            if session.cryptography_result is not None
            and session.cryptography_result.defensive_questions
            and session.cryptography_result.defensive_questions[0].strip()
            else None
        )
        null_control = (
            session.strategy_result.null_controls[0].strip()
            if session.strategy_result is not None
            and session.strategy_result.null_controls
            and session.strategy_result.null_controls[0].strip()
            else None
        )
        stop_condition = (
            session.strategy_result.stop_conditions[0].strip()
            if session.strategy_result is not None
            and session.strategy_result.stop_conditions
            and session.strategy_result.stop_conditions[0].strip()
            else None
        )
        return (
            f"Round {round_index} branch focus: {leading_branch}. "
            f"Recent local evidence: {leading_signal}. "
            + (f"Role-guided experiment focus: {role_guided_summary}. " if role_guided_summary else "")
            + (f"Defensive question to tighten: {defensive_question}. " if defensive_question else "")
            + (f"Preserve null-control: {null_control}. " if null_control else "")
            + (f"Stop if this condition is reached: {stop_condition}. " if stop_condition else "")
            + "Generate a stricter bounded follow-up branch plus a conservative null explanation."
        )

    def _dedupe_hypotheses(
        self,
        *,
        existing_hypotheses: list[Hypothesis],
        new_hypotheses: list[Hypothesis],
    ) -> list[Hypothesis]:
        seen = {
            (
                hypothesis.summary.strip().lower(),
                (hypothesis.planned_test or "").strip().lower(),
            )
            for hypothesis in existing_hypotheses
        }
        unique_hypotheses: list[Hypothesis] = []
        for hypothesis in new_hypotheses:
            key = (
                hypothesis.summary.strip().lower(),
                (hypothesis.planned_test or "").strip().lower(),
            )
            if key in seen:
                continue
            seen.add(key)
            unique_hypotheses.append(hypothesis)
        return unique_hypotheses

    def _execute_hypothesis_branch(
        self,
        *,
        session: ResearchSession,
        seed: ResearchSeed,
        math_formalization: str,
        hypothesis: Hypothesis,
        research_target: ResearchTarget | None,
        selected_pack: ExperimentPack | None = None,
    ) -> None:
        transition_hypothesis(hypothesis, HypothesisStatus.RUNNING)
        branch_jobs = self._build_branch_jobs(
            session=session,
            seed_text=seed.raw_text,
            formalization=math_formalization,
            hypothesis=hypothesis,
            research_target=research_target,
            selected_pack=selected_pack,
        )
        if not branch_jobs:
            transition_hypothesis(hypothesis, HypothesisStatus.CLOSED)
            self._trace(
                session=session,
                event_type="job_skipped",
                agent="orchestrator",
                hypothesis_id=hypothesis.hypothesis_id,
                summary="No applicable bounded jobs were available for the selected branch and experiment-pack context.",
                data={
                    "selected_pack_name": selected_pack.pack_name if selected_pack is not None else None,
                },
            )
            return

        branch_results: list[dict[str, object]] = []
        for job, pack_step in branch_jobs:
            session.jobs.append(job)
            self._trace(
                session=session,
                event_type="job_planned",
                agent="orchestrator",
                hypothesis_id=hypothesis.hypothesis_id,
                summary="Compute job planned through the registry-controlled executor.",
                data={
                    "tool_name": job.tool_name,
                    "timeout_seconds": job.timeout_seconds,
                    "tool_plan": job.tool_plan.model_dump(mode="json") if job.tool_plan is not None else None,
                    "experiment_spec": (
                        job.experiment_spec.model_dump(mode="json")
                        if job.experiment_spec is not None
                        else None
                    ),
                    "research_mode": session.research_mode.value,
                    "sandbox_id": session.sandbox_spec.sandbox_id if session.sandbox_spec else None,
                    "selected_pack_name": selected_pack.pack_name if selected_pack is not None else None,
                    "pack_step_id": pack_step.step_id if pack_step is not None else None,
                },
            )
            executed_job, raw_result = self._execute_with_fallback(
                session=session,
                hypothesis=hypothesis,
                job=job,
            )
            workspace = self._record_math_workspace_if_needed(
                session=session,
                job=executed_job,
                raw_result=raw_result,
            )
            evidence = self._record_evidence(
                session=session,
                hypothesis=hypothesis,
                job=executed_job,
                raw_result=raw_result,
                workspace=workspace,
                selected_pack=selected_pack,
                pack_step=pack_step,
            )
            session.evidence.append(evidence)
            if pack_step is not None:
                step_reference = f"{selected_pack.pack_name}:{pack_step.step_id}"
                if step_reference not in session.executed_pack_steps:
                    session.executed_pack_steps.append(step_reference)
            branch_results.append(raw_result)

        self._apply_branch_observation_outcome(hypothesis, branch_results)

    def _build_branch_jobs(
        self,
        *,
        session: ResearchSession,
        seed_text: str,
        formalization: str,
        hypothesis: Hypothesis,
        research_target: ResearchTarget | None,
        selected_pack: ExperimentPack | None,
    ) -> list[tuple[ComputeJob, ExperimentPackStep | None]]:
        if selected_pack is None:
            tool_plans = self._build_default_branch_tool_plans(
                session=session,
                seed_text=seed_text,
                hypothesis=hypothesis,
                research_target=research_target,
            )
            jobs: list[tuple[ComputeJob, ExperimentPackStep | None]] = []
            for tool_index, tool_plan in enumerate(tool_plans):
                if tool_index > 0 and not self._tool_is_available_for_branch(tool_plan.tool_name):
                    continue
                experiment_spec = self._build_experiment_spec(
                    session=session,
                    seed_text=seed_text,
                    formalization=formalization,
                    hypothesis=hypothesis,
                    tool_plan=tool_plan,
                    research_target=research_target,
                )
                jobs.append(
                    (
                        self._create_job(
                            hypothesis_id=hypothesis.hypothesis_id,
                            tool_plan=tool_plan,
                            experiment_spec=experiment_spec,
                            seed_text=seed_text,
                            formalization=formalization,
                            hypothesis_summary=hypothesis.summary,
                            planned_test=hypothesis.planned_test or "",
                            research_target=research_target,
                        ),
                        None,
                    )
                )
            return jobs

        steps = self.experiment_pack_registry.steps_for_execution(
            pack=selected_pack,
            research_target=research_target,
            seed_text=seed_text,
            available_tools=self.executor.registry.names(),
            advanced_math_enabled=self.config.advanced_math_enabled,
            sage_enabled=self.config.sage.enabled,
        )
        if not steps:
            raise ValueError(
                f"Experiment pack {selected_pack.pack_name} has no applicable bounded steps for the current target."
            )

        budget = self._remaining_job_budget(session)
        if budget is not None:
            steps = steps[: max(1, budget)]

        jobs: list[tuple[ComputeJob, ExperimentPackStep | None]] = []
        for step in steps:
            tool_plan = self._build_pack_tool_plan(
                hypothesis=hypothesis,
                pack=selected_pack,
                step=step,
            )
            experiment_spec = self._build_pack_experiment_spec(
                seed_text=seed_text,
                formalization=formalization,
                hypothesis=hypothesis,
                tool_plan=tool_plan,
                step=step,
                research_target=research_target,
                pack=selected_pack,
            )
            jobs.append(
                (
                    self._create_job(
                        hypothesis_id=hypothesis.hypothesis_id,
                        tool_plan=tool_plan,
                        experiment_spec=experiment_spec,
                        seed_text=seed_text,
                        formalization=formalization,
                        hypothesis_summary=hypothesis.summary,
                        planned_test=hypothesis.planned_test or "",
                        research_target=research_target,
                    ),
                    step,
                )
            )
        return jobs

    def _create_job(
        self,
        *,
        hypothesis_id: str,
        tool_plan: ToolPlan,
        experiment_spec: ExperimentSpec,
        seed_text: str,
        formalization: str,
        hypothesis_summary: str,
        planned_test: str,
        research_target: ResearchTarget | None,
    ) -> ComputeJob:
        if (
            research_target is not None
            and research_target.target_origin == "synthetic"
            and tool_plan.tool_name == "placeholder_math_tool"
        ):
            raise ValueError("Synthetic research targets cannot fall back to placeholder_math_tool.")
        return ComputeJob(
            hypothesis_id=hypothesis_id,
            tool_name=tool_plan.tool_name,
            tool_plan=tool_plan,
            experiment_spec=experiment_spec,
            payload=self._build_tool_payload(
                tool_plan=tool_plan,
                experiment_spec=experiment_spec,
                seed_text=seed_text,
                formalization=formalization,
                hypothesis_summary=hypothesis_summary,
                planned_test=planned_test,
                research_target=research_target,
            ),
            timeout_seconds=self.config.tool_timeout_seconds,
        )

    def _record_evidence(
        self,
        *,
        session: ResearchSession,
        hypothesis: Hypothesis,
        job: ComputeJob,
        raw_result: dict[str, object],
        workspace: MathWorkspace | None,
        selected_pack: ExperimentPack | None,
        pack_step: ExperimentPackStep | None,
    ) -> Evidence:
        evidence = Evidence(
            hypothesis_id=job.hypothesis_id,
            source=job.tool_name,
            summary=build_evidence_summary(raw_result),
            tool_name=job.tool_name,
            tool_metadata_snapshot=raw_result.get("tool_metadata"),
            experiment_type=(
                job.experiment_spec.experiment_type.value
                if job.experiment_spec is not None
                else ""
            )
            or None,
            selected_by_roles=list(job.tool_plan.selected_by_roles) if job.tool_plan is not None else [],
            selected_pack_name=selected_pack.pack_name if selected_pack is not None else None,
            pack_step_id=pack_step.step_id if pack_step is not None else None,
            target_kind=(
                job.experiment_spec.target_kind
                if job.experiment_spec is not None
                else None
            ),
            sandbox_id=session.sandbox_spec.sandbox_id if session.sandbox_spec is not None else None,
            research_target_reference=(
                session.research_target.target_reference
                if session.research_target is not None
                else None
            ),
            target_origin=(
                session.research_target.target_origin
                if session.research_target is not None
                else None
            ),
            synthetic_target_name=(
                session.research_target.synthetic_target_name
                if session.research_target is not None
                else None
            ),
            target_profile=(
                session.research_target.target_profile
                if session.research_target is not None
                else None
            ),
            deterministic=bool(raw_result.get("deterministic", True)),
            conclusion=build_evidence_conclusion(raw_result),
            workspace_id=workspace.workspace_id if workspace is not None else None,
            artifact_paths=list(workspace.artifact_paths) if workspace is not None else [],
            notes=extract_evidence_notes(raw_result),
            raw_result=raw_result,
        )
        self._trace(
            session=session,
            event_type="evidence_recorded",
            agent="orchestrator",
            hypothesis_id=hypothesis.hypothesis_id,
            summary=evidence.summary,
            data={
                "evidence_id": evidence.evidence_id,
                "tool_name": evidence.tool_name,
                "deterministic": evidence.deterministic,
                "conclusion": evidence.conclusion,
                "experiment_type": evidence.experiment_type,
                "selected_by_roles": evidence.selected_by_roles,
                "target_kind": evidence.target_kind,
                "workspace_id": evidence.workspace_id,
                "artifact_paths": evidence.artifact_paths,
                "sandbox_id": evidence.sandbox_id,
                "research_target_reference": evidence.research_target_reference,
                "target_origin": evidence.target_origin,
                "synthetic_target_name": evidence.synthetic_target_name,
                "target_profile": evidence.target_profile,
                "selected_pack_name": evidence.selected_pack_name,
                "pack_step_id": evidence.pack_step_id,
            },
        )
        return evidence

    def _apply_branch_observation_outcome(
        self,
        hypothesis: Hypothesis,
        raw_results: list[dict[str, object]],
    ) -> None:
        if not raw_results:
            transition_hypothesis(hypothesis, HypothesisStatus.CLOSED)
            return

        aggregate_data: dict[str, object] = {
            "recognized": False,
            "parsed": False,
            "well_formed": False,
            "consistent": False,
            "format_recognized": False,
            "supported": False,
            "manual_review_recommended": False,
            "issues": [],
            "repeatability": False,
            "keyword_hit_count": 0,
        }
        for raw_result in raw_results:
            result = raw_result.get("result", {})
            if not isinstance(result, dict):
                continue
            result_data = result.get("result_data", {})
            if not isinstance(result_data, dict):
                continue
            for key in (
                "recognized",
                "parsed",
                "well_formed",
                "consistent",
                "format_recognized",
                "supported",
                "manual_review_recommended",
                "repeatability",
            ):
                aggregate_data[key] = bool(aggregate_data[key]) or bool(result_data.get(key, False))
            aggregate_data["keyword_hit_count"] = int(aggregate_data["keyword_hit_count"]) + int(
                result_data.get("keyword_hit_count", 0)
            )
            issues = result_data.get("issues")
            if isinstance(issues, list):
                aggregate_data["issues"].extend(str(item) for item in issues if str(item).strip())

        self._apply_observation_outcome(
            hypothesis,
            {
                "tool_name": "branch_aggregate",
                "result": {
                    "result_data": aggregate_data,
                },
            },
        )

    def _execute_with_fallback(
        self,
        *,
        session: ResearchSession,
        hypothesis: Hypothesis,
        job: ComputeJob,
    ) -> tuple[ComputeJob, dict[str, object]]:
        raw_result = self._execute_local_job(
            session=session,
            hypothesis=hypothesis,
            job=job,
        )
        self._trace(
            session=session,
            event_type="job_executed",
            agent="ComputeExecutor",
            hypothesis_id=hypothesis.hypothesis_id,
            summary="Compute job executed through the approved local tool registry.",
                data=build_job_trace_data(raw_result)
            | {
                "selected_by_roles": (
                    list(job.tool_plan.selected_by_roles)
                    if job.tool_plan is not None
                    else []
                ),
                "experiment_type": (
                    job.experiment_spec.experiment_type.value
                    if job.experiment_spec is not None
                    else None
                ),
            },
        )

        if not should_fallback_from_sage(job=job, raw_result=raw_result):
            return job, raw_result

        fallback_job = ComputeJob(
            hypothesis_id=job.hypothesis_id,
            tool_name="symbolic_check_tool",
            tool_plan=ToolPlan(
                tool_name="symbolic_check_tool",
                reason=(
                    "Fallback to the simpler deterministic symbolic tool because the Sage adapter "
                    "path was unavailable or did not produce a usable result."
                ),
                priority=job.tool_plan.priority if job.tool_plan is not None else 1,
                expected_output="parsed symbolic expression and normalized form",
                deterministic_expected=True,
            ),
            experiment_spec=ExperimentSpec(
                experiment_type=ExperimentType.SYMBOLIC_SIMPLIFICATION,
                target_kind="symbolic",
                target_reference=(
                    job.experiment_spec.target_reference
                    if job.experiment_spec is not None
                    else "x + y - y"
                ),
                parameters={
                    **(job.experiment_spec.parameters if job.experiment_spec is not None else {}),
                    "fallback_from": "sage_symbolic_tool",
                },
                repeat_count=1,
                deterministic_required=True,
            ),
            payload={
                "expression": (
                    job.experiment_spec.target_reference
                    if job.experiment_spec is not None
                    else "x + y - y"
                ),
            },
            timeout_seconds=job.timeout_seconds,
        )
        session.jobs.append(fallback_job)
        self._trace(
            session=session,
            event_type="job_planned",
            agent="orchestrator",
            hypothesis_id=hypothesis.hypothesis_id,
            summary="Fallback compute job planned after unavailable advanced symbolic path.",
            data={
                "tool_name": fallback_job.tool_name,
                "timeout_seconds": fallback_job.timeout_seconds,
                "tool_plan": fallback_job.tool_plan.model_dump(mode="json"),
                "experiment_spec": fallback_job.experiment_spec.model_dump(mode="json"),
            },
        )
        fallback_result = self._execute_local_job(
            session=session,
            hypothesis=hypothesis,
            job=fallback_job,
        )
        append_result_note(
            fallback_result,
            "Fallback executed after sage_symbolic_tool returned an unavailable or error state.",
        )
        self._trace(
            session=session,
            event_type="job_executed",
            agent="ComputeExecutor",
            hypothesis_id=hypothesis.hypothesis_id,
            summary="Fallback compute job executed through the approved local tool registry.",
            data=build_job_trace_data(fallback_result)
            | {
                "selected_by_roles": (
                    list(fallback_job.tool_plan.selected_by_roles)
                    if fallback_job.tool_plan is not None
                    else []
                ),
                "experiment_type": (
                    fallback_job.experiment_spec.experiment_type.value
                    if fallback_job.experiment_spec is not None
                    else None
                ),
            },
        )
        return fallback_job, fallback_result

    def _execute_local_job(
        self,
        *,
        session: ResearchSession,
        hypothesis: Hypothesis,
        job: ComputeJob,
    ) -> dict[str, object]:
        if session.sandbox_spec is None or session.research_target is None:
            return self.executor.execute(job)

        sandbox_result = self.sandbox_executor.execute(
            request=SandboxExecutionRequest(
                session_id=session.session_id,
                hypothesis_id=hypothesis.hypothesis_id,
                sandbox_id=session.sandbox_spec.sandbox_id,
                research_mode=session.research_mode,
                local_only=session.sandbox_spec.local_only,
                reversible=session.sandbox_spec.reversible,
                bounded=session.sandbox_spec.bounded,
                tool_name=job.tool_name,
                research_target=session.research_target,
                approved_tool_names=list(session.sandbox_spec.approved_tool_names),
            ),
            job=job,
        )
        assert sandbox_result.raw_result is not None
        return sandbox_result.raw_result

    def _record_math_workspace_if_needed(
        self,
        *,
        session: ResearchSession,
        job: ComputeJob,
        raw_result: dict[str, object],
    ) -> MathWorkspace | None:
        if not self._is_advanced_math_tool(job.tool_name) or job.experiment_spec is None:
            return None

        workspace = self.math_artifact_store.create_workspace(
            session_id=session.session_id,
            experiment_type=job.experiment_spec.experiment_type.value,
            tool_name=job.tool_name,
            notes=[
                "Workspace created for bounded advanced local math execution.",
                f"target_kind={job.experiment_spec.target_kind}",
                (
                    f"sandbox_id={session.sandbox_spec.sandbox_id}"
                    if session.sandbox_spec is not None
                    else "sandbox_id=none"
                ),
            ],
        )
        self.math_artifact_store.write_execution_artifact(
            workspace=workspace,
            job=job,
            payload=raw_result,
        )
        session.math_workspaces.append(workspace)
        return workspace

    def _resolve_research_mode(
        self,
        research_mode: ResearchMode | str | None,
    ) -> ResearchMode:
        if research_mode is None:
            return self.config.research.default_mode
        if isinstance(research_mode, ResearchMode):
            return research_mode
        return ResearchMode(str(research_mode).strip().lower())

    def _build_sandbox_spec(
        self,
        *,
        research_mode: ResearchMode,
        seed_text: str,
    ) -> SandboxSpec | None:
        if research_mode != ResearchMode.SANDBOXED_EXPLORATORY:
            return None

        exploration_profile = self._resolve_exploration_profile(seed_text)
        max_branches = self.config.research.max_exploratory_branches
        max_rounds = self.config.research.max_exploratory_rounds
        max_jobs = self.config.research.max_jobs_per_session
        if exploration_profile == ExplorationProfile.AGGRESSIVE_BOUNDED:
            max_branches = max(
                max_branches,
                self.config.research.aggressive_max_exploratory_branches,
            )
            max_rounds = max(
                max_rounds,
                self.config.research.aggressive_max_exploratory_rounds,
            )
            max_jobs = max(
                max_jobs,
                self.config.research.aggressive_max_jobs_per_session,
            )

        approved_tool_names = [
            metadata.name
            for metadata in self.executor.registry.list_metadata()
            if metadata.source_type == "built_in"
        ]
        return SandboxSpec(
            mode=research_mode,
            exploration_profile=exploration_profile,
            max_exploratory_branches=max_branches,
            max_exploratory_rounds=max_rounds,
            max_jobs_per_session=max_jobs,
            approved_tool_names=approved_tool_names,
            notes=[
                "Sandboxed exploratory mode permits only bounded local tool execution.",
                "Built-in tools are approved by default; plugin tools are excluded unless explicitly integrated later.",
                "Primary branch count is capped before execution to avoid unbounded exploratory fan-out.",
                "Exploratory rounds are capped to keep multi-round follow-up bounded and replayable.",
                (
                    "Aggressive bounded profile enabled: exploratory depth is increased but still stays inside local sandbox limits."
                    if exploration_profile == ExplorationProfile.AGGRESSIVE_BOUNDED
                    else "Cautious profile enabled: exploratory depth remains conservative by default."
                ),
            ],
        )

    def _resolve_exploration_profile(self, seed_text: str) -> ExplorationProfile:
        lowered = seed_text.lower()
        aggressive_tokens = (
            "aggressive",
            "deep",
            "deeper",
            "multi-round",
            "multi round",
            "iterative",
            "fuzz",
            "mutation",
            "mutate",
            "testbed",
            "corpus",
            "counterexample",
            "invariant",
            "formal",
            "parser anomaly",
            "validation edge",
            "edge-case",
            "edge case",
        )
        hit_count = sum(1 for token in aggressive_tokens if token in lowered)
        if hit_count >= 2:
            return ExplorationProfile.AGGRESSIVE_BOUNDED
        return self.config.research.default_exploration_profile

    def _build_research_target(
        self,
        *,
        session: ResearchSession,
        seed_text: str,
        formalization: str,
        hypotheses: list[Hypothesis],
        synthetic_target_name: str | None = None,
    ) -> ResearchTarget:
        if synthetic_target_name:
            return self.target_registry.build_synthetic_target(synthetic_target_name)

        reference_hypothesis = max(
            hypotheses,
            key=lambda hypothesis: hypothesis.score,
            default=Hypothesis(
                source_agent="orchestrator",
                summary=seed_text,
                rationale=formalization or seed_text,
                branch_type=BranchType.CORE,
                priority=1,
            ),
        )
        target_kind = self._determine_target_kind(
            seed_text=seed_text,
            planned_test=reference_hypothesis.planned_test or "",
            summary=reference_hypothesis.summary,
        )
        target_reference = self._target_reference_for_kind(
            target_kind=target_kind,
            seed_text=seed_text,
            formalization=formalization,
            hypothesis=reference_hypothesis,
            session=session,
        )
        curve_name = extract_curve_name(
            f"{seed_text} {formalization} {reference_hypothesis.summary} {reference_hypothesis.planned_test or ''}"
        )
        return self.target_registry.apply_profile(
            ResearchTarget(
                target_kind=target_kind,
                target_reference=target_reference,
                curve_name=curve_name,
                notes=[
                    "Research target was inferred from the validated seed plus the strongest formalized branch.",
                    "This target is descriptive and bounded; it does not authorize unrestricted execution.",
                ],
            )
        )

    def _apply_observation_outcome(
        self,
        hypothesis: Hypothesis,
        raw_result: dict[str, object],
    ) -> None:
        result = raw_result.get("result", {})
        if not isinstance(result, dict):
            transition_hypothesis(hypothesis, HypothesisStatus.CLOSED)
            return
        result_data = result.get("result_data", {})
        if not isinstance(result_data, dict):
            result_data = {}

        if (
            bool(result_data.get("recognized"))
            or bool(result_data.get("parsed"))
            or bool(result_data.get("well_formed"))
            or bool(result_data.get("consistent"))
            or bool(result_data.get("format_recognized"))
            or bool(result_data.get("supported"))
        ):
            transition_hypothesis(hypothesis, HypothesisStatus.OBSERVED_SIGNAL)
            if result_data.get("manual_review_recommended", False) or result_data.get("issues"):
                transition_hypothesis(hypothesis, HypothesisStatus.NEEDS_MANUAL_REVIEW)
            else:
                transition_hypothesis(hypothesis, HypothesisStatus.VALIDATED)
                transition_hypothesis(hypothesis, HypothesisStatus.CLOSED)
            return

        if bool(result_data.get("repeatability")):
            transition_hypothesis(hypothesis, HypothesisStatus.OBSERVED_SIGNAL)
            transition_hypothesis(hypothesis, HypothesisStatus.VALIDATED)
            transition_hypothesis(hypothesis, HypothesisStatus.CLOSED)
            return

        if result_data.get("keyword_hit_count", 0) > 0:
            transition_hypothesis(hypothesis, HypothesisStatus.OBSERVED_SIGNAL)
            if result_data.get("manual_review_recommended", False):
                transition_hypothesis(hypothesis, HypothesisStatus.NEEDS_MANUAL_REVIEW)
            else:
                transition_hypothesis(hypothesis, HypothesisStatus.VALIDATED)
                transition_hypothesis(hypothesis, HypothesisStatus.CLOSED)
            return

        transition_hypothesis(hypothesis, HypothesisStatus.CLOSED)

    def _resolve_experiment_pack(
        self,
        *,
        seed_text: str,
        research_target: ResearchTarget | None,
        explicit_pack_name: str | None,
    ) -> tuple[ExperimentPack | None, list[ExperimentPackRecommendation]]:
        recommendations = self.experiment_pack_registry.recommend(
            seed_text=seed_text,
            research_target=research_target,
        )
        if not explicit_pack_name:
            return None, recommendations

        selected_pack = self.experiment_pack_registry.require(explicit_pack_name)
        applicable_steps = self.experiment_pack_registry.steps_for_execution(
            pack=selected_pack,
            research_target=research_target,
            seed_text=seed_text,
            available_tools=self.executor.registry.names(),
            advanced_math_enabled=self.config.advanced_math_enabled,
            sage_enabled=self.config.sage.enabled,
        )
        if not applicable_steps:
            target_kind = research_target.target_kind if research_target is not None else "generic"
            raise ValueError(
                f"Experiment pack {selected_pack.pack_name} has no applicable bounded steps for target kind {target_kind}."
            )
        return selected_pack, recommendations

    def _remaining_job_budget(self, session: ResearchSession) -> int | None:
        if session.sandbox_spec is None:
            return None
        remaining = session.sandbox_spec.max_jobs_per_session - len(session.jobs)
        return max(0, remaining)

    def _build_tool_plan(
        self,
        *,
        session: ResearchSession,
        seed_text: str,
        hypothesis: Hypothesis,
        research_target: ResearchTarget | None = None,
    ) -> ToolPlan:
        return build_tool_plan(
            config=self.config,
            session=session,
            seed_text=seed_text,
            hypothesis=hypothesis,
            research_target=research_target,
        )

    def _build_default_branch_tool_plans(
        self,
        *,
        session: ResearchSession,
        seed_text: str,
        hypothesis: Hypothesis,
        research_target: ResearchTarget | None = None,
    ) -> list[ToolPlan]:
        target_kind = (
            research_target.target_kind
            if research_target is not None and research_target.target_origin == "synthetic"
            else self._determine_target_kind(
                seed_text=seed_text,
                planned_test=hypothesis.planned_test or "",
                summary=hypothesis.summary,
            )
        )
        if (
            session.research_mode != ResearchMode.SANDBOXED_EXPLORATORY
            and target_kind == "smart_contract"
        ):
            return build_standard_smart_contract_tool_plans(
                config=self.config,
                session=session,
                seed_text=seed_text,
                hypothesis=hypothesis,
                research_target=research_target,
            )
        return [
            self._build_tool_plan(
                session=session,
                seed_text=seed_text,
                hypothesis=hypothesis,
                research_target=research_target,
            )
        ]

    def _build_pack_tool_plan(
        self,
        *,
        hypothesis: Hypothesis,
        pack: ExperimentPack,
        step: ExperimentPackStep,
    ) -> ToolPlan:
        return build_pack_tool_plan(
            hypothesis=hypothesis,
            pack=pack,
            step=step,
        )

    def _build_experiment_spec(
        self,
        *,
        session: ResearchSession,
        seed_text: str,
        formalization: str,
        hypothesis: Hypothesis,
        tool_plan: ToolPlan,
        research_target: ResearchTarget | None = None,
    ) -> ExperimentSpec:
        return build_experiment_spec(
            config=self.config,
            session=session,
            seed_text=seed_text,
            formalization=formalization,
            hypothesis=hypothesis,
            tool_plan=tool_plan,
            research_target=research_target,
        )

    def _build_pack_experiment_spec(
        self,
        *,
        seed_text: str,
        formalization: str,
        hypothesis: Hypothesis,
        tool_plan: ToolPlan,
        step: ExperimentPackStep,
        research_target: ResearchTarget | None,
        pack: ExperimentPack,
    ) -> ExperimentSpec:
        return build_pack_experiment_spec(
            seed_text=seed_text,
            formalization=formalization,
            hypothesis=hypothesis,
            tool_plan=tool_plan,
            step=step,
            research_target=research_target,
            pack=pack,
        )

    def _determine_target_kind(
        self,
        *,
        seed_text: str,
        planned_test: str,
        summary: str,
    ) -> str:
        return determine_target_kind(
            seed_text=seed_text,
            planned_test=planned_test,
            summary=summary,
        )

    def _tool_name_for_target_kind(self, target_kind: str, *, combined_text: str = "") -> str:
        return tool_name_for_target_kind(
            config=self.config,
            target_kind=target_kind,
            combined_text=combined_text,
        )

    def _resolve_tool_name_for_hypothesis(
        self,
        *,
        session: ResearchSession,
        hypothesis: Hypothesis,
        target_kind: str,
        combined_text: str,
    ) -> tuple[str, list[str]]:
        return resolve_tool_name_for_hypothesis(
            config=self.config,
            session=session,
            hypothesis=hypothesis,
            target_kind=target_kind,
            combined_text=combined_text,
        )

    def _normalized_tool_family_hints(self, session: ResearchSession) -> set[str]:
        return normalized_tool_family_hints(session)

    def _normalized_role_tool_hints(self, session: ResearchSession) -> dict[str, set[str]]:
        return normalized_role_tool_hints(session)

    def _normalize_tool_hint(self, value: str) -> str | None:
        return normalize_tool_hint(value)

    def _choose_role_guided_candidate(
        self,
        *,
        session: ResearchSession,
        candidates: list[tuple[str, list[str]]],
    ) -> tuple[str, list[str]]:
        return choose_role_guided_candidate(session=session, candidates=candidates)

    def _strategy_guidance_text(self, session: ResearchSession) -> str:
        return strategy_guidance_text(session)

    def _target_reference_for_kind(
        self,
        *,
        target_kind: str,
        seed_text: str,
        formalization: str,
        hypothesis: Hypothesis,
        session: ResearchSession | None = None,
    ) -> str:
        return target_reference_for_kind(
            target_kind=target_kind,
            seed_text=seed_text,
            formalization=formalization,
            hypothesis=hypothesis,
            session=session,
        )

    def _normalized_testbed_hints(self, session: ResearchSession | None) -> set[str]:
        return normalized_testbed_hints(session)

    def _build_tool_payload(
        self,
        *,
        tool_plan: ToolPlan,
        experiment_spec: ExperimentSpec,
        seed_text: str,
        formalization: str,
        hypothesis_summary: str,
        planned_test: str,
        research_target: ResearchTarget | None = None,
    ) -> dict[str, object]:
        return build_tool_payload(
            config=self.config,
            tool_plan=tool_plan,
            experiment_spec=experiment_spec,
            seed_text=seed_text,
            formalization=formalization,
            hypothesis_summary=hypothesis_summary,
            planned_test=planned_test,
            research_target=research_target,
        )

    def _tool_is_available_for_branch(self, tool_name: str) -> bool:
        try:
            tool = self.executor.registry.get(tool_name)
        except KeyError:
            return False
        runner = getattr(tool, "runner", None)
        is_available = getattr(runner, "is_available", None)
        if callable(is_available):
            try:
                return bool(is_available())
            except Exception:
                return False
        return True

    def _is_advanced_math_tool(self, tool_name: str) -> bool:
        return tool_name in {
            "sage_symbolic_tool",
            "finite_field_check_tool",
            "property_invariant_tool",
            "formal_constraint_tool",
        }

    def _build_run_manifest(self, session: ResearchSession) -> RunManifest:
        return build_run_manifest(
            session=session,
            config=self.config,
            plugin_metadata=self.plugin_metadata,
            session_path_fallback=self.session_store.path_for_session(session.session_id),
        )

    def _trace(
        self,
        *,
        session: ResearchSession,
        event_type: str,
        agent: str,
        summary: str,
        hypothesis_id: str | None = None,
        data: dict[str, object] | None = None,
    ) -> None:
        self.trace_writer.append(
            TraceEvent(
                session_id=session.session_id,
                event_type=event_type,
                agent=agent,
                hypothesis_id=hypothesis_id,
                summary=summary,
                data=data,
            )
        )
