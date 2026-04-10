from __future__ import annotations

import subprocess
from pathlib import Path

import app.compute.runners.contract_compile_runner as compile_runner_module
import app.compute.runners.echidna_runner as echidna_runner_module
import app.compute.runners.foundry_runner as foundry_runner_module
import app.compute.runners.slither_runner as slither_runner_module
from app.cli.i18n import t
from app.config import AppConfig
from app.core.doctor import SystemDoctor
from app.main import build_orchestrator, build_parser, render_doctor_report
from app.types import make_id


def _write_demo_plugin(plugin_dir: Path, *, plugin_name: str = "demo_plugin") -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.py").write_text(
        "\n".join(
            [
                f"plugin_name = '{plugin_name}'",
                "plugin_version = '0.1.0'",
                "plugin_description = 'Doctor test plugin.'",
                "",
                "def register(registry):",
                "    return None",
            ]
        ),
        encoding="utf-8",
    )


def _doctor_config(run_root: Path, *, provider: str = "mock") -> AppConfig:
    return AppConfig.model_validate(
        {
            "llm": {
                "default_provider": provider,
                "default_model": f"{provider}-default",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
            "plugins": {
                "enabled": True,
                "directory": "plugins",
                "allow_local_plugins": True,
            },
            "local_research": {
                "smart_contract_compile_enabled": False,
                "slither_enabled": False,
                "echidna_enabled": False,
                "foundry_enabled": False,
            },
            "storage": {
                "artifacts_dir": str(run_root),
                "sessions_dir": str(run_root / "sessions"),
                "traces_dir": str(run_root / "traces"),
                "math_artifacts_dir": str(run_root / "math"),
                "bundles_dir": str(run_root / "bundles"),
            },
            "advanced_math_enabled": False,
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )


def test_system_doctor_reports_ok_for_mock_runtime() -> None:
    run_root = Path(".test_runs") / make_id("doctor")
    config = _doctor_config(run_root)
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    assert report.overall_status == "ok"
    assert len(report.checks) == 11
    assert any(check.title == "Provider Configuration" and check.status == "ok" for check in report.checks)
    assert any(check.title == "Hosted Provider Smoke Path" and check.status == "info" for check in report.checks)
    assert any(check.title == "Tool Registry" and check.status == "ok" for check in report.checks)
    plugin_check = next(check for check in report.checks if check.title == "Plugin Loading")
    storage_check = next(check for check in report.checks if check.title == "Storage and Reproducibility Paths")
    assert any("bounded local safety gate" in item.lower() for item in plugin_check.details)
    assert any("approved export roots" in item.lower() for item in storage_check.details)
    assert any("bundle export copies only session snapshots, traces, and artifact references" in item.lower() for item in storage_check.details)
    assert any(check.title == "Advanced Math / Sage" and check.status == "info" for check in report.checks)
    assert any(check.title == "Smart-Contract Compiler" and check.status == "info" for check in report.checks)
    assert any(check.title == "Smart-Contract Static Analyzer" and check.status == "info" for check in report.checks)
    assert any(check.title == "Smart-Contract Echidna Adapter" and check.status == "info" for check in report.checks)
    assert any(check.title == "Smart-Contract Foundry Adapter" and check.status == "info" for check in report.checks)
    assert any(check.title == "Local Research Adapters" for check in report.checks)


def test_runtime_ru_labels_for_polish_sensitive_sections_are_human_readable() -> None:
    assert t("ru", "report.research_mode") == "Режим исследования"
    assert t("ru", "report.experiment_pack") == "Экспериментальный пакет"
    assert t("ru", "report.recommended_packs") == "Рекомендуемые пакеты"
    assert t("ru", "report.executed_pack_steps") == "Выполненные шаги пакета"
    assert t("ru", "report.contract_inventory") == "Инвентаризация контрактов"
    assert t("ru", "report.validation_posture") == "Позиция валидации"
    assert t("ru", "report.shared_follow_up") == "Общий последующий шаг"
    assert t("ru", "report.ecc_review_queue") == "Очередь ECC-проверки"
    assert t("ru", "report.ecc_exit_criteria") == "Условия завершения ECC"


def test_system_doctor_reports_blocked_unsafe_plugin_paths() -> None:
    run_root = Path(".test_runs") / make_id("doctorunsafeplugin")
    plugin_root = run_root / "plugins"
    _write_demo_plugin(plugin_root / "bad plugin", plugin_name="bad_plugin")
    config = _doctor_config(run_root).model_copy(
        update={
            "plugins": _doctor_config(run_root).plugins.model_copy(
                update={"directory": str(plugin_root)}
            )
        }
    )
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    plugin_check = next(check for check in report.checks if check.title == "Plugin Loading")
    assert plugin_check.status == "warning"
    assert "blocked by bounded local safety checks" in plugin_check.summary
    assert any("blocked plugin paths" in item.lower() for item in plugin_check.details)


def test_system_doctor_reports_error_when_provider_key_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    run_root = Path(".test_runs") / make_id("doctorprovider")
    config = _doctor_config(run_root, provider="openai")
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    provider_check = next(check for check in report.checks if check.title == "Provider Configuration")
    smoke_check = next(check for check in report.checks if check.title == "Hosted Provider Smoke Path")
    assert report.overall_status == "error"
    assert provider_check.status == "error"
    assert "OPENAI_API_KEY" in provider_check.summary
    assert smoke_check.status == "warning"
    assert "OPENAI_API_KEY" in smoke_check.summary


def test_system_doctor_reports_ready_for_hosted_provider_with_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    run_root = Path(".test_runs") / make_id("doctorproviderwired")
    config = _doctor_config(run_root, provider="openai")
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    provider_check = next(check for check in report.checks if check.title == "Provider Configuration")
    smoke_check = next(check for check in report.checks if check.title == "Hosted Provider Smoke Path")
    assert report.overall_status == "ok"
    assert provider_check.status == "ok"
    assert "openai" in provider_check.summary
    assert smoke_check.status == "ok"
    assert "openai" in smoke_check.summary


def test_system_doctor_reports_ready_for_anthropic_with_key(monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    run_root = Path(".test_runs") / make_id("doctoranthropic")
    config = _doctor_config(run_root, provider="anthropic")
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    provider_check = next(check for check in report.checks if check.title == "Provider Configuration")
    smoke_check = next(check for check in report.checks if check.title == "Hosted Provider Smoke Path")
    assert report.overall_status == "ok"
    assert provider_check.status == "ok"
    assert "anthropic" in provider_check.summary
    assert smoke_check.status == "ok"
    assert "anthropic" in smoke_check.summary


def test_system_doctor_reports_ready_for_openrouter_with_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    run_root = Path(".test_runs") / make_id("doctoropenrouter")
    config = _doctor_config(run_root, provider="openrouter")
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    provider_check = next(check for check in report.checks if check.title == "Provider Configuration")
    smoke_check = next(check for check in report.checks if check.title == "Hosted Provider Smoke Path")
    assert report.overall_status == "ok"
    assert provider_check.status == "ok"
    assert "openrouter" in provider_check.summary
    assert smoke_check.status == "ok"
    assert "openrouter" in smoke_check.summary
    assert any("openrouter/auto" in item for item in smoke_check.details)


def test_system_doctor_reports_ready_local_contract_compiler(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        return "solc" if binary == "solc" else None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(compile_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(compile_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(compile_runner_module, "list_managed_solc_versions", lambda _: [])
    monkeypatch.setattr(compile_runner_module.subprocess, "run", fake_run)

    run_root = Path(".test_runs") / make_id("doctorcompiler")
    config = _doctor_config(run_root).model_copy(
        update={
            "local_research": _doctor_config(run_root).local_research.model_copy(
                update={"smart_contract_compile_enabled": True}
            )
        }
    )
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    compiler_check = next(check for check in report.checks if check.title == "Smart-Contract Compiler")
    assert compiler_check.status == "ok"
    assert "solc" in compiler_check.summary


def test_system_doctor_reports_ready_local_slither_adapter(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        if binary == "slither":
            return "slither"
        if binary == "solc":
            return "solc"
        return None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="0.11.5",
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(slither_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(slither_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(slither_runner_module.subprocess, "run", fake_run)

    run_root = Path(".test_runs") / make_id("doctorslither")
    base_config = _doctor_config(run_root)
    config = base_config.model_copy(
        update={
            "local_research": base_config.local_research.model_copy(
                update={"slither_enabled": True}
            )
        }
    )
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    slither_check = next(check for check in report.checks if check.title == "Smart-Contract Static Analyzer")
    assert slither_check.status == "ok"
    assert "Slither" in slither_check.summary


def test_system_doctor_reports_ready_local_foundry_adapter(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        if binary == "forge":
            return "forge"
        if binary == "solc":
            return "solc"
        return None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            if args[0] == "forge":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="forge 1.0.0",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(foundry_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(foundry_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(foundry_runner_module.subprocess, "run", fake_run)

    run_root = Path(".test_runs") / make_id("doctorfoundry")
    base_config = _doctor_config(run_root)
    config = base_config.model_copy(
        update={
            "local_research": base_config.local_research.model_copy(
                update={"foundry_enabled": True}
            )
        }
    )
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    foundry_check = next(check for check in report.checks if check.title == "Smart-Contract Foundry Adapter")
    assert foundry_check.status == "ok"
    assert "Foundry" in foundry_check.summary or "Forge" in foundry_check.summary


def test_system_doctor_reports_ready_local_echidna_adapter(monkeypatch) -> None:
    def fake_resolve_local_binary(binary: str) -> str | None:
        if binary == "echidna":
            return "echidna"
        if binary == "solc":
            return "solc"
        return None

    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            if args[0] == "echidna":
                return subprocess.CompletedProcess(
                    args=args,
                    returncode=0,
                    stdout="echidna 2.2.2",
                    stderr="",
                )
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(echidna_runner_module, "resolve_local_binary", fake_resolve_local_binary)
    monkeypatch.setattr(echidna_runner_module, "resolve_managed_solc_binary", lambda **_: (None, None))
    monkeypatch.setattr(echidna_runner_module.subprocess, "run", fake_run)

    run_root = Path(".test_runs") / make_id("doctorechidna")
    base_config = _doctor_config(run_root)
    config = base_config.model_copy(
        update={
            "local_research": base_config.local_research.model_copy(
                update={"echidna_enabled": True}
            )
        }
    )
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    echidna_check = next(check for check in report.checks if check.title == "Smart-Contract Echidna Adapter")
    assert echidna_check.status == "ok"
    assert "Echidna" in echidna_check.summary


def test_system_doctor_reports_ready_for_managed_contract_compiler(monkeypatch) -> None:
    def fake_run(
        args,
        *,
        capture_output,
        text,
        encoding,
        timeout,
        check,
        input=None,
    ):
        if "--version" in args:
            return subprocess.CompletedProcess(
                args=args,
                returncode=0,
                stdout="solc, the solidity compiler commandline interface\nVersion: 0.8.20",
                stderr="",
            )
        raise AssertionError(f"Unexpected subprocess args: {args}")

    monkeypatch.setattr(compile_runner_module, "resolve_local_binary", lambda _: None)
    monkeypatch.setattr(
        compile_runner_module,
        "resolve_managed_solc_binary",
        lambda **_: ("C:/managed/solc.exe", "0.8.20"),
    )
    monkeypatch.setattr(compile_runner_module, "list_managed_solc_versions", lambda _: ["0.8.20"])
    monkeypatch.setattr(compile_runner_module.subprocess, "run", fake_run)

    run_root = Path(".test_runs") / make_id("doctormanagedcompiler")
    base_config = _doctor_config(run_root)
    config = base_config.model_copy(
        update={
            "local_research": base_config.local_research.model_copy(
                update={"smart_contract_compile_enabled": True}
            )
        }
    )
    orchestrator = build_orchestrator(config)

    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="en",
    ).run()

    compiler_check = next(check for check in report.checks if check.title == "Smart-Contract Compiler")
    assert compiler_check.status == "ok"
    assert any("Installed managed compilers: 0.8.20" in item for item in compiler_check.details)


def test_doctor_parser_and_render_output() -> None:
    parser = build_parser()
    args = parser.parse_args(["--doctor", "--lang", "ru"])

    assert args.doctor is True
    assert args.lang == "ru"

    run_root = Path(".test_runs") / make_id("doctorrender")
    config = _doctor_config(run_root)
    orchestrator = build_orchestrator(config)
    report = SystemDoctor(
        config=config,
        orchestrator=orchestrator,
        language="ru",
    ).run()

    rendered = render_doctor_report(report, language="ru")

    assert "ID отчёта проверки" in rendered
    assert "Проверка готовности" in rendered
    assert "[НОРМА]" in rendered or "[СПРАВКА]" in rendered
