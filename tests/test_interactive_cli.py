from __future__ import annotations

from pathlib import Path

from app.cli.i18n import localize_error, normalize_language, t
from app.cli.interactive import (
    _SESSION_FLOW_BACK,
    MENU_OPTIONS,
    InteractiveConsole,
    curve_helper_choices,
    curve_summary_lines,
    should_launch_interactive,
    tool_summary_lines,
)
from app.cli.interactive_support import InteractiveRenderer
from app.cli.ui import ASCII_FALLBACK_BANNER, ConsoleTheme, LocalConsoleUI, MenuOption
from app.config import AppConfig
from app.main import build_orchestrator, build_parser
from app.models.report import ResearchReport
from app.models.seed import ResearchSeed
from app.models.session import ResearchSession
from app.types import ConfidenceLevel, make_id


def test_should_launch_interactive_rules() -> None:
    assert should_launch_interactive(
        interactive_flag=True,
        has_idea=False,
        has_replay_source=False,
        stdin_isatty=False,
        stdout_isatty=False,
    )
    assert should_launch_interactive(
        interactive_flag=False,
        has_idea=False,
        has_replay_source=False,
        stdin_isatty=True,
        stdout_isatty=True,
    )
    assert not should_launch_interactive(
        interactive_flag=False,
        has_idea=True,
        has_replay_source=False,
        stdin_isatty=True,
        stdout_isatty=True,
    )


def test_interactive_parser_supports_flag() -> None:
    parser = build_parser()
    args = parser.parse_args(["--interactive", "--lang", "ru"])

    assert args.interactive is True
    assert args.lang == "ru"
    assert args.idea is None


def test_parser_supports_routing_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--show-routing",
            "--model",
            "gpt-test",
            "--math-provider",
            "openai",
            "--math-model",
            "gpt-math",
        ]
    )

    assert args.show_routing is True
    assert args.model == "gpt-test"
    assert args.math_agent_provider == "openai"
    assert args.math_agent_model == "gpt-math"


def test_curve_helper_choices_and_curve_registry_summary() -> None:
    choices = curve_helper_choices()
    ru_choices = curve_helper_choices("ru")
    lines = curve_summary_lines()

    assert choices[0].curve_name is None
    assert choices[1].curve_name == "secp256k1"
    assert choices[-1].curve_name == "x25519"
    assert "АВТО" in ru_choices[0].label
    assert any("secp256k1" in line for line in lines)
    assert any("ed25519" in line for line in lines)


def test_tool_summary_lines_include_builtin_and_plugin_tools() -> None:
    run_root = f".test_runs/{make_id('interactive')}"
    plugin_root = f"{run_root}/plugins"
    plugin_dir = f"{plugin_root}/demo_plugin"
    Path(plugin_dir).mkdir(parents=True, exist_ok=True)
    Path(f"{plugin_dir}/plugin.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from collections.abc import Mapping",
                "from typing import Any",
                "",
                "from app.tools.base import BaseTool",
                "",
                "plugin_name = 'demo_plugin'",
                "plugin_version = '0.1.0'",
                "plugin_description = 'Bounded local test plugin.'",
                "",
                "class DemoTool(BaseTool):",
                "    name = 'plugin_note_normalizer_tool'",
                "    description = 'Demo bounded plugin tool.'",
                "    version = '0.1.0'",
                "    category = 'plugin_research_helper'",
                "    input_schema_hint = 'text string'",
                "    output_schema_hint = 'normalized note summary'",
                "",
                "    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:",
                "        return self.make_result(status='ok', conclusion='ok', result_data={'value': 'ok'})",
                "",
                "def register(registry: Any) -> None:",
                "    registry.register(DemoTool())",
            ]
        ),
        encoding='utf-8',
    )
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
            "plugins": {
                "enabled": True,
                "directory": plugin_root,
                "allow_local_plugins": True,
            },
            "storage": {
                "artifacts_dir": run_root,
                "sessions_dir": f"{run_root}/sessions",
                "traces_dir": f"{run_root}/traces",
                "math_artifacts_dir": f"{run_root}/math",
                "bundles_dir": f"{run_root}/bundles",
            },
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    orchestrator = build_orchestrator(config)
    lines = tool_summary_lines(orchestrator)

    assert MENU_OPTIONS["1"] == "Start Research"
    assert MENU_OPTIONS["2"] == "Evaluation Lab"
    assert MENU_OPTIONS["3"] == "System / Tools"
    assert MENU_OPTIONS["4"] == "Exit"
    assert any("ecc_curve_parameter_tool" in line for line in lines)
    assert any("plugin_note_normalizer_tool" in line for line in lines)


