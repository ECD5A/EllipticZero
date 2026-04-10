from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.core.replay_loader import ReplayLoader
from app.core.replay_planner import ReplayPlanner
from app.main import build_orchestrator
from app.models.replay_request import ReplayRequest
from app.models.replay_result import ReplayResult
from app.types import make_id


def _make_config(run_root: Path) -> AppConfig:
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
            "advanced_math_enabled": True,
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )


def _make_source_session() -> tuple[AppConfig, object]:
    run_root = Path(".test_runs") / make_id("replay")
    config = _make_config(run_root)
    orchestrator = build_orchestrator(config)
    session = orchestrator.run_session(
        seed_text="Inspect whether secp256k1 metadata labels remain consistent across local reasoning and tool output.",
        author="replay-test",
    )
    return config, session


def test_replay_models_basic_behavior() -> None:
    request = ReplayRequest(
        source_type="session",
        source_path="artifacts/sessions/example.json",
        dry_run=True,
        reexecute=False,
    )
    result = ReplayResult(
        source_type="session",
        source_path="artifacts/sessions/example.json",
        session_id="session_123",
        dry_run=True,
        reexecuted=False,
        success=True,
        summary="Replay dry-run completed.",
    )

    assert request.source_type == "session"
    assert request.dry_run is True
    assert request.reexecute is False
    assert result.success is True
    assert result.summary == "Replay dry-run completed."


def test_replay_loader_supports_session_manifest_and_bundle() -> None:
    _, session = _make_source_session()
    assert session.session_file_path is not None
    assert session.manifest_file_path is not None
    assert session.bundle_dir is not None

    loader = ReplayLoader()
    loaded_session = loader.load(
        ReplayRequest(source_type="session", source_path=session.session_file_path, dry_run=True, reexecute=False)
    )
    loaded_manifest = loader.load(
        ReplayRequest(source_type="manifest", source_path=session.manifest_file_path, dry_run=True, reexecute=False)
    )
    loaded_bundle = loader.load(
        ReplayRequest(source_type="bundle", source_path=session.bundle_dir, dry_run=True, reexecute=False)
    )

    assert loaded_session.recovered_seed == session.seed.raw_text
    assert loaded_manifest.tool_names
    assert loaded_bundle.bundle_dir == session.bundle_dir


def test_replay_dry_run_summary() -> None:
    config, session = _make_source_session()
    loader = ReplayLoader()
    planner = ReplayPlanner()
    loaded = loader.load(
        ReplayRequest(source_type="bundle", source_path=session.bundle_dir, dry_run=True, reexecute=False)
    )
    plan = planner.build_plan(
        loaded_source=loaded,
        available_tools=build_orchestrator(config).executor.registry.names(),
        preserve_original_seed=True,
    )
    result = planner.dry_run_result(
        request=ReplayRequest(source_type="bundle", source_path=session.bundle_dir, dry_run=True, reexecute=False),
        plan=plan,
    )

    assert result.dry_run is True
    assert result.success is True
    assert "re-execution possible=True" in result.summary
    assert "before/after comparison=True" in result.summary
    assert any("tools_referenced=" in note for note in result.notes)


def test_replay_controlled_reexecution_path() -> None:
    config, session = _make_source_session()
    loader = ReplayLoader()
    planner = ReplayPlanner()
    orchestrator = build_orchestrator(config)
    request = ReplayRequest(
        source_type="session",
        source_path=session.session_file_path,
        dry_run=False,
        reexecute=True,
    )

    loaded = loader.load(request)
    plan = planner.build_plan(
        loaded_source=loaded,
        available_tools=orchestrator.executor.registry.names(),
        preserve_original_seed=True,
    )
    result = planner.execute(
        request=request,
        plan=plan,
        orchestrator=orchestrator,
        author="replay-runner",
    )

    assert result.success is True
    assert result.reexecuted is True
    assert result.generated_session_path is not None
    generated_payload = json.loads(Path(result.generated_session_path).read_text(encoding="utf-8"))
    assert generated_payload["is_replay"] is True
    assert generated_payload["replay_source_type"] == "session"
    assert generated_payload["replay_mode"] == "reexecute"
    assert generated_payload["original_session_id"] == session.session_id
    assert generated_payload["comparison_baseline_session_id"] == session.session_id
    assert generated_payload["report"]["before_after_comparison"]
    assert generated_payload["comparative_report"]["cross_session_comparison"] is not None
    assert any("before/after comparison" in note.lower() for note in result.notes)


def test_replay_loader_malformed_input_handling() -> None:
    run_root = Path(".test_runs") / make_id("replaybad")
    bad_manifest = run_root / "bad_manifest.json"
    bad_manifest.parent.mkdir(parents=True, exist_ok=True)
    bad_manifest.write_text('{"session_id": 1, "bad": true}', encoding="utf-8")

    loader = ReplayLoader()
    try:
        loader.load(
            ReplayRequest(
                source_type="manifest",
                source_path=str(bad_manifest),
                dry_run=True,
                reexecute=False,
            )
        )
    except ValueError as exc:
        assert "malformed" in str(exc).lower() or "not found" in str(exc).lower()
    else:
        raise AssertionError("Malformed replay input should raise ValueError.")
