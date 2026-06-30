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
CASE_STUDY_CASE_ID = "smartbugs-reentrancy-legacy-call"
HARDENED_REENTRANCY_CONTROL = (
    PROJECT_ROOT
    / "examples"
    / "case_studies"
    / "smartbugs_reentrancy"
    / "HardenedReentrancyVault.sol"
)
REENTRANCY_RECHECK_FAMILIES = {
    "asset_exit_without_balance_validation",
    "accounting_update_after_external_call",
    "reentrancy_review_required",
    "unchecked_external_call_surface",
}
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
        choices=("text", "json", "markdown"),
        default="text",
        help="Validation summary format.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output file. Standard output is used when omitted.",
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
    rendered = render_validation(result, output_format=args.format)
    if args.output:
        output_path = args.output.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        print(output_path)
    else:
        print(rendered)
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
                    "path": relative_path,
                    "dataset_category": case["category"],
                    "passed": False,
                    "reason": "source file missing",
                    "expected_positive": True,
                    "detected_positive": False,
                    "classification": "invalid",
                    "expected_any_family": sorted(str(item) for item in case["expected_families"]),
                    "observed_families": [],
                    "issue_count": 0,
                }
            )
            continue

        result_data = _run_pattern_check(
            tool=tool,
            source_path=source_path,
            source_label=relative_path,
        )
        family_counts = result_data.get("issue_family_counts", {})
        observed_families = set(family_counts if isinstance(family_counts, dict) else {})
        expected_families = {str(item) for item in case["expected_families"]}
        category_matches = str(case["category"]) in annotated_categories
        family_matches = bool(expected_families & observed_families)
        classification = (
            "true_positive"
            if category_matches and family_matches
            else "false_negative"
            if category_matches
            else "invalid"
        )
        case_results.append(
            {
                "case_id": case["case_id"],
                "path": relative_path,
                "dataset_category": case["category"],
                "passed": category_matches and family_matches,
                "category_annotation_present": category_matches,
                "expected_positive": True,
                "detected_positive": family_matches,
                "classification": classification,
                "expected_any_family": sorted(expected_families),
                "observed_families": sorted(observed_families),
                "issue_count": int(result_data.get("issue_count", 0) or 0),
            }
        )

    safe_path = PROJECT_ROOT / "examples" / "golden_cases" / "contracts" / "SyntheticSafeLedger.sol"
    safe_result_data = _run_pattern_check(
        tool=tool,
        source_path=safe_path,
        source_label=str(safe_path.relative_to(PROJECT_ROOT)),
    )
    safe_issue_count = int(safe_result_data.get("issue_count", 0) or 0)
    case_results.append(
        {
            "case_id": "ellipticzero-safe-ledger-control",
            "path": str(safe_path.relative_to(PROJECT_ROOT)),
            "dataset_category": "clean_control",
            "passed": safe_issue_count == 0,
            "expected_positive": False,
            "detected_positive": safe_issue_count > 0,
            "classification": "true_negative" if safe_issue_count == 0 else "false_positive",
            "expected_any_family": [],
            "observed_families": sorted(
                safe_result_data.get("issue_family_counts", {})
            ),
            "issue_count": safe_issue_count,
        }
    )

    metrics = _classification_metrics(case_results)
    case_study = _build_reentrancy_case_study(tool=tool, case_results=case_results)
    passed_count = sum(bool(item["passed"]) for item in case_results)
    return {
        "schema_version": 2,
        "passed": passed_count == len(case_results) and bool(case_study["passed"]),
        "passed_case_count": passed_count,
        "total_case_count": len(case_results),
        "metrics": metrics,
        "source": {
            "repository": SMARTBUGS_REPOSITORY,
            "expected_commit": SMARTBUGS_COMMIT,
            "observed_commit": observed_commit,
            "commit_matches": commit_matches,
        },
        "case_results": case_results,
        "case_study": case_study,
        "limitations": [
            "This is a targeted deterministic family check, not a full SmartBugs benchmark.",
            "A passing case means that at least one expected review family was surfaced; it does not prove exploitability.",
            "The reported false-positive rate is limited to one synthetic clean control and must not be generalized.",
            "The hardened case-study fixture demonstrates a bounded recheck, not an audited production patch.",
        ],
    }