def test_local_console_ui_fallback_banner_keeps_zero_readable() -> None:
    ui = LocalConsoleUI(theme=ConsoleTheme(top_margin=1))

    assert any("ELLIPTICZERO" in line for line in ASCII_FALLBACK_BANNER)
    assert ui.hero_banner()[0] == ""


def test_local_console_ui_menu_navigation_with_arrow_keys() -> None:
    ui = LocalConsoleUI(theme=ConsoleTheme(top_margin=0))
    keys = iter(["down", "enter"])

    selection = ui.choose_menu(
        header_lines=["header"],
        options=[
            MenuOption("FIRST", "first option"),
            MenuOption("SECOND", "second option"),
        ],
        key_provider=lambda: next(keys),
    )

    assert selection == 1


def test_local_console_ui_menu_can_return_language_toggle() -> None:
    ui = LocalConsoleUI(theme=ConsoleTheme(top_margin=0))
    keys = iter(["down", "toggle_language"])

    selection = ui.choose_menu(
        header_lines=["header"],
        options=[
            MenuOption("FIRST", "first option"),
            MenuOption("SECOND", "second option"),
        ],
        key_provider=lambda: next(keys),
    )

    assert selection == "toggle_language"
    assert ui.last_menu_index == 1


def test_curve_helper_escape_returns_to_domain_selection() -> None:
    orchestrator = build_orchestrator(
        AppConfig.model_validate(
            {
                "llm": {
                    "default_provider": "mock",
                    "default_model": "mock-default",
                    "timeout_seconds": 30,
                    "max_request_tokens": 2048,
                    "max_total_requests_per_session": 16,
                },
                "storage": {
                    "artifacts_dir": ".test_runs/interactive_back",
                    "sessions_dir": ".test_runs/interactive_back/sessions",
                    "traces_dir": ".test_runs/interactive_back/traces",
                    "math_artifacts_dir": ".test_runs/interactive_back/math",
                    "bundles_dir": ".test_runs/interactive_back/bundles",
                },
                "log_level": "INFO",
                "max_hypotheses": 2,
                "tool_timeout_seconds": 15,
            }
        )
    )
    console = InteractiveConsole(orchestrator, language="ru")
    console.ui.choose_menu = lambda **kwargs: None

    assert console._select_curve_helper() is _SESSION_FLOW_BACK


def test_local_console_ui_russian_layout_toggle_key_is_supported() -> None:
    ui = LocalConsoleUI(theme=ConsoleTheme(top_margin=0))

    assert ui._normalize_printable_key("l") == "toggle_language"
    assert ui._normalize_printable_key("L") == "toggle_language"
    assert ui._normalize_printable_key("д") == "toggle_language"
    assert ui._normalize_printable_key("Д") == "toggle_language"


def test_local_console_ui_menu_renders_single_active_arrow() -> None:
    ui = LocalConsoleUI(theme=ConsoleTheme(top_margin=0))
    ui.color_enabled = False

    lines = ui.render_menu_screen(
        header_lines=["header"],
        options=[
            MenuOption("FIRST", "first option"),
            MenuOption("SECOND", "second option"),
            MenuOption("THIRD", "third option"),
        ],
        selected_index=1,
    )

    panel_text = "\n".join(lines)
    assert panel_text.count(">") == 1


def test_local_console_ui_menu_truncates_long_labels_without_breaking_panel() -> None:
    ui = LocalConsoleUI(theme=ConsoleTheme(top_margin=0))
    ui.color_enabled = False

    lines = ui.render_menu_screen(
        header_lines=["header"],
        options=[
            MenuOption(
                "contract-repo-scale-lending-protocol",
                "Run the long golden case safely.",
            ),
            MenuOption("RETURN", "Go back."),
        ],
        selected_index=0,
    )
    panel_lines = [line.strip() for line in lines if line.strip().startswith(("+", "|"))]
    panel_widths = {len(line) for line in panel_lines}

    assert len(panel_widths) == 1
    assert any("contract-repo-scale-len..." in line for line in panel_lines)


