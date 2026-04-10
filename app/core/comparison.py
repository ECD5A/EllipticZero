from __future__ import annotations

from collections import Counter

from app.models.comparative_report import (
    BranchComparison,
    ComparativeReport,
    ComparativeReportSection,
    CrossSessionComparison,
    ToolComparison,
)
from app.models.session import ResearchSession
from app.types import ConfidenceLevel, HypothesisStatus


def build_comparative_report(
    session: ResearchSession,
    *,
    baseline_session: ResearchSession | None = None,
    baseline_source_path: str | None = None,
) -> ComparativeReport:
    """Build a cautious comparative view over the session outputs."""

    branch_comparison = compare_hypotheses(session)
    tool_comparison = compare_tool_outcomes(session)
    manual_review_items = collect_manual_review_items(session, tool_comparison)
    tested_hypotheses = summarize_tested_hypotheses(session)
    tool_usage = summarize_tool_usage(session)
    cross_session_comparison = (
        compare_against_baseline(
            session,
            baseline_session,
            baseline_source_path=baseline_source_path,
        )
        if baseline_session is not None
        else None
    )
    if cross_session_comparison is not None and cross_session_comparison.regressions:
        manual_review_items = _ordered_unique(
            [
                *manual_review_items,
                "Cross-session comparison surfaced possible regressions or missing coverage relative to the baseline session.",
            ]
        )

    sections = [
        ComparativeReportSection(
            title="Tested Hypotheses",
            summary=(
                "Multiple bounded branches were compared."
                if len(session.hypotheses) > 1
                else "Comparative branch analysis was limited to a single primary branch."
            ),
            findings=tested_hypotheses,
            recommendations=[],
        ),
        ComparativeReportSection(
            title="Tool Usage",
            summary=(
                "Multiple local tool paths contributed inspectable outputs."
                if len({item.tool_name for item in session.jobs if item.tool_name}) > 1
                else "Tool comparison remained limited because only one primary tool path was executed."
            ),
            findings=tool_usage,
            recommendations=[],
        ),
        ComparativeReportSection(
            title="Comparative Findings",
            summary=_comparative_summary(
                branch_comparison=branch_comparison,
                tool_comparison=tool_comparison,
                manual_review_items=manual_review_items,
            ),
            findings=[branch_comparison.summary, tool_comparison.consistency_summary],
            recommendations=manual_review_items,
        ),
    ]
    if cross_session_comparison is not None:
        sections.append(
            ComparativeReportSection(
                title="Before/After Comparison",
                summary=cross_session_comparison.summary,
                findings=[
                    *cross_session_comparison.improvements,
                    *cross_session_comparison.regressions,
                    *cross_session_comparison.stable_findings,
                ],
                recommendations=[
                    *cross_session_comparison.regressions,
                    *cross_session_comparison.notes[:2],
                ],
            )
        )

    analysis_generated = (
        len(session.hypotheses) > 1
        or len(tool_comparison.tool_names) > 1
        or cross_session_comparison is not None
    )
    notes = [
        "Comparative analysis is descriptive and evidence-first.",
        "Stronger branches indicate better bounded support within the recorded session, not proven correctness.",
    ]
    if cross_session_comparison is not None:
        notes.append(
            f"Cross-session baseline: {cross_session_comparison.baseline_session_id}."
        )
    if not analysis_generated:
        notes.append("Comparative output remained limited because only one primary execution path was available.")

    return ComparativeReport(
        session_id=session.session_id,
        analysis_generated=analysis_generated,
        summary=_comparative_summary(
            branch_comparison=branch_comparison,
            tool_comparison=tool_comparison,
            manual_review_items=manual_review_items,
            cross_session_comparison=cross_session_comparison,
        ),
        baseline_session_id=(
            cross_session_comparison.baseline_session_id
            if cross_session_comparison is not None
            else None
        ),
        baseline_source_path=(
            cross_session_comparison.baseline_source_path
            if cross_session_comparison is not None
            else None
        ),
        branch_comparisons=[branch_comparison],
        tool_comparisons=[tool_comparison],
        cross_session_comparison=cross_session_comparison,
        sections=sections,
        manual_review_items=manual_review_items,
        notes=notes,
    )


