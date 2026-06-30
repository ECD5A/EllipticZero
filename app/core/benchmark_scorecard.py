# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.core.golden_cases import list_golden_cases, prepare_golden_case_run
from app.models import ResearchSession


class BenchmarkOrchestrator(Protocol):
    def run_session(self, **kwargs: Any) -> ResearchSession: ...


class BenchmarkCaseResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    case_id: str
    domain: str
    passed: bool
    passed_checks: list[str] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    observed_tools: list[str] = Field(default_factory=list)
    observed_issue_families: list[str] = Field(default_factory=list)
    session_id: str | None = None


class BenchmarkScorecard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: int = 1
    passed: bool
    score_percent: float
    passed_check_count: int
    total_check_count: int
    case_results: list[BenchmarkCaseResult] = Field(default_factory=list)


def run_benchmark_scorecard(
    *,
    orchestrator: BenchmarkOrchestrator,
    root: Path | None = None,
    case_ids: list[str] | None = None,
) -> BenchmarkScorecard:
    selected_ids = set(case_ids or [])
    cases = [
        case
        for case in list_golden_cases(root)
        if not selected_ids or str(case.get("case_id", "")) in selected_ids
    ]
    if selected_ids:
        resolved_ids = {str(case.get("case_id", "")) for case in cases}
        missing_ids = sorted(selected_ids - resolved_ids)
        if missing_ids:
            raise ValueError("Unknown benchmark case(s): " + ", ".join(missing_ids))

    results: list[BenchmarkCaseResult] = []
    for case in cases:
        case_id = str(case.get("case_id", "")).strip()
        domain = str(case.get("domain", "")).strip()
        try:
            prepared = prepare_golden_case_run(case_id, root)
            session = orchestrator.run_session(
                seed_text=prepared.seed_text,
                author="benchmark-scorecard",
                domain=prepared.domain,
                synthetic_target_name=prepared.synthetic_target_name,
                experiment_pack_name=prepared.experiment_pack_name,
            )
            results.append(_evaluate_case(case=case, session=session))
        except Exception as exc:
            results.append(
                BenchmarkCaseResult(
                    case_id=case_id,
                    domain=domain,
                    passed=False,
                    failed_checks=[f"case execution failed: {type(exc).__name__}: {exc}"],
                )
            )

    passed_check_count = sum(len(result.passed_checks) for result in results)
    total_check_count = sum(
        len(result.passed_checks) + len(result.failed_checks) for result in results
    )
    score_percent = (
        round((passed_check_count / total_check_count) * 100, 2)
        if total_check_count
        else 0.0
    )
    return BenchmarkScorecard(
        passed=bool(results) and all(result.passed for result in results),
        score_percent=score_percent,
        passed_check_count=passed_check_count,
        total_check_count=total_check_count,
        case_results=results,
    )


def render_benchmark_scorecard(
    scorecard: BenchmarkScorecard,
    *,
    language: str = "en",
    output_format: str = "text",
) -> str:
    if output_format == "json":
        return json.dumps(scorecard.model_dump(mode="json"), indent=2, ensure_ascii=False)

    is_ru = language == "ru"
    title = "BENCHMARK SCORECARD" if not is_ru else "СВОДКА BENCHMARK-ПРОВЕРКИ"
    status = (
        ("PASS" if scorecard.passed else "FAIL")
        if not is_ru
        else ("ПРОЙДЕНО" if scorecard.passed else "НЕ ПРОЙДЕНО")
    )
    lines = [
        title,
        f"Status: {status}" if not is_ru else f"Статус: {status}",
        (
            f"Score: {scorecard.score_percent:.2f}% "
            f"({scorecard.passed_check_count}/{scorecard.total_check_count} checks)"
            if not is_ru
            else f"Результат: {scorecard.score_percent:.2f}% "
            f"({scorecard.passed_check_count}/{scorecard.total_check_count} проверок)"
        ),
        "",
    ]
    for result in scorecard.case_results:
        marker = "PASS" if result.passed else "FAIL"
        lines.append(f"[{marker}] {result.case_id}")
        for failed in result.failed_checks:
            lines.append(f"  - {failed}")
    return "\n".join(lines).rstrip()


