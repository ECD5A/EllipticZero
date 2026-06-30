# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

SMARTBUGS_REPOSITORY = "https://github.com/smartbugs/smartbugs-curated.git"
SMARTBUGS_COMMIT = "230e649123477eff332742a59a1c7cc6dc286cab"
VALIDATION_CASES = (
    {
        "case_id": "smartbugs-access-control-phishable",
        "path": "dataset/access_control/phishable.sol",
        "category": "access_control",
        "expected_families": ("tx_origin_auth_surface", "tx_origin_usage"),
    },
    {
        "case_id": "smartbugs-reentrancy-legacy-call",
        "path": "dataset/reentrancy/reentrancy_simple.sol",
        "category": "reentrancy",
        "expected_families": ("reentrancy_review_required",),
    },
    {
        "case_id": "smartbugs-unchecked-low-level-call",
        "path": "dataset/unchecked_low_level_calls/unchecked_return_value.sol",
        "category": "unchecked_low_level_calls",
        "expected_families": ("unchecked_external_call_surface",),
    },
    {
        "case_id": "smartbugs-dos-send-loop",
        "path": "dataset/denial_of_service/send_loop.sol",
        "category": "denial_of_service",
        "expected_families": ("external_call_in_loop",),
    },
    {
        "case_id": "smartbugs-bad-randomness",
        "path": "dataset/bad_randomness/guess_the_random_number.sol",
        "category": "bad_randomness",
        "expected_families": ("entropy_source_review_required",),
    },
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate deterministic review families against a pinned SmartBugs subset."
    )
    parser.add_argument(
        "--dataset-root",
        type=Path,
        required=True,
        help="Path to a local checkout of smartbugs/smartbugs-curated.",
    )
    parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="Validation summary format.",
    )
    parser.add_argument(
        "--require-pinned-commit",
        action="store_true",
        help="Fail unless the local checkout is at the pinned dataset commit.",
    )
    args = parser.parse_args()

    result = run_validation(
        dataset_root=args.dataset_root,
        require_pinned_commit=args.require_pinned_commit,
    )
    print(render_validation(result, output_format=args.format))
    return 0 if result["passed"] else 1


def run_validation(
    *,
    dataset_root: Path,
    require_pinned_commit: bool = False,
) -> dict[str, Any]:
    from app.tools.builtin.contract_pattern_check_tool import ContractPatternCheckTool

    root = dataset_root.expanduser().resolve()
    manifest_path = root / "vulnerabilities.json"
    if not manifest_path.is_file():
        raise ValueError(f"SmartBugs vulnerabilities.json not found under: {root}")

    annotations = json.loads(manifest_path.read_text(encoding="utf-8"))
    annotation_by_path = {
        str(item.get("path", "")): item
        for item in annotations
        if isinstance(item, dict) and item.get("path")
    }
    observed_commit = _git_commit(root)
    commit_matches = observed_commit == SMARTBUGS_COMMIT
    if require_pinned_commit and not commit_matches:
        raise ValueError(
            f"SmartBugs commit mismatch: expected {SMARTBUGS_COMMIT}; "
            f"observed {observed_commit or 'unavailable'}"
        )

    tool = ContractPatternCheckTool()
    case_results: list[dict[str, Any]] = []
    for case in VALIDATION_CASES:
        relative_path = str(case["path"])
        source_path = root / relative_path
        annotation = annotation_by_path.get(relative_path, {})
        annotated_categories = {
            str(item.get("category", ""))
            for item in annotation.get("vulnerabilities", [])
            if isinstance(item, dict)
        }
        if not source_path.is_file():
            case_results.append(
                {
                    "case_id": case["case_id"],
                    "passed": False,
                    "reason": "source file missing",
                    "observed_families": [],
                }
            )
            continue

        tool_result = tool.run(
            tool.validate_payload(
                {
                    "contract_code": source_path.read_text(encoding="utf-8"),
                    "language": "solidity",
                    "source_label": relative_path,
                }
            )
        )
        result_data = tool_result.get("result_data", {})
        family_counts = result_data.get("issue_family_counts", {})
        observed_families = set(family_counts if isinstance(family_counts, dict) else {})
        expected_families = {str(item) for item in case["expected_families"]}
        category_matches = str(case["category"]) in annotated_categories
        family_matches = bool(expected_families & observed_families)
        case_results.append(
            {
                "case_id": case["case_id"],
                "path": relative_path,
                "dataset_category": case["category"],
                "passed": category_matches and family_matches,
                "category_annotation_present": category_matches,
                "expected_any_family": sorted(expected_families),
                "observed_families": sorted(observed_families),
                "issue_count": int(result_data.get("issue_count", 0) or 0),
            }
        )

    safe_path = PROJECT_ROOT / "examples" / "golden_cases" / "contracts" / "SyntheticSafeLedger.sol"
    safe_result = tool.run(
        tool.validate_payload(
            {
                "contract_code": safe_path.read_text(encoding="utf-8"),
                "language": "solidity",
                "source_label": str(safe_path.relative_to(PROJECT_ROOT)),
            }
        )
    )
    safe_issue_count = int(safe_result.get("result_data", {}).get("issue_count", 0) or 0)
    case_results.append(
        {
            "case_id": "ellipticzero-safe-ledger-control",
            "path": str(safe_path.relative_to(PROJECT_ROOT)),
            "dataset_category": "clean_control",
            "passed": safe_issue_count == 0,
            "expected_any_family": [],
            "observed_families": sorted(
                safe_result.get("result_data", {}).get("issue_family_counts", {})
            ),
            "issue_count": safe_issue_count,
        }
    )

    passed_count = sum(bool(item["passed"]) for item in case_results)
    return {
        "schema_version": 1,
        "passed": passed_count == len(case_results),
        "passed_case_count": passed_count,
        "total_case_count": len(case_results),
        "source": {
            "repository": SMARTBUGS_REPOSITORY,
            "expected_commit": SMARTBUGS_COMMIT,
            "observed_commit": observed_commit,
            "commit_matches": commit_matches,
        },
        "case_results": case_results,
        "limitations": [
            "This is a targeted deterministic family check, not a full SmartBugs benchmark.",
            "A passing case means that at least one expected review family was surfaced; it does not prove exploitability.",
            "The clean control is synthetic and does not establish a general false-positive rate.",
        ],
    }


def render_validation(result: dict[str, Any], *, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)
    status = "PASS" if result["passed"] else "FAIL"
    lines = [
        "SMARTBUGS TARGETED VALIDATION",
        f"Status: {status}",
        f"Cases: {result['passed_case_count']}/{result['total_case_count']}",
        f"Pinned commit: {result['source']['commit_matches']}",
        "",
    ]
    for case in result["case_results"]:
        marker = "PASS" if case["passed"] else "FAIL"
        lines.append(f"[{marker}] {case['case_id']}")
    lines.extend(["", *[f"Note: {item}" for item in result["limitations"]]])
    return "\n".join(lines)


def _git_commit(root: Path) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    value = completed.stdout.strip()
    return value if completed.returncode == 0 and value else None


if __name__ == "__main__":
    raise SystemExit(main())
