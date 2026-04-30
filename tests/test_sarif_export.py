from __future__ import annotations

import json
from pathlib import Path

from app.core.replay_loader import LoadedReplaySource
from app.core.sarif_export import build_sarif_payload, write_sarif_file
from app.core.seed_parsing import build_smart_contract_seed
from app.main import build_parser
from app.models.report import ResearchReport
from app.models.seed import ResearchSeed
from app.models.session import ResearchSession
from app.types import ConfidenceLevel


def _saved_contract_run() -> LoadedReplaySource:
    seed_text = build_smart_contract_seed(
        idea_text="Review vault permission lanes.",
        contract_code="pragma solidity ^0.8.20; contract Vault {}",
        source_label="contracts/Vault.sol",
    )
    report = ResearchReport(
        session_id="session_sarif",
        seed_text=seed_text,
        summary="Bounded smart-contract review.",
        contract_finding_cards=[
            "Potential finding: externally reachable value-flow lane requires review. Line hint: 7."
        ],
        contract_static_findings=[
            "Static signal: parser and surface summaries should be cross-checked."
        ],
        contract_manual_review_items=[
            "Manual review: confirm admin role assumptions before deployment."
        ],
        regression_flags=[
            "Regression watch: compare permission changes against the saved baseline."
        ],
        quality_gates=[
            "Evidence gate: local tool output must be inspected before escalation."
        ],
        confidence=ConfidenceLevel.MANUAL_REVIEW_REQUIRED,
    )
    session = ResearchSession(
        session_id="session_sarif",
        seed=ResearchSeed(raw_text=seed_text),
        report=report,
        selected_pack_name="vault_permission_benchmark_pack",
    )
    return LoadedReplaySource(
        source_type="bundle",
        source_path="artifacts/bundles/session_sarif",
        session=session,
        original_session_id="session_sarif",
        tool_names=["contract_parser_tool", "contract_surface_tool"],
        experiment_types=["smart_contract_parse", "smart_contract_surface"],
        selected_pack_name="vault_permission_benchmark_pack",
    )


def test_sarif_export_builds_code_scanning_payload_from_saved_run(tmp_path: Path) -> None:
    loaded = _saved_contract_run()
    payload = build_sarif_payload(loaded_source=loaded)
    results = payload["runs"][0]["results"]
    rule_ids = {result["ruleId"] for result in results}

    assert payload["version"] == "2.1.0"
    assert "EZ-CONTRACT-FINDING" in rule_ids
    assert "EZ-CONTRACT-MANUAL-REVIEW" in rule_ids
    assert "EZ-REGRESSION-FLAG" in rule_ids
    assert results[0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] == (
        "contracts/Vault.sol"
    )
    assert results[0]["locations"][0]["physicalLocation"]["region"]["startLine"] == 7
    assert results[0]["properties"]["ellipticzeroSeverity"] == "medium"
    assert "smart-contracts" in results[0]["properties"]["tags"]
    assert results[0]["partialFingerprints"]["ellipticzero/v1"]
    assert all(result["properties"]["reviewRequired"] is True for result in results)

    output_path, result_count = write_sarif_file(
        loaded_source=loaded,
        output_path=tmp_path / "ellipticzero.sarif",
    )
    written = json.loads(output_path.read_text(encoding="utf-8"))

    assert result_count == len(results)
    assert written["runs"][0]["tool"]["driver"]["name"] == "EllipticZero"


def test_parser_supports_saved_run_sarif_export() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--replay-bundle",
            "artifacts/bundles/session_sarif",
            "--export-sarif",
            "artifacts/sarif/session_sarif.sarif",
        ]
    )

    assert args.replay_bundle == "artifacts/bundles/session_sarif"
    assert args.export_sarif == "artifacts/sarif/session_sarif.sarif"
