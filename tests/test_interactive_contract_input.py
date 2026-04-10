from __future__ import annotations

from app.cli.interactive import _PROMPT_TOGGLE_LANGUAGE, _SESSION_FLOW_BACK, InteractiveConsole
from app.config import AppConfig
from app.main import build_orchestrator


def _build_console(run_root: str) -> InteractiveConsole:
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
                "math_artifacts_dir": f"{run_root}/math",
                "bundles_dir": f"{run_root}/bundles",
            },
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )
    return InteractiveConsole(build_orchestrator(config))


def test_interactive_console_normalizes_drag_dropped_paths() -> None:
    console = _build_console(".test_runs/interactive-normalize")

    assert console._normalize_contract_source_path('"C:\\tmp\\Vault.sol"') == "C:\\tmp\\Vault.sol"
    assert console._normalize_contract_source_path("'C:\\tmp\\Vault.sol'") == "C:\\tmp\\Vault.sol"


def test_interactive_console_detects_contract_snippets() -> None:
    console = _build_console(".test_runs/interactive-snippet")

    assert console._looks_like_contract_code("pragma solidity ^0.8.20;")
    assert console._looks_like_contract_code("@external")
    assert not console._looks_like_contract_code("not a contract")


def test_multiline_contract_input_finishes_on_done_marker() -> None:
    console = _build_console(".test_runs/interactive-multiline-finish")
    responses = iter(["pragma solidity ^0.8.20;", "", "contract Vault {}", "/done"])
    console._prompt_raw = lambda label: next(responses)

    result = console._prompt_multiline_contract_code()

    assert result == "pragma solidity ^0.8.20;\n\ncontract Vault {}"


def test_multiline_contract_input_supports_back() -> None:
    console = _build_console(".test_runs/interactive-multiline-back")
    responses = iter(["/back"])
    console._prompt_raw = lambda label: next(responses)

    result = console._prompt_multiline_contract_code()

    assert result is _SESSION_FLOW_BACK


def test_multiline_contract_input_supports_cancel() -> None:
    console = _build_console(".test_runs/interactive-multiline-cancel")
    responses = iter(["/cancel"])
    console._prompt_raw = lambda label: next(responses)

    result = console._prompt_multiline_contract_code()

    assert result is None


def test_prompt_raw_supports_language_toggle_command() -> None:
    console = _build_console(".test_runs/interactive-lang-raw")
    console.ui.prompt_raw = lambda label: "/lang"

    result = console._prompt_raw("seed >")

    assert result is _PROMPT_TOGGLE_LANGUAGE
    assert console.language == "ru"


def test_prompt_with_default_supports_language_toggle_command() -> None:
    console = _build_console(".test_runs/interactive-lang-default")
    console.ui.prompt = lambda label, default=None: "/lang"

    result = console._prompt("inspect only?", default="n")

    assert result is _PROMPT_TOGGLE_LANGUAGE
    assert console.language == "ru"
