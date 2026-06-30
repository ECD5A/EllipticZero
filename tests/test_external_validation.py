from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_smartbugs_subset import (
    SMARTBUGS_COMMIT,
    VALIDATION_CASES,
    render_validation,
    run_validation,
)


def test_targeted_external_validation_uses_pinned_annotations(tmp_path: Path) -> None:
    snippets = {
        "access_control": (
            "contract C { address owner; function withdrawAll(address to) public { "
            "require(tx.origin == owner); to.call(''); } }"
        ),
        "reentrancy": (
            "contract C { mapping(address=>uint) userBalance; function withdraw() public { "
            "msg.sender.call.value(userBalance[msg.sender])(); userBalance[msg.sender]=0; } }"
        ),
        "unchecked_low_level_calls": (
            "contract C { function callnotchecked(address target) public { target.call(''); } }"
        ),
        "denial_of_service": (
            "contract C { address[] users; function refundAll() public { "
            "for(uint i=0;i<users.length;i++){ require(users[i].send(1)); } } }"
        ),
        "bad_randomness": (
            "contract C { function draw() public view returns(bytes32) { "
            "return keccak256(blockhash(block.number-1), now); } }"
        ),
    }
    annotations = []
    for case in VALIDATION_CASES:
        source_path = tmp_path / str(case["path"])
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "pragma solidity ^0.4.24; " + snippets[str(case["category"])],
            encoding="utf-8",
        )
        annotations.append(
            {
                "path": case["path"],
                "vulnerabilities": [{"category": case["category"], "lines": [1]}],
            }
        )
    (tmp_path / "vulnerabilities.json").write_text(
        json.dumps(annotations),
        encoding="utf-8",
    )

    result = run_validation(dataset_root=tmp_path)

    assert result["source"]["expected_commit"] == SMARTBUGS_COMMIT
    assert result["passed"] is True
    assert result["passed_case_count"] == 6
    assert result["total_case_count"] == 6
    assert result["metrics"] == {
        "true_positive_count": 5,
        "false_negative_count": 0,
        "true_negative_count": 1,
        "false_positive_count": 0,
        "invalid_count": 0,
        "positive_case_count": 5,
        "negative_case_count": 1,
        "recall_percent": 100.0,
        "miss_rate_percent": 0.0,
        "false_positive_rate_percent": 0.0,
        "specificity_percent": 100.0,
        "precision_percent": 100.0,
    }
    assert result["case_study"]["passed"] is True
    assert result["case_study"]["after"]["observed_relevant_families"] == []

    markdown = render_validation(result, output_format="markdown")
    assert "| Recall | 100.00% | 5 positive cases |" in markdown
    assert "## Before/After Reentrancy Case Study" in markdown
    assert "Relevant families after hardening: none" in markdown


def test_targeted_external_validation_reports_a_missed_family(tmp_path: Path) -> None:
    snippets = {
        "access_control": "contract C { function f() public { require(tx.origin == msg.sender); } }",
        "reentrancy": "contract C { function withdraw() public pure returns(uint) { return 1; } }",
        "unchecked_low_level_calls": "contract C { function f(address a) public { a.call(''); } }",
        "denial_of_service": (
            "contract C { address[] users; function f() public { "
            "for(uint i=0;i<users.length;i++){ users[i].send(1); } } }"
        ),
        "bad_randomness": (
            "contract C { function f() public view returns(bytes32) { "
            "return keccak256(blockhash(block.number-1), now); } }"
        ),
    }
    annotations = []
    for case in VALIDATION_CASES:
        source_path = tmp_path / str(case["path"])
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text(
            "pragma solidity ^0.4.24; " + snippets[str(case["category"])],
            encoding="utf-8",
        )
        annotations.append(
            {
                "path": case["path"],
                "vulnerabilities": [{"category": case["category"], "lines": [1]}],
            }
        )
    (tmp_path / "vulnerabilities.json").write_text(
        json.dumps(annotations),
        encoding="utf-8",
    )

    result = run_validation(dataset_root=tmp_path)

    assert result["passed"] is False
    assert result["metrics"]["true_positive_count"] == 4
    assert result["metrics"]["false_negative_count"] == 1
    assert result["metrics"]["recall_percent"] == 80.0
    assert result["metrics"]["miss_rate_percent"] == 20.0
    missed = next(
        case
        for case in result["case_results"]
        if case["case_id"] == "smartbugs-reentrancy-legacy-call"
    )
    assert missed["classification"] == "false_negative"