def compare_against_baseline(
    session: ResearchSession,
    baseline_session: ResearchSession,
    *,
    baseline_source_path: str | None = None,
) -> CrossSessionComparison:
    """Compare the current run against a saved baseline session conservatively."""

    current_tool_names = _session_tool_names(session)
    baseline_tool_names = _session_tool_names(baseline_session)
    added_tools = [name for name in current_tool_names if name not in baseline_tool_names]
    removed_tools = [name for name in baseline_tool_names if name not in current_tool_names]

    current_evidence_count = len(session.evidence)
    baseline_evidence_count = len(baseline_session.evidence)
    current_manual_review_count = _session_manual_review_count(session)
    baseline_manual_review_count = _session_manual_review_count(baseline_session)
    current_priority_count = _session_priority_finding_count(session)
    baseline_priority_count = _session_priority_finding_count(baseline_session)
    current_casebook_gap_count = _session_casebook_gap_count(session)
    baseline_casebook_gap_count = _session_casebook_gap_count(baseline_session)
    current_confidence = _session_confidence_value(session)
    baseline_confidence = _session_confidence_value(baseline_session)

    improvements: list[str] = []
    regressions: list[str] = []
    stable_findings: list[str] = []
    notes = [
        f"baseline_session={baseline_session.session_id}",
        f"baseline_source={baseline_source_path or 'saved session snapshot'}",
        f"evidence_count={baseline_evidence_count}->{current_evidence_count}",
        f"tool_count={len(baseline_tool_names)}->{len(current_tool_names)}",
    ]

    if current_evidence_count > baseline_evidence_count:
        improvements.append(
            f"Coverage expanded from {baseline_evidence_count} to {current_evidence_count} recorded evidence items."
        )
    elif current_evidence_count < baseline_evidence_count:
        regressions.append(
            f"Coverage narrowed from {baseline_evidence_count} to {current_evidence_count} recorded evidence items; confirm the reduced path was intentional."
        )
    else:
        stable_findings.append(
            f"Recorded evidence count stayed stable at {current_evidence_count} items."
        )

    if added_tools:
        improvements.append(
            "Additional bounded tool paths were recorded in the current run: "
            + ", ".join(added_tools[:4])
            + "."
        )
    if removed_tools:
        regressions.append(
            "The current run did not reproduce these baseline tool paths: "
            + ", ".join(removed_tools[:4])
            + "."
        )
    if not added_tools and not removed_tools:
        stable_findings.append("The bounded tool-path set stayed consistent with the baseline session.")

    if current_manual_review_count < baseline_manual_review_count:
        improvements.append(
            f"Manual-review surface narrowed from {baseline_manual_review_count} to {current_manual_review_count} items."
        )
    elif current_manual_review_count > baseline_manual_review_count:
        regressions.append(
            f"Manual-review surface widened from {baseline_manual_review_count} to {current_manual_review_count} items."
        )

    if current_priority_count < baseline_priority_count:
        improvements.append(
            f"Priority contract findings narrowed from {baseline_priority_count} to {current_priority_count} items."
        )
    elif current_priority_count > baseline_priority_count:
        regressions.append(
            f"Priority contract findings increased from {baseline_priority_count} to {current_priority_count} items."
        )
    elif current_priority_count > 0:
        stable_findings.append(
            f"Priority contract findings stayed stable at {current_priority_count} items."
        )

    if current_casebook_gap_count < baseline_casebook_gap_count:
        improvements.append(
            f"Casebook gaps narrowed from {baseline_casebook_gap_count} to {current_casebook_gap_count} items."
        )
    elif current_casebook_gap_count > baseline_casebook_gap_count:
        regressions.append(
            f"Casebook gaps widened from {baseline_casebook_gap_count} to {current_casebook_gap_count} items."
        )
    elif current_casebook_gap_count > 0:
        stable_findings.append(
            f"Casebook gaps stayed stable at {current_casebook_gap_count} items."
        )

    if current_confidence != baseline_confidence:
        current_rank = _confidence_rank(current_confidence)
        baseline_rank = _confidence_rank(baseline_confidence)
        if current_rank > baseline_rank:
            improvements.append(
                f"Bounded confidence moved from {baseline_confidence or 'unavailable'} to {current_confidence or 'unavailable'}."
            )
        elif current_rank < baseline_rank:
            regressions.append(
                f"Bounded confidence moved from {baseline_confidence or 'unavailable'} to {current_confidence or 'unavailable'}."
            )
    elif current_confidence:
        stable_findings.append(
            f"Bounded confidence stayed at {current_confidence}."
        )

    summary = _cross_session_summary(improvements=improvements, regressions=regressions)
    if not improvements and not regressions and not stable_findings:
        stable_findings.append(
            "The before/after comparison remained limited because the two sessions exposed very similar recorded structure."
        )

    return CrossSessionComparison(
        baseline_session_id=baseline_session.session_id,
        current_session_id=session.session_id,
        baseline_source_path=baseline_source_path,
        summary=summary,
        improvements=improvements,
        regressions=regressions,
        stable_findings=stable_findings,
        notes=notes,
    )


