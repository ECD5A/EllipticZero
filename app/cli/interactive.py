from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from app.cli.i18n import is_affirmative, localize_error, normalize_language, t
from app.cli.interactive_support import (
    CurveHelperChoice,
    InteractiveRenderer,
)
from app.cli.interactive_support import (
    curve_helper_choices as build_curve_helper_choices,
)
from app.cli.interactive_support import (
    curve_summary_lines as build_curve_summary_lines,
)
from app.cli.interactive_support import (
    tool_summary_lines as build_tool_summary_lines,
)
from app.cli.text_rendering import (
    render_evaluation_summary,
    render_run_evaluation_summary,
)
from app.cli.ui import CYAN, GRAY, GREEN, RED, WHITE, LocalConsoleUI, MenuOption
from app.core.doctor import SystemDoctor
from app.core.golden_cases import (
    GoldenCaseError,
    list_golden_cases,
    prepare_golden_case_run,
)
from app.core.orchestrator import ResearchOrchestrator
from app.core.provider_privacy import (
    build_provider_context_preview,
    render_provider_context_preview,
)
from app.core.replay_loader import LoadedReplaySource, ReplayLoader
from app.core.replay_planner import ReplayPlanner
from app.core.report_markdown import write_report_markdown_file
from app.core.sarif_export import write_sarif_file
from app.core.seed_parsing import build_smart_contract_seed, infer_contract_root_from_source_path
from app.llm.providers import SUPPORTED_PROVIDER_NAMES
from app.llm.router import build_route_overview, summarize_route_mode
from app.models.replay_request import ReplayRequest
from app.models.replay_result import ReplayResult
from app.models.session import ResearchSession
from app.tools.curve_registry import CURVE_REGISTRY, CurveRegistryEntry
from app.tools.smart_contract_utils import infer_contract_language

MENU_OPTIONS: dict[str, str] = {
    "1": "Start Research",
    "2": "Advanced / Internal",
    "3": "Exit",
}

_SESSION_FLOW_BACK = object()
_PROMPT_TOGGLE_LANGUAGE = object()

def should_launch_interactive(
    *,
    interactive_flag: bool,
    has_idea: bool,
    has_replay_source: bool,
    stdin_isatty: bool,
    stdout_isatty: bool,
) -> bool:
    """Return whether the interactive launcher should start."""

    if interactive_flag:
        return True
    if has_idea or has_replay_source:
        return False
    return stdin_isatty and stdout_isatty

def curve_helper_choices(language: str = "en") -> list[CurveHelperChoice]:
    """Return optional helper selections shown before seed entry."""

    normalized = normalize_language(language)
    return build_curve_helper_choices(
        language=normalized,
        translate=lambda key, **kwargs: t(normalized, key, **kwargs),
    )


def tool_summary_lines(orchestrator: ResearchOrchestrator) -> list[str]:
    """Return tool summary lines for interactive tests and views."""

    return build_tool_summary_lines(orchestrator)


def curve_summary_lines() -> list[str]:
    """Return curve summary lines for interactive tests and views."""

    return build_curve_summary_lines()