def _evaluate_case(
    *,
    case: dict[str, Any],
    session: ResearchSession,
) -> BenchmarkCaseResult:
    case_id = str(case.get("case_id", "")).strip()
    domain = str(case.get("domain", "")).strip()
    assertions = case.get("benchmark_assertions")
    assertions = assertions if isinstance(assertions, dict) else {}
    passed: list[str] = []
    failed: list[str] = []

    def check(condition: bool, success: str, failure: str) -> None:
        (passed if condition else failed).append(success if condition else failure)

    expected_pack = str(case.get("recommended_pack", "")).strip()
    check(
        session.selected_pack_name == expected_pack,
        f"selected pack={expected_pack}",
        f"expected pack={expected_pack}; observed={session.selected_pack_name or 'none'}",
    )
    check(
        bool(session.executed_pack_steps),
        "pack steps executed",
        "no pack steps executed",
    )

    minimum_evidence = int(assertions.get("minimum_evidence", 1) or 1)
    check(
        len(session.evidence) >= minimum_evidence,
        f"evidence>={minimum_evidence}",
        f"evidence expected>={minimum_evidence}; observed={len(session.evidence)}",
    )

    successful_tools = _successful_tools(session)
    observed_tools = sorted({evidence.tool_name for evidence in session.evidence if evidence.tool_name})
    for tool_name in _string_list(assertions.get("required_tools")):
        check(
            tool_name in successful_tools,
            f"tool succeeded={tool_name}",
            f"required tool did not produce a valid result={tool_name}",
        )

    report = session.report
    for field_name in _string_list(assertions.get("required_report_fields")):
        value = getattr(report, field_name, None) if report is not None else None
        check(
            bool(value),
            f"report field populated={field_name}",
            f"required report field is empty={field_name}",
        )

    issue_families, pattern_issue_count, pattern_result_present = _pattern_findings(session)
    for family in _string_list(assertions.get("expected_issue_families")):
        check(
            family in issue_families,
            f"expected issue family observed={family}",
            f"expected issue family missed={family}",
        )
    if assertions.get("expect_no_pattern_issues") is True:
        check(
            pattern_result_present and pattern_issue_count == 0,
            "control case produced no built-in pattern issues",
            f"control case pattern issue count={pattern_issue_count}",
        )

    return BenchmarkCaseResult(
        case_id=case_id,
        domain=domain,
        passed=not failed,
        passed_checks=passed,
        failed_checks=failed,
        observed_tools=observed_tools,
        observed_issue_families=sorted(issue_families),
        session_id=session.session_id,
    )


def _successful_tools(session: ResearchSession) -> set[str]:
    successful: set[str] = set()
    for evidence in session.evidence:
        result = _tool_result(evidence.raw_result)
        if evidence.tool_name and result.get("status") in {"ok", "observed_issue"}:
            successful.add(evidence.tool_name)
    return successful


def _pattern_findings(session: ResearchSession) -> tuple[set[str], int, bool]:
    families: set[str] = set()
    issue_count = 0
    present = False
    for evidence in session.evidence:
        if evidence.tool_name != "contract_pattern_check_tool":
            continue
        present = True
        result = _tool_result(evidence.raw_result)
        result_data = result.get("result_data")
        if not isinstance(result_data, dict):
            continue
        issue_count += int(result_data.get("issue_count", 0) or 0)
        family_counts = result_data.get("issue_family_counts")
        if isinstance(family_counts, dict):
            families.update(str(name) for name in family_counts)
    return families, issue_count, present


def _tool_result(raw_result: dict[str, Any]) -> dict[str, Any]:
    nested = raw_result.get("result")
    if isinstance(nested, dict):
        return nested
    return raw_result


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]
