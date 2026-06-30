from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_smartbugs_subset import SMARTBUGS_COMMIT, VALIDATION_CASES, run_validation


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