def render_validation(result: dict[str, Any], *, output_format: str) -> str:
    if output_format == "json":
        return json.dumps(result, indent=2, ensure_ascii=False)
    if output_format == "markdown":
        return _render_markdown(result)
    status = "PASS" if result["passed"] else "FAIL"
    metrics = result["metrics"]
    lines = [
        "SMARTBUGS TARGETED VALIDATION",
        f"Status: {status}",
        f"Cases: {result['passed_case_count']}/{result['total_case_count']}",
        f"Recall: {_format_percent(metrics['recall_percent'])}",
        f"Miss rate: {_format_percent(metrics['miss_rate_percent'])}",
        f"Targeted false-positive rate: {_format_percent(metrics['false_positive_rate_percent'])}",
        f"Pinned commit: {result['source']['commit_matches']}",
        "",
    ]
    for case in result["case_results"]:
        marker = "PASS" if case["passed"] else "FAIL"
        lines.append(f"[{marker}] {case['case_id']} ({case['classification']})")
    case_study = result["case_study"]
    lines.extend(
        [
            "",
            "REENTRANCY BEFORE/AFTER CASE STUDY",
            f"Status: {'PASS' if case_study['passed'] else 'FAIL'}",
            f"Before families: {', '.join(case_study['before']['observed_families']) or 'none'}",
            f"After relevant families: {', '.join(case_study['after']['observed_relevant_families']) or 'none'}",
        ]
    )
    lines.extend(["", *[f"Note: {item}" for item in result["limitations"]]])
    return "\n".join(lines)


def _classification_metrics(case_results: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        "true_positive": 0,
        "false_negative": 0,
        "true_negative": 0,
        "false_positive": 0,
        "invalid": 0,
    }
    for case in case_results:
        classification = str(case.get("classification", "invalid"))
        counts[classification if classification in counts else "invalid"] += 1

    positive_count = counts["true_positive"] + counts["false_negative"]
    negative_count = counts["true_negative"] + counts["false_positive"]
    recall = _safe_percent(counts["true_positive"], positive_count)
    miss_rate = _safe_percent(counts["false_negative"], positive_count)
    false_positive_rate = _safe_percent(counts["false_positive"], negative_count)
    specificity = _safe_percent(counts["true_negative"], negative_count)
    precision = _safe_percent(
        counts["true_positive"],
        counts["true_positive"] + counts["false_positive"],
    )
    return {
        **{f"{name}_count": value for name, value in counts.items()},
        "positive_case_count": positive_count,
        "negative_case_count": negative_count,
        "recall_percent": recall,
        "miss_rate_percent": miss_rate,
        "false_positive_rate_percent": false_positive_rate,
        "specificity_percent": specificity,
        "precision_percent": precision,
    }