def compare_hypotheses(session: ResearchSession) -> BranchComparison:
    """Compare branches conservatively using lifecycle and evidence richness."""

    compared_aspects = ["status", "score", "evidence_count", "priority"]
    if not session.hypotheses:
        return BranchComparison(
            compared_aspects=compared_aspects,
            summary="No hypothesis branches were available for comparative analysis.",
            notes=["No branch-level comparison was possible."],
        )

    evidence_counts = Counter(evidence.hypothesis_id for evidence in session.evidence)
    ranked = sorted(
        session.hypotheses,
        key=lambda hypothesis: (
            _status_rank(hypothesis.status),
            evidence_counts.get(hypothesis.hypothesis_id, 0),
            hypothesis.score,
            hypothesis.priority,
        ),
        reverse=True,
    )
    stronger = [ranked[0].hypothesis_id] if ranked else []
    weaker = [
        hypothesis.hypothesis_id
        for hypothesis in session.hypotheses
        if hypothesis.status == HypothesisStatus.REJECTED
    ]
    if not weaker and len(ranked) > 1:
        weaker = [ranked[-1].hypothesis_id]

    if len(session.hypotheses) == 1:
        summary = (
            "Only one hypothesis branch reached the comparative layer, so branch comparison remained limited."
        )
    else:
        summary = (
            "Hypothesis branches were compared using lifecycle status, recorded evidence count, and bounded "
            "branch scores. Executed or validated branches with recorded evidence were treated as relatively "
            "stronger support candidates, while rejected or unsupported branches remained weaker."
        )

    findings = [
        f"{hypothesis.hypothesis_id}: status={hypothesis.status.value}, score={hypothesis.score:.2f}, "
        f"evidence={evidence_counts.get(hypothesis.hypothesis_id, 0)}"
        for hypothesis in ranked
    ]
    return BranchComparison(
        hypothesis_ids=[hypothesis.hypothesis_id for hypothesis in session.hypotheses],
        compared_aspects=compared_aspects,
        summary=summary,
        stronger_branch_ids=stronger,
        weaker_branch_ids=weaker,
        notes=findings,
    )


