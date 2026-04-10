from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.models.tool_payloads import SmartContractAuditPayload
from app.tools.base import BaseTool
from app.tools.smart_contract_utils import (
    build_contract_outline,
    detect_contract_patterns,
    infer_contract_language,
    prioritize_contract_issues,
)


class ContractPatternCheckTool(BaseTool):
    """Run bounded static pattern checks against smart-contract source text."""

    name = "contract_pattern_check_tool"
    category = "smart_contract_audit"
    description = "Run bounded static checks for reentrancy review surfaces, unsafe call patterns, and access-control gaps."
    version = "0.1.0"
    input_schema_hint = "SmartContractAuditPayload"
    output_schema_hint = "Bounded smart-contract pattern findings"
    payload_model = SmartContractAuditPayload

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        language = infer_contract_language(
            source_label=str(payload.get("source_label", "")).strip() or None,
            hinted_language=str(payload.get("language", "")).strip() or None,
            contract_code=str(payload.get("contract_code", "")),
        )
        outline = build_contract_outline(
            contract_code=str(payload.get("contract_code", "")),
            language=language,
        )
        issues, notes = detect_contract_patterns(outline)
        manual_review = bool(issues)
        issue_counts: dict[str, int] = {}
        for issue in issues:
            issue_counts[issue] = issue_counts.get(issue, 0) + 1
        issue_family_counts: dict[str, int] = {}
        for issue in issues:
            family = issue.split(":", 1)[0]
            issue_family_counts[family] = issue_family_counts.get(family, 0) + 1
        note_type_counts: dict[str, int] = {}
        for note in notes:
            family = note.split(":", 1)[0]
            note_type_counts[family] = note_type_counts.get(family, 0) + 1
        prioritized_issues = prioritize_contract_issues(issues)
        priority_counts: dict[str, int] = {}
        for item in prioritized_issues:
            priority = item["priority"]
            priority_counts[priority] = priority_counts.get(priority, 0) + 1

        return self.make_result(
            status="ok" if not issues else "observed_issue",
            conclusion="Bounded smart-contract pattern checks completed locally without implying a validated exploit path.",
            notes=[
                *notes,
                "Pattern findings are bounded review signals and should be confirmed manually before stronger claims.",
            ],
            result_data={
                "recognized": bool(outline.contract_names or outline.functions),
                "language": outline.language,
                "contract_names": outline.contract_names,
                "function_count": len(outline.functions),
                "issues": issues,
                "issue_count": len(issues),
                "issue_type_counts": issue_counts,
                "issue_family_counts": issue_family_counts,
                "prioritized_issues": prioritized_issues[:12],
                "priority_counts": priority_counts,
                "highest_priority": prioritized_issues[0]["priority"] if prioritized_issues else None,
                "notes": notes,
                "note_type_counts": note_type_counts,
                "manual_review_recommended": manual_review,
                "bounded_static_analysis": True,
            },
        )
