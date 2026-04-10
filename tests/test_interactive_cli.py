from __future__ import annotations

from pathlib import Path

from app.cli.i18n import normalize_language, t
from app.cli.interactive import (
    _SESSION_FLOW_BACK,
    MENU_OPTIONS,
    InteractiveConsole,
    curve_helper_choices,
    curve_summary_lines,
    should_launch_interactive,
    tool_summary_lines,
)
from app.cli.ui import ASCII_FALLBACK_BANNER, ConsoleTheme, LocalConsoleUI, MenuOption
from app.config import AppConfig
from app.main import build_orchestrator, build_parser
from app.types import make_id


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
    assert MENU_OPTIONS["2"] == "Advanced / Internal"
    assert MENU_OPTIONS["3"] == "Exit"
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


def test_i18n_language_normalization_and_lookup() -> None:
    assert normalize_language("ru_RU") == "ru"
    assert normalize_language("en-US") == "en"
    assert t("ru", "menu.exit.label") == "ВЫХОД"
    assert t("en", "menu.start_research.label") == "START RESEARCH"
    assert t("ru", "menu.return.label") == "НАЗАД"