def compare_tool_outcomes(session: ResearchSession) -> ToolComparison:
    """Compare tool outcomes conservatively using recorded evidence and job planning."""

    tool_names = _ordered_unique(
        [evidence.tool_name for evidence in session.evidence if evidence.tool_name]
        + [job.tool_name for job in session.jobs if job.tool_name]
    )
    experiment_types = _ordered_unique(
        [
            evidence.experiment_type
            for evidence in session.evidence
            if evidence.experiment_type
        ]
    )
    if not tool_names:
        return ToolComparison(
            consistency_summary="No local tool outcomes were available for comparison.",
            notes=["Tool comparison was skipped because no tool names were recorded."],
        )

    conclusion_lines = [
        f"{evidence.tool_name or evidence.source}: {evidence.conclusion or evidence.summary}"
        for evidence in session.evidence
    ]
    normalized_conclusions = {
        (evidence.conclusion or evidence.summary).strip().lower()
        for evidence in session.evidence
        if (evidence.conclusion or evidence.summary).strip()
    }
    conflicting_signals = conclusion_lines if len(normalized_conclusions) > 1 else []

    if len(tool_names) == 1:
        consistency_summary = (
            "Tool outcome comparison remained limited because the session produced one primary tool result."
        )
    elif conflicting_signals:
        consistency_summary = (
            "Recorded tool outcomes showed divergent or inconclusive signals across multiple bounded tool paths."
        )
    else:
        consistency_summary = (
            "Recorded tool outcomes remained broadly consistent across the available bounded local tool paths."
        )

    notes = [
        f"tool_count={len(tool_names)}",
        f"evidence_count={len(session.evidence)}",
    ]
    return ToolComparison(
        tool_names=tool_names,
        experiment_types=experiment_types,
        consistency_summary=consistency_summary,
        conflicting_signals=conflicting_signals,
        notes=notes,
    )


def summarize_tested_hypotheses(session: ResearchSession) -> list[str]:
    """Return short report-friendly branch summaries."""

    evidence_counts = Counter(evidence.hypothesis_id for evidence in session.evidence)
    return [
        f"{hypothesis.hypothesis_id}: {hypothesis.status.value}; score={hypothesis.score:.2f}; "
        f"evidence={evidence_counts.get(hypothesis.hypothesis_id, 0)}; {hypothesis.summary}"
        for hypothesis in session.hypotheses
    ]


def summarize_tool_usage(session: ResearchSession) -> list[str]:
    """Return short report-friendly tool summaries."""

    tool_counts = Counter(evidence.tool_name or evidence.source for evidence in session.evidence)
    summaries: list[str] = []
    for tool_name in _ordered_unique([job.tool_name for job in session.jobs if job.tool_name]):
        evidence_count = tool_counts.get(tool_name, 0)
        experiment_types = _ordered_unique(
            [
                evidence.experiment_type
                for evidence in session.evidence
                if evidence.tool_name == tool_name and evidence.experiment_type
            ]
        )
        experiment_hint = ", ".join(experiment_types) if experiment_types else "no recorded experiment type"
        summaries.append(
            f"{tool_name}: jobs={sum(1 for job in session.jobs if job.tool_name == tool_name)}, "
            f"evidence={evidence_count}, experiments={experiment_hint}"
        )
    return summaries


def collect_manual_review_items(
    session: ResearchSession,
    tool_comparison: ToolComparison | None = None,
) -> list[str]:
    """Collect bounded manual-review reminders from recorded session state."""

    items: list[str] = []
    if not session.evidence:
        items.append("Manual review is required because no local evidence was recorded.")
    if any(not evidence.deterministic for evidence in session.evidence):
        items.append("Manual review is required because at least one recorded result was not deterministic.")
    if any(
        hypothesis.status == HypothesisStatus.NEEDS_MANUAL_REVIEW
        for hypothesis in session.hypotheses
    ):
        items.append("At least one branch ended in needs_manual_review and should be inspected directly.")
    if any(
        _contains_manual_review_language(evidence.conclusion or "")
        or _contains_manual_review_language(" ".join(evidence.notes))
        for evidence in session.evidence
    ):
        items.append("At least one tool outcome already flagged manual review or unsupported handling.")
    if tool_comparison is not None and tool_comparison.conflicting_signals:
        items.append("Tool outcomes were not fully consistent and should be reviewed before any stronger claim.")
    return _ordered_unique(items)


