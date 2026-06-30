from __future__ import annotations

import json
from pathlib import Path

from app.config import AppConfig
from app.core.benchmark_scorecard import (
    render_benchmark_scorecard,
    run_benchmark_scorecard,
)
from app.main import build_orchestrator, build_parser


def test_benchmark_scorecard_runs_detection_and_control_cases(tmp_path: Path) -> None:
    run_root = tmp_path / "benchmark"
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "max_total_requests_per_session": 16,
            },
            "storage": {
                "artifacts_dir": str(run_root),
                "sessions_dir": str(run_root / "sessions"),
                "traces_dir": str(run_root / "traces"),
                "math_artifacts_dir": str(run_root / "math"),
                "bundles_dir": str(run_root / "bundles"),
            },
            "local_research": {
                "slither_enabled": False,
                "foundry_enabled": False,
                "echidna_enabled": False,
            },
            "log_level": "WARNING",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )

    scorecard = run_benchmark_scorecard(
        orchestrator=build_orchestrator(config),
        case_ids=[
            "contract-reentrancy-review-lane",
            "contract-safe-ledger-control",
        ],
    )

    assert scorecard.passed is True
    assert scorecard.score_percent == 100.0
    assert len(scorecard.case_results) == 2
    assert any(
        "reentrancy_review_required" in result.observed_issue_families
        for result in scorecard.case_results
    )
    control = next(
        result
        for result in scorecard.case_results
        if result.case_id == "contract-safe-ledger-control"
    )
    assert control.observed_issue_families == []

    payload = json.loads(render_benchmark_scorecard(scorecard, output_format="json"))
    assert payload["passed"] is True
    assert "[PASS] contract-safe-ledger-control" in render_benchmark_scorecard(scorecard)


def test_benchmark_scorecard_cli_arguments_are_exposed() -> None:
    args = build_parser().parse_args(
        ["--benchmark-scorecard", "--benchmark-scorecard-format", "json"]
    )

    assert args.benchmark_scorecard is True
    assert args.benchmark_scorecard_format == "json"
