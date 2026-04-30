from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.threat_intel import ThreatIntelCache, ThreatIntelProfile, match_threat_intel_profiles
from app.models.tool_payloads import SmartContractAuditPayload
from app.tools.base import BaseTool
from app.tools.smart_contract_utils import (
    build_contract_issue_line_hints,
    build_contract_outline,
    build_normalized_contract_findings,
    detect_contract_patterns,
    infer_contract_language,
    prioritize_contract_issues,
)


class ContractPatternCheckTool(BaseTool):
    """Run scoped static pattern checks against smart-contract source text."""

    name = "contract_pattern_check_tool"
    category = "smart_contract_audit"
    description = "Run scoped static checks for reentrancy review surfaces, unsafe call patterns, and access-control gaps."
    version = "0.1.0"
    input_schema_hint = "SmartContractAuditPayload"
    output_schema_hint = "Scoped smart-contract pattern findings"
    payload_model = SmartContractAuditPayload

    def __init__(
        self,
        *,
        threat_intel_cache: ThreatIntelCache | None = None,
        threat_intel_profiles: list[ThreatIntelProfile] | None = None,
    ) -> None:
        self.threat_intel_cache = threat_intel_cache or ThreatIntelCache()
        self.threat_intel_profiles = threat_intel_profiles

    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        contract_code = str(payload.get("contract_code", ""))
        language = infer_contract_language(
            source_label=str(payload.get("source_label", "")).strip() or None,
            hinted_language=str(payload.get("language", "")).strip() or None,
            contract_code=contract_code,
        )
        outline = build_contract_outline(
            contract_code=contract_code,
            language=language,
        )
        issues, notes = detect_contract_patterns(outline)
        profiles = self.threat_intel_profiles
        if profiles is None:
            profiles = self.threat_intel_cache.load_profiles()
        known_case_matches = match_threat_intel_profiles(
            profiles=profiles,
            contract_code=contract_code,
            issues=issues,
            notes=notes,
        )
        if known_case_matches:
            notes.extend(
                f"known_case_match:{match.profile_id}:{match.evidence_strength}"
                for match in known_case_matches[:8]
            )
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
        issue_line_hints = build_contract_issue_line_hints(outline, issues)
        issue_line_hint_map = {
            str(hint.get("issue")): hint
            for hint in issue_line_hints
            if str(hint.get("issue", "")).strip()
        }
        prioritized_issues = _attach_issue_line_hints(
            prioritize_contract_issues(issues),
            issue_line_hint_map,
        )
        priority_counts: dict[str, int] = {}
        for item in prioritized_issues:
            priority = str(item.get("priority", "medium"))
            priority_counts[priority] = priority_counts.get(priority, 0) + 1
        known_case_match_mappings = [match.to_mapping() for match in known_case_matches]
        normalized_findings = build_normalized_contract_findings(
            prioritized_issues,
            known_case_matches=known_case_match_mappings,
        )

        return self.make_result(
            status="ok" if not issues else "observed_issue",
            conclusion="Scoped smart-contract pattern checks completed locally without implying a validated exploit path.",
            notes=[
                *notes,
                "Pattern findings are scoped review signals and should be confirmed manually before stronger claims.",
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
                "issue_line_hints": issue_line_hints,
                "issue_line_hint_count": len(issue_line_hints),
                "prioritized_issues": prioritized_issues[:12],
                "normalized_findings": normalized_findings[:12],
                "normalized_finding_count": len(normalized_findings),
                "priority_counts": priority_counts,
                "highest_priority": prioritized_issues[0]["priority"] if prioritized_issues else None,
                "highest_severity": normalized_findings[0]["severity"] if normalized_findings else None,
                "known_case_profile_count": len(profiles),
                "known_case_match_count": len(known_case_matches),
                "known_case_matches": known_case_match_mappings,
                "known_case_sources": sorted({match.source_id for match in known_case_matches}),
                "notes": notes,
                "note_type_counts": note_type_counts,
                "manual_review_recommended": manual_review,
                "bounded_static_analysis": True,
            },
        )


def _attach_issue_line_hints(
    prioritized_issues: list[dict[str, str]],
    line_hints_by_issue: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    for item in prioritized_issues:
        enriched_item: dict[str, object] = dict(item)
        hint = line_hints_by_issue.get(str(item.get("issue", "")))
        if isinstance(hint, dict):
            line = hint.get("line")
            if isinstance(line, int) and line > 0:
                enriched_item["line"] = line
                enriched_item["line_hint"] = f"Line hint: {line}"
            function = hint.get("function")
            if isinstance(function, str) and function.strip():
                enriched_item["function"] = function.strip()
            evidence = hint.get("evidence")
            if isinstance(evidence, str) and evidence.strip():
                enriched_item["line_evidence"] = evidence.strip()
        enriched.append(enriched_item)
    return enriched