def _comparative_summary(
    *,
    branch_comparison: BranchComparison,
    tool_comparison: ToolComparison,
    manual_review_items: list[str],
    cross_session_comparison: CrossSessionComparison | None = None,
) -> str:
    if cross_session_comparison is not None and cross_session_comparison.regressions:
        return (
            "Comparative analysis identified bounded before/after differences relative to the baseline session, "
            "including at least one possible regression or missing coverage path that still requires manual review."
        )
    if cross_session_comparison is not None and cross_session_comparison.improvements:
        return (
            "Comparative analysis identified bounded before/after differences relative to the baseline session, "
            "with narrower or better-supported signals on the current run."
        )
    if manual_review_items:
        return (
            "Comparative analysis identified bounded branch and tool differences, but manual review remains "
            "necessary before drawing stronger conclusions."
        )
    if len(branch_comparison.hypothesis_ids) <= 1 and len(tool_comparison.tool_names) <= 1:
        return (
            "Comparative analysis remained limited because the session produced only one primary branch and "
            "one primary tool outcome."
        )
    return (
        "Comparative analysis highlighted relatively stronger and weaker bounded research paths while preserving "
        "cautious evidence-first interpretation."
    )


def _status_rank(status: HypothesisStatus) -> int:
    return {
        HypothesisStatus.CLOSED: 7,
        HypothesisStatus.VALIDATED: 6,
        HypothesisStatus.OBSERVED_SIGNAL: 5,
        HypothesisStatus.RUNNING: 4,
        HypothesisStatus.PLANNED: 3,
        HypothesisStatus.EXPANDED: 2,
        HypothesisStatus.FORMALIZED: 1,
        HypothesisStatus.SEEDED: 0,
        HypothesisStatus.NEEDS_MANUAL_REVIEW: -1,
        HypothesisStatus.DEFERRED: -2,
        HypothesisStatus.REJECTED: -3,
    }.get(status, -4)


def _contains_manual_review_language(text: str) -> bool:
    lowered = text.lower()
    return any(
        token in lowered
        for token in ("manual review", "unsupported", "unavailable", "inconclusive", "error")
    )


def _ordered_unique(values: list[str | None]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value or "").strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _session_tool_names(session: ResearchSession) -> list[str]:
    return _ordered_unique(
        [evidence.tool_name for evidence in session.evidence if evidence.tool_name]
        + [job.tool_name for job in session.jobs if job.tool_name]
    )


def _session_manual_review_count(session: ResearchSession) -> int:
    if session.report is not None and session.report.manual_review_items:
        return len(session.report.manual_review_items)
    return len(collect_manual_review_items(session, compare_tool_outcomes(session)))


def _session_priority_finding_count(session: ResearchSession) -> int:
    if session.report is not None and session.report.contract_priority_findings:
        return len(session.report.contract_priority_findings)
    return 0


def _session_casebook_gap_count(session: ResearchSession) -> int:
    if session.report is not None and session.report.contract_casebook_gaps:
        return len(session.report.contract_casebook_gaps)
    return 0


def _session_confidence_value(session: ResearchSession) -> str | None:
    if session.report is not None:
        return session.report.confidence.value
    return None


def _confidence_rank(value: str | None) -> int:
    if value is None:
        return -1
    normalized = value.strip().lower()
    ordering = {
        ConfidenceLevel.MANUAL_REVIEW_REQUIRED.value: 0,
        ConfidenceLevel.INCONCLUSIVE.value: 1,
        ConfidenceLevel.LOW.value: 2,
        ConfidenceLevel.MEDIUM.value: 3,
        ConfidenceLevel.HIGH.value: 4,
    }
    return ordering.get(normalized, -1)


def _cross_session_summary(*, improvements: list[str], regressions: list[str]) -> str:
    if regressions and improvements:
        return (
            "Before/after comparison found bounded deltas relative to the baseline session, including both narrower "
            "signals and new or missing paths that still need review."
        )
    if regressions:
        return (
            "Before/after comparison found possible regressions or missing coverage relative to the baseline session."
        )
    if improvements:
        return (
            "Before/after comparison found narrower or better-supported bounded signals relative to the baseline session."
        )
    return "Before/after comparison remained broadly stable relative to the baseline session."
