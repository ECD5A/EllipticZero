from __future__ import annotations

from pathlib import Path

import pytest

from app.config import AppConfig
from app.core.filtering import validate_seed_text
from app.core.planning_helpers import determine_target_kind
from app.core.seed_parsing import build_smart_contract_seed
from app.main import build_orchestrator


def test_validate_seed_text_accepts_russian_technical_ecc_seed() -> None:
    seed = "проверить формат сжатой точки secp256k1 и координату x вне поля"

    assert validate_seed_text(seed) == seed


def test_validate_seed_text_accepts_short_russian_technical_ecc_seed() -> None:
    seed = "сжатая точка"

    assert validate_seed_text(seed) == seed


def test_validate_seed_text_accepts_short_english_technical_ecc_seed() -> None:
    seed = "compressed point"

    assert validate_seed_text(seed) == seed


def test_validate_seed_text_accepts_unknown_research_phrase() -> None:
    seed = "flumor braid cache anomaly"

    assert validate_seed_text(seed) == seed


def test_validate_seed_text_accepts_vague_input_for_agent_review() -> None:
    seed = "помоги"

    assert validate_seed_text(seed) == seed


def test_validate_seed_text_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_seed_text("   ")


def test_unknown_seed_with_generic_agent_scaffold_stays_generic() -> None:
    target_kind = determine_target_kind(
        seed_text="абракадабра флюмор новая гипотеза",
        planned_test="Run a controlled local classification pass to detect technical focus terms.",
        summary=(
            "Investigate whether the seed can be reduced to a bounded and testable property "
            "of an elliptic-curve object, point representation, or cryptographic implementation."
        ),
    )

    assert target_kind == "generic"


def test_russian_ecc_seed_routes_to_ecc_without_keyword_gate() -> None:
    target_kind = determine_target_kind(
        seed_text="сжатая точка",
        planned_test="",
        summary="",
    )

    assert target_kind == "point"


def test_russian_smart_contract_seed_routes_to_contract_without_keyword_gate() -> None:
    target_kind = determine_target_kind(
        seed_text="новый метод проверки прав доступа в смарт-контракте",
        planned_test="",
        summary="",
    )

    assert target_kind == "smart_contract"


def test_unknown_seed_runs_neutral_placeholder_path(tmp_path: Path) -> None:
    run_root = tmp_path / "unknown_seed"
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
                "log_level": "WARNING",
                "max_hypotheses": 2,
                "tool_timeout_seconds": 15,
            }
        )
    )

    session = orchestrator.run_session(
        seed_text="абракадабра флюмор новая гипотеза",
        author="test",
    )

    assert session.research_target is not None
    assert session.research_target.target_kind == "generic"
    assert session.jobs
    assert session.jobs[0].tool_name == "placeholder_math_tool"
    assert session.report is not None
    assert "neutral bounded local classification" in session.report.summary
    assert all("elliptic-curve" not in item for item in session.report.recommendations)


def test_explicit_ecc_domain_does_not_switch_to_smart_contract(tmp_path: Path) -> None:
    run_root = tmp_path / "explicit_ecc"
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
                "log_level": "WARNING",
                "max_hypotheses": 2,
                "tool_timeout_seconds": 15,
            }
        )
    )

    session = orchestrator.run_session(
        seed_text="delegatecall access control странная идея",
        author="test",
        domain="ecc_research",
    )

    assert session.seed.domain == "ecc_research"
    assert session.research_target is not None
    assert session.research_target.target_kind != "smart_contract"


def test_explicit_smart_contract_domain_stays_contract_even_with_ecc_terms(tmp_path: Path) -> None:
    run_root = tmp_path / "explicit_contract"
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
                "log_level": "WARNING",
                "max_hypotheses": 2,
                "tool_timeout_seconds": 15,
            }
        )
    )
    seed = build_smart_contract_seed(
        idea_text="проверить ECDSA signature flow внутри контракта",
        contract_code="pragma solidity ^0.8.20; contract Vault { function f() external {} }",
    )

    session = orchestrator.run_session(seed_text=seed, author="test", domain="smart_contract_audit")

    assert session.seed.domain == "smart_contract_audit"
    assert session.research_target is not None
    assert session.research_target.target_kind == "smart_contract"