def _build_reentrancy_case_study(
    *,
    tool: Any,
    case_results: list[dict[str, Any]],
) -> dict[str, Any]:
    before = next(
        (item for item in case_results if item.get("case_id") == CASE_STUDY_CASE_ID),
        None,
    )
    if before is None:
        return {
            "case_id": CASE_STUDY_CASE_ID,
            "passed": False,
            "reason": "before case result unavailable",
            "before": {},
            "after": {},
        }
    if not HARDENED_REENTRANCY_CONTROL.is_file():
        return {
            "case_id": CASE_STUDY_CASE_ID,
            "passed": False,
            "reason": "hardened control unavailable",
            "before": before,
            "after": {},
        }

    after_result = _run_pattern_check(
        tool=tool,
        source_path=HARDENED_REENTRANCY_CONTROL,
        source_label=str(HARDENED_REENTRANCY_CONTROL.relative_to(PROJECT_ROOT)),
    )
    after_family_counts = after_result.get("issue_family_counts", {})
    after_families = set(
        after_family_counts if isinstance(after_family_counts, dict) else {}
    )
    observed_relevant = sorted(after_families & REENTRANCY_RECHECK_FAMILIES)
    passed = before.get("classification") == "true_positive" and not observed_relevant
    return {
        "case_id": "smartbugs-reentrancy-before-after",
        "title": "Legacy reentrancy signal and hardened recheck",
        "passed": passed,
        "before": {
            "case_id": before.get("case_id"),
            "path": before.get("path"),
            "classification": before.get("classification"),
            "observed_families": before.get("observed_families", []),
            "issue_count": before.get("issue_count", 0),
        },
        "after": {
            "path": HARDENED_REENTRANCY_CONTROL.relative_to(PROJECT_ROOT).as_posix(),
            "observed_families": sorted(after_families),
            "observed_relevant_families": observed_relevant,
            "issue_count": int(after_result.get("issue_count", 0) or 0),
        },
        "hardening": [
            "apply checks-effects-interactions before the external value transfer",
            "guard the withdrawal path against nested entry",
            "require the low-level call result",
        ],
        "recheck": (
            "The deterministic reentrancy, post-call accounting, and unchecked-call families "
            "must be absent from the hardened fixture."
        ),
    }


def _run_pattern_check(*, tool: Any, source_path: Path, source_label: str) -> dict[str, Any]:
    tool_result = tool.run(
        tool.validate_payload(
            {
                "contract_code": source_path.read_text(encoding="utf-8"),
                "language": "solidity",
                "source_label": source_label,
            }
        )
    )
    result_data = tool_result.get("result_data", {})
    return result_data if isinstance(result_data, dict) else {}


def _render_markdown(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    source = result["source"]
    case_study = result["case_study"]
    lines = [
        "# SmartBugs Targeted Validation",
        "",
        f"**Status:** {'PASS' if result['passed'] else 'FAIL'}  ",
        f"**Dataset commit:** `{source['expected_commit']}`  ",
        f"**Cases:** `{result['passed_case_count']}/{result['total_case_count']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Result | Support |",
        "| --- | ---: | ---: |",
        f"| Recall | {_format_percent(metrics['recall_percent'])} | {metrics['positive_case_count']} positive cases |",
        f"| Miss rate | {_format_percent(metrics['miss_rate_percent'])} | {metrics['positive_case_count']} positive cases |",
        f"| Targeted false-positive rate | {_format_percent(metrics['false_positive_rate_percent'])} | {metrics['negative_case_count']} negative control |",
        f"| Precision | {_format_percent(metrics['precision_percent'])} | case-level classification |",
        "",
        "## Cases",
        "",
        "| Case | Expected | Classification | Observed families |",
        "| --- | --- | --- | --- |",
    ]
    for case in result["case_results"]:
        expected = "positive" if case.get("expected_positive") else "negative"
        families = ", ".join(case.get("observed_families", [])) or "none"
        lines.append(
            f"| `{case['case_id']}` | {expected} | `{case['classification']}` | {families} |"
        )
    lines.extend(
        [
            "",
            "## Before/After Reentrancy Case Study",
            "",
            f"**Status:** {'PASS' if case_study['passed'] else 'FAIL'}",
            "",
            f"- Before: `{case_study.get('before', {}).get('path', 'unavailable')}`",
            "- Detected before: "
            + (", ".join(case_study.get("before", {}).get("observed_families", [])) or "none"),
            f"- Hardened control: `{case_study.get('after', {}).get('path', 'unavailable')}`",
            "- Relevant families after hardening: "
            + (
                ", ".join(case_study.get("after", {}).get("observed_relevant_families", []))
                or "none"
            ),
            f"- Recheck rule: {case_study.get('recheck', 'unavailable')}",
            "",
            "## Limitations",
            "",
            *[f"- {item}" for item in result["limitations"]],
        ]
    )
    return "\n".join(lines)


def _safe_percent(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100, 2)


def _format_percent(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}%"


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