def test_i18n_session_action_labels_are_available() -> None:
    assert t("en", "menu.export_review_files.label") == "EXPORT REVIEW FILES"
    assert t("en", "menu.evaluation.label") == "EVALUATION LAB"
    assert t("en", "menu.provider_context_preview.label") == "PROVIDER PREVIEW"
    assert t("en", "hint.open_session_actions").startswith("Enter opens session actions")
    assert t("ru", "menu.export_review_files.label") == "ВЫГРУЗИТЬ ОТЧЁТ И SARIF"
    assert t("ru", "block.review_snapshot") == "КРАТКАЯ СВОДКА ПРОВЕРКИ"
    assert t("ru", "prompt.seed_example.ecc").startswith("Пример: secp256k1")


def test_i18n_localizes_common_validation_errors() -> None:
    error = (
        "Research idea is too vague. Include a curve, contract behavior, point behavior, "
        "implementation detail, anomaly, or testable mathematical/security property."
    )

    assert "Идея слишком общая" in localize_error("ru", ValueError(error))


def test_interactive_renderer_localizes_and_wraps_known_mock_summary() -> None:
    renderer = InteractiveRenderer(
        ui=LocalConsoleUI(theme=ConsoleTheme(top_margin=0)),
        translate=lambda key, **kwargs: t("ru", key, **kwargs),
        get_language=lambda: "ru",
        get_provider=lambda: "mock",
    )
    summary = (
        "The session preserved the original seed, produced bounded hypotheses, ran a registry-controlled "
        "local compute job, and recorded preliminary evidence without claiming a validated mathematical or "
        "cryptographic result."
    )

    localized = renderer.localized_summary(summary)
    rows = renderer.wrapped_panel_rows(localized, width=44)

    assert localized.startswith("Сессия сохранила")
    assert len(rows) > 1


def test_interactive_renderer_localizes_generic_mock_summary() -> None:
    renderer = InteractiveRenderer(
        ui=LocalConsoleUI(theme=ConsoleTheme(top_margin=0)),
        translate=lambda key, **kwargs: t("ru", key, **kwargs),
        get_language=lambda: "ru",
        get_provider=lambda: "mock",
    )
    summary = (
        "The session preserved the original seed, ran a neutral bounded local classification pass, "
        "and avoided forcing the idea into a known ECC or smart-contract pattern."
    )

    assert "не стала насильно подгонять" in renderer.localized_summary(summary)


def test_interactive_session_action_exports_review_files(tmp_path: Path) -> None:
    run_root = tmp_path / "interactive_exports"
    orchestrator = build_orchestrator(
        AppConfig.model_validate(
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
                "log_level": "INFO",
                "max_hypotheses": 2,
                "tool_timeout_seconds": 15,
            }
        )
    )
    console = InteractiveConsole(orchestrator, language="ru")
    session_id = "session_interactive_export"
    session = ResearchSession(
        session_id=session_id,
        seed=ResearchSeed(raw_text="Review local report export from the interactive console."),
        report=ResearchReport(
            session_id=session_id,
            seed_text="Review local report export from the interactive console.",
            summary="Interactive export summary.",
            contract_finding_cards=["Potential finding: exported review files need human review."],
            confidence=ConfidenceLevel.MANUAL_REVIEW_REQUIRED,
        ),
        session_file_path=str(run_root / "sessions" / f"{session_id}.json"),
        trace_file_path=str(run_root / "traces" / f"{session_id}.jsonl"),
        bundle_dir=str(run_root / "bundles" / session_id),
    )
    console._pause = lambda: None

    console._export_session_review_files(session=session)

    bundle_dir = Path(session.bundle_dir or "")
    report_path = bundle_dir / "report.md"
    sarif_path = bundle_dir / "review.sarif"

    assert report_path.exists()
    assert sarif_path.exists()
    assert "Interactive export summary." in report_path.read_text(encoding="utf-8")


def test_interactive_saved_source_path_accepts_back() -> None:
    console = object.__new__(InteractiveConsole)
    console._prompt_raw = lambda _label: "/back"
    console.t = lambda key, **_kwargs: key
    console._pause = lambda: None

    assert console._prompt_saved_source_path() is None


def test_i18n_language_normalization_and_lookup() -> None:
    assert normalize_language("ru_RU") == "ru"
    assert normalize_language("en-US") == "en"
    assert t("ru", "menu.exit.label") == "ВЫХОД"
    assert t("en", "menu.start_research.label") == "START RESEARCH"
    assert t("ru", "menu.return.label") == "НАЗАД"