class InteractiveConsole:
    """Interactive launcher with arrow-key navigation and a rebuilt local UI."""

    def __init__(self, orchestrator: ResearchOrchestrator, *, language: str = "en") -> None:
        self.orchestrator = orchestrator
        self.loader = ReplayLoader()
        self.planner = ReplayPlanner()
        self.ui = LocalConsoleUI()
        self.language = normalize_language(language)
        self.renderer = InteractiveRenderer(
            ui=self.ui,
            translate=self.t,
            get_language=lambda: self.language,
            get_provider=lambda: self.orchestrator.config.llm.default_provider,
        )

    def run(self) -> int:
        self.ui.play_boot_animation()
        home_start_index = 0
        while True:
            selection = self.ui.choose_menu(
                header_lines=self._home_header_lines(),
                options=self._home_options(),
                start_index=home_start_index,
                hint=self.t("menu.hint") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                home_start_index = self.ui.last_menu_index
                continue
            if isinstance(selection, int):
                home_start_index = selection
            if selection == 0:
                self._run_new_session()
            elif selection == 1:
                self._run_advanced_menu()
            elif selection == 2:
                self.ui.clear()
                for line in self._home_header_lines():
                    print(line)
                print()
                print(self.ui.center_text(self.t("console.closed"), color=GRAY))
                return 0

    def _home_header_lines(self) -> list[str]:
        return self.renderer.home_header_lines()

    def _runtime_status_line(self) -> str:
        return self.renderer.runtime_status_line()

    def _screen_header_lines(self, title: str, subtitle: str) -> list[str]:
        return self.renderer.screen_header_lines(title, subtitle)

    def _print_panel_block(self, title: str, rows: list[str], *, title_color: str = WHITE) -> None:
        self.renderer.print_panel_block(title, rows, title_color=title_color)

    def _print_list_block(self, title: str, items: list[str], *, color: str = CYAN) -> None:
        self.renderer.print_list_block(title, items, color=color)

    def _summary_row(self, label: str, value: str) -> str:
        return self.renderer.summary_row(label, value)

    def _pause(self) -> None:
        self.ui.pause(self.t("prompt.pause"))

    def _pause_or_toggle(self) -> str:
        return self.ui.wait_action(self.t("hint.return_toggle"))

    def _toggle_language(self) -> None:
        self.language = "ru" if self.language == "en" else "en"

    def t(self, key: str, **kwargs: object) -> str:
        return t(self.language, key, **kwargs)

    def _home_options(self) -> list[MenuOption]:
        return [
            MenuOption(self.t("menu.start_research.label"), self.t("menu.start_research.desc")),
            MenuOption(self.t("menu.advanced.label"), self.t("menu.advanced.desc")),
            MenuOption(self.t("menu.exit.label"), self.t("menu.exit.desc")),
        ]

    def _run_new_session(self) -> None:
        while True:
            selected_domain = self._select_research_domain()
            if selected_domain is None:
                return

            helper_curve = self._select_curve_helper() if selected_domain == "ecc_research" else None
            if helper_curve is _SESSION_FLOW_BACK:
                continue
            seed_text = self._build_seed_for_domain(selected_domain)
            if seed_text is _SESSION_FLOW_BACK:
                continue
            if seed_text is None:
                return
            break
        self.ui.clear()
        for line in self._screen_header_lines(
            self.t("screen.new_session.title"),
            self.t("screen.new_session.subtitle"),
        ):
            print(line)
        self._print_panel_block(
            self.t("block.session_workflow"),
            [
                self._summary_row(
                    self.t("workflow.entry_mode.label"),
                    self.t(
                        "workflow.entry_mode.value.smart_contract"
                        if selected_domain == "smart_contract_audit"
                        else "workflow.entry_mode.value.ecc"
                    ),
                ),
                self._summary_row(
                    self.t("workflow.domain.label"),
                    self.t(
                        "workflow.domain.value.smart_contract"
                        if selected_domain == "smart_contract_audit"
                        else "workflow.domain.value.ecc"
                    ),
                ),
                self._summary_row(self.t("workflow.local_execution.label"), self.t("workflow.local_execution.value")),
                self._summary_row(self.t("workflow.run_outputs.label"), self.t("workflow.run_outputs.value")),
            ],
        )

        if helper_curve is not None:
            entry = CURVE_REGISTRY.resolve(helper_curve)
            if entry is not None:
                self._print_curve_helper(entry)

        self._print_panel_block(
            self.t("block.run_stages"),
            [
                self.t("stage.1"),
                self.t("stage.2"),
                self.t("stage.3"),
                self.t("stage.4"),
            ],
            title_color=CYAN,
        )

        try:
            with self._quiet_runtime_logs():
                session = self.orchestrator.run_session(
                    seed_text=seed_text,
                    author=None,
                    domain=selected_domain,
                )
        except ValueError as exc:
            print(
                self.ui.center_text(
                    self.t("message.input_rejected", error=localize_error(self.language, exc)),
                    color=RED,
                    bold=True,
                )
            )
            self._pause()
            return

        self._open_completed_session(session=session, helper_curve=helper_curve)

    def _open_completed_session(self, *, session: ResearchSession, helper_curve: str | None = None) -> None:
        self._print_session_result(session=session, helper_curve=helper_curve)
        while True:
            action = self.ui.wait_action(self.t("hint.open_session_actions"))
            if action == "toggle_language":
                self._toggle_language()
                self._print_session_result(session=session, helper_curve=helper_curve)
                continue
            break
        while True:
            action = self._session_action_menu(session=session, helper_curve=helper_curve)
            if action == "toggle_language":
                self._toggle_language()
                self._print_session_result(session=session, helper_curve=helper_curve)
                continue
            break

    def _session_action_menu(self, *, session: ResearchSession, helper_curve: str | None) -> str:
        start_index = 0
        while True:
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(
                    self.t("screen.session_actions.title"),
                    self.t("screen.session_actions.subtitle"),
                ),
                options=[
                    MenuOption(
                        self.t("menu.export_review_files.label"),
                        self.t("menu.export_review_files.desc"),
                    ),
                    MenuOption(
                        self.t("menu.show_output_paths.label"),
                        self.t("menu.show_output_paths.desc"),
                    ),
                    MenuOption(self.t("menu.return.label"), self.t("menu.return.desc")),
                ],
                start_index=start_index,
                hint=self.t("hint.session_actions") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                return "toggle_language"
            if selection is None or selection == 2:
                return "return"
            if isinstance(selection, int):
                start_index = selection
            if selection == 0:
                self._export_session_review_files(session=session)
            elif selection == 1:
                self._show_session_output_paths(session=session, helper_curve=helper_curve)

    def _export_session_review_files(self, *, session: ResearchSession) -> None:
        if not session.bundle_dir:
            print(self.ui.center_text(self.t("message.export_unavailable"), color=RED, bold=True))
            self._pause()
            return
        bundle_dir = Path(session.bundle_dir)
        loaded_source = self._loaded_source_from_session(session)
        report_path = bundle_dir / "report.md"
        sarif_path = bundle_dir / "review.sarif"
        try:
            write_report_markdown_file(
                loaded_source=loaded_source,
                output_path=report_path,
            )
            _, sarif_result_count = write_sarif_file(
                loaded_source=loaded_source,
                output_path=sarif_path,
            )
        except ValueError as exc:
            print(self.ui.center_text(self.t("message.export_failed", error=str(exc)), color=RED, bold=True))
            self._pause()
            return
        self.ui.clear()
        for line in self._screen_header_lines(
            self.t("screen.session_actions.title"),
            self.t("screen.session_actions.subtitle"),
        ):
            print(line)
        self._print_panel_block(
            self.t("block.export_outputs"),
            [
                self._summary_row(self.t("label.markdown_report"), str(report_path)),
                self._summary_row(self.t("label.sarif_file"), str(sarif_path)),
                self._summary_row(self.t("label.sarif_results"), str(sarif_result_count)),
            ],
            title_color=GREEN,
        )
        print(self.ui.center_text(self.t("message.export_complete"), color=GREEN, bold=True))
        self._pause()

    def _show_session_output_paths(self, *, session: ResearchSession, helper_curve: str | None) -> None:
        self._print_session_result(session=session, helper_curve=helper_curve)
        self._pause()

    def _loaded_source_from_session(self, session: ResearchSession) -> LoadedReplaySource:
        return LoadedReplaySource(
            source_type="bundle" if session.bundle_dir else "session",
            source_path=session.bundle_dir or session.session_file_path or session.session_id,
            session=session,
            bundle_dir=session.bundle_dir,
            recovered_seed=session.seed.raw_text,
            original_session_id=session.original_session_id or session.session_id,
            tool_names=[job.tool_name for job in session.jobs if job.tool_name],
            experiment_types=[
                evidence.experiment_type for evidence in session.evidence if evidence.experiment_type
            ],
            artifact_paths=[
                artifact
                for evidence in session.evidence
                for artifact in evidence.artifact_paths
            ],
            trace_file_path=session.trace_file_path,
            research_mode=session.research_mode.value,
            exploration_profile=(
                session.sandbox_spec.exploration_profile.value
                if session.sandbox_spec is not None
                else None
            ),
            selected_pack_name=session.selected_pack_name,
            notes=["Loaded directly from the completed interactive session."],
        )

    def _run_advanced_menu(self) -> None:
        advanced_start_index = 0
        while True:
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(
                    self.t("screen.advanced.title"),
                    self.t("screen.advanced.subtitle"),
                ),
                options=self._advanced_options(),
                start_index=advanced_start_index,
                hint=self.t("hint.replay") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                advanced_start_index = self.ui.last_menu_index
                continue
            if selection is None or selection == 6:
                return
            if isinstance(selection, int):
                advanced_start_index = selection
            if selection == 0:
                self._run_evaluation_menu()
            elif selection == 1:
                self._run_replay()
            elif selection == 2:
                self._show_routing()
            elif selection == 3:
                self._show_tools()
            elif selection == 4:
                self._show_curves()
            elif selection == 5:
                self._show_system_check()

    def _advanced_options(self) -> list[MenuOption]:
        return [
            MenuOption(self.t("menu.evaluation.label"), self.t("menu.evaluation.desc")),
            MenuOption(self.t("menu.replay.label"), self.t("menu.replay.desc")),
            MenuOption(self.t("menu.routing.label"), self.t("menu.routing.desc")),
            MenuOption(self.t("menu.tools.label"), self.t("menu.tools.desc")),
            MenuOption(self.t("menu.curves.label"), self.t("menu.curves.desc")),
            MenuOption(self.t("menu.doctor.label"), self.t("menu.doctor.desc")),
            MenuOption(self.t("menu.return.label"), self.t("menu.return.desc")),
        ]

    def _run_evaluation_menu(self) -> None:
        evaluation_start_index = 0
        while True:
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(
                    self.t("screen.evaluation.title"),
                    self.t("screen.evaluation.subtitle"),
                ),
                options=self._evaluation_options(),
                start_index=evaluation_start_index,
                hint=self.t("hint.replay") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                evaluation_start_index = self.ui.last_menu_index
                continue
            if selection is None or selection == 5:
                return
            if isinstance(selection, int):
                evaluation_start_index = selection
            if selection == 0:
                self._run_golden_case_menu()
            elif selection == 1:
                self._run_experiment_pack_menu()
            elif selection == 2:
                self._show_evaluation_summary_menu()
            elif selection == 3:
                self._run_baseline_compare()
            elif selection == 4:
                self._show_provider_context_preview()

    def _evaluation_options(self) -> list[MenuOption]:
        return [
            MenuOption(self.t("menu.golden_cases.label"), self.t("menu.golden_cases.desc")),
            MenuOption(self.t("menu.experiment_packs.label"), self.t("menu.experiment_packs.desc")),
            MenuOption(self.t("menu.evaluation_summary.label"), self.t("menu.evaluation_summary.desc")),
            MenuOption(self.t("menu.compare_baseline.label"), self.t("menu.compare_baseline.desc")),
            MenuOption(self.t("menu.provider_context_preview.label"), self.t("menu.provider_context_preview.desc")),
            MenuOption(self.t("menu.return.label"), self.t("menu.return.desc")),
        ]

    def _run_golden_case_menu(self) -> None:
        golden_start_index = 0
        while True:
            cases = list_golden_cases()
            options = [
                MenuOption(
                    str(case.get("case_id", "")),
                    self.t(
                        "menu.golden_case.desc",
                        domain=case.get("domain", "unknown"),
                        pack=case.get("recommended_pack", "none"),
                    ),
                )
                for case in cases
            ]
            options.append(MenuOption(self.t("menu.return.label"), self.t("menu.return.desc")))
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(
                    self.t("screen.golden_cases.title"),
                    self.t("screen.golden_cases.subtitle"),
                ),
                options=options,
                start_index=golden_start_index,
                hint=self.t("hint.replay") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                golden_start_index = self.ui.last_menu_index
                continue
            if selection is None or selection == len(cases):
                return
            if isinstance(selection, int):
                golden_start_index = selection
            case_id = str(cases[int(selection)].get("case_id", "")).strip()
            try:
                golden_run = prepare_golden_case_run(case_id)
            except GoldenCaseError as exc:
                print(self.ui.center_text(self.t("message.golden_case_failed", error=str(exc)), color=RED, bold=True))
                self._pause()
                return
            self._run_prepared_session(
                title=self.t("screen.golden_run.title"),
                subtitle=self.t("screen.golden_run.subtitle"),
                seed_text=golden_run.seed_text,
                domain=golden_run.domain,
                experiment_pack_name=golden_run.experiment_pack_name,
                synthetic_target_name=golden_run.synthetic_target_name,
                context_rows=[
                    self._summary_row(self.t("label.golden_case"), golden_run.case_id),
                    self._summary_row(self.t("workflow.domain.label"), golden_run.domain),
                    self._summary_row(self.t("label.experiment_pack"), golden_run.experiment_pack_name),
                    self._summary_row(self.t("label.input_path"), str(golden_run.input_path)),
                ],
            )

    def _run_experiment_pack_menu(self) -> None:
        pack_start_index = 0
        while True:
            packs = self.orchestrator.experiment_pack_registry.list_packs()
            options = [
                MenuOption(
                    pack.pack_name,
                    self.t(
                        "menu.experiment_pack.desc",
                        targets=", ".join(pack.target_kinds),
                        steps=len(pack.steps),
                    ),
                )
                for pack in packs
            ]
            options.append(MenuOption(self.t("menu.return.label"), self.t("menu.return.desc")))
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(
                    self.t("screen.experiment_packs.title"),
                    self.t("screen.experiment_packs.subtitle"),
                ),
                options=options,
                start_index=pack_start_index,
                hint=self.t("hint.replay") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                pack_start_index = self.ui.last_menu_index
                continue
            if selection is None or selection == len(packs):
                return
            if isinstance(selection, int):
                pack_start_index = selection
            pack = packs[int(selection)]
            selected_domain = self._domain_for_pack(pack.target_kinds)
            helper_curve = self._select_curve_helper() if selected_domain == "ecc_research" else None
            if helper_curve is _SESSION_FLOW_BACK:
                continue
            seed_text = self._build_seed_for_domain(selected_domain)
            if seed_text is _SESSION_FLOW_BACK:
                continue
            if seed_text is None:
                return
            self._run_prepared_session(
                title=self.t("screen.experiment_pack_run.title"),
                subtitle=self.t("screen.experiment_pack_run.subtitle"),
                seed_text=str(seed_text),
                domain=selected_domain,
                helper_curve=helper_curve if isinstance(helper_curve, str) else None,
                experiment_pack_name=pack.pack_name,
                context_rows=[
                    self._summary_row(self.t("label.experiment_pack"), pack.pack_name),
                    self._summary_row(self.t("workflow.domain.label"), selected_domain),
                    self._summary_row(self.t("label.pack_steps"), str(len(pack.steps))),
                ],
            )

    def _show_evaluation_summary_menu(self) -> None:
        summary_start_index = 0
        while True:
            options = [
                MenuOption(self.t("menu.project_summary.label"), self.t("menu.project_summary.desc")),
                MenuOption(self.t("menu.saved_run_summary.label"), self.t("menu.saved_run_summary.desc")),
                MenuOption(self.t("menu.return.label"), self.t("menu.return.desc")),
            ]
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(
                    self.t("screen.evaluation_summary.title"),
                    self.t("screen.evaluation_summary.subtitle"),
                ),
                options=options,
                start_index=summary_start_index,
                hint=self.t("hint.replay") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                summary_start_index = self.ui.last_menu_index
                continue
            if selection is None or selection == 2:
                return
            if isinstance(selection, int):
                summary_start_index = selection
            if selection == 0:
                self._show_project_evaluation_summary()
            elif selection == 1:
                self._show_saved_run_evaluation_summary()

    def _show_project_evaluation_summary(self) -> None:
        while True:
            body = render_evaluation_summary(
                language=self.language,
                golden_cases=list_golden_cases(),
                pack_names=self.orchestrator.experiment_pack_registry.names(),
                provider_names=list(SUPPORTED_PROVIDER_NAMES),
            )
            self._show_text_document(
                title=self.t("screen.project_summary.title"),
                subtitle=self.t("screen.project_summary.subtitle"),
                body=body,
            )
            action = self._pause_or_toggle()
            if action == "toggle_language":
                self._toggle_language()
                continue
            break

    def _show_saved_run_evaluation_summary(self) -> None:
        loaded = self._load_saved_source_interactively(
            title=self.t("screen.saved_run_summary.title"),
            subtitle=self.t("screen.saved_run_summary.subtitle"),
        )
        if loaded is None:
            return
        while True:
            body = render_run_evaluation_summary(
                language=self.language,
                loaded_source=loaded,
            )
            self._show_text_document(
                title=self.t("screen.saved_run_summary.title"),
                subtitle=self.t("screen.saved_run_summary.subtitle"),
                body=body,
            )
            action = self._pause_or_toggle()
            if action == "toggle_language":
                self._toggle_language()
                continue
            break

    def _run_baseline_compare(self) -> None:
        loaded = self._load_saved_source_interactively(
            title=self.t("screen.compare_baseline.title"),
            subtitle=self.t("screen.compare_baseline.subtitle"),
        )
        if loaded is None:
            return
        if loaded.session is None:
            print(self.ui.center_text(self.t("message.compare_baseline_missing"), color=RED, bold=True))
            self._pause()
            return

        selected_domain = self._select_research_domain()
        if selected_domain is None:
            return
        helper_curve = self._select_curve_helper() if selected_domain == "ecc_research" else None
        if helper_curve is _SESSION_FLOW_BACK:
            return
        seed_text = self._build_seed_for_domain(selected_domain)
        if seed_text is _SESSION_FLOW_BACK or seed_text is None:
            return
        self._run_prepared_session(
            title=self.t("screen.compare_run.title"),
            subtitle=self.t("screen.compare_run.subtitle"),
            seed_text=str(seed_text),
            domain=selected_domain,
            helper_curve=helper_curve if isinstance(helper_curve, str) else None,
            comparison_baseline=loaded.session,
            comparison_baseline_source_type=loaded.source_type,
            comparison_baseline_source_path=loaded.source_path,
            context_rows=[
                self._summary_row(self.t("label.baseline_source"), loaded.source_type),
                self._summary_row(self.t("label.baseline_path"), loaded.source_path),
                self._summary_row(self.t("workflow.domain.label"), selected_domain),
            ],
        )

    def _show_provider_context_preview(self) -> None:
        selected_domain = self._select_research_domain()
        if selected_domain is None:
            return
        seed_text = self._build_seed_for_domain(selected_domain)
        if seed_text is _SESSION_FLOW_BACK or seed_text is None:
            return
        while True:
            preview = build_provider_context_preview(
                config=self.orchestrator.config,
                seed_text=str(seed_text),
            )
            body = render_provider_context_preview(
                preview=preview,
                language=self.language,
            )
            self._show_text_document(
                title=self.t("screen.provider_context_preview.title"),
                subtitle=self.t("screen.provider_context_preview.subtitle"),
                body=body,
            )
            action = self._pause_or_toggle()
            if action == "toggle_language":
                self._toggle_language()
                continue
            break

    def _load_saved_source_interactively(self, *, title: str, subtitle: str) -> LoadedReplaySource | None:
        source_type = self._select_saved_source_type(title=title, subtitle=subtitle)
        if source_type is None:
            return None
        source_path = self._prompt_saved_source_path()
        if source_path is None:
            return None
        request = ReplayRequest(
            source_type=source_type,
            source_path=source_path,
            dry_run=True,
            reexecute=False,
            preserve_original_seed=True,
        )
        try:
            return self.loader.load(request)
        except ValueError as exc:
            print(self.ui.center_text(self.t("message.replay_rejected", error=str(exc)), color=RED, bold=True))
            self._pause()
            return None

    def _select_saved_source_type(self, *, title: str, subtitle: str) -> str | None:
        source_start_index = 0
        while True:
            options = [
                MenuOption(self.t("replay.option.session.label"), self.t("replay.option.session.desc")),
                MenuOption(self.t("replay.option.manifest.label"), self.t("replay.option.manifest.desc")),
                MenuOption(self.t("replay.option.bundle.label"), self.t("replay.option.bundle.desc")),
                MenuOption(self.t("replay.option.return.label"), self.t("replay.option.return.desc")),
            ]
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(title, subtitle),
                options=options,
                start_index=source_start_index,
                hint=self.t("hint.replay") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                source_start_index = self.ui.last_menu_index
                continue
            if selection is None or selection == 3:
                return None
            if isinstance(selection, int):
                source_start_index = selection
            return {0: "session", 1: "manifest", 2: "bundle"}[int(selection)]

    def _prompt_saved_source_path(self) -> str | None:
        while True:
            source_path = self._prompt_raw(self.t("prompt.path"))
            if source_path is _PROMPT_TOGGLE_LANGUAGE:
                continue
            source_path = str(source_path).strip()
            if source_path.lower() in {"/back", "/cancel"}:
                return None
            if source_path:
                return source_path
            print(self.ui.center_text(self.t("message.replay_path_required"), color=RED, bold=True))
            self._pause()

    def _run_prepared_session(
        self,
        *,
        title: str,
        subtitle: str,
        seed_text: str,
        domain: str,
        helper_curve: str | None = None,
        experiment_pack_name: str | None = None,
        synthetic_target_name: str | None = None,
        comparison_baseline: ResearchSession | None = None,
        comparison_baseline_source_type: str | None = None,
        comparison_baseline_source_path: str | None = None,
        context_rows: list[str] | None = None,
    ) -> None:
        self.ui.clear()
        for line in self._screen_header_lines(title, subtitle):
            print(line)
        if context_rows:
            self._print_panel_block(self.t("block.prepared_run"), context_rows, title_color=CYAN)
        try:
            with self._quiet_runtime_logs():
                session = self.orchestrator.run_session(
                    seed_text=seed_text,
                    author=None,
                    domain=domain,
                    experiment_pack_name=experiment_pack_name,
                    synthetic_target_name=synthetic_target_name,
                    comparison_baseline=comparison_baseline,
                    comparison_baseline_source_type=comparison_baseline_source_type,
                    comparison_baseline_source_path=comparison_baseline_source_path,
                )
        except ValueError as exc:
            print(
                self.ui.center_text(
                    self.t("message.input_rejected", error=localize_error(self.language, exc)),
                    color=RED,
                    bold=True,
                )
            )
            self._pause()
            return
        self._open_completed_session(session=session, helper_curve=helper_curve)

    def _show_text_document(self, *, title: str, subtitle: str, body: str) -> None:
        self.ui.clear()
        for line in self._screen_header_lines(title, subtitle):
            print(line)
        for index, section in enumerate(self._split_text_sections(body)):
            if index == 0 and len(section) == 1:
                continue
            section_title = section[0].rstrip(":") if section else self.t("block.summary")
            rows: list[str] = []
            for raw_line in (section[1:] if len(section) > 1 else section):
                rows.extend(self.renderer.wrapped_panel_rows(raw_line, width=76))
            self._print_panel_block(section_title, rows or [self.t("value.none")], title_color=CYAN)

    def _split_text_sections(self, body: str) -> list[list[str]]:
        sections: list[list[str]] = []
        current: list[str] = []
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                if current:
                    sections.append(current)
                    current = []
                continue
            current.append(stripped)
        if current:
            sections.append(current)
        return sections

    def _domain_for_pack(self, target_kinds: list[str]) -> str:
        return "smart_contract_audit" if set(target_kinds) == {"smart_contract"} else "ecc_research"

    def _run_replay(self) -> None:
        replay_start_index = 0
        while True:
            replay_options = [
                MenuOption(self.t("replay.option.session.label"), self.t("replay.option.session.desc")),
                MenuOption(self.t("replay.option.manifest.label"), self.t("replay.option.manifest.desc")),
                MenuOption(self.t("replay.option.bundle.label"), self.t("replay.option.bundle.desc")),
                MenuOption(self.t("replay.option.return.label"), self.t("replay.option.return.desc")),
            ]
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(
                    self.t("screen.replay.title"),
                    self.t("screen.replay.subtitle"),
                ),
                options=replay_options,
                start_index=replay_start_index,
                hint=self.t("hint.replay") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                replay_start_index = self.ui.last_menu_index
                continue
            break
        if selection is None or selection == 3:
            return

        source_type = {0: "session", 1: "manifest", 2: "bundle"}[selection]
        source_path = self._prompt_saved_source_path()
        if source_path is None:
            return

        while True:
            dry_run_value = self._prompt(self.t("prompt.dry_run"), default="n")
            if dry_run_value is _PROMPT_TOGGLE_LANGUAGE:
                continue
            dry_run = is_affirmative(self.language, str(dry_run_value))
            break
        request = ReplayRequest(
            source_type=source_type,
            source_path=source_path,
            dry_run=dry_run,
            reexecute=not dry_run,
            preserve_original_seed=True,
        )
        try:
            loaded = self.loader.load(request)
            plan = self.planner.build_plan(
                loaded_source=loaded,
                available_tools=self.orchestrator.executor.registry.names(),
                preserve_original_seed=request.preserve_original_seed,
            )
            with self._quiet_runtime_logs():
                result = self.planner.execute(
                    request=request,
                    plan=plan,
                    orchestrator=self.orchestrator,
                    author=None,
                )
        except ValueError as exc:
            print(self.ui.center_text(self.t("message.replay_rejected", error=str(exc)), color=RED, bold=True))
            self._pause()
            return

        self._print_replay_result(result)
        while True:
            action = self._pause_or_toggle()
            if action == "toggle_language":
                self._toggle_language()
                self._print_replay_result(result)
                continue
            break

    def _show_tools(self) -> None:
        while True:
            self.ui.clear()
            metadata = self.orchestrator.executor.registry.list_metadata()
            for line in self._screen_header_lines(
                self.t("screen.tools.title"),
                self.t("screen.tools.subtitle"),
            ):
                print(line)
            deterministic_count = sum(1 for item in metadata if item.deterministic)
            built_in_count = sum(1 for item in metadata if item.source_type == "built_in")
            plugin_count = sum(1 for item in metadata if item.source_type == "plugin")
            self._print_panel_block(
                self.t("block.tool_summary"),
                [
                    self._summary_row(self.t("label.total_tools"), str(len(metadata))),
                    self._summary_row(self.t("label.built_in_tools"), str(built_in_count)),
                    self._summary_row(self.t("label.plugin_tools"), str(plugin_count)),
                    self._summary_row(self.t("label.deterministic_tools"), str(deterministic_count)),
                ],
            )
            rows: list[list[str]] = []
            for item in metadata:
                source = item.source_type
                if item.plugin_name:
                    source = f"{source}:{item.plugin_name}"
                rows.append(
                    [
                        item.name,
                        item.category,
                        "det" if item.deterministic else "bound",
                        source,
                        item.description,
                    ]
                )
            for line in self.ui.table(
                [
                    self.t("table.name"),
                    self.t("table.category"),
                    self.t("table.mode"),
                    self.t("table.source"),
                    self.t("table.description"),
                ],
                rows,
                [24, 12, 6, 18, 26],
            ):
                print(line)
            action = self._pause_or_toggle()
            if action == "toggle_language":
                self._toggle_language()
                continue
            break

    def _show_routing(self) -> None:
        while True:
            self.ui.clear()
            for line in self._screen_header_lines(
                self.t("screen.routing.title"),
                self.t("screen.routing.subtitle"),
            ):
                print(line)
            route_rows = build_route_overview(self.orchestrator.config)
            self._print_panel_block(
                self.t("block.routing_summary"),
                [
                    self._summary_row(
                        self.t("label.shared_provider"),
                        self.orchestrator.config.llm.default_provider,
                    ),
                    self._summary_row(
                        self.t("label.shared_model"),
                        self.orchestrator.config.llm.default_model,
                    ),
                    self._summary_row(
                        self.t("label.routing_mode"),
                        self.t(
                            "value.shared_default"
                            if summarize_route_mode(self.orchestrator.config) == "shared-default"
                            else "value.mixed_overrides"
                        ),
                    ),
                    self._summary_row(
                        self.t("label.fallback_provider"),
                        self.orchestrator.config.llm.fallback_provider or self.t("value.none"),
                    ),
                ],
                title_color=CYAN,
            )
            rows = [
                [
                    item.agent_name,
                    item.provider,
                    item.model,
                    self.t("value.shared") if item.mode == "shared" else self.t("value.override"),
                ]
                for item in route_rows
            ]
            for line in self.ui.table(
                [
                    self.t("table.agent"),
                    self.t("table.provider"),
                    self.t("table.model"),
                    self.t("table.routing_mode"),
                ],
                rows,
                [18, 12, 24, 14],
            ):
                print(line)
            action = self._pause_or_toggle()
            if action == "toggle_language":
                self._toggle_language()
                continue
            break

    def _show_curves(self) -> None:
        while True:
            self.ui.clear()
            entries = CURVE_REGISTRY.list_entries()
            alias_count = sum(len(entry.aliases) for entry in entries)
            on_curve_supported = sum(1 for entry in entries if entry.supports_on_curve_check)
            family_count = len({entry.family for entry in entries})
            for line in self._screen_header_lines(
                self.t("screen.curves.title"),
                self.t("screen.curves.subtitle"),
            ):
                print(line)
            self._print_panel_block(
                self.t("block.curve_summary"),
                [
                    self._summary_row(self.t("label.known_curves"), str(len(entries))),
                    self._summary_row(self.t("label.registered_aliases"), str(alias_count)),
                    self._summary_row(self.t("label.curve_families"), str(family_count)),
                    self._summary_row(self.t("label.on_curve_support"), str(on_curve_supported)),
                ],
            )
            rows: list[list[str]] = []
            for entry in entries:
                rows.append(
                    [
                        entry.canonical_name,
                        entry.family,
                        entry.field_type,
                        ", ".join(entry.usage_category) or "general",
                        entry.short_description,
                    ]
                )
            for line in self.ui.table(
                [
                    self.t("table.curve"),
                    self.t("table.family"),
                    self.t("table.field"),
                    self.t("table.usage"),
                    self.t("table.description"),
                ],
                rows,
                [12, 10, 12, 22, 24],
            ):
                print(line)
            action = self._pause_or_toggle()
            if action == "toggle_language":
                self._toggle_language()
                continue
            break

    def _show_system_check(self) -> None:
        while True:
            report = SystemDoctor(
                config=self.orchestrator.config,
                orchestrator=self.orchestrator,
                language=self.language,
            ).run()
            loaded_plugins = sum(1 for item in self.orchestrator.plugin_metadata if item.load_status == "loaded")
            failed_plugins = sum(1 for item in self.orchestrator.plugin_metadata if item.load_status != "loaded")
            self.ui.clear()
            for line in self._screen_header_lines(
                self.t("screen.doctor.title"),
                self.t("screen.doctor.subtitle"),
            ):
                print(line)
            self._print_panel_block(
                self.t("block.doctor_summary"),
                [
                    self._summary_row(
                        self.t("label.overall_status"),
                        self.t(f"doctor.status.{report.overall_status}"),
                    ),
                    self._summary_row(
                        self.t("label.active_provider"),
                        self.orchestrator.config.llm.default_provider,
                    ),
                    self._summary_row(
                        self.t("label.registry_tools"),
                        str(len(self.orchestrator.executor.registry.names())),
                    ),
                    self._summary_row(
                        self.t("label.loaded_plugins"),
                        str(loaded_plugins),
                    ),
                    self._summary_row(
                        self.t("label.failed_plugins"),
                        str(failed_plugins),
                    ),
                ],
                title_color=self._doctor_status_color(report.overall_status),
            )
            print(self.ui.center_text(report.summary, color=WHITE))
            for check in report.checks:
                self._print_panel_block(
                    f"[{self.t(f'doctor.status.{check.status}').upper()}] {check.title}",
                    [check.summary, *[f"- {item}" for item in check.details]],
                    title_color=self._doctor_status_color(check.status),
                )
            action = self._pause_or_toggle()
            if action == "toggle_language":
                self._toggle_language()
                continue
            break

    def _select_curve_helper(self) -> str | object | None:
        helper_start_index = 0
        while True:
            choices = curve_helper_choices(self.language)
            options = [MenuOption(choice.label, choice.description) for choice in choices]
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(
                    self.t("screen.curve_helper.title"),
                    self.t("screen.curve_helper.subtitle"),
                ),
                options=options,
                start_index=helper_start_index,
                hint=self.t("hint.curve_helper") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                helper_start_index = self.ui.last_menu_index
                continue
            if selection is None:
                return _SESSION_FLOW_BACK
            return choices[selection].curve_name

    def _select_research_domain(self) -> str | None:
        domain_options = [
            MenuOption(self.t("domain.ecc.label"), self.t("domain.ecc.desc")),
            MenuOption(self.t("domain.smart_contract.label"), self.t("domain.smart_contract.desc")),
        ]
        start_index = 0
        while True:
            selection = self.ui.choose_menu(
                header_lines=self._screen_header_lines(
                    self.t("screen.domain.title"),
                    self.t("screen.domain.subtitle"),
                ),
                options=domain_options,
                start_index=start_index,
                hint=self.t("hint.domain_select") + " " + self.t("hint.toggle_language"),
            )
            if selection == "toggle_language":
                self._toggle_language()
                continue
            if selection is None:
                return None
            return "smart_contract_audit" if selection == 1 else "ecc_research"

    def _build_seed_for_domain(self, selected_domain: str) -> str | object | None:
        if selected_domain == "smart_contract_audit":
            return self._collect_smart_contract_seed()

        return self._collect_ecc_seed()

    def _collect_ecc_seed(self) -> str | None:
        while True:
            self.ui.clear()
            for line in self._screen_header_lines(
                self.t("screen.seed_input.title"),
                self.t("screen.seed_input.subtitle"),
            ):
                print(line)
            print(self.ui.center_text(self.t("prompt.seed_hint"), color=GRAY, dim=True))
            print(self.ui.center_text(self.t("prompt.seed_example.ecc"), color=GRAY, dim=True))
            seed_text = self._prompt_raw(self.t("prompt.seed"))
            if seed_text is _PROMPT_TOGGLE_LANGUAGE:
                continue
            seed_text = str(seed_text).strip()
            if seed_text:
                return seed_text
            print(self.ui.center_text(self.t("message.seed_required"), color=RED, bold=True))
            self._pause()

    def _collect_smart_contract_seed(self) -> str | object | None:
        source = self._collect_contract_source()
        if source is _SESSION_FLOW_BACK:
            return _SESSION_FLOW_BACK
        if source is None:
            return None
        contract_code, source_label = source

        language = infer_contract_language(
            source_label=source_label,
            hinted_language=None,
            contract_code=contract_code,
        )

        while True:
            print(self.ui.center_text(self.t("prompt.contract.idea_hint"), color=GRAY, dim=True))
            idea_text = self._prompt_raw(self.t("prompt.contract.idea"))
            if idea_text is _PROMPT_TOGGLE_LANGUAGE:
                continue
            idea_text = str(idea_text).strip()
            if idea_text:
                break
            print(self.ui.center_text(self.t("message.seed_required"), color=RED, bold=True))

        try:
            return build_smart_contract_seed(
                idea_text=idea_text,
                contract_code=contract_code,
                language=language,
                source_label=source_label,
                contract_root=infer_contract_root_from_source_path(source_label),
            )
        except ValueError as exc:
            print(
                self.ui.center_text(
                    self.t("message.input_rejected", error=localize_error(self.language, exc)),
                    color=RED,
                    bold=True,
                )
            )
            self._pause()
            return None

    def _collect_contract_source(self) -> tuple[str, str | None] | object | None:
        while True:
            self.ui.clear()
            for line in self._screen_header_lines(
                self.t("screen.contract_source.title"),
                self.t("screen.contract_source.subtitle"),
            ):
                print(line)
            print(self.ui.center_text(self.t("prompt.contract.input_hint"), color=GRAY, dim=True))
            source_input = self._prompt_centered_raw(self.t("prompt.contract.file"))
            if source_input is _PROMPT_TOGGLE_LANGUAGE:
                continue
            source_input = str(source_input).strip()
            if source_input.lower() == "/back":
                return _SESSION_FLOW_BACK
            if source_input.lower() == "/cancel":
                return None

            normalized_path = self._normalize_contract_source_path(source_input)
            if normalized_path:
                contract_path = Path(normalized_path)
                if not contract_path.exists() or not contract_path.is_file():
                    print(
                        self.ui.center_text(
                            self.t("message.contract_path_invalid", path=normalized_path),
                            color=RED,
                            bold=True,
                        )
                    )
                    continue
                try:
                    contract_code = contract_path.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    contract_code = contract_path.read_text(encoding="utf-8-sig")
                return contract_code, str(contract_path)

            if not source_input:
                contract_code = self._prompt_multiline_contract_code()
            elif self._looks_like_contract_code(source_input):
                contract_code = self._prompt_multiline_contract_code(initial_line=source_input)
            else:
                print(self.ui.center_text(self.t("message.contract_source_invalid"), color=RED, bold=True))
                continue

            if contract_code is _SESSION_FLOW_BACK:
                continue
            if contract_code is None:
                return None
            if not contract_code.strip():
                print(self.ui.center_text(self.t("message.contract_code_required"), color=RED, bold=True))
                continue
            return contract_code, None

    def _prompt_multiline_contract_code(self, initial_line: str | None = None) -> str | object | None:
        print(self.ui.center_text(self.t("prompt.contract.paste_hint"), color=GRAY, dim=True))
        lines: list[str] = [initial_line] if initial_line else []
        while True:
            line = self._prompt_raw("")
            if line is _PROMPT_TOGGLE_LANGUAGE:
                print(self.ui.center_text(self.t("prompt.contract.paste_hint"), color=GRAY, dim=True))
                continue
            line = str(line)
            lowered = line.strip().lower()
            if lowered == "/back":
                return _SESSION_FLOW_BACK
            if lowered == "/cancel":
                return None
            if lowered in {"/done", "/end"}:
                if lines:
                    break
                return _SESSION_FLOW_BACK
            lines.append(line)
        return "\n".join(lines).strip()

    def _normalize_contract_source_path(self, value: str) -> str | None:
        stripped = value.strip()
        if not stripped:
            return None
        if stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
            stripped = stripped[1:-1].strip()
        return stripped or None

    def _looks_like_contract_code(self, value: str) -> bool:
        lowered = value.lower()
        return any(
            token in lowered
            for token in (
                "pragma solidity",
                "contract ",
                "interface ",
                "library ",
                "function ",
                "modifier ",
                "@external",
                "@internal",
                "@payable",
                "# @version",
                "def __init__",
                "def ",
                "delegatecall",
                "tx.origin",
                "selfdestruct",
            )
        )

    def _print_curve_helper(self, entry: CurveRegistryEntry) -> None:
        self.renderer.print_curve_helper(entry)

    def _print_session_result(self, *, session: ResearchSession, helper_curve: str | None) -> None:
        self.renderer.print_session_result(session=session, helper_curve=helper_curve)

    def _print_replay_result(self, result: ReplayResult) -> None:
        self.renderer.print_replay_result(result)

    def _loaded_plugin_count(self) -> int:
        return sum(1 for item in self.orchestrator.plugin_metadata if item.load_status == "loaded")

    def _doctor_status_color(self, status: str) -> str:
        return self.renderer.doctor_status_color(status)

    def _prompt(self, label: str, *, default: str | None = None) -> str | object:
        value = self.ui.prompt(label, default=default)
        if value.strip().lower() in {"/lang", "/language"}:
            self._toggle_language()
            return _PROMPT_TOGGLE_LANGUAGE
        if not value and default is not None:
            return default
        return value

    def _prompt_raw(self, label: str) -> str | object:
        value = self.ui.prompt_raw(label)
        if value.strip().lower() in {"/lang", "/language"}:
            self._toggle_language()
            return _PROMPT_TOGGLE_LANGUAGE
        return value

    def _prompt_centered_raw(self, label: str) -> str | object:
        value = self.ui.prompt_centered_raw(label)
        if value.strip().lower() in {"/lang", "/language"}:
            self._toggle_language()
            return _PROMPT_TOGGLE_LANGUAGE
        return value

    @contextlib.contextmanager
    def _quiet_runtime_logs(self):
        root_logger = logging.getLogger()
        previous_level = root_logger.level
        root_logger.setLevel(logging.WARNING)
        try:
            yield
        finally:
            root_logger.setLevel(previous_level)
