from __future__ import annotations

from dataclasses import dataclass, field

from app.core.orchestrator import ResearchOrchestrator
from app.core.replay_loader import LoadedReplaySource
from app.models.replay_request import ReplayRequest
from app.models.replay_result import ReplayResult
from app.models.session import ResearchSession


@dataclass
class ReplayPlan:
    source_type: str
    source_path: str
    session_id: str | None
    original_session_id: str | None
    seed_text: str | None
    research_mode: str | None = None
    exploration_profile: str | None = None
    selected_pack_name: str | None = None
    tool_names: list[str] = field(default_factory=list)
    experiment_types: list[str] = field(default_factory=list)
    artifact_paths: list[str] = field(default_factory=list)
    reexecution_possible: bool = False
    before_after_comparison_possible: bool = False
    baseline_session: ResearchSession | None = None
    baseline_source_type: str | None = None
    baseline_source_path: str | None = None
    notes: list[str] = field(default_factory=list)


class ReplayPlanner:
    """Plan safe replay inspection or controlled re-execution."""

    def build_plan(
        self,
        *,
        loaded_source: LoadedReplaySource,
        available_tools: list[str],
        preserve_original_seed: bool = True,
    ) -> ReplayPlan:
        seed_text = loaded_source.recovered_seed if preserve_original_seed else loaded_source.recovered_seed
        notes = list(loaded_source.notes)
        if not preserve_original_seed:
            notes.append(
                "V10 replay preserves the recovered seed text; alternative seed mutation is not supported."
            )
        if loaded_source.research_mode:
            notes.append(
                f"Recovered research mode from source: {loaded_source.research_mode}."
            )
        if loaded_source.exploration_profile:
            notes.append(
                f"Recovered exploration profile from source: {loaded_source.exploration_profile}."
            )
        if loaded_source.selected_pack_name:
            notes.append(
                f"Recovered experiment pack from source: {loaded_source.selected_pack_name}."
            )

        missing_tools = sorted(set(loaded_source.tool_names) - set(available_tools))
        if missing_tools:
            notes.append(
                "Referenced tools not currently registered: " + ", ".join(missing_tools)
            )
        reexecution_possible = bool(seed_text and not missing_tools)
        if not seed_text:
            notes.append("Re-execution is unavailable because no seed text could be recovered.")
        elif reexecution_possible:
            notes.append(
                "Controlled re-execution is possible through the current orchestrator and tool registry."
            )
        before_after_comparison_possible = loaded_source.session is not None
        if before_after_comparison_possible:
            notes.append(
                "Re-execution can attach a bounded before/after comparison against the recovered source session."
            )
        else:
            notes.append(
                "Before/after comparison is unavailable because the source session snapshot could not be recovered."
            )

        session_id = (
            loaded_source.session.session_id
            if loaded_source.session is not None
            else (loaded_source.manifest.session_id if loaded_source.manifest is not None else None)
        )
        return ReplayPlan(
            source_type=loaded_source.source_type,
            source_path=loaded_source.source_path,
            session_id=session_id,
            original_session_id=loaded_source.original_session_id,
            seed_text=seed_text,
            research_mode=loaded_source.research_mode,
            exploration_profile=loaded_source.exploration_profile,
            selected_pack_name=loaded_source.selected_pack_name,
            tool_names=list(loaded_source.tool_names),
            experiment_types=list(loaded_source.experiment_types),
            artifact_paths=list(loaded_source.artifact_paths),
            reexecution_possible=reexecution_possible,
            before_after_comparison_possible=before_after_comparison_possible,
            baseline_session=loaded_source.session,
            baseline_source_type=loaded_source.source_type,
            baseline_source_path=loaded_source.source_path,
            notes=notes,
        )

    def dry_run_result(self, *, request: ReplayRequest, plan: ReplayPlan) -> ReplayResult:
        return ReplayResult(
            source_type=request.source_type,
            source_path=request.source_path,
            session_id=plan.session_id,
            dry_run=True,
            reexecuted=False,
            success=True,
            summary=self._summarize_plan(plan=plan, dry_run=True),
            notes=plan.notes + [
                f"tools_referenced={', '.join(plan.tool_names) or 'none'}",
                f"experiment_types={', '.join(plan.experiment_types) or 'none'}",
                f"artifacts_referenced={len(plan.artifact_paths)}",
                f"reexecution_possible={plan.reexecution_possible}",
                f"before_after_comparison_possible={plan.before_after_comparison_possible}",
            ],
        )

    def execute(
        self,
        *,
        request: ReplayRequest,
        plan: ReplayPlan,
        orchestrator: ResearchOrchestrator,
        author: str | None = None,
    ) -> ReplayResult:
        if request.dry_run:
            return self.dry_run_result(request=request, plan=plan)
        if not request.reexecute:
            return ReplayResult(
                source_type=request.source_type,
                source_path=request.source_path,
                session_id=plan.session_id,
                dry_run=False,
                reexecuted=False,
                success=False,
                summary="Replay request was neither dry-run nor re-execution capable.",
                notes=plan.notes,
            )
        if not plan.reexecution_possible or not plan.seed_text:
            return ReplayResult(
                source_type=request.source_type,
                source_path=request.source_path,
                session_id=plan.session_id,
                dry_run=False,
                reexecuted=False,
                success=False,
                summary="Controlled replay could not proceed because the source was only partially replayable.",
                notes=plan.notes,
            )

        session = orchestrator.run_session(
            seed_text=plan.seed_text,
            author=author,
            research_mode=plan.research_mode,
            experiment_pack_name=plan.selected_pack_name,
            replay_source_type=request.source_type,
            replay_source_path=request.source_path,
            original_session_id=plan.original_session_id or plan.session_id,
            replay_mode="reexecute",
            replay_notes=plan.notes + [
                f"tools_referenced={', '.join(plan.tool_names) or 'none'}",
                f"experiment_types={', '.join(plan.experiment_types) or 'none'}",
                f"reused_research_mode={plan.research_mode or 'standard'}",
                "reused_seed=recovered_from_replay_source",
                "new_execution=orchestrator_controlled",
            ],
            comparison_baseline=plan.baseline_session,
            comparison_baseline_source_type=plan.baseline_source_type,
            comparison_baseline_source_path=plan.baseline_source_path,
        )
        comparison_note = (
            [
                "Before/after comparison against the recovered source session was attached to the generated report."
            ]
            if session.comparative_report is not None and session.comparative_report.cross_session_comparison is not None
            else []
        )
        return ReplayResult(
            source_type=request.source_type,
            source_path=request.source_path,
            session_id=session.session_id,
            dry_run=False,
            reexecuted=True,
            success=True,
            summary=self._summarize_plan(plan=plan, dry_run=False),
            generated_session_path=session.session_file_path,
            generated_trace_path=session.trace_file_path,
            generated_bundle_path=session.bundle_dir,
            notes=plan.notes
            + comparison_note
            + ["Replay produced a new session, trace, and reproducibility bundle."],
        )

    def _summarize_plan(self, *, plan: ReplayPlan, dry_run: bool) -> str:
        mode = "dry-run inspection" if dry_run else "controlled re-execution"
        return (
            f"Replay {mode} loaded {plan.source_type} source for session "
            f"{plan.session_id or 'unknown'}; recovered seed={'yes' if plan.seed_text else 'no'}; "
            f"referenced tools={len(plan.tool_names)}; referenced experiment types={len(plan.experiment_types)}; "
            f"research_mode={plan.research_mode or 'standard'}; "
            f"exploration_profile={plan.exploration_profile or 'none'}; "
            f"experiment_pack={plan.selected_pack_name or 'none'}; "
            f"re-execution possible={plan.reexecution_possible}; "
            f"before/after comparison={plan.before_after_comparison_possible}."
        )
