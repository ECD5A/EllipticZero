from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from app.core.seed_parsing import (
    extract_contract_language,
    extract_contract_name,
    extract_contract_source_label,
)
from app.models.job import ComputeJob
from app.models.run_manifest import RunArtifactReference
from app.models.sandbox import ResearchMode
from app.models.session import ResearchSession
from app.storage.fingerprints import hash_file
from app.tools.smart_contract_utils import prioritize_contract_issues
from app.types import BranchType, HypothesisStatus


def ordered_unique(values: Iterable[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = str(value).strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def compose_evidence_summary(session: ResearchSession) -> str:
    summaries = [
        evidence.summary.strip()
        for evidence in session.evidence
        if evidence.summary.strip()
    ]
    if not summaries:
        return "No local evidence was recorded. Manual review is required before any claim."
    if len(summaries) == 1:
        return summaries[0]
    return " ".join(
        f"[{index}] {summary}"
        for index, summary in enumerate(summaries, start=1)
    )


def build_job_trace_data(raw_result: dict[str, object]) -> dict[str, object]:
    result = raw_result.get("result", {})
    result_data = result.get("result_data", {}) if isinstance(result, dict) else {}
    sandbox = raw_result.get("sandbox", {}) if isinstance(raw_result.get("sandbox"), dict) else {}

    issues = result_data.get("issues", []) if isinstance(result_data, dict) else []
    errors = result_data.get("errors", []) if isinstance(result_data, dict) else []
    cases = result_data.get("cases", []) if isinstance(result_data, dict) else []

    return {
        "job_id": raw_result.get("job_id"),
        "tool_name": raw_result.get("tool_name"),
        "tool_version": raw_result.get("tool_version"),
        "deterministic": raw_result.get("deterministic"),
        "timeout_seconds": raw_result.get("timeout_seconds"),
        "status": result.get("status") if isinstance(result, dict) else None,
        "conclusion": result.get("conclusion") if isinstance(result, dict) else None,
        "issue_count": len(issues) if isinstance(issues, list) else 0,
        "error_count": len(errors) if isinstance(errors, list) else 0,
        "case_count": len(cases) if isinstance(cases, list) else 0,
        "target_profile": sandbox.get("target_profile"),
        "sandbox_notes": sandbox.get("notes"),
    }


def build_local_experiment_summary(session: ResearchSession) -> list[str]:
    items: list[str] = []
    for evidence in session.evidence:
        role_label = " + ".join(evidence.selected_by_roles) if evidence.selected_by_roles else "Default planner"
        experiment_label = evidence.experiment_type or "local_experiment"
        pack_label = (
            f" via {evidence.selected_pack_name}:{evidence.pack_step_id}"
            if evidence.selected_pack_name and evidence.pack_step_id
            else (f" via {evidence.selected_pack_name}" if evidence.selected_pack_name else "")
        )
        outcome = (evidence.conclusion or evidence.summary).strip()
        if len(outcome) > 180:
            outcome = outcome[:177].rstrip() + "..."
        items.append(
            f"{role_label} -> {evidence.tool_name or evidence.source} [{experiment_label}]{pack_label}: {outcome}"
        )
    return ordered_unique(items)


def build_local_signal_summary(session: ResearchSession) -> list[str]:
    items: list[str] = []
    for evidence in session.evidence:
        result = evidence.raw_result.get("result", {})
        if not isinstance(result, dict):
            continue
        result_data = result.get("result_data", {})
        if not isinstance(result_data, dict):
            result_data = {}
        tool_name = evidence.tool_name or evidence.source
        if int(result_data.get("anomaly_count", 0) or 0) > 0:
            testbed_name = result_data.get("testbed_name", "bounded_testbed")
            items.append(
                f"{tool_name} surfaced {result_data.get('anomaly_count')} anomaly-bearing case(s) in {testbed_name}."
            )
            continue
        if int(result_data.get("finding_count", 0) or 0) > 0:
            detector_counts = result_data.get("detector_name_counts", {})
            strongest_detector = None
            if isinstance(detector_counts, dict) and detector_counts:
                strongest_detector = next(iter(detector_counts))
            if strongest_detector:
                items.append(
                    f"{tool_name} reported {result_data.get('finding_count')} detector finding(s); strongest detector: {strongest_detector}."
                )
            else:
                items.append(
                    f"{tool_name} reported {result_data.get('finding_count')} detector finding(s)."
                )
            continue
        issues = result_data.get("issues", [])
        if isinstance(issues, list) and issues:
            items.append(
                f"{tool_name} reported {len(issues)} bounded issue(s); strongest issue: {issues[0]}."
            )
            continue
        if result_data.get("counterexample") not in (None, "", "none", [], {}):
            items.append(
                f"{tool_name} produced a bounded counterexample: {result_data.get('counterexample')}."
            )
            continue
        if result_data.get("format_consistent") is False:
            items.append(f"{tool_name} found a bounded ECC format inconsistency.")
            continue
        if result_data.get("on_curve") is False:
            items.append(f"{tool_name} found a bounded on-curve failure signal.")
            continue
        if result_data.get("x_in_field_range") is False or result_data.get("y_in_field_range") is False:
            items.append(f"{tool_name} found a bounded field-range violation.")
            continue

    if not items:
        items.append("No anomaly-bearing local signal exceeded the bounded baseline in this session.")
    return ordered_unique(items)


def build_ecc_benchmark_summary(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    testbed_names: list[str] = []
    issue_counter: Counter[str] = Counter()
    anomaly_count = 0
    total_cases = 0

    for evidence in session.evidence:
        if evidence.tool_name != "ecc_testbed_tool":
            continue
        result = evidence.raw_result.get("result", {})
        if not isinstance(result, dict):
            continue
        result_data = result.get("result_data", {})
        if not isinstance(result_data, dict):
            continue
        testbed_name = _as_optional_str(result_data.get("testbed_name"))
        if testbed_name:
            testbed_names.append(testbed_name)
        anomaly_count += int(result_data.get("anomaly_count", 0) or 0)
        total_cases += int(result_data.get("case_count", 0) or 0)
        issue_type_counts = result_data.get("issue_type_counts", {})
        if isinstance(issue_type_counts, dict):
            for issue, count in issue_type_counts.items():
                issue_counter[str(issue)] += int(count or 0)

    if not testbed_names:
        return []

    family_labels = ordered_unique(_ecc_testbed_focus_label(name) for name in testbed_names)
    items: list[str] = []
    ecc_pack_label = _ecc_benchmark_pack_label(session.selected_pack_name)
    if ecc_pack_label:
        items.append(f"Selected ECC benchmark pack: {ecc_pack_label}.")
    items.append(
        "ECC benchmark packs exercised: "
        + ", ".join(ordered_unique(testbed_names))
        + f" | cases={total_cases} | anomaly-bearing={anomaly_count}."
    )
    if family_labels:
        items.append("Covered review families: " + ", ".join(family_labels) + ".")

    strongest_issues = [issue for issue, _ in issue_counter.most_common(3)]
    if strongest_issues:
        items.append("Strongest bounded benchmark issues: " + "; ".join(strongest_issues) + ".")

    coverage_rank = len(set(testbed_names))
    if coverage_rank >= 3:
        items.append("ECC benchmark posture: broad bounded coverage across encoding, family, and subgroup-style review paths.")
    elif coverage_rank >= 2:
        items.append("ECC benchmark posture: usable bounded coverage across more than one ECC review family.")
    else:
        items.append("ECC benchmark posture: narrow bounded coverage; expand local testbed breadth before stronger conclusions.")
    return ordered_unique(items)


def build_ecc_benchmark_posture(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    support_map = _collect_ecc_family_support(session)
    if not support_map:
        return []

    residual_labels = _collect_ecc_residual_labels(session)
    comparison_state = _collect_ecc_comparison_state(session)
    overall_label = "broad" if len(support_map) >= 3 else ("partial" if len(support_map) >= 2 else "narrow")
    items: list[str] = [
        f"ECC benchmark posture: overall={overall_label}; families={len(support_map)}; "
        f"pack={_ecc_benchmark_pack_label(session.selected_pack_name) or 'none'}."
    ]
    for family in _ordered_ecc_family_keys(support_map):
        labels = sorted(support_map[family])
        items.append(
            f"ECC benchmark posture for {family}: coverage={_ecc_support_coverage_label(labels, family in residual_labels)}; "
            f"support={', '.join(labels)}; baseline={comparison_state.get(family, 'unchanged')}."
        )
    return ordered_unique(items)[:5]


def build_ecc_family_coverage(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    support_map = _collect_ecc_family_support(session)
    if not support_map:
        return []

    residual_labels = _collect_ecc_residual_labels(session)
    items: list[str] = []
    for family in _ordered_ecc_family_keys(support_map):
        labels = sorted(support_map[family])
        items.append(
            f"ECC family coverage for {family}: breadth={_ecc_support_coverage_label(labels, family in residual_labels)}; "
            f"support={', '.join(labels)}; residual-risk={'yes' if family in residual_labels else 'no'}."
        )
    return ordered_unique(items)[:5]


def build_ecc_coverage_matrix(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    support_map = _collect_ecc_family_support(session)
    if not support_map:
        return []

    residual_labels = _collect_ecc_residual_labels(session)
    comparison_state = _collect_ecc_comparison_state(session)
    items: list[str] = []
    for family in sorted(support_map):
        labels = sorted(support_map[family])
        coverage = _ecc_support_coverage_label(labels, family in residual_labels)
        items.append(
            f"ECC coverage matrix for {family}: coverage={coverage}; support={', '.join(labels)}; "
            f"baseline={comparison_state.get(family, 'unchanged')}; residual-risk={'yes' if family in residual_labels else 'no'}."
        )
    return ordered_unique(items)[:5]


def build_ecc_benchmark_case_summaries(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "ecc_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "ecc_testbed"
        cases = int(result_data.get("case_count", 0) or 0)
        anomalies = int(result_data.get("anomaly_count", 0) or 0)
        issue_summary = _as_count_summary(result_data.get("issue_type_counts"))
        items.append(
            f"ECC benchmark case {testbed_name}: focus={_ecc_testbed_focus_label(testbed_name)}; "
            f"cases={cases}; anomaly-bearing={anomalies}; dominant issues={issue_summary or 'none'}."
        )
    return ordered_unique(items)[:5]


def build_ecc_review_focus(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    focus: list[str] = []
    for evidence in session.evidence:
        tool_name = evidence.tool_name or evidence.source
        result = evidence.raw_result.get("result", {})
        if not isinstance(result, dict):
            continue
        result_data = result.get("result_data", {})
        if not isinstance(result_data, dict):
            continue

        if tool_name == "ecc_testbed_tool":
            testbed_name = _as_optional_str(result_data.get("testbed_name")) or ""
            if testbed_name == "encoding_edge_corpus":
                focus.append(
                    "Focus encoding edges around compressed, uncompressed, and family-limited public-key forms before trusting downstream ECC handling."
                )
            elif testbed_name == "subgroup_cofactor_corpus":
                focus.append(
                    "Treat cofactor-bearing or subgroup-sensitive families as manual-review items until local subgroup and cofactor assumptions are explicitly bounded."
                )
            elif testbed_name == "curve_family_corpus":
                focus.append(
                    "Separate short-Weierstrass handling from Montgomery or Edwards family assumptions before interpreting ECC validation signals."
                )
            elif testbed_name == "curve_domain_corpus":
                focus.append(
                    "Confirm registry completeness for generator, order, and cofactor metadata before leaning on domain-derived ECC conclusions."
                )
            elif testbed_name == "twist_hygiene_corpus":
                focus.append(
                    "Treat twist-sensitive 25519-family handling as a distinct review lane until subgroup, cofactor, and family-specific validation assumptions are bounded."
                )
            elif testbed_name == "domain_completeness_corpus":
                focus.append(
                    "Keep generator, order, cofactor, and family-limited registry completeness explicit before relying on curve-domain conclusions."
                )
            elif testbed_name == "family_transition_corpus":
                focus.append(
                    "Keep transitions between short-Weierstrass, Montgomery, and Edwards handling explicit before comparing bounded ECC validation signals."
                )
        if tool_name == "ecc_point_format_tool" and _as_optional_str(result_data.get("encoding")) == "unknown":
            focus.append(
                "Re-check unsupported or ambiguous public-key encodings before treating the input as a bounded ECC point."
            )
        if tool_name == "ecc_consistency_check_tool":
            if result_data.get("on_curve_checked") is False:
                focus.append(
                    "Keep curve-family assumptions narrow when bounded on-curve validation could not run locally."
                )
            if result_data.get("x_in_field_range") is False or result_data.get("y_in_field_range") is False:
                focus.append(
                    "Review field-range violations before escalating any higher-level ECC interpretation."
                )
        issues = result_data.get("issues", [])
        if isinstance(issues, list):
            joined = " ".join(str(item) for item in issues).lower()
            if any(token in joined for token in ("subgroup", "cofactor", "twist")):
                focus.append(
                    "Treat subgroup, cofactor, and twist assumptions as active review items until the local family-specific validation path is explicit."
                )
            if "25519" in joined or "montgomery" in joined or "edwards" in joined:
                focus.append(
                    "Keep 25519-family handling separate from short-Weierstrass validation assumptions during bounded ECC review."
                )
    if not focus and build_ecc_benchmark_summary(session):
        focus.append(
            "Use the bounded ECC benchmark packs to narrow encoding, family, and subgroup assumptions before escalating conclusions."
        )
    return ordered_unique(focus)[:6]


def build_ecc_residual_risk(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    items: list[str] = []
    unresolved_25519 = False
    missing_domain = False
    subgroup_gap = False
    unsupported_encoding = False
    family_transition_gap = False

    for evidence in session.evidence:
        result = evidence.raw_result.get("result", {})
        if not isinstance(result, dict):
            continue
        result_data = result.get("result_data", {})
        if not isinstance(result_data, dict):
            continue
        issues = result_data.get("issues", [])
        if isinstance(issues, list):
            joined = " ".join(str(item) for item in issues).lower()
            unresolved_25519 = unresolved_25519 or "25519-family" in joined
            missing_domain = missing_domain or "missing bounded domain metadata" in joined
            subgroup_gap = subgroup_gap or "subgroup" in joined or "cofactor" in joined or "twist" in joined
            family_transition_gap = family_transition_gap or "family transition" in joined or "short-weierstrass" in joined
        if evidence.tool_name == "ecc_point_format_tool" and _as_optional_str(result_data.get("encoding")) == "unknown":
            unsupported_encoding = True
        if evidence.tool_name == "ecc_testbed_tool":
            testbed_name = _as_optional_str(result_data.get("testbed_name")) or ""
            unresolved_25519 = unresolved_25519 or testbed_name in {"encoding_edge_corpus", "curve_family_corpus"} and any(
                "25519" in str(case.get("case_id", "")).lower()
                for case in result_data.get("cases", [])
                if isinstance(case, dict) and case.get("anomaly_detected")
            )
            missing_domain = missing_domain or testbed_name == "domain_completeness_corpus"
            subgroup_gap = subgroup_gap or testbed_name == "twist_hygiene_corpus"
            family_transition_gap = family_transition_gap or testbed_name == "family_transition_corpus"

    if unsupported_encoding:
        items.append(
            "Residual risk remains around unsupported or ambiguous ECC encodings until bounded parsing rules are narrowed to the actual curve family."
        )
    if subgroup_gap:
        items.append(
            "Residual risk remains around subgroup, cofactor, or twist assumptions where local checks cannot yet validate the full family-specific hygiene path."
        )
    if missing_domain:
        items.append(
            "Residual risk remains around incomplete curve-domain metadata for higher-order or partially specified registry entries."
        )
    if unresolved_25519:
        items.append(
            "Residual risk remains around Montgomery or Edwards family handling because bounded short-Weierstrass checks do not prove 25519-family safety properties."
        )
    if family_transition_gap:
        items.append(
            "Residual risk remains around family transitions because bounded checks still separate short-Weierstrass, Montgomery, and Edwards validation assumptions."
        )
    if not items and build_ecc_benchmark_summary(session):
        items.append(
            "Residual ECC risk remains because the bounded benchmark layer still narrows only a subset of encoding, family, and subgroup assumptions."
        )
    return ordered_unique(items)[:5]


def build_ecc_signal_consensus(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    support_map = _collect_ecc_family_support(session)
    if not support_map:
        return []

    residual_labels = _collect_ecc_residual_labels(session)
    comparison_state = _collect_ecc_comparison_state(session)
    items: list[str] = []
    for family in _ordered_ecc_family_keys(support_map):
        labels = sorted(support_map[family])
        support_count = len(labels)
        status = "converging" if support_count >= 3 and family not in residual_labels else (
            "developing" if support_count >= 2 else "narrow"
        )
        delta = comparison_state.get(family)
        delta_text = f"; baseline delta={delta}" if delta is not None else ""
        items.append(
            f"ECC consensus for {family}: status={status}; support="
            + ", ".join(labels)
            + delta_text
            + "."
        )
    return ordered_unique(items)[:4]


def build_ecc_validation_matrix(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    support_map = _collect_ecc_family_support(session)
    if not support_map:
        return []

    residual_labels = _collect_ecc_residual_labels(session)
    comparison_state = _collect_ecc_comparison_state(session)
    items: list[str] = []
    for family in _ordered_ecc_family_keys(support_map):
        labels = sorted(support_map[family])
        support_count = len(labels)
        if support_count >= 3 and family not in residual_labels:
            posture = "boundedly supported"
        elif support_count >= 2:
            posture = "developing bounded support"
        else:
            posture = "narrow support"
        if family in residual_labels:
            posture += " with residual risk"
        items.append(
            f"ECC validation for {family}: posture={posture}; support="
            + ", ".join(labels)
            + f"; baseline={comparison_state.get(family, 'unchanged')}."
        )
    return ordered_unique(items)[:4]


def build_ecc_comparison_focus(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []
    if session.comparative_report is None or session.comparative_report.cross_session_comparison is None:
        return []

    comparison = session.comparative_report.cross_session_comparison
    comparison_state = _collect_ecc_comparison_state(session)
    items = [f"ECC baseline session: {comparison.baseline_session_id}."]
    improved = [family for family, state in comparison_state.items() if state == "narrowed"]
    regressions = [family for family, state in comparison_state.items() if state == "regression risk"]
    stable = [family for family, state in comparison_state.items() if state == "stable"]

    if improved:
        items.append("Narrowed ECC families: " + ", ".join(improved) + ".")
    if regressions:
        items.append("Re-check ECC families with regression risk first: " + ", ".join(regressions) + ".")
    if stable:
        items.append("Stable ECC carry-over: " + ", ".join(stable) + ".")
    if len(items) == 1:
        items.append(
            "No ECC-family-specific before/after delta rose above the bounded baseline; keep the strongest family under manual review."
        )
    return ordered_unique(items)[:4]


def build_ecc_benchmark_delta(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []
    if session.comparative_report is None or session.comparative_report.cross_session_comparison is None:
        return []

    support_map = _collect_ecc_family_support(session)
    comparison_state = _collect_ecc_comparison_state(session)
    residual_labels = _collect_ecc_residual_labels(session)
    comparison = session.comparative_report.cross_session_comparison
    items: list[str] = [
        f"ECC benchmark delta anchored to baseline session {comparison.baseline_session_id}."
    ]
    for family in _ordered_ecc_family_keys(support_map):
        state = comparison_state.get(family)
        if state is None:
            continue
        support_labels = ", ".join(sorted(support_map[family]))
        residual = "yes" if family in residual_labels else "no"
        items.append(
            f"ECC benchmark delta for {family}: {state}; current support={support_labels}; residual-risk={residual}."
        )
    if len(items) == 1:
        items.append(
            "ECC benchmark delta stayed close to the bounded baseline; no family-specific movement rose above the current support threshold."
        )
    return ordered_unique(items)[:4]


def build_ecc_regression_summary(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []
    if session.comparative_report is None or session.comparative_report.cross_session_comparison is None:
        return []

    support_map = _collect_ecc_family_support(session)
    comparison_state = _collect_ecc_comparison_state(session)
    residual_labels = _collect_ecc_residual_labels(session)
    comparison = session.comparative_report.cross_session_comparison
    items: list[str] = [f"ECC regression watch anchored to baseline session {comparison.baseline_session_id}."]
    for family in _ordered_ecc_family_keys(support_map):
        labels = ", ".join(sorted(support_map[family]))
        items.append(
            f"ECC regression summary for {family}: state={comparison_state.get(family, 'unchanged')}; "
            f"support={labels}; residual-risk={'yes' if family in residual_labels else 'no'}."
        )
    return ordered_unique(items)[:5]


def build_ecc_review_queue(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    support_map = _collect_ecc_family_support(session)
    residual_labels = _collect_ecc_residual_labels(session)
    comparison_state = _collect_ecc_comparison_state(session)
    if not support_map:
        return []

    items: list[str] = []
    for family in _ordered_ecc_family_keys(support_map):
        if family not in residual_labels and comparison_state.get(family) == "narrowed":
            continue
        support_labels = ", ".join(sorted(support_map[family]))
        items.append(
            f"ECC review queue: re-check {family} first; current support={support_labels}; baseline={comparison_state.get(family, 'unchanged')}."
        )
    if not items:
        items.append(
            "ECC review queue: preserve the strongest family-specific benchmark path and re-run it only if new family-limited inputs or baseline deltas appear."
        )
    return ordered_unique(items)[:4]


def build_ecc_triage_snapshot(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    support_map = _collect_ecc_family_support(session)
    if not support_map:
        return []

    residual_labels = _collect_ecc_residual_labels(session)
    comparison_state = _collect_ecc_comparison_state(session)
    review_queue = build_ecc_review_queue(session)
    validation_matrix = build_ecc_validation_matrix(session)
    benchmark_delta = build_ecc_benchmark_delta(session)

    def _family_rank(family: str) -> tuple[int, int, str]:
        unresolved = 0 if family in residual_labels else 1
        support_width = -len(support_map.get(family, set()))
        return (unresolved, support_width, family)

    primary_family = sorted(support_map, key=_family_rank)[0]
    support_labels = ", ".join(sorted(support_map[primary_family]))
    items = [
        f"ECC triage snapshot - primary family: {primary_family}; support={support_labels}; "
        f"baseline={comparison_state.get(primary_family, 'unchanged')}; "
        f"residual-risk={'yes' if primary_family in residual_labels else 'no'}."
    ]

    if validation_matrix:
        items.append("ECC triage snapshot - validation posture: " + _trim_sentence(validation_matrix[0], 260))
    if benchmark_delta:
        items.append("ECC triage snapshot - before/after delta: " + _trim_sentence(benchmark_delta[0], 260))
    if review_queue:
        items.append("ECC triage snapshot - next ECC check: " + _trim_sentence(review_queue[0], 260))

    return ordered_unique(items)[:4]


def build_ecc_exit_criteria(session: ResearchSession) -> list[str]:
    if not _is_ecc_session(session):
        return []

    support_map = _collect_ecc_family_support(session)
    residual_labels = _collect_ecc_residual_labels(session)
    if not support_map:
        return []

    items: list[str] = []
    for family in _ordered_ecc_family_keys(support_map):
        if family == "encoding":
            items.append(
                "ECC exit criteria for encoding: ambiguous or unsupported encoding paths should disappear, or remain explicitly isolated from downstream curve-family conclusions."
            )
        elif family == "subgroup/cofactor/twist":
            items.append(
                "ECC exit criteria for subgroup/cofactor/twist: family-specific hygiene assumptions should narrow under repeated bounded checks, or remain explicitly manual-review-only."
            )
        elif family == "family transitions":
            items.append(
                "ECC exit criteria for family transitions: short-Weierstrass, Montgomery, and Edwards assumptions should stay separated without new contradictory bounded signals."
            )
        elif family == "domain completeness":
            items.append(
                "ECC exit criteria for domain completeness: generator, order, cofactor, and registry completeness gaps should narrow before stronger curve-domain claims."
            )
    if residual_labels:
        items.append(
            "Residual ECC families should either narrow under a repeated bounded benchmark pass or remain clearly marked as unresolved manual-review lanes."
        )
    return ordered_unique(items)[:5]


def build_evidence_profile(session: ResearchSession) -> list[str]:
    tool_names = ordered_unique((evidence.tool_name or evidence.source) for evidence in session.evidence)
    experiment_types = ordered_unique(
        evidence.experiment_type for evidence in session.evidence if evidence.experiment_type
    )
    artifact_count = sum(len(evidence.artifact_paths) for evidence in session.evidence)
    if _is_smart_contract_session(session):
        domain_label = "smart-contract audit"
    elif _is_ecc_session(session):
        domain_label = "ecc research"
    else:
        domain_label = "bounded research"

    items = [
        f"Evidence profile: domain={domain_label}; evidence={len(session.evidence)}; tools={len(tool_names)}; experiment-types={len(experiment_types)}; artifacts={artifact_count}."
    ]
    if session.selected_pack_name:
        items.append(
            f"Pack provenance: selected={session.selected_pack_name}; executed steps={len(session.executed_pack_steps)}."
        )
    if session.research_target is not None:
        items.append(
            f"Target anchor: kind={session.research_target.target_kind}; profile={session.research_target.target_profile or 'unknown'}; origin={session.research_target.target_origin}."
        )
    if session.comparison_baseline_session_id or (
        session.comparative_report is not None and session.comparative_report.cross_session_comparison is not None
    ):
        items.append(
            "Comparison anchor: "
            + (
                f"baseline={session.comparison_baseline_session_id or session.comparative_report.cross_session_comparison.baseline_session_id}; "
                "before/after available."
            )
        )
    return ordered_unique(items)[:4]


def build_evidence_coverage_summary(session: ResearchSession) -> list[str]:
    tool_names = ordered_unique((evidence.tool_name or evidence.source) for evidence in session.evidence)
    experiment_types = ordered_unique(
        evidence.experiment_type for evidence in session.evidence if evidence.experiment_type
    )
    artifact_count = sum(len(evidence.artifact_paths) for evidence in session.evidence)
    tool_backed_count = sum(1 for evidence in session.evidence if evidence.tool_name)
    manual_review_count = len(session.report.manual_review_items) if session.report is not None else 0
    finding_card_count = len(session.report.contract_finding_cards) if session.report is not None else 0

    if _is_smart_contract_session(session):
        domain_label = "smart-contract audit"
    elif _is_ecc_session(session):
        domain_label = "ECC research"
    else:
        domain_label = "bounded research"

    items = [
        f"Evidence coverage: domain={domain_label}; evidence={len(session.evidence)}; "
        f"tool-backed={tool_backed_count}; tools={len(tool_names)}; "
        f"experiment-types={len(experiment_types)}; artifacts={artifact_count}."
    ]
    if session.executed_pack_steps or session.selected_pack_name:
        items.append(
            f"Benchmark coverage: selected-pack={session.selected_pack_name or 'none'}; "
            f"executed-steps={len(session.executed_pack_steps)}; "
            f"recommended-packs={len(session.recommended_pack_names)}."
        )
    if finding_card_count or manual_review_count:
        items.append(
            f"Review coverage: finding-cards={finding_card_count}; "
            f"manual-review-items={manual_review_count}."
        )
    if session.comparative_report is not None:
        comparison_ready = session.comparative_report.cross_session_comparison is not None
        items.append(
            "Comparison coverage: "
            f"branch-comparisons={len(session.comparative_report.branch_comparisons)}; "
            f"tool-comparisons={len(session.comparative_report.tool_comparisons)}; "
            f"before-after={'yes' if comparison_ready else 'no'}."
        )
    return ordered_unique(items)[:4]


def build_calibration_blockers(session: ResearchSession) -> list[str]:
    if session.report is None:
        return []

    tool_names = ordered_unique((evidence.tool_name or evidence.source) for evidence in session.evidence)
    items: list[str] = []
    if len(tool_names) < 2:
        items.append(
            "Calibration blocker: only one bounded tool path contributed evidence; repeat under a second local check before stronger conclusions."
        )
    if session.report.regression_flags:
        items.append(
            "Calibration blocker: before/after comparison still shows regression-like deltas or missing reproduction against the baseline."
        )
    if _is_smart_contract_session(session):
        if session.report.contract_casebook_gaps:
            items.append(
                "Calibration blocker: repo-casebook coverage still has open gaps, so strongest contract lanes remain only partially bounded."
            )
        if session.report.contract_manual_review_items:
            items.append(
                "Calibration blocker: contract manual-review items remain open across privileged, value-flow, or protocol-specific paths."
            )
    elif _is_ecc_session(session):
        if session.report.ecc_residual_risk:
            items.append(
                "Calibration blocker: ECC residual risk remains around family-specific encoding, subgroup, cofactor, twist, or domain assumptions."
            )
        if not session.report.ecc_comparison_focus:
            items.append(
                "Calibration blocker: no ECC before/after baseline is attached yet, so family-level narrowing still relies on one bounded run."
            )
    if not items and session.report.confidence.value in {"medium", "high"}:
        items.append(
            "No dominant calibration blocker exceeded the bounded threshold; remaining uncertainty is structural rather than caused by one unresolved gap."
        )
    return ordered_unique(items)[:5]


def build_reproducibility_summary(session: ResearchSession) -> list[str]:
    outputs: list[str] = []
    if session.session_file_path:
        outputs.append("session")
    if session.trace_file_path:
        outputs.append("trace")
    if session.comparative_report_file_path:
        outputs.append("comparative-report")
    if session.bundle_dir:
        outputs.append("bundle")

    items: list[str] = []
    if outputs:
        items.append("Reproducibility outputs recorded: " + ", ".join(outputs) + ".")
    artifact_count = sum(len(evidence.artifact_paths) for evidence in session.evidence)
    if artifact_count:
        items.append(f"Local evidence artifacts referenced for export: {artifact_count}.")
    if outputs:
        items.append(
            "Approved-root export policy keeps session, trace, and artifact copies bounded to the local storage directories."
        )
    if session.selected_pack_name:
        items.append(
            f"Pack and step provenance preserved for replay: {session.selected_pack_name}; steps={len(session.executed_pack_steps)}."
        )
    if session.comparison_baseline_session_id:
        items.append(
            f"Baseline linkage preserved for replay/compare: {session.comparison_baseline_session_id}."
        )
    return ordered_unique(items)[:4]


def build_toolchain_fingerprint_summary(session: ResearchSession) -> list[str]:
    tool_names = ordered_unique((evidence.tool_name or evidence.source) for evidence in session.evidence)
    metadata_snapshots = unique_metadata_snapshots(session)
    version_pairs = _tool_version_pairs(metadata_snapshots)

    items = [
        f"Toolchain fingerprint: tools={len(tool_names)}; "
        f"metadata-snapshots={len(metadata_snapshots)}; jobs={len(session.jobs)}."
    ]
    if version_pairs:
        items.append("Tool versions: " + ", ".join(version_pairs[:6]) + ".")
    if session.plugin_metadata:
        loaded = sum(1 for item in session.plugin_metadata if item.load_status == "loaded")
        items.append(
            f"Plugin fingerprint: loaded={loaded}; total={len(session.plugin_metadata)}."
        )
    if session.is_replay:
        items.append(
            f"Replay fingerprint: source={session.replay_source_type or 'unknown'}; "
            f"mode={session.replay_mode or 'conservative'}."
        )
    return ordered_unique(items)[:4]


def _tool_version_pairs(metadata_snapshots: list[dict[str, Any]]) -> list[str]:
    pairs: list[str] = []
    for metadata in metadata_snapshots:
        name = _metadata_value(metadata, "name") or _metadata_value(metadata, "tool_name")
        version = _metadata_value(metadata, "version") or _metadata_value(metadata, "tool_version")
        if not name:
            continue
        pairs.append(f"{name}={version or 'unknown'}")
    return ordered_unique(pairs)


def _metadata_value(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def build_quality_gates(session: ResearchSession) -> list[str]:
    if session.report is None:
        return []

    tool_names = ordered_unique((evidence.tool_name or evidence.source) for evidence in session.evidence)
    comparison_ready = bool(
        session.comparative_report is not None
        and session.comparative_report.cross_session_comparison is not None
    )
    outputs = [
        name
        for name, present in (
            ("session", bool(session.session_file_path)),
            ("trace", bool(session.trace_file_path)),
            ("comparative", bool(session.comparative_report_file_path)),
            ("bundle", bool(session.bundle_dir)),
        )
        if present
    ]
    evidence_status = "pass" if len(session.evidence) >= 2 and len(tool_names) >= 2 else "watch"
    items = [
        f"Quality gate evidence-depth: {evidence_status}; evidence={len(session.evidence)}; tool-paths={len(tool_names)}."
    ]
    if _is_smart_contract_session(session):
        if session.report.contract_benchmark_posture:
            items.append("Quality gate contract benchmark: " + session.report.contract_benchmark_posture[0])
    elif _is_ecc_session(session):
        if session.report.ecc_benchmark_posture:
            items.append("Quality gate ECC benchmark: " + session.report.ecc_benchmark_posture[0])
        if session.report.ecc_coverage_matrix:
            items.append("Quality gate ECC coverage: " + session.report.ecc_coverage_matrix[0])
    items.append(
        "Quality gate comparison: "
        + ("ready" if comparison_ready else "pending")
        + "; baseline="
        + (session.comparison_baseline_session_id or "none")
        + "."
    )
    items.append(
        "Quality gate reproducibility: "
        + ("ready" if {"session", "trace", "bundle"}.issubset(set(outputs)) else "partial")
        + "; outputs="
        + (", ".join(outputs) if outputs else "none")
        + "."
    )
    if session.report.calibration_blockers:
        items.append("Quality gate blockers: open; " + session.report.calibration_blockers[0])
    else:
        items.append("Quality gate blockers: no dominant blocker exceeded the bounded threshold.")
    return ordered_unique(items)[:5]


def build_hardening_summary(session: ResearchSession) -> list[str]:
    if session.report is None:
        return []

    loaded_plugins = [item.plugin_name for item in session.plugin_metadata if item.load_status == "loaded"]
    blocked_plugins = [
        item.plugin_name
        for item in session.plugin_metadata
        if item.load_status != "loaded"
        and any("safety checks" in note.lower() for note in item.notes)
    ]
    items = [
        "Hardening posture: plugin safety gate remains active; "
        f"loaded={len(loaded_plugins)}; blocked={len(blocked_plugins)}."
    ]
    items.append(
        "Hardening posture: exportable session snapshots, traces, and artifacts stay bounded to approved local roots for artifacts, math workspaces, sessions, and traces."
    )
    if session.bundle_dir:
        items.append(
            "Hardening posture: reproducibility bundles preserve focus, comparison readiness, and quality/hardening summaries in overview.json."
        )
    if session.report.before_after_comparison:
        items.append(
            "Hardening posture: before/after linkage is preserved so bounded regressions can be replayed against the saved baseline."
        )
    elif session.comparison_baseline_session_id:
        items.append(
            f"Hardening posture: baseline anchor is recorded for later bounded replay ({session.comparison_baseline_session_id})."
        )
    if _is_smart_contract_session(session) and session.report.contract_manual_review_items:
        items.append(
            "Hardening posture: contract manual-review lanes stay explicit instead of being upgraded into automated findings."
        )
    elif _is_ecc_session(session) and session.report.ecc_residual_risk:
        items.append(
            "Hardening posture: ECC residual-family risks remain explicit instead of being smoothed into stronger claims."
        )
    return ordered_unique(items)[:5]


def build_validation_posture(session: ResearchSession) -> list[str]:
    if session.report is None:
        return []

    items = [
        f"Validation posture: confidence={session.report.confidence.value}; evidence={len(session.evidence)}; comparative={'yes' if bool(session.report.before_after_comparison) else 'no'}."
    ]
    if _is_smart_contract_session(session):
        if session.report.contract_benchmark_posture:
            items.append("Smart-contract benchmark posture: " + session.report.contract_benchmark_posture[0])
        if session.report.contract_toolchain_alignment:
            items.append("Smart-contract support path: " + session.report.contract_toolchain_alignment[0])
    elif _is_ecc_session(session):
        if session.report.ecc_validation_matrix:
            items.append("ECC validation posture: " + session.report.ecc_validation_matrix[0])
        if session.report.ecc_coverage_matrix:
            items.append("ECC coverage posture: " + session.report.ecc_coverage_matrix[0])
        if session.report.ecc_benchmark_delta:
            items.append("ECC baseline posture: " + session.report.ecc_benchmark_delta[0])
    if session.report.calibration_blockers:
        items.append("Primary blocker: " + session.report.calibration_blockers[0])
    return ordered_unique(items)[:4]


def build_shared_follow_up(session: ResearchSession) -> list[str]:
    if session.report is None:
        return []

    items: list[str] = []
    if session.report.calibration_blockers:
        items.append("Address the dominant calibration blocker before escalating any bounded finding.")
    if not session.report.before_after_comparison:
        items.append("Attach a saved bounded baseline run before treating the current session as a stable before/after reference.")
    if _is_smart_contract_session(session):
        if session.report.contract_review_queue:
            items.append("Smart-contract follow-up: " + session.report.contract_review_queue[0])
    elif _is_ecc_session(session):
        if session.report.ecc_review_queue:
            items.append("ECC follow-up: " + session.report.ecc_review_queue[0])
        if session.report.ecc_exit_criteria:
            items.append("ECC exit check: " + session.report.ecc_exit_criteria[0])
    if session.report.reproducibility_summary:
        items.append("Preserve the current reproducibility bundle and manifest focus summary before the next bounded replay.")
    return ordered_unique(items)[:4]


def build_manifest_focus_summary(session: ResearchSession) -> list[str]:
    if session.report is None:
        return []

    focus: list[str] = []
    if _is_smart_contract_session(session):
        focus.extend(session.report.contract_triage_snapshot[:2])
        focus.extend(session.report.remediation_delta_summary[:1])
        focus.extend(session.report.contract_repo_triage[:2])
        focus.extend(session.report.contract_review_focus[:1])
    elif _is_ecc_session(session):
        focus.extend(session.report.ecc_triage_snapshot[:2])
        focus.extend(session.report.remediation_delta_summary[:1])
        focus.extend(session.report.ecc_benchmark_posture[:1])
        focus.extend(session.report.ecc_coverage_matrix[:1])
        focus.extend(session.report.ecc_validation_matrix[:1])
        focus.extend(session.report.ecc_review_queue[:1])
        focus.extend(session.report.ecc_review_focus[:1])
    else:
        focus.extend(session.report.recommendations[:2])
    focus.extend(session.report.quality_gates[:1])
    focus.extend(session.report.before_after_comparison[:1])
    if not focus:
        focus.extend(session.report.confidence_rationale[:2])
    if not focus:
        focus.extend(session.report.recommendations[:2])
    if not focus and session.report.summary:
        focus.append(session.report.summary)
    return ordered_unique(focus)[:4]


def build_confidence_rationale(session: ResearchSession) -> list[str]:
    if session.report is None:
        return []

    evidence_count = len(session.evidence)
    tool_names = ordered_unique((evidence.tool_name or evidence.source) for evidence in session.evidence)
    validated_count = sum(1 for hypothesis in session.hypotheses if hypothesis.status == HypothesisStatus.VALIDATED)
    observed_count = sum(1 for hypothesis in session.hypotheses if hypothesis.status == HypothesisStatus.OBSERVED_SIGNAL)
    manual_review_count = sum(
        1 for hypothesis in session.hypotheses if hypothesis.status == HypothesisStatus.NEEDS_MANUAL_REVIEW
    )
    items = [
        f"Bounded confidence={session.report.confidence.value}; evidence={evidence_count}; tools={len(tool_names)}; validated hypotheses={validated_count}; observed signals={observed_count}; manual-review hypotheses={manual_review_count}."
    ]

    if tool_names:
        items.append("Tool diversity contributing to calibration: " + ", ".join(tool_names[:6]) + ".")
    if session.report.evidence_profile:
        items.append("Evidence anchors: " + "; ".join(session.report.evidence_profile[:2]))
    if session.report.calibration_blockers:
        items.append("Current calibration blockers: " + "; ".join(session.report.calibration_blockers[:2]))

    if _is_smart_contract_session(session):
        lane_candidates = _collect_contract_alignment_lanes(session)
        support_labels = _casebook_support_labels(session)
        casebook_names = ordered_unique(
            [
                _as_optional_str(_extract_result(evidence)[1].get("testbed_name")) or "contract_testbed"
                for evidence in session.evidence
                if (evidence.tool_name or "") == "contract_testbed_tool"
            ]
        )
        priority_count = len(session.report.contract_priority_findings)
        if lane_candidates:
            items.append(
                f"Repo-scale anchors: strongest lanes={min(3, len(lane_candidates))}; priority findings={priority_count}; support vectors={', '.join(support_labels[:4] or ['inventory-only'])}."
            )
        if casebook_names:
            items.append("Benchmark anchors: " + ", ".join(casebook_names[:4]) + ".")
        if session.report.contract_casebook_gaps or session.report.contract_manual_review_items:
            items.append(
                "Confidence remains bounded by unresolved repo-casebook gaps or manual-review items that still need a narrower follow-up pass."
            )
    elif _is_ecc_session(session):
        ecc_casebooks = ordered_unique(
            [
                _as_optional_str(_extract_result(evidence)[1].get("testbed_name")) or "ecc_testbed"
                for evidence in session.evidence
                if (evidence.tool_name or "") == "ecc_testbed_tool"
            ]
        )
        if ecc_casebooks:
            items.append("ECC calibration anchors: " + ", ".join(ecc_casebooks[:4]) + ".")
        if session.report.ecc_residual_risk:
            items.append(
                "Confidence remains bounded by family-specific residual risk around encoding, subgroup, cofactor, or curve-family assumptions."
            )

    if session.report.before_after_comparison:
        items.append("Cross-session comparison contributed additional calibration against a saved bounded baseline.")

    return ordered_unique(items)[:6]


def build_contract_overview(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    seed_text = session.seed.raw_text
    source_label = extract_contract_source_label(seed_text)
    language = extract_contract_language(seed_text) or "solidity"
    contract_name = extract_contract_name(seed_text)
    parser_result = _first_contract_result(session, "contract_parser_tool")
    compile_result = _first_contract_result(session, "contract_compile_tool")

    contract_names = _as_str_list(parser_result.get("contract_names")) if parser_result else []
    if not contract_names and compile_result:
        contract_names = _as_str_list(compile_result.get("compiled_contract_names"))
    interface_names = _as_str_list(parser_result.get("interface_names")) if parser_result else []
    library_names = _as_str_list(parser_result.get("library_names")) if parser_result else []
    imports = _as_str_list(parser_result.get("imports")) if parser_result else []
    function_names = _as_str_list(parser_result.get("function_names")) if parser_result else []
    pragma = _as_optional_str(parser_result.get("pragma")) if parser_result else None

    all_named_units = contract_names or ([contract_name] if contract_name else [])
    unit_bits: list[str] = []
    if all_named_units:
        unit_bits.append(f"contracts: {', '.join(all_named_units)}")
    if interface_names:
        unit_bits.append(f"interfaces: {', '.join(interface_names)}")
    if library_names:
        unit_bits.append(f"libraries: {', '.join(library_names)}")

    lines: list[str] = []
    first_line_bits = [f"language: {language}"]
    if source_label:
        first_line_bits.insert(0, f"source: {source_label}")
    if unit_bits:
        first_line_bits.append("; ".join(unit_bits))
    lines.append(" | ".join(first_line_bits))

    detail_bits: list[str] = []
    if pragma:
        detail_bits.append(f"pragma: {pragma}")
    if function_names:
        shown_functions = ", ".join(function_names[:6])
        suffix = "" if len(function_names) <= 6 else ", ..."
        detail_bits.append(f"functions: {len(function_names)} ({shown_functions}{suffix})")
    if imports:
        detail_bits.append(f"imports: {len(imports)}")
    if detail_bits:
        lines.append(" | ".join(detail_bits))

    return ordered_unique(lines)


def build_contract_inventory_summary(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_inventory_tool":
            continue
        _, result_data = _extract_result(evidence)
        root_path = _as_optional_str(result_data.get("root_path"))
        file_count = int(result_data.get("file_count", 0) or 0)
        solidity_count = int(result_data.get("solidity_file_count", 0) or 0)
        vyper_count = int(result_data.get("vyper_file_count", 0) or 0)
        if root_path:
            items.append(
                f"Scoped contract root: {root_path} | files: {file_count} | solidity={solidity_count} | vyper={vyper_count}"
            )
        scope_summary = _as_str_list(result_data.get("scope_summary"))
        if scope_summary:
            items.append("Scope split: " + ", ".join(scope_summary[:4]))
        candidate_files = _as_str_list(result_data.get("candidate_files"))
        if candidate_files:
            shown = ", ".join(candidate_files[:5])
            suffix = "" if len(candidate_files) <= 5 else ", ..."
            items.append(f"Candidate review files: {shown}{suffix}")
        dependency_candidate_files = _as_str_list(result_data.get("dependency_candidate_files"))
        if dependency_candidate_files:
            shown = ", ".join(dependency_candidate_files[:4])
            suffix = "" if len(dependency_candidate_files) <= 4 else ", ..."
            items.append(f"Dependency review files: {shown}{suffix}")
        entrypoint_candidates = _as_str_list(result_data.get("entrypoint_candidates"))
        if entrypoint_candidates:
            shown = ", ".join(entrypoint_candidates[:5])
            suffix = "" if len(entrypoint_candidates) <= 5 else ", ..."
            items.append(f"Entrypoint review files: {shown}{suffix}")
        pragma_summary = _as_str_list(result_data.get("pragma_summary"))
        if pragma_summary:
            items.append(f"Pragma summary: {', '.join(pragma_summary[:5])}")
        import_graph_summary = _as_str_list(result_data.get("import_graph_summary"))
        if import_graph_summary:
            items.append(f"Import graph: {', '.join(import_graph_summary[:3])}")
        shared_dependency_files = _as_str_list(result_data.get("shared_dependency_files"))
        if shared_dependency_files:
            items.append(f"Shared dependency files: {', '.join(shared_dependency_files[:4])}")
        dependency_review_files = _as_str_list(result_data.get("dependency_review_files"))
        if dependency_review_files:
            items.append(f"Risk-linked dependency files: {', '.join(dependency_review_files[:4])}")
        entrypoint_flow_summaries = _as_str_list(result_data.get("entrypoint_flow_summaries"))
        if entrypoint_flow_summaries:
            items.append(f"Entrypoint flows: {', '.join(entrypoint_flow_summaries[:3])}")
        entrypoint_review_lanes = _as_str_list(result_data.get("entrypoint_review_lanes"))
        if entrypoint_review_lanes:
            items.append(f"Review lanes: {', '.join(entrypoint_review_lanes[:3])}")
        risk_family_lane_summaries = _as_str_list(result_data.get("risk_family_lane_summaries"))
        if risk_family_lane_summaries:
            items.append(f"Risk family lanes: {', '.join(risk_family_lane_summaries[:3])}")
        entrypoint_function_family_priorities = _as_str_list(result_data.get("entrypoint_function_family_priorities"))
        if entrypoint_function_family_priorities:
            items.append(f"Function-family priorities: {', '.join(entrypoint_function_family_priorities[:3])}")
        risk_linked_files = _as_str_list(result_data.get("risk_linked_files"))
        if risk_linked_files:
            items.append(f"Risk-linked files: {', '.join(risk_linked_files[:4])}")
        largest_files = _as_str_list(result_data.get("largest_files"))
        if largest_files:
            items.append(f"Largest files: {', '.join(largest_files[:4])}")
    return ordered_unique(items)


def build_contract_protocol_map(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    inventory = _first_contract_result(session, "contract_inventory_tool")
    if not inventory:
        return []

    entrypoint_candidates = _as_str_list(inventory.get("entrypoint_candidates"))
    shared_dependency_files = _as_str_list(inventory.get("shared_dependency_files"))
    review_lanes = _as_str_list(inventory.get("entrypoint_review_lanes"))
    risk_family_lane_summaries = _as_str_list(inventory.get("risk_family_lane_summaries"))
    function_family_priorities = _as_str_list(inventory.get("entrypoint_function_family_priorities"))
    risk_linked_files = _as_str_list(inventory.get("risk_linked_files"))

    items: list[str] = []
    if entrypoint_candidates:
        shown = ", ".join(entrypoint_candidates[:5])
        suffix = "" if len(entrypoint_candidates) <= 5 else ", ..."
        items.append(f"Entrypoints: {shown}{suffix}.")

    for title, families in (
        ("Authority / upgrade contour", {"upgrade/control", "proxy/storage"}),
        ("Asset / accounting contour", {"asset-flow", "token/allowance", "vault/share", "reserve/fee/debt"}),
        ("Pricing / collateral contour", {"oracle/price", "collateral/liquidation"}),
        (
            "Signature / entropy / lifecycle contour",
            {"permit/signature", "entropy/time", "assembly", "lifecycle/destruction"},
        ),
    ):
        line = _build_contract_protocol_module_line(
            title=title,
            families=families,
            function_family_priorities=function_family_priorities,
            risk_family_lane_summaries=risk_family_lane_summaries,
            review_lanes=review_lanes,
            risk_linked_files=risk_linked_files,
        )
        if line:
            items.append(line)

    if shared_dependency_files:
        items.append("Shared hubs: " + ", ".join(shared_dependency_files[:3]) + ".")

    casebook_line = _build_contract_protocol_casebook_line(session)
    if casebook_line:
        items.append(casebook_line)

    return ordered_unique(items)[:7]


def build_contract_protocol_invariants(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    lane_candidates = _collect_contract_alignment_lanes(session)
    toolchain_state = _collect_contract_toolchain_state(session)
    family_hits = _collect_contract_family_hits(session)
    ordered_families = _ordered_contract_family_priority_list(lane_candidates, family_hits)

    items: list[str] = []
    for family in ordered_families[:5]:
        lane_label = next(
            (label for label, families in lane_candidates if family in families),
            None,
        )
        support_labels, gap_labels = _contract_lane_alignment_labels(
            families=[family],
            toolchain_state=toolchain_state,
        )
        invariant_line = _contract_protocol_invariant_line(family)
        line = f"{_contract_follow_up_family_label(family).capitalize()} invariant: {invariant_line}"
        if lane_label:
            line += f" Strongest lane: {lane_label}."
        else:
            line += "."
        if support_labels:
            line += " Current support: " + ", ".join(support_labels[:3]) + "."
        if gap_labels:
            line += " Gaps: " + "; ".join(gap_labels[:2]) + "."
        items.append(line)

    return ordered_unique(items)[:6]


def build_contract_signal_consensus(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    lane_candidates = _collect_contract_alignment_lanes(session)
    toolchain_state = _collect_contract_toolchain_state(session)
    family_hits = _collect_contract_family_hits(session)
    ordered_families = _ordered_contract_family_priority_list(lane_candidates, family_hits)

    items: list[str] = []
    for family in ordered_families[:5]:
        lane_label = next(
            (label for label, families in lane_candidates if family in families),
            None,
        )
        support_labels, gap_labels = _contract_lane_alignment_labels(
            families=[family],
            toolchain_state=toolchain_state,
        )
        if len(support_labels) >= 3:
            posture = "Strong consensus"
        elif len(support_labels) >= 2:
            posture = "Partial consensus"
        elif support_labels:
            posture = "Weak consensus"
        else:
            posture = "No strong consensus"
        line = (
            f"{posture} on {_contract_follow_up_family_label(family)}: support="
            + ", ".join(support_labels or ["inventory-only"])
        )
        if lane_label:
            line += f"; strongest lane={lane_label}"
        if gap_labels:
            line += "; gaps=" + "; ".join(gap_labels[:2])
        line += "."
        items.append(line)

    return ordered_unique(items)[:6]


def build_contract_validation_matrix(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    lane_candidates = _collect_contract_alignment_lanes(session)
    if not lane_candidates:
        return []

    toolchain_state = _collect_contract_toolchain_state(session)
    case_matches = _collect_repo_casebook_priority_matches(session)

    items: list[str] = []
    for index, (lane_label, families) in enumerate(lane_candidates[:4], start=1):
        support_labels, gap_labels = _contract_lane_alignment_labels(
            families=families,
            toolchain_state=toolchain_state,
        )
        matched_case = _match_contract_review_queue_case(
            lane_label=lane_label,
            families=families,
            case_matches=case_matches,
        )
        family_label = _contract_follow_up_family_label(families[0]) if families else "repo review"
        posture = _contract_lane_validation_posture(
            support_labels=support_labels,
            gap_labels=gap_labels,
            matched_case=matched_case,
        )
        line = (
            f"Matrix {index}: {lane_label}. Family={family_label}. "
            f"Posture={posture}; support={', '.join(support_labels or ['inventory-only'])}"
        )
        if matched_case:
            line += f"; anchored case={matched_case}"
        if gap_labels:
            line += f"; remaining gaps={'; '.join(gap_labels[:2])}"
        line += "."
        items.append(line)

    return ordered_unique(items)[:6]


def build_contract_benchmark_posture(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    support_labels = _casebook_support_labels(session)
    lane_samples = [label for label, _ in _collect_contract_alignment_lanes(session)]
    gap_fragments = _collect_casebook_gap_fragments(session)
    candidates: list[tuple[int, int, str, list[str]]] = []

    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        repo_case_count = int(result_data.get("repo_case_count", 0) or 0)
        if repo_case_count <= 0:
            continue

        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "repo_casebook"
        focus_label = _contract_casebook_focus_label(testbed_name)
        matched_case_count = int(result_data.get("matched_case_count", 0) or 0)
        matched_review_lane_count = int(result_data.get("matched_review_lane_count", 0) or 0)
        matched_risk_family_lane_count = int(result_data.get("matched_risk_family_lane_count", 0) or 0)
        matched_function_priority_count = int(result_data.get("matched_function_priority_count", 0) or 0)
        validation_group_count = int(result_data.get("validation_group_count", 0) or 0)
        validated_group_count = int(result_data.get("validated_group_count", 0) or 0)
        coverage_label = _extract_casebook_coverage_label(_as_str_list(result_data.get("repo_casebook_coverage")))
        sample_lanes = _casebook_lane_samples(result_data)
        issue_summary = _as_count_summary(result_data.get("issue_type_counts"))

        posture = _contract_benchmark_posture_label(
            coverage_label=coverage_label,
            matched_case_count=matched_case_count,
            validated_group_count=validated_group_count,
            support_count=len(support_labels),
        )
        score = (
            matched_case_count * 10
            + matched_review_lane_count * 3
            + matched_risk_family_lane_count * 2
            + matched_function_priority_count
            + validated_group_count * 2
        )
        coverage_rank = {"full": 0, "partial": 1, "minimal": 2, "none": 3}.get(coverage_label, 3)

        lines = [
            (
                f"{posture} for {testbed_name} ({focus_label}): coverage={coverage_label}; "
                f"matched cases={matched_case_count}/{repo_case_count}; "
                f"validated controls={validated_group_count}/{validation_group_count}; "
                f"support={', '.join(support_labels or ['inventory-only'])}."
            )
        ]
        strongest_lane = sample_lanes[0] if sample_lanes else (lane_samples[0] if lane_samples else None)
        if strongest_lane:
            lines.append(f"Primary benchmark lane for {testbed_name}: {strongest_lane}.")
        if issue_summary:
            lines.append(f"Dominant benchmark issues for {testbed_name}: {issue_summary}.")
        if gap_fragments:
            lines.append(f"Benchmark gaps keeping {testbed_name} open: {', '.join(gap_fragments[:3])}.")
        candidates.append((coverage_rank, -score, testbed_name, lines))

    ordered = sorted(candidates, key=lambda item: (item[0], item[1], item[2]))
    output: list[str] = []
    for _, _, _, lines in ordered[:2]:
        output.extend(lines)
    return ordered_unique(output)[:6]


def build_contract_benchmark_pack_summary(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    pack_name = _as_optional_str(session.selected_pack_name)
    if not _is_contract_benchmark_pack(pack_name):
        return []

    executed_steps = [
        step.split(":", 1)[1]
        for step in session.executed_pack_steps
        if step.startswith(f"{pack_name}:")
    ]
    pack_tools = ordered_unique(
        [
            evidence.tool_name or evidence.source
            for evidence in session.evidence
            if evidence.selected_pack_name == pack_name
        ]
    )
    casebooks = ordered_unique(
        [
            _as_optional_str(_extract_result(evidence)[1].get("testbed_name")) or "contract_testbed"
            for evidence in session.evidence
            if evidence.selected_pack_name == pack_name and evidence.tool_name == "contract_testbed_tool"
        ]
    )

    items: list[str] = []
    if executed_steps:
        items.append(
            f"Benchmark pack {pack_name} executed {len(executed_steps)} bounded step(s): {', '.join(executed_steps)}."
        )
    if pack_tools:
        items.append(f"Benchmark pack tools: {', '.join(pack_tools)}.")
    if pack_name == "contract_static_benchmark_pack":
        items.append(
            "Static benchmark emphasis: keep parser, compile, surface, and static-review layers aligned before broader smart-contract escalation."
        )
    elif pack_name == "repo_casebook_benchmark_pack":
        items.append(
            "Repo benchmark emphasis: preserve bounded inventory, review-lane mapping, and matched repo-casebook coverage inside the scoped contract root."
        )
    elif pack_name == "protocol_casebook_benchmark_pack":
        items.append(
            "Protocol benchmark emphasis: compare protocol-style authority, accounting, pricing, reserve, and debt lanes against bounded repo casebooks."
        )
    elif pack_name == "upgrade_control_benchmark_pack":
        items.append(
            "Upgrade benchmark emphasis: keep proxy, delegatecall, implementation, and storage-slot review lanes aligned against anchored upgrade/control casebooks."
        )
    elif pack_name == "vault_permission_benchmark_pack":
        items.append(
            "Vault benchmark emphasis: keep permit, allowance, vault-share, and redeem/accounting lanes aligned against anchored vault-permission casebooks."
        )
    elif pack_name == "lending_protocol_benchmark_pack":
        items.append(
            "Lending benchmark emphasis: keep collateral, liquidation, reserve, fee, and debt-accounting lanes aligned against anchored lending-style casebooks."
        )
    elif pack_name == "governance_timelock_benchmark_pack":
        items.append(
            "Governance benchmark emphasis: keep governance execution, timelock delay, guardian pause, and upgrade-control lanes aligned against anchored governance/timelock archetypes."
        )
    elif pack_name == "reward_distribution_benchmark_pack":
        items.append(
            "Rewards benchmark emphasis: keep reward-index, emission, claim, reserve-backed distribution, and share-adjacent lanes aligned against anchored rewards archetypes."
        )
    elif pack_name == "stablecoin_collateral_benchmark_pack":
        items.append(
            "Stablecoin benchmark emphasis: keep mint, redemption, collateral, oracle, reserve, peg-defence, and liquidation lanes aligned against anchored stablecoin archetypes."
        )
    elif pack_name == "amm_liquidity_benchmark_pack":
        items.append(
            "AMM benchmark emphasis: keep swap routing, reserve updates, LP accounting, fee growth, and oracle-sync lanes aligned against anchored AMM/liquidity archetypes."
        )
    elif pack_name == "bridge_custody_benchmark_pack":
        items.append(
            "Bridge benchmark emphasis: keep relay validation, proof handling, custody release, withdrawal finalization, and replay-protection lanes aligned against anchored bridge/custody archetypes."
        )
    elif pack_name == "staking_rebase_benchmark_pack":
        items.append(
            "Staking benchmark emphasis: keep stake, rebase, queued withdrawal, slash, and validator-reward lanes aligned against anchored staking/rebase archetypes."
        )
    elif pack_name == "keeper_auction_benchmark_pack":
        items.append(
            "Keeper benchmark emphasis: keep keeper incentives, auction settlement, oracle freshness, liquidation, and reserve-buffer lanes aligned against anchored keeper/auction archetypes."
        )
    elif pack_name == "treasury_vesting_benchmark_pack":
        items.append(
            "Treasury benchmark emphasis: keep treasury release, vesting schedule, beneficiary payout, sweep control, and timelock lanes aligned against anchored treasury/vesting archetypes."
        )
    elif pack_name == "insurance_recovery_benchmark_pack":
        items.append(
            "Insurance benchmark emphasis: keep deficit absorption, reserve recovery, emergency settlement, and insurance-fund depletion lanes aligned against anchored insurance/recovery archetypes."
        )
    if casebooks:
        items.append(f"Benchmark pack matched casebooks: {', '.join(casebooks[:3])}.")
    return ordered_unique(items)[:6]


def build_contract_benchmark_case_summaries(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    pack_name = _as_optional_str(session.selected_pack_name)
    if not _is_contract_benchmark_pack(pack_name):
        return []

    items: list[str] = []
    for evidence in session.evidence:
        if evidence.selected_pack_name != pack_name or evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "contract_testbed"
        archetype_label = _contract_casebook_archetype_label(testbed_name)
        for case in result_data.get("cases", []):
            if not isinstance(case, dict) or not bool(case.get("anomaly_detected")):
                continue
            case_id = _as_optional_str(case.get("case_id"))
            if case_id is None:
                continue
            matched_bits = ordered_unique(
                [
                    *_as_str_list(case.get("matched_review_lanes"))[:2],
                    *_as_str_list(case.get("matched_risk_family_lanes"))[:1],
                    *_as_str_list(case.get("matched_function_family_priorities"))[:1],
                ]
            )
            issues = _as_str_list(case.get("issues"))
            focus = _as_optional_str(case.get("validation_focus"))
            variant_role = _as_optional_str(case.get("variant_role"))
            prefix = "Repo benchmark case" if bool(case.get("repo_case")) else "Benchmark case"
            line = f"{prefix} {case_id} from {testbed_name}"
            if archetype_label:
                line += f" [{archetype_label}]"
            if variant_role:
                line += f" ({variant_role})"
            line += ":"
            detail_bits: list[str] = []
            if focus:
                detail_bits.append(f"focus={focus}")
            if matched_bits:
                detail_bits.append(f"lanes={', '.join(matched_bits[:3])}")
            if issues:
                detail_bits.append(f"issues={', '.join(issues[:3])}")
            if not detail_bits:
                detail_bits.append("anomaly-bearing bounded case")
            line += " " + "; ".join(detail_bits) + "."
            items.append(line)
        remediation_validation = _as_str_list(result_data.get("remediation_validation"))
        if remediation_validation:
            items.append(
                f"Benchmark control signal for {testbed_name}: {remediation_validation[0]}"
            )
    return ordered_unique(items)[:6]


def build_contract_repo_priorities(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    lane_candidates: dict[tuple[str, str], dict[str, Any]] = {}
    family_supports: dict[str, list[dict[str, Any]]] = defaultdict(list)
    repo_scope_items: list[tuple[int, int, str]] = []

    for evidence in session.evidence:
        result, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_inventory_tool":
            pragma_summary = _as_str_list(result_data.get("pragma_summary"))
            issues = set(_as_str_list(result_data.get("issues")))
            if len(pragma_summary) > 1:
                repo_scope_items.append(
                    (
                        _contract_repo_priority_rank("medium"),
                        6,
                        "Medium priority repo scope: confirm pragma drift and compiler boundaries before trusting repo-scale findings.",
                    )
                )
            if "inventory_scan_truncated" in issues:
                repo_scope_items.append(
                    (
                        _contract_repo_priority_rank("medium"),
                        5,
                        "Medium priority repo scope: confirm that the bounded contract inventory did not omit in-scope files.",
                    )
                )
            for summary in _as_str_list(result_data.get("entrypoint_function_family_priorities")):
                _record_repo_priority_summary(
                    lane_candidates=lane_candidates,
                    summary=summary,
                    reason_prefix="repo function-family priority",
                    weight=3,
                    priority="medium",
                )
            for summary in _as_str_list(result_data.get("risk_family_lane_summaries")):
                _record_repo_priority_summary(
                    lane_candidates=lane_candidates,
                    summary=summary,
                    reason_prefix="repo risk-family lane",
                    weight=2,
                    priority="medium",
                )
            for lane in _as_str_list(result_data.get("entrypoint_review_lanes")):
                _record_repo_review_lane(
                    lane_candidates=lane_candidates,
                    lane=lane,
                    weight=2,
                    priority="medium",
                )
        elif evidence.tool_name == "contract_compile_tool":
            if result.get("status") == "observed_issue" or int(result_data.get("error_count", 0) or 0) > 0:
                repo_scope_items.append(
                    (
                        _contract_repo_priority_rank("high"),
                        10,
                        "High priority repo scope: resolve compile-facing issues before trusting downstream repo-scale analysis.",
                    )
                )
        elif evidence.tool_name == "contract_surface_tool":
            _add_surface_family_supports(family_supports, result_data)
        elif evidence.tool_name == "contract_pattern_check_tool":
            prioritized = result_data.get("prioritized_issues")
            if not isinstance(prioritized, list):
                prioritized = prioritize_contract_issues(_as_str_list(result_data.get("issues")))
            _add_pattern_family_supports(family_supports, prioritized)
        elif evidence.tool_name == "contract_testbed_tool":
            _add_testbed_family_supports(family_supports, result_data)
        elif evidence.tool_name == "slither_audit_tool":
            impact_counts = result_data.get("impact_counts")
            if isinstance(impact_counts, dict):
                if int(impact_counts.get("high", 0) or 0) > 0:
                    repo_scope_items.append(
                        (
                            _contract_repo_priority_rank("high"),
                            8,
                            "High priority repo scope: cross-check high-impact Slither findings against the strongest local repo lanes.",
                        )
                    )
                elif int(impact_counts.get("medium", 0) or 0) > 0:
                    repo_scope_items.append(
                        (
                            _contract_repo_priority_rank("medium"),
                            6,
                            "Medium priority repo scope: compare medium-impact Slither findings against built-in repo priorities before narrowing scope.",
                        )
                    )
        elif evidence.tool_name == "echidna_audit_tool":
            failing_tests = _as_str_list(result_data.get("failing_tests"))
            if failing_tests:
                repo_scope_items.append(
                    (
                        _contract_repo_priority_rank("high"),
                        9,
                        "High priority repo scope: inspect failing Echidna checks before treating any repo lane as locally validated.",
                    )
                )
        elif evidence.tool_name == "foundry_audit_tool":
            if int(result_data.get("inspect_contracts_succeeded", 0) or 0) > 0:
                repo_scope_items.append(
                    (
                        _contract_repo_priority_rank("medium"),
                        4,
                        "Medium priority repo scope: use Foundry structural inspection output to validate method and storage assumptions along the strongest lanes.",
                    )
                )

    lane_items: list[tuple[int, int, str]] = []
    for candidate in lane_candidates.values():
        for support in family_supports.get(candidate["family"], []):
            candidate["score"] += int(support["weight"])
            candidate["priority_rank"] = min(candidate["priority_rank"], _contract_repo_priority_rank(support["priority"]))
            if support["text"] not in candidate["supporting_signals"]:
                candidate["supporting_signals"].append(support["text"])

        priority_label = _contract_repo_priority_label(candidate["priority_rank"], candidate["score"])
        supporting_signals = candidate["supporting_signals"][:3] or ["bounded repo inventory already converges on this lane"]
        lane_items.append(
            (
                _contract_repo_priority_rank(priority_label.lower()),
                -candidate["score"],
                f"{priority_label} priority repo lane: {candidate['lane_label']}. Supporting signals: "
                + "; ".join(supporting_signals)
                + ".",
            )
        )

    ordered_scope = [line for _, _, line in sorted(repo_scope_items, key=lambda item: (item[0], -item[1], item[2]))]
    ordered_lanes = [line for _, _, line in sorted(lane_items, key=lambda item: (item[0], item[1], item[2]))]
    return ordered_unique([*ordered_scope[:3], *ordered_lanes[:5]])[:8]


def build_contract_repo_triage(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    family_counts: Counter[str] = Counter()
    active_tools: set[str] = set()
    primary_lanes: list[str] = []
    risk_linked_files: list[str] = []
    casebook_candidates: list[tuple[int, str]] = []

    for evidence in session.evidence:
        result, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_inventory_tool":
            active_tools.add(evidence.tool_name)
            primary_lanes.extend(_as_str_list(result_data.get("entrypoint_review_lanes"))[:2])
            primary_lanes.extend(_as_str_list(result_data.get("risk_family_lane_summaries"))[:2])
            risk_linked_files.extend(_as_str_list(result_data.get("risk_linked_files"))[:4])
            dependency_review_files = _as_str_list(result_data.get("dependency_review_files"))
            if dependency_review_files:
                risk_linked_files.extend(dependency_review_files[:2])
            for summary in _as_str_list(result_data.get("entrypoint_function_family_priorities")):
                _, _, tail = summary.partition("=>")
                for family_token in tail.split(","):
                    resolved_family = _normalize_contract_repo_family(family_token)
                    if resolved_family:
                        family_counts[resolved_family] += 2
        elif evidence.tool_name == "contract_surface_tool":
            active_tools.add(evidence.tool_name)
            for family in _surface_families(result_data):
                family_counts[family] += 2
        elif evidence.tool_name == "contract_pattern_check_tool":
            active_tools.add(evidence.tool_name)
            prioritized = result_data.get("prioritized_issues")
            if not isinstance(prioritized, list):
                prioritized = prioritize_contract_issues(_as_str_list(result_data.get("issues")))
            for item in prioritized:
                if not isinstance(item, dict):
                    continue
                issue_name = _as_optional_str(item.get("issue"))
                if not issue_name:
                    continue
                resolved_family = _normalize_contract_repo_family(issue_name.split(":", 1)[0])
                if not resolved_family:
                    continue
                priority = (_as_optional_str(item.get("priority")) or "low").lower()
                family_counts[resolved_family] += {"high": 3, "medium": 2, "low": 1}.get(priority, 1)
        elif evidence.tool_name == "contract_testbed_tool":
            active_tools.add(evidence.tool_name)
            testbed_name = _as_optional_str(result_data.get("testbed_name")) or "contract_testbed"
            resolved_families = _contract_testbed_families(testbed_name)
            for resolved_family in resolved_families:
                family_counts[resolved_family] += 3
            repo_case_count = int(result_data.get("repo_case_count", 0) or 0)
            if repo_case_count <= 0:
                continue
            matched_case_count = int(result_data.get("matched_case_count", 0) or 0)
            matched_review_lane_count = int(result_data.get("matched_review_lane_count", 0) or 0)
            validated_group_count = int(result_data.get("validated_group_count", 0) or 0)
            validation_group_count = int(result_data.get("validation_group_count", 0) or 0)
            coverage_label = _extract_casebook_coverage_label(
                _as_str_list(result_data.get("repo_casebook_coverage"))
            )
            focus_label = _contract_casebook_focus_label(testbed_name)
            score = matched_case_count + matched_review_lane_count + validated_group_count
            casebook_candidates.append(
                (
                    score,
                    f"Use bounded repo casebook {testbed_name} for {focus_label}; coverage={coverage_label}; "
                    f"matched cases={matched_case_count}/{repo_case_count}; review lanes={matched_review_lane_count}; "
                    f"validated controls={validated_group_count}/{validation_group_count}.",
                )
            )
        elif evidence.tool_name in {
            "contract_compile_tool",
            "slither_audit_tool",
            "echidna_audit_tool",
            "foundry_audit_tool",
        }:
            active_tools.add(evidence.tool_name)

    items: list[str] = []
    if primary_lanes:
        items.append(
            f"Start repo review from {primary_lanes[0]}; it is the strongest bounded lane before widening to unrelated files."
        )
    inventory = _first_contract_result(session, "contract_inventory_tool")
    if inventory:
        first_party_file_count = int(inventory.get("first_party_file_count", 0) or 0)
        dependency_file_count = int(inventory.get("dependency_file_count", 0) or 0)
        first_party_dependency_edges = int(inventory.get("first_party_dependency_edges", 0) or 0)
        if dependency_file_count > 0:
            items.append(
                f"Keep first-party scope primary ({first_party_file_count} files) and widen into imported dependency code ({dependency_file_count} files; first-party -> dependency edges={first_party_dependency_edges}) only for matched bounded lanes."
            )
    if family_counts:
        family, _ = family_counts.most_common(1)[0]
        items.append(
            f"Treat {_contract_follow_up_family_label(family)} as the top repo family and re-run "
            f"{_format_contract_follow_up_tools(family, active_tools)} there before widening scope."
        )
    if casebook_candidates:
        _, line = max(casebook_candidates, key=lambda item: (item[0], item[1]))
        items.append(line)
    if len(primary_lanes) > 1:
        items.append(
            f"Keep the next bounded lane queued as a secondary pass: {primary_lanes[1]}."
        )
    if risk_linked_files:
        items.append(
            "Anchor the first repository pass to risk-linked files: "
            + ", ".join(risk_linked_files[:3])
            + "."
        )
    return ordered_unique(items)[:5]


def build_contract_triage_snapshot(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    priority_lines = build_contract_repo_priorities(session)
    triage_lines = build_contract_repo_triage(session)
    review_queue = build_contract_review_queue(session)
    finding_cards = build_contract_finding_cards(session)
    inventory = _first_contract_result(session, "contract_inventory_tool") or {}

    top_lane = _first_matching_line(priority_lines, ("priority repo lane", "priority repo scope"))
    if top_lane is None:
        top_lane = _first_matching_line(triage_lines, ("start repo review", "top repo family"))
    if top_lane is None and priority_lines:
        top_lane = priority_lines[0]

    files = ordered_unique(
        [
            *_as_str_list(inventory.get("risk_linked_files"))[:3],
            *_as_str_list(inventory.get("entrypoint_candidates"))[:3],
            *_as_str_list(inventory.get("candidate_files"))[:3],
            *_as_str_list(inventory.get("shared_dependency_files"))[:2],
        ]
    )

    items: list[str] = []
    if top_lane:
        items.append("Triage snapshot - top repo lane: " + _trim_sentence(top_lane, 260))
    if files:
        items.append("Triage snapshot - top files/contracts: " + ", ".join(files[:5]) + ".")

    why_line = _first_matching_line(finding_cards, ("Why it matters:", "Evidence:"))
    if why_line is None:
        why_line = _first_matching_line(priority_lines, ("Supporting signals:",))
    if why_line:
        items.append("Triage snapshot - why it matters: " + _trim_sentence(why_line, 260))

    next_step = review_queue[0] if review_queue else _first_matching_line(triage_lines, ("re-run", "manual", "review"))
    if next_step:
        items.append("Triage snapshot - next manual step: " + _trim_sentence(next_step, 260))

    return ordered_unique(items)[:4]


def build_contract_casebook_coverage(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        items.extend(_as_str_list(result_data.get("repo_casebook_coverage")))
    return ordered_unique(items)[:6]


def build_contract_casebook_coverage_matrix(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    items: list[tuple[int, int, str]] = []
    support_labels = _casebook_support_labels(session)
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        repo_case_count = int(result_data.get("repo_case_count", 0) or 0)
        if repo_case_count <= 0:
            continue

        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "repo_casebook"
        casebook_families = _contract_testbed_families(testbed_name)
        coverage_label = _extract_casebook_coverage_label(_as_str_list(result_data.get("repo_casebook_coverage")))
        matched_case_count = int(result_data.get("matched_case_count", 0) or 0)
        matched_review_lane_count = int(result_data.get("matched_review_lane_count", 0) or 0)
        matched_risk_family_lane_count = int(result_data.get("matched_risk_family_lane_count", 0) or 0)
        matched_function_priority_count = int(result_data.get("matched_function_priority_count", 0) or 0)
        validation_group_count = int(result_data.get("validation_group_count", 0) or 0)
        validated_group_count = int(result_data.get("validated_group_count", 0) or 0)
        issue_summary = _as_count_summary(result_data.get("issue_type_counts")) or "no dominant issue family"
        posture = _contract_benchmark_posture_label(
            coverage_label=coverage_label,
            matched_case_count=matched_case_count,
            validated_group_count=validated_group_count,
            support_count=len(support_labels),
        )
        strongest_lane = next(iter(_casebook_lane_samples(result_data)), None)
        line = (
            f"Casebook matrix for {testbed_name}: posture={posture}; coverage={coverage_label}; "
            f"cases={matched_case_count}/{repo_case_count}; lanes={matched_review_lane_count}; "
            f"risk-lanes={matched_risk_family_lane_count}; function-priorities={matched_function_priority_count}; "
            f"validated controls={validated_group_count}/{validation_group_count}; "
            f"support={', '.join(support_labels or ['inventory-only'])}; dominant issues={issue_summary}"
        )
        if casebook_families:
            line += "; families=" + ", ".join(
                _contract_follow_up_family_label(family) for family in casebook_families
            )
        if strongest_lane:
            line += f"; strongest lane={strongest_lane}"
        line += "."
        score = matched_case_count * 10 + matched_review_lane_count * 3 + validated_group_count * 2
        coverage_rank = {"full": 0, "partial": 1, "minimal": 2, "none": 3}.get(coverage_label, 3)
        items.append((coverage_rank, -score, line))

    ordered = [line for _, _, line in sorted(items, key=lambda item: (item[0], item[1], item[2]))]
    return ordered_unique(ordered)[:5]


def build_contract_casebook_case_studies(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        repo_case_count = int(result_data.get("repo_case_count", 0) or 0)
        if repo_case_count <= 0:
            continue
        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "repo_casebook"
        casebook_families = _contract_testbed_families(testbed_name)
        matched_case_count = int(result_data.get("matched_case_count", 0) or 0)
        matched_review_lane_count = int(result_data.get("matched_review_lane_count", 0) or 0)
        matched_risk_family_lane_count = int(result_data.get("matched_risk_family_lane_count", 0) or 0)
        matched_function_priority_count = int(result_data.get("matched_function_priority_count", 0) or 0)
        validation_group_count = int(result_data.get("validation_group_count", 0) or 0)
        validated_group_count = int(result_data.get("validated_group_count", 0) or 0)
        casebook_focus = _contract_casebook_focus_label(testbed_name)
        archetype_label = _contract_casebook_archetype_label(testbed_name)
        casebook_coverage = _extract_casebook_coverage_label(_as_str_list(result_data.get("repo_casebook_coverage")))
        items.append(
            f"Case study {testbed_name} ({casebook_focus}): coverage={casebook_coverage}; "
            f"matched cases={matched_case_count}/{repo_case_count}; review lanes={matched_review_lane_count}; "
            f"risk-family lanes={matched_risk_family_lane_count}; function-family priorities={matched_function_priority_count}; "
            f"validated controls={validated_group_count}/{validation_group_count}."
        )
        if archetype_label:
            items.append(f"Case study archetype: {archetype_label}.")
        if casebook_families:
            items.append(
                "Case study families: "
                + ", ".join(_contract_follow_up_family_label(family) for family in casebook_families)
                + "."
            )
        detail_bits: list[str] = []
        matched_case_ids = _as_str_list(result_data.get("matched_case_ids"))
        if matched_case_ids:
            detail_bits.append(f"matched cases: {', '.join(matched_case_ids[:4])}")
        issue_counts = _as_count_summary(result_data.get("issue_type_counts"))
        if issue_counts:
            detail_bits.append(f"dominant issues: {issue_counts}")
        if detail_bits:
            items.append(
                f"Case study details for {testbed_name}: " + "; ".join(detail_bits) + "."
            )
    return ordered_unique(items)[:6]


def build_contract_casebook_benchmark_support(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    compile_support = "compile path not run"
    static_support_parts: list[str] = []
    invariant_support = "invariant path not run"
    structural_support = "structural inspection path not run"

    for evidence in session.evidence:
        result, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_compile_tool":
            compiled_count = int(result_data.get("compiled_contract_count", 0) or 0)
            error_count = int(result_data.get("error_count", 0) or 0)
            warning_count = int(result_data.get("warning_count", 0) or 0)
            compiler_version = _as_optional_str(result_data.get("compiler_version"))
            if result.get("status") == "ok":
                compile_support = (
                    f"compile ok ({compiled_count} contract(s); warnings={warning_count}; errors={error_count}"
                    + (f"; compiler={compiler_version}" if compiler_version else "")
                    + ")"
                )
            elif result.get("status") == "observed_issue":
                compile_support = (
                    f"compile issues (warnings={warning_count}; errors={error_count}"
                    + (f"; compiler={compiler_version}" if compiler_version else "")
                    + ")"
                )
            else:
                compile_support = "compile path unavailable"
        elif evidence.tool_name == "contract_pattern_check_tool":
            issue_count = int(result_data.get("issue_count", 0) or 0)
            if issue_count > 0:
                static_support_parts.append(f"built-in pattern={issue_count} issue(s)")
            else:
                static_support_parts.append("built-in pattern=ok")
        elif evidence.tool_name == "slither_audit_tool":
            finding_count = int(result_data.get("finding_count", 0) or 0)
            impact_counts = _as_count_summary(result_data.get("impact_counts"))
            if finding_count > 0:
                detail = f"Slither={finding_count} finding(s)"
                if impact_counts:
                    detail += f" ({impact_counts})"
                static_support_parts.append(detail)
            elif result.get("status") == "unavailable":
                static_support_parts.append("Slither unavailable")
            else:
                static_support_parts.append("Slither=ok")
        elif evidence.tool_name == "echidna_audit_tool":
            if bool(result_data.get("analysis_applicable")):
                failing_test_count = int(result_data.get("failing_test_count", 0) or 0)
                test_count = int(result_data.get("test_count", 0) or 0)
                invariant_support = (
                    f"Echidna applicable (tests={test_count}; failing={failing_test_count})"
                )
            elif result.get("status") == "unavailable":
                invariant_support = "Echidna unavailable"
            else:
                invariant_support = "Echidna not applicable"
        elif evidence.tool_name == "foundry_audit_tool":
            inspect_succeeded = int(result_data.get("inspect_contracts_succeeded", 0) or 0)
            contract_names = _as_str_list(result_data.get("contract_names"))
            if inspect_succeeded > 0:
                structural_support = (
                    f"Foundry inspected {inspect_succeeded}/{max(len(contract_names), inspect_succeeded)} contract(s)"
                )
            elif result.get("status") == "unavailable":
                structural_support = "Foundry unavailable"
            else:
                structural_support = "Foundry build-only"

    static_support = "; ".join(ordered_unique(static_support_parts)) if static_support_parts else "static paths not run"

    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        repo_case_count = int(result_data.get("repo_case_count", 0) or 0)
        if repo_case_count <= 0:
            continue
        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "repo_casebook"
        focus_label = _contract_casebook_focus_label(testbed_name)
        matched_case_count = int(result_data.get("matched_case_count", 0) or 0)
        matched_review_lane_count = int(result_data.get("matched_review_lane_count", 0) or 0)
        coverage_label = _extract_casebook_coverage_label(_as_str_list(result_data.get("repo_casebook_coverage")))
        items.append(
            f"Benchmark support for {testbed_name} ({focus_label}): coverage={coverage_label}; "
            f"matched cases={matched_case_count}/{repo_case_count}; review lanes={matched_review_lane_count}; "
            f"{compile_support}; {static_support}; {invariant_support}; {structural_support}."
        )
    return ordered_unique(items)[:4]


def build_contract_casebook_priority_cases(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    case_candidates: list[tuple[int, str, str]] = []

    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        if int(result_data.get("repo_case_count", 0) or 0) <= 0:
            continue

        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "repo_casebook"
        for case in result_data.get("cases", []):
            if not isinstance(case, dict) or not bool(case.get("repo_case")):
                continue
            case_id = _as_optional_str(case.get("case_id"))
            if case_id is None:
                continue
            review_lanes = _as_str_list(case.get("matched_review_lanes"))
            risk_family_lanes = _as_str_list(case.get("matched_risk_family_lanes"))
            function_priorities = _as_str_list(case.get("matched_function_family_priorities"))
            issue_strings = _as_str_list(case.get("issues"))
            candidate_files = _as_str_list(case.get("candidate_files"))
            lane_bits = ordered_unique([*review_lanes[:2], *risk_family_lanes[:1], *function_priorities[:1]])
            if not lane_bits and not issue_strings:
                continue
            score = (
                len(review_lanes) * 5
                + len(risk_family_lanes) * 3
                + len(function_priorities) * 2
                + len(issue_strings)
            )
            issue_text = ", ".join(issue_strings[:3]) if issue_strings else "no issue strings captured"
            line = (
                f"Priority case {case_id} from {testbed_name}: "
                f"lanes={', '.join(lane_bits[:3]) if lane_bits else 'no matched lanes'}; "
                f"issues={issue_text}"
            )
            if candidate_files:
                line += f"; files={', '.join(candidate_files[:3])}"
            line += "."
            case_candidates.append((-score, testbed_name, line))

    ordered = sorted(case_candidates, key=lambda item: (item[0], item[1], item[2]))
    return ordered_unique([line for _, _, line in ordered])[:4]


def build_contract_casebook_gaps(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    inventory_review_lanes, inventory_risk_lanes, inventory_function_priorities = _collect_inventory_lane_sets(session)
    if not inventory_review_lanes and not inventory_risk_lanes and not inventory_function_priorities:
        return []

    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        repo_case_count = int(result_data.get("repo_case_count", 0) or 0)
        if repo_case_count <= 0:
            continue

        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "repo_casebook"
        matched_review_lanes, matched_risk_lanes, matched_function_priorities = _collect_matched_casebook_lane_sets(result_data)
        missing_review_lanes = ordered_unique([lane for lane in inventory_review_lanes if lane not in matched_review_lanes])
        missing_risk_lanes = ordered_unique([lane for lane in inventory_risk_lanes if lane not in matched_risk_lanes])
        missing_function_priorities = ordered_unique(
            [lane for lane in inventory_function_priorities if lane not in matched_function_priorities]
        )
        coverage_label = _extract_casebook_coverage_label(_as_str_list(result_data.get("repo_casebook_coverage")))
        items.append(
            f"Casebook gap scan for {testbed_name}: coverage={coverage_label}; "
            f"unmatched review lanes={len(missing_review_lanes)}; "
            f"unmatched risk-family lanes={len(missing_risk_lanes)}; "
            f"unmatched function-family priorities={len(missing_function_priorities)}."
        )
        remaining_bits = ordered_unique(
            [*missing_review_lanes[:2], *missing_risk_lanes[:1], *missing_function_priorities[:1]]
        )
        if remaining_bits:
            items.append(
                f"Remaining repo gaps for {testbed_name}: {', '.join(remaining_bits[:4])}."
            )

    return ordered_unique(items)[:6]


def build_contract_casebook_triage(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    support_labels = _casebook_support_labels(session)
    triage_candidates: list[tuple[int, int, str, list[str]]] = []

    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        repo_case_count = int(result_data.get("repo_case_count", 0) or 0)
        if repo_case_count <= 0:
            continue

        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "repo_casebook"
        focus_label = _contract_casebook_focus_label(testbed_name)
        matched_case_count = int(result_data.get("matched_case_count", 0) or 0)
        matched_review_lane_count = int(result_data.get("matched_review_lane_count", 0) or 0)
        matched_risk_family_lane_count = int(result_data.get("matched_risk_family_lane_count", 0) or 0)
        matched_function_priority_count = int(result_data.get("matched_function_priority_count", 0) or 0)
        validation_group_count = int(result_data.get("validation_group_count", 0) or 0)
        validated_group_count = int(result_data.get("validated_group_count", 0) or 0)
        coverage_label = _extract_casebook_coverage_label(_as_str_list(result_data.get("repo_casebook_coverage")))
        lane_samples = _casebook_lane_samples(result_data)
        issue_summary = _as_count_summary(result_data.get("issue_type_counts"))

        score = (
            matched_case_count * 10
            + matched_review_lane_count * 3
            + matched_risk_family_lane_count * 2
            + matched_function_priority_count
            + validated_group_count * 2
        )
        coverage_rank = {"full": 0, "partial": 1, "minimal": 2, "none": 3}.get(coverage_label, 3)

        lines = [
            (
                f"Primary casebook triage for {testbed_name} ({focus_label}): "
                f"coverage={coverage_label}; matched cases={matched_case_count}/{repo_case_count}; "
                f"validated controls={validated_group_count}/{validation_group_count}; "
                f"review lanes={matched_review_lane_count}; risk-family lanes={matched_risk_family_lane_count}; "
                f"function-family priorities={matched_function_priority_count}."
            )
        ]
        if lane_samples:
            lines.append(
                f"Strongest bounded lanes for {testbed_name}: {', '.join(lane_samples[:3])}."
            )
        posture_bits: list[str] = []
        if support_labels:
            posture_bits.append("support=" + ", ".join(support_labels))
        if issue_summary:
            posture_bits.append(f"dominant issues={issue_summary}")
        if posture_bits:
            lines.append(
                f"Benchmark posture for {testbed_name}: " + "; ".join(posture_bits) + "."
            )
        triage_candidates.append((coverage_rank, -score, testbed_name, lines))

    ordered = sorted(triage_candidates, key=lambda item: (item[0], item[1], item[2]))
    output: list[str] = []
    for _, _, _, lines in ordered[:2]:
        output.extend(lines)
    return ordered_unique(output)[:6]


def build_contract_toolchain_alignment(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    lane_candidates = _collect_contract_alignment_lanes(session)
    toolchain_state = _collect_contract_toolchain_state(session)
    items: list[str] = []

    for lane_label, families in lane_candidates[:4]:
        support_labels, gap_labels = _contract_lane_alignment_labels(
            families=families,
            toolchain_state=toolchain_state,
        )
        if not support_labels:
            support_labels = ["inventory-only"]
        line = (
            f"Lane alignment for {lane_label}: support="
            + ", ".join(support_labels)
            + "."
        )
        if gap_labels:
            line += " Remaining gaps: " + "; ".join(gap_labels[:2]) + "."
        items.append(line)

    return ordered_unique(items)[:6]


def build_contract_review_queue(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    lane_candidates = _collect_contract_alignment_lanes(session)
    if not lane_candidates:
        return []

    toolchain_state = _collect_contract_toolchain_state(session)
    active_tools = {
        evidence.tool_name
        for evidence in session.evidence
        if isinstance(evidence.tool_name, str) and evidence.tool_name.strip()
    }
    case_matches = _collect_repo_casebook_priority_matches(session)
    casebook_gap_fragments = _collect_casebook_gap_fragments(session)

    items: list[str] = []
    for index, (lane_label, families) in enumerate(lane_candidates[:3], start=1):
        support_labels, gap_labels = _contract_lane_alignment_labels(
            families=families,
            toolchain_state=toolchain_state,
        )
        matched_case = _match_contract_review_queue_case(
            lane_label=lane_label,
            families=families,
            case_matches=case_matches,
        )
        line = (
            f"Queue {index}: review {lane_label} first; support="
            + ", ".join(support_labels or ["inventory-only"])
            + "; matched case="
            + (matched_case or "no direct repo-casebook priority case")
            + "."
        )
        line += (
            " Next replay: "
            + _format_contract_follow_up_tools_for_families(families, active_tools)
            + " after "
            + _contract_follow_up_action_for_families(families)
            + "."
        )
        if gap_labels:
            line += " Remaining gaps: " + "; ".join(gap_labels[:2]) + "."
        items.append(line)

    if casebook_gap_fragments:
        items.append(
            "Gap queue: expand review to "
            + ", ".join(casebook_gap_fragments[:4])
            + " before closing the current bounded repo pass."
        )

    return ordered_unique(items)[:6]


def build_contract_compile_summary(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_compile_tool":
            continue
        result, result_data = _extract_result(evidence)
        status = _as_optional_str(result.get("status")) or "unknown"
        compiled_names = _as_str_list(result_data.get("compiled_contract_names"))
        warning_count = int(result_data.get("warning_count", 0) or 0)
        error_count = int(result_data.get("error_count", 0) or 0)
        compiler_version = _as_optional_str(result_data.get("compiler_version"))
        if status == "ok":
            line = (
                f"Compile check succeeded for {len(compiled_names)} contract(s)"
                + (f" ({', '.join(compiled_names)})" if compiled_names else "")
                + f"; warnings={warning_count}; errors={error_count}."
            )
        elif status == "observed_issue":
            line = (
                f"Compile check surfaced issues; warnings={warning_count}; errors={error_count}."
            )
        else:
            line = evidence.conclusion or evidence.summary
        if compiler_version:
            line += f" Compiler: {compiler_version}."
        items.append(line)
    return ordered_unique(items)


def build_contract_surface_summary(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_surface_tool":
            continue
        _, result_data = _extract_result(evidence)
        items.append(
            "Reachable surface: "
            f"public={len(_as_str_list(result_data.get('public_functions')))}, "
            f"external={len(_as_str_list(result_data.get('external_functions')))}, "
            f"payable={len(_as_str_list(result_data.get('payable_functions')))}, "
            f"privileged={len(_as_str_list(result_data.get('privileged_functions')))}."
        )
        risk_bits: list[str] = []
        for label, key in (
            ("low-level", "low_level_call_functions"),
            ("value-transfer", "call_with_value_functions"),
            ("delegatecall", "delegatecall_functions"),
            ("proxy-delegate", "proxy_delegatecall_functions"),
            ("selfdestruct", "selfdestruct_functions"),
            ("tx.origin", "tx_origin_functions"),
            ("timestamp", "timestamp_functions"),
            ("entropy", "entropy_source_functions"),
            ("assembly", "assembly_functions"),
            ("token-transfer", "token_transfer_functions"),
            ("token-transferFrom", "token_transfer_from_functions"),
            ("approve", "approve_functions"),
            ("signature", "signature_validation_functions"),
            ("oracle", "oracle_dependency_functions"),
            ("liquidation-fee", "liquidation_fee_functions"),
            ("fee", "fee_collection_functions"),
            ("reserve-buffer", "reserve_buffer_functions"),
            ("reserve-accounting", "reserve_accounting_functions"),
            ("debt-accounting", "debt_accounting_functions"),
            ("bad-debt", "bad_debt_socialization_functions"),
            ("state-transition", "state_transition_functions"),
            ("accounting", "accounting_mutation_functions"),
            ("storage-slot-write", "storage_slot_write_functions"),
            ("implementation-ref", "implementation_reference_functions"),
        ):
            names = _as_str_list(result_data.get(key))
            if names:
                risk_bits.append(f"{label}={', '.join(names[:4])}")
        if risk_bits:
            items.append("Review surfaces: " + "; ".join(risk_bits) + ".")
        structural_bits: list[str] = []
        if bool(result_data.get("implementation_slot_constant_present")):
            structural_bits.append("implementation-slot-constant=yes")
        if bool(result_data.get("storage_gap_present")):
            structural_bits.append("storage-gap=yes")
        if structural_bits:
            items.append("Structural storage hints: " + "; ".join(structural_bits) + ".")
    return ordered_unique(items)


def build_contract_priority_findings(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        result, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_compile_tool":
            if result.get("status") == "observed_issue" or int(result_data.get("error_count", 0) or 0) > 0:
                items.append("High priority: resolve compiler-facing issues before trusting downstream contract analysis.")
        elif evidence.tool_name == "contract_pattern_check_tool":
            prioritized = result_data.get("prioritized_issues")
            if not isinstance(prioritized, list):
                prioritized = prioritize_contract_issues(_as_str_list(result_data.get("issues")))
            for item in prioritized[:4]:
                if not isinstance(item, dict):
                    continue
                priority = _as_optional_str(item.get("priority")) or "medium"
                summary = _as_optional_str(item.get("summary"))
                if summary:
                    items.append(f"{priority.capitalize()} priority: {summary}.")
        elif evidence.tool_name == "slither_audit_tool":
            impact_counts = result_data.get("impact_counts")
            if isinstance(impact_counts, dict):
                if int(impact_counts.get("high", 0) or 0) > 0:
                    items.append(
                        "High priority: inspect high-impact Slither detector findings before narrowing the audit scope."
                    )
                elif int(impact_counts.get("medium", 0) or 0) > 0:
                    items.append(
                        "Medium priority: inspect medium-impact Slither detector findings and compare them against built-in signals."
                    )
        elif evidence.tool_name == "echidna_audit_tool":
            failing_tests = _as_str_list(result_data.get("failing_tests"))
            if failing_tests:
                items.append(
                    "High priority: inspect failing Echidna checks: "
                    + ", ".join(failing_tests[:4])
                    + "."
                )
        elif evidence.tool_name == "contract_testbed_tool":
            anomaly_count = int(result_data.get("anomaly_count", 0) or 0)
            testbed_name = _as_optional_str(result_data.get("testbed_name")) or "contract_testbed"
            if anomaly_count > 0:
                items.append(
                    f"Medium priority: compare the contract against anomaly-bearing cases from {testbed_name} before stronger conclusions."
                )
        elif evidence.tool_name == "foundry_audit_tool":
            if int(result_data.get("inspect_contracts_succeeded", 0) or 0) == 0 and bool(
                result_data.get("contract_names")
            ):
                items.append(
                    "Medium priority: review Foundry structural inspection gaps before relying on build-only results."
                )
    return ordered_unique(items)[:8]


def build_contract_finding_cards(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session) or session.report is None:
        return []

    sources = session.report
    potential_findings = ordered_unique(
        [
            *sources.contract_priority_findings,
            *sources.contract_review_queue,
            *sources.contract_residual_risk,
            *sources.contract_review_focus,
        ]
    )
    evidence_lines = ordered_unique(
        [
            *sources.contract_static_findings,
            *sources.contract_testbed_findings,
            *sources.contract_surface_summary,
            *sources.contract_compile_summary,
            *sources.contract_toolchain_alignment,
        ]
    )
    why_lines = ordered_unique(
        [
            *sources.contract_residual_risk,
            *sources.contract_signal_consensus,
            *sources.contract_validation_matrix,
            *sources.contract_manual_review_items,
        ]
    )
    fix_lines = ordered_unique(
        [
            *sources.contract_remediation_guidance,
            *sources.contract_remediation_validation,
        ]
    )
    recheck_lines = ordered_unique(
        [
            *sources.contract_remediation_follow_up,
            *sources.contract_exit_criteria,
        ]
    )

    if not potential_findings and not evidence_lines:
        return []

    cards: list[str] = []
    card_count = min(3, max(len(potential_findings), 1))
    for index in range(card_count):
        potential = _contract_card_value(
            potential_findings,
            index,
            "No standalone finding was produced; keep the current contract signal set in manual-review mode.",
        )
        keywords = _contract_card_keywords(potential)
        fallback_why = (
            "The current evidence is bounded and should not be treated as a confirmed vulnerability without review."
        )
        fallback_fix = "Narrow the implicated flow, harden the control path, and keep the claim manual-review bounded."
        fallback_recheck = (
            "Re-run the same bounded smart-contract audit path and compare the strongest local signals."
        )
        evidence = _contract_card_match_value(
            evidence_lines,
            index,
            keywords,
            "No direct local evidence line was available for this card.",
        )
        why = _contract_card_match_value(
            why_lines,
            index,
            keywords,
            fallback_why,
        )
        fix = _contract_card_match_value(
            fix_lines,
            index,
            keywords,
            fallback_fix,
        )
        recheck = _contract_card_match_value(
            recheck_lines,
            index,
            keywords,
            fallback_recheck,
        )
        cards.append(
            f"Finding card {index + 1}: Potential finding: {_contract_card_excerpt(potential, 90)} "
            f"Evidence: {_contract_card_excerpt(evidence, 95)} "
            f"Why it matters: {_contract_card_excerpt(why, 85)} "
            f"Fix direction: {_contract_card_excerpt(fix, 85)} "
            f"Recheck: {_contract_card_excerpt(recheck, 90)}"
        )

    return ordered_unique(cards)


def _contract_card_excerpt(text: str, limit: int) -> str:
    normalized = " ".join(text.strip().split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip(" .,;:") + "..."


def _contract_card_value(values: list[str], index: int, fallback: str) -> str:
    if not values:
        return fallback
    return values[index] if index < len(values) else values[-1]


def _contract_card_match_value(values: list[str], index: int, keywords: list[str], fallback: str) -> str:
    if not values:
        return fallback
    normalized_keywords = ordered_unique(keyword.lower() for keyword in keywords if len(keyword.strip()) > 2)
    best_value: str | None = None
    best_score = 0
    for value in values:
        lowered = value.lower()
        score = sum(1 for keyword in normalized_keywords if keyword in lowered)
        if score > best_score:
            best_value = value
            best_score = score
    if best_value is not None:
        return best_value
    return _contract_card_value(values, index, fallback)


def _contract_card_keywords(text: str) -> list[str]:
    lowered = text.lower()
    keyword_groups = [
        (
            ("reentrancy", "sweep", "rescue", "external call", "value transfer", "low-level call"),
            ["reentrancy", "sweep", "rescue", "asset", "asset-flow", "external", "value", "balance", "accounting"],
        ),
        (
            ("share", "vault", "asset-backing", "mint", "redeem"),
            ["vault", "share", "asset-backing", "asset", "conversion", "redeem", "mint"],
        ),
        (
            ("replay", "nonce", "permit", "signature", "ecrecover"),
            ["permit", "signature", "nonce", "domain", "signer"],
        ),
        (
            ("allowance", "approve", "transferfrom", "token"),
            ["token", "allowance", "approve", "transfer"],
        ),
        (
            ("delegatecall", "proxy", "storage", "implementation", "slot"),
            ["proxy", "storage", "delegatecall", "implementation", "slot"],
        ),
        (
            ("upgrade", "admin", "owner", "role", "pause", "privileged", "authority"),
            ["upgrade", "authority", "role", "owner", "pause", "admin", "control"],
        ),
        (
            ("oracle", "price", "twap"),
            ["oracle", "price", "freshness", "twap"],
        ),
        (
            ("collateral", "liquidation", "health"),
            ["collateral", "liquidation", "health", "threshold"],
        ),
        (
            ("reserve", "debt", "fee"),
            ["reserve", "debt", "fee", "protocol"],
        ),
    ]
    keywords: list[str] = []
    for triggers, group_keywords in keyword_groups:
        if any(trigger in lowered for trigger in triggers):
            keywords.extend(group_keywords)
    return ordered_unique(keywords)


def build_contract_static_findings(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name == "contract_pattern_check_tool":
            _, result_data = _extract_result(evidence)
            issue_count = int(result_data.get("issue_count", 0) or 0)
            family_counts = _as_count_summary(result_data.get("issue_family_counts"))
            note_counts = _as_count_summary(result_data.get("note_type_counts"))
            if issue_count or family_counts:
                line = f"Built-in pattern review reported {issue_count} issue(s)."
                if family_counts:
                    line += f" Top issue families: {family_counts}."
                if note_counts:
                    line += f" Supporting notes: {note_counts}."
                items.append(line)
        elif evidence.tool_name == "slither_audit_tool":
            result, result_data = _extract_result(evidence)
            finding_count = int(result_data.get("finding_count", 0) or 0)
            detector_counts = _as_count_summary(result_data.get("detector_name_counts"))
            impact_counts = _as_count_summary(result_data.get("impact_counts"))
            confidence_counts = _as_count_summary(result_data.get("confidence_counts"))
            if finding_count or detector_counts:
                line = f"Slither reported {finding_count} detector finding(s)."
                if impact_counts:
                    line += f" Impact: {impact_counts}."
                if detector_counts:
                    line += f" Detectors: {detector_counts}."
                if confidence_counts:
                    line += f" Confidence: {confidence_counts}."
                items.append(line)
            elif result.get("status") == "unavailable":
                items.append(evidence.conclusion or evidence.summary)
        elif evidence.tool_name == "echidna_audit_tool":
            result, result_data = _extract_result(evidence)
            analysis_mode = _as_optional_str(result_data.get("analysis_mode")) or "property"
            test_count = int(result_data.get("test_count", 0) or 0)
            failing_test_count = int(result_data.get("failing_test_count", 0) or 0)
            passing_test_count = int(result_data.get("passing_test_count", 0) or 0)
            failing_tests = _as_str_list(result_data.get("failing_tests"))
            if bool(result_data.get("analysis_applicable")):
                line = (
                    f"Echidna ran in {analysis_mode} mode; tests={test_count}; "
                    f"passing={passing_test_count}; failing={failing_test_count}."
                )
                if failing_tests:
                    line += f" Failing checks: {', '.join(failing_tests[:4])}."
                items.append(line)
            elif result.get("status") == "unavailable":
                items.append(evidence.conclusion or evidence.summary)
            elif result.get("status") == "ok":
                items.append(evidence.conclusion or evidence.summary)
        elif evidence.tool_name == "foundry_audit_tool":
            result, result_data = _extract_result(evidence)
            contract_names = _as_str_list(result_data.get("contract_names"))
            inspect_succeeded = int(result_data.get("inspect_contracts_succeeded", 0) or 0)
            method_counts = _as_count_summary(result_data.get("method_identifier_counts"))
            storage_counts = _as_count_summary(result_data.get("storage_entry_counts"))
            if contract_names or inspect_succeeded:
                line = (
                    f"Foundry reviewed {len(contract_names)} contract(s)"
                    + (f" ({', '.join(contract_names)})" if contract_names else "")
                    + f"; inspected={inspect_succeeded}."
                )
                if method_counts:
                    line += f" Method identifiers: {method_counts}."
                if storage_counts:
                    line += f" Storage layout entries: {storage_counts}."
                items.append(line)
            elif result.get("status") == "unavailable":
                items.append(evidence.conclusion or evidence.summary)
    return ordered_unique(items)


def build_contract_testbed_findings(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "contract_testbed"
        anomaly_count = int(result_data.get("anomaly_count", 0) or 0)
        case_count = int(result_data.get("case_count", 0) or 0)
        repo_case_count = int(result_data.get("repo_case_count", 0) or 0)
        matched_review_lane_count = int(result_data.get("matched_review_lane_count", 0) or 0)
        matched_function_priority_count = int(result_data.get("matched_function_priority_count", 0) or 0)
        issue_counts = _as_count_summary(result_data.get("issue_type_counts"))
        if repo_case_count > 0:
            line = (
                f"Repo casebook {testbed_name} reviewed {case_count} case(s), "
                f"flagged {anomaly_count} anomaly-bearing case(s), and matched {matched_review_lane_count} review lane(s)."
            )
            if matched_function_priority_count > 0:
                line += f" Matched function-family priorities: {matched_function_priority_count}."
        else:
            line = f"Testbed {testbed_name} reviewed {case_count} case(s) and flagged {anomaly_count} anomaly-bearing case(s)."
        if issue_counts:
            line += f" Dominant issues: {issue_counts}."
        items.append(line)
    return ordered_unique(items)


def build_contract_remediation_validation(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        items.extend(_as_str_list(result_data.get("remediation_validation")))
    return ordered_unique(items)[:6]


def build_contract_remediation_follow_up(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    active_tools = {
        evidence.tool_name
        for evidence in session.evidence
        if isinstance(evidence.tool_name, str) and evidence.tool_name.strip()
    }
    lane_followups: list[tuple[str, list[str]]] = []
    seen_lane_labels: set[str] = set()
    repo_casebook_runs: list[tuple[str, list[str]]] = []
    family_hits: set[str] = set()
    validation_present = False

    def _record_lane(label: str, families: list[str]) -> None:
        normalized_label = label.strip()
        normalized_families = ordered_unique(families)
        if not normalized_label or not normalized_families or normalized_label in seen_lane_labels:
            return
        seen_lane_labels.add(normalized_label)
        lane_followups.append((normalized_label, normalized_families))
        family_hits.update(normalized_families)

    for evidence in session.evidence:
        _, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_inventory_tool":
            for lane in _as_str_list(result_data.get("entrypoint_review_lanes")):
                _record_lane(lane, _repo_lane_families(lane))
            if len(lane_followups) < 3:
                for summary in _as_str_list(result_data.get("risk_family_lane_summaries")):
                    for label, family in _repo_priority_summary_candidates(summary):
                        _record_lane(label, [family])
                        if len(lane_followups) >= 3:
                            break
                    if len(lane_followups) >= 3:
                        break
            if len(lane_followups) < 3:
                for summary in _as_str_list(result_data.get("entrypoint_function_family_priorities")):
                    for label, family in _repo_priority_summary_candidates(summary):
                        _record_lane(label, [family])
                        if len(lane_followups) >= 3:
                            break
                    if len(lane_followups) >= 3:
                        break
        elif evidence.tool_name == "contract_surface_tool":
            family_hits.update(_surface_families(result_data))
        elif evidence.tool_name == "contract_pattern_check_tool":
            prioritized = result_data.get("prioritized_issues")
            if not isinstance(prioritized, list):
                prioritized = prioritize_contract_issues(_as_str_list(result_data.get("issues")))
            for item in prioritized:
                if not isinstance(item, dict):
                    continue
                family = _normalize_contract_repo_family(_as_optional_str(item.get("family")))
                if family is not None:
                    family_hits.add(family)
        elif evidence.tool_name == "contract_testbed_tool":
            testbed_name = _as_optional_str(result_data.get("testbed_name")) or "contract_testbed"
            families = _contract_testbed_families(testbed_name)
            family_hits.update(families)
            if int(result_data.get("repo_case_count", 0) or 0) > 0:
                repo_casebook_runs.append((testbed_name, families))
            if _as_str_list(result_data.get("remediation_validation")):
                validation_present = True

    items: list[str] = []
    covered_families: set[str] = set()

    for lane_label, families in lane_followups[:3]:
        covered_families.update(families)
        items.append(
            f"Re-check repo lane {lane_label} with "
            f"{_format_contract_follow_up_tools_for_families(families, active_tools)} "
            f"after {_contract_follow_up_action_for_families(families)}."
        )

    for testbed_name, families in repo_casebook_runs[:2]:
        resolved_families = families or ["asset-flow"]
        covered_families.update(resolved_families)
        items.append(
            f"Re-run bounded repo casebook {testbed_name} with "
            f"{_format_contract_follow_up_tools_for_families(resolved_families, active_tools)} "
            f"after {_contract_follow_up_action_for_families(resolved_families)} to confirm matched lanes and casebook coverage shrink."
        )

    if validation_present:
        items.append(
            "Repeat the safer-control comparison after hardening to confirm the strongest bounded signal weakens instead of moving to a different review lane."
        )

    for family in (
        "upgrade/control",
        "asset-flow",
        "reserve/fee/debt",
        "proxy/storage",
        "token/allowance",
        "vault/share",
        "permit/signature",
        "oracle/price",
        "collateral/liquidation",
        "entropy/time",
        "assembly",
        "lifecycle/destruction",
    ):
        if family in family_hits and family not in covered_families:
            items.append(
                f"Re-check the strongest {_contract_follow_up_family_label(family)} paths with "
                f"{_format_contract_follow_up_tools(family, active_tools)} "
                f"after {_contract_follow_up_action(family)}."
            )

    return ordered_unique(items)[:8]


def build_contract_exit_criteria(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    lane_candidates = _collect_contract_alignment_lanes(session)
    if not lane_candidates:
        return []

    toolchain_state = _collect_contract_toolchain_state(session)
    active_tools = {
        evidence.tool_name
        for evidence in session.evidence
        if isinstance(evidence.tool_name, str) and evidence.tool_name.strip()
    }
    case_matches = _collect_repo_casebook_priority_matches(session)
    casebook_gap_fragments = _collect_casebook_gap_fragments(session)

    items: list[str] = []
    for lane_label, families in lane_candidates[:3]:
        support_labels, _ = _contract_lane_alignment_labels(
            families=families,
            toolchain_state=toolchain_state,
        )
        matched_case = _match_contract_review_queue_case(
            lane_label=lane_label,
            families=families,
            case_matches=case_matches,
        )
        line = (
            f"Exit criterion for {lane_label}: "
            + _format_contract_follow_up_tools_for_families(families, active_tools)
            + " should still replay cleanly after "
            + _contract_follow_up_action_for_families(families)
            + ", while direct support ("
            + ", ".join(support_labels or ["inventory-only"])
            + ") weakens or downgrades."
        )
        if matched_case:
            line += f" Matched case {matched_case} should stop aligning directly with this lane."
        else:
            line += " No new direct repo-casebook alignment should appear for this lane on bounded replay."
        items.append(line)

    if casebook_gap_fragments:
        items.append(
            "Do not close the current bounded repo pass while these casebook gaps remain unresolved without an explicit manual-review decision: "
            + ", ".join(casebook_gap_fragments[:4])
            + "."
        )

    compile_status = str(toolchain_state.get("compile_status", "not-run"))
    if compile_status == "observed_issue":
        items.append(
            "Do not close the repo review while compile-facing issues remain, because downstream lane convergence can still be distorted."
        )
    elif compile_status == "unavailable":
        items.append(
            "Do not close the repo review until a compiler-aware pass is available or the missing compile path is explicitly accepted as an unresolved limitation."
        )

    return ordered_unique(items)[:6]


def build_contract_residual_risk(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    lane_candidates = _collect_contract_alignment_lanes(session)
    if not lane_candidates:
        return []

    toolchain_state = _collect_contract_toolchain_state(session)
    case_matches = _collect_repo_casebook_priority_matches(session)
    casebook_gap_fragments = _collect_casebook_gap_fragments(session)

    items: list[str] = []
    for index, (lane_label, families) in enumerate(lane_candidates[:3], start=1):
        support_labels, gap_labels = _contract_lane_alignment_labels(
            families=families,
            toolchain_state=toolchain_state,
        )
        matched_case = _match_contract_review_queue_case(
            lane_label=lane_label,
            families=families,
            case_matches=case_matches,
        )
        posture = _contract_residual_risk_posture(
            support_labels=support_labels,
            gap_labels=gap_labels,
            matched_case=matched_case,
        )
        line = (
            f"Residual risk {index}: {lane_label}. Families={_format_contract_follow_up_family_labels(families)}. "
            f"Status={posture}; support={', '.join(support_labels or ['inventory-only'])}"
        )
        if matched_case:
            line += f"; matched case={matched_case}"
        if gap_labels:
            line += f"; remaining gaps={'; '.join(gap_labels[:2])}"
        line += "."
        items.append(line)

    if casebook_gap_fragments:
        items.append(
            "Residual repo-casebook gaps still remain around "
            + ", ".join(casebook_gap_fragments[:4])
            + "."
        )

    return ordered_unique(items)[:6]


def build_contract_review_focus(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        _, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_inventory_tool":
            candidate_files = _as_str_list(result_data.get("candidate_files"))
            entrypoint_candidates = _as_str_list(result_data.get("entrypoint_candidates"))
            pragma_summary = _as_str_list(result_data.get("pragma_summary"))
            shared_dependency_files = _as_str_list(result_data.get("shared_dependency_files"))
            entrypoint_flow_summaries = _as_str_list(result_data.get("entrypoint_flow_summaries"))
            entrypoint_review_lanes = _as_str_list(result_data.get("entrypoint_review_lanes"))
            risk_family_lane_summaries = _as_str_list(result_data.get("risk_family_lane_summaries"))
            entrypoint_function_family_priorities = _as_str_list(result_data.get("entrypoint_function_family_priorities"))
            risk_linked_files = _as_str_list(result_data.get("risk_linked_files"))
            dependency_dirs_present = _as_str_list(result_data.get("dependency_dirs_present"))
            if candidate_files:
                items.append(
                    "Focus repository candidate files first: "
                    + ", ".join(candidate_files[:5])
                    + "."
                )
            if entrypoint_candidates:
                items.append(
                    "Focus top-level entrypoint review across: "
                    + ", ".join(entrypoint_candidates[:5])
                    + "."
                )
            if entrypoint_flow_summaries:
                items.append("Focus entrypoint-to-dependency review chains before widening the repository scan.")
            if entrypoint_review_lanes:
                items.append("Focus prioritized entrypoint review lanes that already converge on risky dependency families.")
            if risk_family_lane_summaries:
                items.append("Focus risk-family lanes per entrypoint before broadening the repository review.")
            if entrypoint_function_family_priorities:
                items.append("Focus prioritized function families per entrypoint before widening the repo-scale audit.")
            if len(pragma_summary) > 1:
                items.append("Focus pragma drift and compiler-version boundaries across the scoped repository inventory.")
            if shared_dependency_files:
                items.append("Focus shared internal dependencies that fan into multiple entrypoint or review files.")
            if risk_linked_files:
                items.append("Focus repo-linked risky files and dependency paths before treating any single file as isolated.")
            if dependency_dirs_present:
                items.append("Focus scope boundaries between first-party contracts and dependency directories before deeper review.")
        elif evidence.tool_name == "contract_compile_tool":
            if result_data.get("pragma_spec") or int(result_data.get("error_count", 0) or 0) > 0:
                items.append("Confirm pragma selection and compiler compatibility before trusting downstream contract analysis.")
        elif evidence.tool_name == "contract_surface_tool":
            if _as_str_list(result_data.get("privileged_functions")) or _as_str_list(result_data.get("unguarded_state_changing_functions")):
                items.append("Focus access control review on privileged and externally reachable state-changing functions.")
            if any(
                _as_str_list(result_data.get(key))
                for key in ("role_management_functions", "pause_control_functions", "role_guarded_functions")
            ):
                items.append("Focus role management, operator or guardian control, and pause-authority paths.")
            if any(
                _as_str_list(result_data.get(key))
                for key in ("low_level_call_functions", "call_with_value_functions", "delegatecall_functions")
            ):
                items.append("Focus external call sequencing, value transfer handling, and delegatecall exposure.")
            if any(
                _as_str_list(result_data.get(key))
                for key in ("token_transfer_functions", "token_transfer_from_functions", "approve_functions")
            ):
                items.append("Focus token transfer, approval, and allowance handling.")
            if any(
                _as_str_list(result_data.get(key))
                for key in ("deposit_like_functions", "asset_exit_functions", "rescue_or_sweep_functions")
            ):
                items.append("Focus deposit, claim, withdraw, rescue, and sweep flow consistency across externally reachable paths.")
            if _as_str_list(result_data.get("accounting_mutation_functions")):
                items.append("Focus balance, allowance, claim-state, and accounting consistency around externally reachable value flow.")
            if any(
                _as_str_list(result_data.get(key))
                for key in ("share_accounting_functions", "vault_conversion_functions")
            ):
                items.append("Focus vault share mint or burn logic, asset backing, and asset-share conversion assumptions.")
            if _as_str_list(result_data.get("signature_validation_functions")):
                items.append("Focus signature validation, permit flows, and replay protection.")
            if _as_str_list(result_data.get("oracle_dependency_functions")):
                items.append("Focus oracle freshness checks and price dependency assumptions.")
            if any(
                _as_str_list(result_data.get(key))
                for key in (
                    "collateral_management_functions",
                    "liquidation_functions",
                    "liquidation_fee_functions",
                    "reserve_dependency_functions",
                )
            ):
                items.append(
                    "Focus collateral ratios, liquidation eligibility, liquidation-fee allocation, reserve-derived pricing, and health-factor assumptions."
                )
            if any(
                _as_str_list(result_data.get(key))
                for key in (
                    "fee_collection_functions",
                    "reserve_buffer_functions",
                    "reserve_accounting_functions",
                    "debt_accounting_functions",
                    "bad_debt_socialization_functions",
                )
            ):
                items.append(
                    "Focus protocol-fee collection, reserve synchronization, reserve-buffer coverage, bad-debt socialization, debt-state transitions, and accrual-side accounting assumptions."
                )
            if _as_str_list(result_data.get("assembly_functions")):
                items.append("Focus inline assembly review and storage mutation paths.")
            if any(
                result_data.get(key)
                for key in ("implementation_slot_constant_present", "storage_gap_present")
            ) or any(
                _as_str_list(result_data.get(key))
                for key in (
                    "proxy_delegatecall_functions",
                    "storage_slot_write_functions",
                    "implementation_reference_functions",
                )
            ):
                items.append("Focus proxy delegation, implementation-slot writes, and storage-layout isolation assumptions.")
            if any(
                _as_str_list(result_data.get(key))
                for key in ("timestamp_functions", "entropy_source_functions")
            ):
                items.append("Focus timestamp, entropy, and randomness assumptions.")
            if _as_str_list(result_data.get("state_transition_functions")) or _as_str_list(result_data.get("loop_functions")):
                items.append("Focus state-machine transitions and loop-driven execution paths.")
        elif evidence.tool_name == "contract_pattern_check_tool":
            family_counts = result_data.get("issue_family_counts")
            if isinstance(family_counts, dict):
                if any(key in family_counts for key in ("unguarded_upgrade_surface", "unvalidated_implementation_target")):
                    items.append("Focus upgrade authorization and implementation target validation.")
                if any(
                    key in family_counts
                    for key in (
                        "unguarded_role_management_surface",
                        "unguarded_pause_control_surface",
                        "unguarded_privileged_state_change",
                    )
                ):
                    items.append("Focus authorization boundaries for role grants, operator paths, and pause controls.")
                if any(
                    key in family_counts
                    for key in (
                        "asset_exit_without_balance_validation",
                        "unguarded_rescue_or_sweep_flow",
                        "unguarded_rescue_or_sweep_surface",
                    )
                ):
                    items.append("Focus cross-function fund movement, asset-exit validation, and rescue or sweep authority.")
                if any(
                    key in family_counts
                    for key in (
                        "share_mint_without_asset_backing_review",
                        "share_redeem_without_share_validation",
                        "vault_conversion_review_required",
                    )
                ):
                    items.append("Focus vault share issuance, redemption validation, and asset-share conversion assumptions.")
                if any(
                    key in family_counts
                    for key in (
                        "proxy_fallback_delegatecall_review_required",
                        "proxy_storage_collision_review_required",
                        "storage_slot_write_review_required",
                    )
                ):
                    items.append("Focus proxy fallback delegation, storage-slot writes, and storage-collision assumptions.")
                if "missing_zero_address_validation" in family_counts:
                    items.append("Focus zero-address validation for critical address inputs and ownership changes.")
                if "signature_replay_review_required" in family_counts:
                    items.append("Focus replay protection, nonce handling, and signature invalidation paths.")
                if "oracle_staleness_review_required" in family_counts:
                    items.append("Focus oracle freshness, staleness windows, and fallback assumptions.")
                if any(
                    key in family_counts
                    for key in (
                        "protocol_fee_without_reserve_sync_review",
                        "reserve_accounting_drift_review_required",
                        "debt_state_transition_review_required",
                    )
                ):
                    items.append("Focus protocol-fee handling, reserve-sync assumptions, and debt-state transitions before widening protocol-style review.")
                if any(
                    key in family_counts
                    for key in (
                        "collateral_ratio_review_required",
                        "liquidation_without_fresh_price_review",
                        "reserve_spot_dependency_review_required",
                    )
                ):
                    items.append("Focus collateral-ratio enforcement, liquidation freshness, and reserve-derived pricing assumptions.")
                if any(key in family_counts for key in ("reentrancy_review_required", "unchecked_external_call_surface", "state_transition_after_external_call", "external_call_in_loop")):
                    items.append("Focus reentrancy-adjacent sequencing and post-call state updates.")
        elif evidence.tool_name == "slither_audit_tool":
            if int(result_data.get("finding_count", 0) or 0) > 0:
                items.append("Cross-check built-in findings against Slither detector output before stronger claims.")
        elif evidence.tool_name == "echidna_audit_tool":
            if bool(result_data.get("analysis_applicable")):
                analysis_mode = _as_optional_str(result_data.get("analysis_mode")) or "property"
                items.append(
                    f"Focus {analysis_mode}-style invariants and falsifiable contract behaviors under bounded fuzzing."
                )
                if int(result_data.get("failing_test_count", 0) or 0) > 0:
                    items.append("Inspect Echidna counterexamples before treating any failing check as a security claim.")
        elif evidence.tool_name == "foundry_audit_tool":
            if int(result_data.get("inspect_contracts_succeeded", 0) or 0) > 0:
                items.append("Use Foundry method identifiers and storage layout output to validate structural assumptions.")
        elif evidence.tool_name == "contract_testbed_tool":
            if int(result_data.get("anomaly_count", 0) or 0) > 0:
                focus_line = _contract_testbed_focus_line(_as_optional_str(result_data.get("testbed_name")))
                if focus_line:
                    items.append(focus_line)
            if int(result_data.get("repo_case_count", 0) or 0) > 0:
                items.append("Focus matched repo-scale casebook lanes before widening manual review across the whole contract repository.")
    return ordered_unique(items)[:8]


def build_contract_remediation_guidance(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []

    family_hits: set[str] = set()
    guidance: list[str] = []
    rerun_signals = False

    for evidence in session.evidence:
        result, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_inventory_tool":
            if len(_as_str_list(result_data.get("pragma_summary"))) > 1:
                guidance.append(
                    "Normalize compiler expectations across the scoped repository before trusting cross-file conclusions, then re-run compile and static checks."
                )
            if "inventory_scan_truncated" in set(_as_str_list(result_data.get("issues"))):
                guidance.append(
                    "Expand or confirm the bounded repository scope before treating any remediation plan as complete."
                )
        elif evidence.tool_name == "contract_compile_tool":
            if result.get("status") == "observed_issue" or int(result_data.get("error_count", 0) or 0) > 0:
                guidance.append(
                    "Resolve compiler-facing issues first so later hardening work is validated against the intended build path."
                )
                rerun_signals = True
        elif evidence.tool_name == "contract_surface_tool":
            family_hits.update(_surface_families(result_data))
        elif evidence.tool_name == "contract_pattern_check_tool":
            prioritized = result_data.get("prioritized_issues")
            if not isinstance(prioritized, list):
                prioritized = prioritize_contract_issues(_as_str_list(result_data.get("issues")))
            for item in prioritized:
                if not isinstance(item, dict):
                    continue
                family = _normalize_contract_repo_family(_as_optional_str(item.get("family")))
                if family:
                    family_hits.add(family)
                    rerun_signals = True
        elif evidence.tool_name == "contract_testbed_tool":
            anomaly_count = int(result_data.get("anomaly_count", 0) or 0)
            testbed_families = _contract_testbed_families(_as_optional_str(result_data.get("testbed_name")))
            if anomaly_count > 0 and testbed_families:
                family_hits.update(testbed_families)
                rerun_signals = True
        elif evidence.tool_name == "slither_audit_tool":
            impact_counts = result_data.get("impact_counts")
            if isinstance(impact_counts, dict) and sum(int(value or 0) for value in impact_counts.values()) > 0:
                rerun_signals = True
                guidance.append(
                    "Reconcile built-in signals with Slither findings and confirm that any hardening step removes the same detector families on re-run."
                )
        elif evidence.tool_name == "echidna_audit_tool":
            failing_tests = _as_str_list(result_data.get("failing_tests"))
            if failing_tests:
                rerun_signals = True
                guidance.append(
                    "Treat failing bounded invariant checks as remediation gates and re-run them after each candidate hardening change."
                )
        elif evidence.tool_name == "foundry_audit_tool":
            if int(result_data.get("inspect_contracts_succeeded", 0) or 0) > 0:
                guidance.append(
                    "Use Foundry structural output to confirm that hardening changes preserve intended method exposure and storage layout assumptions."
                )

    family_guidance_map = {
        "upgrade/control": "Harden authority boundaries on upgrade, initializer, role-management, ownership, and pause-control paths before widening the review.",
        "asset-flow": "Move balance, claim-state, and other accounting updates into a safer order around external value transfer, then re-check the strongest local flow signals.",
        "reserve/fee/debt": "Tighten protocol-fee handling, reserve synchronization, reserve-buffer coverage, bad-debt socialization, and debt-state transitions before trusting reserve or debt accounting paths.",
        "proxy/storage": "Validate implementation targets, delegatecall boundaries, and storage-slot isolation before trusting proxy or upgrade paths.",
        "token/allowance": "Require explicit token return-value handling, safer allowance transitions, and clearer token-flow validation before trusting transfer or approval paths.",
        "vault/share": "Tighten asset-backing, share mint or burn validation, and conversion assumptions before relying on vault-style accounting.",
        "permit/signature": "Tighten replay protection, nonce invalidation, and signature-domain assumptions before treating signature-authorized flows as safe.",
        "oracle/price": "Add or confirm oracle freshness, fallback, and price-sanity checks before trusting price-dependent control flow.",
        "collateral/liquidation": "Add explicit collateral-ratio, health-factor, liquidation-threshold, liquidation-bonus bounds, and reserve-window controls before trusting collateralized control flow.",
        "entropy/time": "Remove or constrain timestamp and entropy assumptions before using them in control-critical or value-sensitive logic.",
        "assembly": "Reduce inline assembly trust boundaries or add explicit surrounding validation before accepting the current storage or memory behavior.",
        "lifecycle/destruction": "Constrain or remove destructive lifecycle paths unless decommissioning behavior is intentionally gated and reviewable.",
    }
    for family in (
        "upgrade/control",
        "asset-flow",
        "reserve/fee/debt",
        "proxy/storage",
        "token/allowance",
        "vault/share",
        "permit/signature",
        "oracle/price",
        "collateral/liquidation",
        "entropy/time",
        "assembly",
        "lifecycle/destruction",
    ):
        if family in family_hits:
            guidance.append(family_guidance_map[family])

    if rerun_signals:
        guidance.append(
            "After any defensive change, re-run compile, surface, static, and bounded testbed checks to confirm the strongest local signal weakens instead of only moving location."
        )

    return ordered_unique(guidance)[:8]


def _repo_lane_families(lane: str) -> list[str]:
    _, separator, marker_part = lane.partition(" => ")
    if not separator:
        return []
    families = [
        family
        for family in (
            _normalize_contract_repo_family(marker.strip())
            for marker in marker_part.split(",")
            if marker.strip()
        )
        if family is not None
    ]
    return ordered_unique(families)


def _repo_priority_summary_candidates(summary: str) -> list[tuple[str, str]]:
    entrypoint, fragments = _parse_repo_priority_summary(summary)
    if not entrypoint:
        return []
    items: list[tuple[str, str]] = []
    for fragment in fragments:
        family_label, _ = _split_repo_priority_fragment(fragment)
        family = _normalize_contract_repo_family(family_label)
        if family is None:
            continue
        items.append((f"{entrypoint} => {fragment}", family))
    return items


def _collect_contract_alignment_lanes(session: ResearchSession) -> list[tuple[str, list[str]]]:
    lane_candidates: dict[str, dict[str, Any]] = {}

    def _record_lane(label: str, families: list[str], weight: int) -> None:
        normalized_label = label.strip()
        normalized_families = ordered_unique(families)
        if not normalized_label or not normalized_families:
            return
        candidate = lane_candidates.get(normalized_label)
        if candidate is None:
            candidate = {
                "label": normalized_label,
                "families": normalized_families,
                "score": 0,
            }
            lane_candidates[normalized_label] = candidate
        else:
            candidate["families"] = ordered_unique([*candidate["families"], *normalized_families])
        candidate["score"] += weight

    for evidence in session.evidence:
        _, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_inventory_tool":
            for lane in _as_str_list(result_data.get("entrypoint_review_lanes")):
                _record_lane(lane, _repo_lane_families(lane), 4)
            for summary in _as_str_list(result_data.get("risk_family_lane_summaries")):
                for label, family in _repo_priority_summary_candidates(summary):
                    _record_lane(label, [family], 3)
            for summary in _as_str_list(result_data.get("entrypoint_function_family_priorities")):
                for label, family in _repo_priority_summary_candidates(summary):
                    _record_lane(label, [family], 2)
        elif evidence.tool_name == "contract_testbed_tool":
            for lane in _casebook_lane_samples(result_data):
                _record_lane(lane, _repo_lane_families(lane), 3)

    ordered = sorted(
        lane_candidates.values(),
        key=lambda item: (-int(item["score"]), str(item["label"]).lower()),
    )
    return [
        (str(item["label"]), list(item["families"]))
        for item in ordered
    ]


def _collect_inventory_lane_sets(session: ResearchSession) -> tuple[list[str], list[str], list[str]]:
    review_lanes: list[str] = []
    risk_lanes: list[str] = []
    function_priorities: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_inventory_tool":
            continue
        _, result_data = _extract_result(evidence)
        review_lanes.extend(_as_str_list(result_data.get("entrypoint_review_lanes")))
        risk_lanes.extend(_as_str_list(result_data.get("risk_family_lane_summaries")))
        function_priorities.extend(_as_str_list(result_data.get("entrypoint_function_family_priorities")))
    return (
        ordered_unique(review_lanes),
        ordered_unique(risk_lanes),
        ordered_unique(function_priorities),
    )


def _collect_matched_casebook_lane_sets(result_data: dict[str, Any]) -> tuple[list[str], list[str], list[str]]:
    matched_review_lanes: list[str] = []
    matched_risk_lanes: list[str] = []
    matched_function_priorities: list[str] = []
    for case in result_data.get("cases", []):
        if not isinstance(case, dict):
            continue
        matched_review_lanes.extend(_as_str_list(case.get("matched_review_lanes")))
        matched_risk_lanes.extend(_as_str_list(case.get("matched_risk_family_lanes")))
        matched_function_priorities.extend(_as_str_list(case.get("matched_function_family_priorities")))
    return (
        ordered_unique(matched_review_lanes),
        ordered_unique(matched_risk_lanes),
        ordered_unique(matched_function_priorities),
    )


def _collect_contract_toolchain_state(session: ResearchSession) -> dict[str, Any]:
    state: dict[str, Any] = {
        "compile_status": "not-run",
        "surface_families": set(),
        "pattern_families": set(),
        "repo_casebook_families": set(),
        "testbed_families": set(),
        "slither_status": "not-run",
        "echidna_status": "not-run",
        "foundry_status": "not-run",
    }

    for evidence in session.evidence:
        result, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_compile_tool":
            status = _as_optional_str(result.get("status"))
            if status in {"ok", "observed_issue", "unavailable"}:
                state["compile_status"] = status
        elif evidence.tool_name == "contract_surface_tool":
            state["surface_families"].update(_surface_families(result_data))
        elif evidence.tool_name == "contract_pattern_check_tool":
            prioritized = result_data.get("prioritized_issues")
            if not isinstance(prioritized, list):
                prioritized = prioritize_contract_issues(_as_str_list(result_data.get("issues")))
            for item in prioritized:
                if not isinstance(item, dict):
                    continue
                family = _normalize_contract_repo_family(_as_optional_str(item.get("family")))
                if family is not None:
                    state["pattern_families"].add(family)
        elif evidence.tool_name == "contract_testbed_tool":
            testbed_name = _as_optional_str(result_data.get("testbed_name"))
            families = _contract_testbed_families(testbed_name)
            if not families:
                continue
            if int(result_data.get("repo_case_count", 0) or 0) > 0:
                state["repo_casebook_families"].update(families)
            else:
                state["testbed_families"].update(families)
        elif evidence.tool_name == "slither_audit_tool":
            state["slither_status"] = (
                "unavailable" if result.get("status") == "unavailable" else "available"
            )
        elif evidence.tool_name == "echidna_audit_tool":
            if bool(result_data.get("analysis_applicable")):
                state["echidna_status"] = "applicable"
            elif result.get("status") == "unavailable":
                state["echidna_status"] = "unavailable"
            else:
                state["echidna_status"] = "not-applicable"
        elif evidence.tool_name == "foundry_audit_tool":
            if int(result_data.get("inspect_contracts_succeeded", 0) or 0) > 0:
                state["foundry_status"] = "inspected"
            elif result.get("status") == "unavailable":
                state["foundry_status"] = "unavailable"
            else:
                state["foundry_status"] = "build-only"

    return state


def _collect_repo_casebook_priority_matches(session: ResearchSession) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        if int(result_data.get("repo_case_count", 0) or 0) <= 0:
            continue
        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "repo_casebook"
        for case in result_data.get("cases", []):
            if not isinstance(case, dict) or not bool(case.get("repo_case")):
                continue
            case_id = _as_optional_str(case.get("case_id"))
            if case_id is None:
                continue
            review_lanes = _as_str_list(case.get("matched_review_lanes"))
            risk_family_lanes = _as_str_list(case.get("matched_risk_family_lanes"))
            function_family_priorities = _as_str_list(case.get("matched_function_family_priorities"))
            families: list[str] = []
            for lane in review_lanes:
                families.extend(_repo_lane_families(lane))
            for summary in [*risk_family_lanes, *function_family_priorities]:
                families.extend(family for _, family in _repo_priority_summary_candidates(summary))
            score = (
                len(review_lanes) * 5
                + len(risk_family_lanes) * 3
                + len(function_family_priorities) * 2
                + len(_as_str_list(case.get("issues")))
            )
            matches.append(
                {
                    "label": f"{case_id} via {testbed_name}",
                    "review_lanes": ordered_unique(review_lanes),
                    "families": ordered_unique(families),
                    "score": score,
                }
            )

    return sorted(
        matches,
        key=lambda item: (-int(item["score"]), str(item["label"]).lower()),
    )


def _match_contract_review_queue_case(
    *,
    lane_label: str,
    families: list[str],
    case_matches: list[dict[str, Any]],
) -> str | None:
    normalized_families = set(ordered_unique(families))
    for case in case_matches:
        if lane_label in case["review_lanes"]:
            return str(case["label"])
    for case in case_matches:
        if normalized_families.intersection(case["families"]):
            return str(case["label"])
    return None


def _collect_casebook_gap_fragments(session: ResearchSession) -> list[str]:
    inventory_review_lanes, inventory_risk_lanes, inventory_function_priorities = _collect_inventory_lane_sets(session)
    if not inventory_review_lanes and not inventory_risk_lanes and not inventory_function_priorities:
        return []

    matched_review_lanes: list[str] = []
    matched_risk_lanes: list[str] = []
    matched_function_priorities: list[str] = []
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        if int(result_data.get("repo_case_count", 0) or 0) <= 0:
            continue
        review_lanes, risk_lanes, function_priorities = _collect_matched_casebook_lane_sets(result_data)
        matched_review_lanes.extend(review_lanes)
        matched_risk_lanes.extend(risk_lanes)
        matched_function_priorities.extend(function_priorities)

    missing_review_lanes = ordered_unique([lane for lane in inventory_review_lanes if lane not in matched_review_lanes])
    missing_risk_lanes = ordered_unique([lane for lane in inventory_risk_lanes if lane not in matched_risk_lanes])
    missing_function_priorities = ordered_unique(
        [lane for lane in inventory_function_priorities if lane not in matched_function_priorities]
    )
    return ordered_unique([*missing_review_lanes[:2], *missing_risk_lanes[:1], *missing_function_priorities[:1]])


def _contract_lane_alignment_labels(
    *,
    families: list[str],
    toolchain_state: dict[str, Any],
) -> tuple[list[str], list[str]]:
    normalized_families = ordered_unique(families)
    support_labels: list[str] = []
    gap_labels: list[str] = []

    compile_status = str(toolchain_state.get("compile_status", "not-run"))
    if compile_status == "ok":
        support_labels.append("compile")
    elif compile_status == "observed_issue":
        support_labels.append("compile-with-issues")
    elif compile_status == "unavailable":
        gap_labels.append("compile path unavailable")
    elif compile_status == "not-run" and any(
        "contract_compile_tool" in _contract_tool_order_for_family(family)
        for family in normalized_families
    ):
        gap_labels.append("no compile pass in this run")

    surface_families = set(toolchain_state.get("surface_families", set()))
    if any(family in surface_families for family in normalized_families):
        support_labels.append("surface")

    pattern_families = set(toolchain_state.get("pattern_families", set()))
    if any(family in pattern_families for family in normalized_families):
        support_labels.append("built-in-static")
    elif any(
        "contract_pattern_check_tool" in _contract_tool_order_for_family(family)
        for family in normalized_families
    ):
        gap_labels.append("built-in family match not yet converged")

    slither_status = str(toolchain_state.get("slither_status", "not-run"))
    if slither_status == "available":
        support_labels.append("Slither")
    elif slither_status == "unavailable":
        gap_labels.append("Slither unavailable")
    elif any(
        "slither_audit_tool" in _contract_tool_order_for_family(family)
        for family in normalized_families
    ):
        gap_labels.append("no Slither pass in this run")

    echidna_status = str(toolchain_state.get("echidna_status", "not-run"))
    if echidna_status == "applicable":
        support_labels.append("Echidna")
    elif echidna_status == "unavailable":
        gap_labels.append("Echidna unavailable")
    elif echidna_status == "not-applicable":
        gap_labels.append("Echidna not applicable in this run")
    elif any(
        "echidna_audit_tool" in _contract_tool_order_for_family(family)
        for family in normalized_families
    ):
        gap_labels.append("no Echidna replay in this run")

    foundry_status = str(toolchain_state.get("foundry_status", "not-run"))
    if foundry_status == "inspected":
        support_labels.append("Foundry")
    elif foundry_status == "unavailable":
        gap_labels.append("Foundry unavailable")
    elif foundry_status == "build-only":
        gap_labels.append("Foundry structural inspection absent")
    elif any(
        "foundry_audit_tool" in _contract_tool_order_for_family(family)
        for family in normalized_families
    ):
        gap_labels.append("no Foundry structural pass in this run")

    repo_casebook_families = set(toolchain_state.get("repo_casebook_families", set()))
    testbed_families = set(toolchain_state.get("testbed_families", set()))
    if any(family in repo_casebook_families for family in normalized_families):
        support_labels.append("repo-casebook")
    if any(family in testbed_families for family in normalized_families):
        support_labels.append("bounded testbed")
    elif any(
        "contract_testbed_tool" in _contract_tool_order_for_family(family)
        for family in normalized_families
    ) and not any(family in repo_casebook_families for family in normalized_families):
        gap_labels.append("no family-matched bounded casebook")

    return ordered_unique(support_labels), ordered_unique(gap_labels)


def _contract_lane_validation_posture(
    *,
    support_labels: list[str],
    gap_labels: list[str],
    matched_case: str | None,
) -> str:
    support_count = len(support_labels)
    has_casebook = "repo-casebook" in support_labels
    has_deep_runtime = any(label in {"Echidna", "Foundry"} for label in support_labels)
    has_static = any(label in {"built-in-static", "Slither"} for label in support_labels)
    severe_gap = any(
        gap in {
            "compile path unavailable",
            "Slither unavailable",
            "Echidna unavailable",
            "Foundry unavailable",
        }
        for gap in gap_labels
    )

    if has_casebook and has_static and has_deep_runtime and support_count >= 5 and not severe_gap:
        return "strong bounded validation"
    if has_casebook and has_static and support_count >= 4:
        return "casebook-backed validation"
    if matched_case and support_count >= 3:
        return "multi-tool triaged"
    if support_count >= 2:
        return "developing bounded coverage"
    return "inventory-led early review"


def _contract_benchmark_posture_label(
    *,
    coverage_label: str,
    matched_case_count: int,
    validated_group_count: int,
    support_count: int,
) -> str:
    if coverage_label == "full" and matched_case_count >= 2 and validated_group_count > 0 and support_count >= 4:
        return "Strong bounded benchmark posture"
    if coverage_label in {"full", "partial"} and matched_case_count > 0 and support_count >= 3:
        return "Usable bounded benchmark posture"
    if coverage_label in {"partial", "minimal"} and matched_case_count > 0:
        return "Early bounded benchmark posture"
    return "Limited benchmark posture"


def _contract_tool_order_for_family(family: str) -> list[str]:
    ordered_tools_by_family = {
        "upgrade/control": [
            "contract_compile_tool",
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "slither_audit_tool",
            "foundry_audit_tool",
            "contract_testbed_tool",
        ],
        "asset-flow": [
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "contract_testbed_tool",
            "echidna_audit_tool",
            "foundry_audit_tool",
            "slither_audit_tool",
        ],
        "reserve/fee/debt": [
            "contract_compile_tool",
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "contract_testbed_tool",
            "echidna_audit_tool",
            "foundry_audit_tool",
            "slither_audit_tool",
        ],
        "proxy/storage": [
            "contract_compile_tool",
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "slither_audit_tool",
            "foundry_audit_tool",
            "contract_testbed_tool",
        ],
        "token/allowance": [
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "contract_testbed_tool",
            "slither_audit_tool",
        ],
        "vault/share": [
            "contract_compile_tool",
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "contract_testbed_tool",
            "echidna_audit_tool",
            "foundry_audit_tool",
        ],
        "permit/signature": [
            "contract_compile_tool",
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "contract_testbed_tool",
            "slither_audit_tool",
        ],
        "oracle/price": [
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "contract_testbed_tool",
            "echidna_audit_tool",
            "slither_audit_tool",
        ],
        "collateral/liquidation": [
            "contract_compile_tool",
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "contract_testbed_tool",
            "echidna_audit_tool",
            "slither_audit_tool",
        ],
        "entropy/time": [
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "contract_testbed_tool",
        ],
        "assembly": [
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "slither_audit_tool",
            "foundry_audit_tool",
        ],
        "lifecycle/destruction": [
            "contract_surface_tool",
            "contract_pattern_check_tool",
            "contract_testbed_tool",
            "slither_audit_tool",
        ],
    }
    return ordered_tools_by_family.get(
        family,
        ["contract_surface_tool", "contract_pattern_check_tool", "contract_testbed_tool"],
    )


def _format_contract_follow_up_tools(family: str, active_tools: set[str]) -> str:
    tool_labels = {
        "contract_compile_tool": "compile",
        "contract_surface_tool": "surface",
        "contract_pattern_check_tool": "pattern",
        "contract_testbed_tool": "bounded testbed",
        "slither_audit_tool": "Slither",
        "echidna_audit_tool": "Echidna",
        "foundry_audit_tool": "Foundry",
    }
    ordered_tools = _contract_tool_order_for_family(family)
    labels = [tool_labels[name] for name in ordered_tools if name in active_tools]
    if not labels:
        labels = ["surface", "pattern"]
    return _format_follow_up_tool_labels(labels)


def _format_contract_follow_up_tools_for_families(families: list[str], active_tools: set[str]) -> str:
    normalized_families = ordered_unique(families)
    if len(normalized_families) == 1:
        return _format_contract_follow_up_tools(normalized_families[0], active_tools)

    tool_labels = {
        "contract_compile_tool": "compile",
        "contract_surface_tool": "surface",
        "contract_pattern_check_tool": "pattern",
        "contract_testbed_tool": "bounded testbed",
        "slither_audit_tool": "Slither",
        "echidna_audit_tool": "Echidna",
        "foundry_audit_tool": "Foundry",
    }
    ordered_tools = ordered_unique(
        tool_name
        for family in normalized_families
        for tool_name in _contract_tool_order_for_family(family)
    )
    labels = [tool_labels[name] for name in ordered_tools if name in active_tools]
    if not labels:
        labels = ["surface", "pattern"]
    return _format_follow_up_tool_labels(labels)


def _format_follow_up_tool_labels(labels: list[str]) -> str:
    normalized = ordered_unique(labels)
    if len(normalized) == 1:
        return f"{normalized[0]} path"
    if len(normalized) == 2:
        return f"{normalized[0]} and {normalized[1]} paths"
    return f"{', '.join(normalized[:-1])}, and {normalized[-1]} paths"


def _contract_follow_up_family_label(family: str) -> str:
    labels = {
        "upgrade/control": "upgrade or control",
        "asset-flow": "asset-flow",
        "reserve/fee/debt": "protocol-fee, reserve-buffer, or debt-accounting",
        "proxy/storage": "proxy or storage",
        "token/allowance": "token or allowance",
        "vault/share": "vault or share-accounting",
        "permit/signature": "signature or permit",
        "oracle/price": "oracle or price-dependent",
        "collateral/liquidation": "collateral, liquidation, or liquidation-fee",
        "entropy/time": "time or entropy-sensitive",
        "assembly": "assembly-sensitive",
        "lifecycle/destruction": "lifecycle or destructive",
    }
    return labels.get(family, family)


def _format_contract_follow_up_family_labels(families: list[str]) -> str:
    normalized = ordered_unique(_contract_follow_up_family_label(family) for family in families)
    if not normalized:
        return "repo review"
    if len(normalized) == 1:
        return normalized[0]
    if len(normalized) == 2:
        return f"{normalized[0]} and {normalized[1]}"
    return f"{', '.join(normalized[:-1])}, and {normalized[-1]}"


def _contract_follow_up_action(family: str) -> str:
    actions = {
        "upgrade/control": "tightening upgrade, initializer, ownership, role, and pause authority boundaries",
        "asset-flow": "hardening balance, claim-state, and asset-exit ordering",
        "reserve/fee/debt": "hardening protocol-fee handling, reserve synchronization, reserve-buffer coverage, and debt-accounting controls",
        "proxy/storage": "hardening implementation validation, delegatecall boundaries, and storage-slot isolation",
        "token/allowance": "hardening token return-value handling and allowance transitions",
        "vault/share": "hardening share-accounting, asset-backing, and conversion validation",
        "permit/signature": "hardening nonce, domain, and replay protections",
        "oracle/price": "hardening freshness, fallback, and price-sanity checks",
        "collateral/liquidation": "hardening collateral-ratio guards, liquidation-fee bounds, liquidation freshness, and reserve-window assumptions",
        "entropy/time": "removing or constraining timestamp and entropy assumptions",
        "assembly": "wrapping inline assembly with stricter surrounding validation",
        "lifecycle/destruction": "gating or removing destructive lifecycle paths",
    }
    return actions.get(family, "tightening the strongest local control assumptions")


def _contract_follow_up_action_for_families(families: list[str]) -> str:
    normalized_families = ordered_unique(families)
    if len(normalized_families) == 1:
        return _contract_follow_up_action(normalized_families[0])

    actions = ordered_unique(_contract_follow_up_action(family) for family in normalized_families)
    if len(actions) == 1:
        return actions[0]
    if len(actions) == 2:
        return f"{actions[0]} and {actions[1]}"
    return f"{'; '.join(actions[:-1])}; and {actions[-1]}"


def _contract_residual_risk_posture(
    *,
    support_labels: list[str],
    gap_labels: list[str],
    matched_case: str | None,
) -> str:
    if matched_case and gap_labels:
        return "open"
    if len(gap_labels) >= 2:
        return "open"
    if gap_labels:
        return "narrowing"
    if matched_case or len(support_labels) >= 3:
        return "watchlist"
    return "monitor"


def _contract_casebook_focus_label(testbed_name: str) -> str:
    labels = {
        "repo_upgrade_casebook": "proxy, upgrade, and storage lanes",
        "repo_asset_flow_casebook": "asset-flow, rescue, and vault lanes",
        "repo_oracle_casebook": "oracle, price, collateral, and liquidation lanes",
        "repo_protocol_accounting_casebook": "protocol-fee, reserve-sync, debt-accounting, and bad-debt socialization lanes",
        "repo_vault_permission_casebook": "vault, permit, allowance, and share-accounting lanes",
        "repo_governance_timelock_casebook": "governance, timelock, guardian, and queued upgrade lanes",
        "repo_rewards_distribution_casebook": "reward-index, emission, claim, and reserve-backed distribution lanes",
        "repo_stablecoin_collateral_casebook": "stablecoin mint, redemption, collateral, reserve, and liquidation lanes",
        "repo_amm_liquidity_casebook": "AMM swap, liquidity, reserve, fee-growth, and oracle-sync lanes",
        "repo_bridge_custody_casebook": "bridge relay, custody, withdrawal-finalization, proof, and replay-protection lanes",
        "repo_staking_rebase_casebook": "staking, rebase, queued withdrawal, slash, and validator-reward lanes",
        "repo_keeper_auction_casebook": "keeper reward, auction settlement, liquidation, oracle, and reserve-buffer lanes",
        "repo_treasury_vesting_casebook": "treasury release, vesting schedule, beneficiary payout, sweep, and timelock lanes",
        "repo_insurance_recovery_casebook": "insurance-fund depletion, deficit absorption, reserve recovery, and emergency-settlement lanes",
    }
    return labels.get(testbed_name, "repo-scale review lanes")


def _contract_casebook_archetype_label(testbed_name: str) -> str | None:
    labels = {
        "repo_upgrade_casebook": "upgrade and proxy control archetype",
        "repo_asset_flow_casebook": "asset-flow and rescue archetype",
        "repo_oracle_casebook": "oracle and liquidation archetype",
        "repo_protocol_accounting_casebook": "lending-style reserve and debt archetype",
        "repo_vault_permission_casebook": "vault and permit archetype",
        "repo_governance_timelock_casebook": "governance and timelock archetype",
        "repo_rewards_distribution_casebook": "reward distribution archetype",
        "repo_stablecoin_collateral_casebook": "stablecoin and collateral archetype",
        "repo_amm_liquidity_casebook": "AMM and liquidity archetype",
        "repo_bridge_custody_casebook": "bridge and custody archetype",
        "repo_staking_rebase_casebook": "staking and rebase archetype",
        "repo_keeper_auction_casebook": "keeper and auction archetype",
        "repo_treasury_vesting_casebook": "treasury and vesting archetype",
        "repo_insurance_recovery_casebook": "insurance and recovery archetype",
    }
    return labels.get(testbed_name)


def _casebook_support_labels(session: ResearchSession) -> list[str]:
    labels: list[str] = []
    for evidence in session.evidence:
        result, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_compile_tool":
            if result.get("status") == "ok":
                labels.append("compile")
            elif result.get("status") == "observed_issue":
                labels.append("compile-with-issues")
        elif evidence.tool_name == "contract_pattern_check_tool":
            labels.append("built-in-static")
        elif evidence.tool_name == "slither_audit_tool":
            if result.get("status") == "unavailable":
                labels.append("Slither-unavailable")
            else:
                labels.append("Slither")
        elif evidence.tool_name == "echidna_audit_tool":
            if bool(result_data.get("analysis_applicable")):
                labels.append("Echidna")
            elif result.get("status") == "unavailable":
                labels.append("Echidna-unavailable")
        elif evidence.tool_name == "foundry_audit_tool":
            if int(result_data.get("inspect_contracts_succeeded", 0) or 0) > 0:
                labels.append("Foundry")
            elif result.get("status") == "unavailable":
                labels.append("Foundry-unavailable")
    return ordered_unique(labels)


def _casebook_lane_samples(result_data: dict[str, Any]) -> list[str]:
    lane_counter: Counter[str] = Counter()
    family_counter: Counter[str] = Counter()
    function_counter: Counter[str] = Counter()
    for case in result_data.get("cases", []):
        if not isinstance(case, dict):
            continue
        for line in _as_str_list(case.get("matched_review_lanes")):
            lane_counter[line] += 1
        for line in _as_str_list(case.get("matched_risk_family_lanes")):
            family_counter[line] += 1
        for line in _as_str_list(case.get("matched_function_family_priorities")):
            function_counter[line] += 1
    ordered_lanes = [line for line, _ in lane_counter.most_common(2)]
    ordered_families = [line for line, _ in family_counter.most_common(1)]
    ordered_functions = [line for line, _ in function_counter.most_common(1)]
    return ordered_unique([*ordered_lanes, *ordered_families, *ordered_functions])


def _extract_casebook_coverage_label(lines: list[str]) -> str:
    for line in lines:
        _, separator, tail = line.partition("coverage=")
        if not separator:
            continue
        label = tail.split(".", 1)[0].strip().lower()
        if label:
            return label
    return "none"


def _build_contract_protocol_module_line(
    *,
    title: str,
    families: set[str],
    function_family_priorities: list[str],
    risk_family_lane_summaries: list[str],
    review_lanes: list[str],
    risk_linked_files: list[str],
) -> str | None:
    matched_function_priorities = [
        summary
        for summary in function_family_priorities
        if _summary_matches_contract_repo_families(summary, families)
    ]
    matched_risk_lanes = [
        summary
        for summary in risk_family_lane_summaries
        if _summary_matches_contract_repo_families(summary, families)
    ]
    matched_review_lanes = [
        lane
        for lane in review_lanes
        if _summary_matches_contract_repo_families(lane, families)
    ]
    matched_risk_files = [
        item
        for item in risk_linked_files
        if _risk_linked_file_matches_contract_repo_families(item, families)
    ]

    fragments: list[str] = []
    if matched_function_priorities:
        fragments.append("function families: " + "; ".join(matched_function_priorities[:2]))
    if matched_risk_lanes:
        fragments.append("risk lanes: " + "; ".join(matched_risk_lanes[:2]))
    elif matched_review_lanes:
        fragments.append("review lanes: " + "; ".join(matched_review_lanes[:2]))
    if matched_risk_files:
        fragments.append("risk-linked files: " + ", ".join(matched_risk_files[:2]))

    if not fragments:
        return None
    return f"{title}: " + " | ".join(fragments) + "."


def _build_contract_protocol_casebook_line(session: ResearchSession) -> str | None:
    best_score = -1
    best_line: str | None = None
    for evidence in session.evidence:
        if evidence.tool_name != "contract_testbed_tool":
            continue
        _, result_data = _extract_result(evidence)
        repo_case_count = int(result_data.get("repo_case_count", 0) or 0)
        if repo_case_count <= 0:
            continue
        testbed_name = _as_optional_str(result_data.get("testbed_name")) or "repo_casebook"
        matched_case_count = int(result_data.get("matched_case_count", 0) or 0)
        matched_review_lane_count = int(result_data.get("matched_review_lane_count", 0) or 0)
        matched_function_priority_count = int(result_data.get("matched_function_priority_count", 0) or 0)
        focus = _contract_casebook_focus_label(testbed_name)
        score = matched_case_count + matched_review_lane_count + matched_function_priority_count
        line = (
            f"Casebook fit: {testbed_name} maps {focus}; matched cases={matched_case_count}/{repo_case_count}; "
            f"review lanes={matched_review_lane_count}; function-family priorities={matched_function_priority_count}."
        )
        if score > best_score:
            best_score = score
            best_line = line
    return best_line


def _collect_contract_family_hits(session: ResearchSession) -> Counter[str]:
    family_hits: Counter[str] = Counter()
    for evidence in session.evidence:
        _, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_inventory_tool":
            for summary in _as_str_list(result_data.get("entrypoint_function_family_priorities")):
                _, fragments = _parse_repo_priority_summary(summary)
                for fragment in fragments:
                    family_label, _ = _split_repo_priority_fragment(fragment)
                    family = _normalize_contract_repo_family(family_label)
                    if family is not None:
                        family_hits[family] += 2
        elif evidence.tool_name == "contract_surface_tool":
            for family in _surface_families(result_data):
                family_hits[family] += 3
        elif evidence.tool_name == "contract_pattern_check_tool":
            prioritized = result_data.get("prioritized_issues")
            if not isinstance(prioritized, list):
                prioritized = prioritize_contract_issues(_as_str_list(result_data.get("issues")))
            for item in prioritized:
                if not isinstance(item, dict):
                    continue
                family = _normalize_contract_repo_family(_as_optional_str(item.get("family")))
                if family is not None:
                    priority = (_as_optional_str(item.get("priority")) or "low").lower()
                    family_hits[family] += {"high": 4, "medium": 3, "low": 1}.get(priority, 1)
        elif evidence.tool_name == "contract_testbed_tool":
            families = _contract_testbed_families(_as_optional_str(result_data.get("testbed_name")))
            if families:
                weight = 4 if int(result_data.get("repo_case_count", 0) or 0) > 0 else 2
                for family in families:
                    family_hits[family] += weight
    return family_hits


def _ordered_contract_family_priority_list(
    lane_candidates: list[tuple[str, list[str]]],
    family_hits: Counter[str],
) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for _, families in lane_candidates:
        for family in families:
            if family not in seen:
                seen.add(family)
                ordered.append(family)
    for family, _ in family_hits.most_common():
        if family not in seen:
            seen.add(family)
            ordered.append(family)
    return ordered


def _contract_protocol_invariant_line(family: str) -> str:
    invariants = {
        "upgrade/control": "privileged state changes and upgrade paths should stay behind explicit authority boundaries, with initializer and pause controls remaining single-purpose and reviewable",
        "asset-flow": "asset exit, claim, rescue, and sweep flows should validate balances or claim state before value leaves the contract, and external calls should not silently outrun accounting updates",
        "reserve/fee/debt": "protocol fees, reserve buffers, debt accrual, and bad-debt handling should move coherently so reserve and debt state do not drift across helper modules",
        "proxy/storage": "delegatecall, implementation selection, and storage-slot writes should preserve storage-layout assumptions and explicit upgrade authorization",
        "token/allowance": "token transfer and approval paths should keep return-value checks, allowance semantics, and arbitrary-from handling aligned with the intended trust boundary",
        "vault/share": "share mint, redeem, and conversion paths should preserve asset backing and keep asset-share accounting internally consistent",
        "permit/signature": "signature and permit paths should bind nonce, signer, domain, and replay state consistently across all externally reachable entrypoints",
        "oracle/price": "price-dependent actions should rely on fresh oracle state or explicit fallback assumptions before affecting user balances or protocol state",
        "collateral/liquidation": "collateral ratios, liquidation eligibility, liquidation-fee allocation, and reserve-derived pricing should remain coherent under liquidation and debt-settlement flows",
        "entropy/time": "timestamp or entropy assumptions should not quietly become the deciding control for economically relevant state transitions",
        "assembly": "inline assembly should remain wrapped by surrounding validation so slot writes and raw memory/state transitions stay auditable",
        "lifecycle/destruction": "destructive lifecycle paths should stay explicitly gated and should not bypass the same authority model as the rest of the protocol",
    }
    return invariants.get(family, "critical protocol assumptions should remain locally reviewable and consistent across externally reachable paths")


def _summary_matches_contract_repo_families(summary: str, families: set[str]) -> bool:
    _, fragments = _parse_repo_priority_summary(summary)
    for fragment in fragments:
        family_label, _ = _split_repo_priority_fragment(fragment)
        if _normalize_contract_repo_family(family_label) in families:
            return True
    return False


def _risk_linked_file_matches_contract_repo_families(item: str, families: set[str]) -> bool:
    _, separator, tail = item.partition("[")
    if not separator:
        return False
    marker_blob = tail.rsplit("]", 1)[0]
    markers = [marker.strip() for marker in marker_blob.split(",") if marker.strip()]
    return any(_normalize_contract_repo_family(marker) in families for marker in markers)


def build_contract_manual_review_items(session: ResearchSession) -> list[str]:
    if not _is_smart_contract_session(session):
        return []
    items: list[str] = []
    for evidence in session.evidence:
        result, result_data = _extract_result(evidence)
        if evidence.tool_name == "contract_inventory_tool":
            candidate_files = _as_str_list(result_data.get("candidate_files"))
            entrypoint_candidates = _as_str_list(result_data.get("entrypoint_candidates"))
            shared_dependency_files = _as_str_list(result_data.get("shared_dependency_files"))
            entrypoint_flow_summaries = _as_str_list(result_data.get("entrypoint_flow_summaries"))
            entrypoint_review_lanes = _as_str_list(result_data.get("entrypoint_review_lanes"))
            risk_family_lane_summaries = _as_str_list(result_data.get("risk_family_lane_summaries"))
            entrypoint_function_family_priorities = _as_str_list(result_data.get("entrypoint_function_family_priorities"))
            risk_linked_files = _as_str_list(result_data.get("risk_linked_files"))
            dependency_dirs_present = _as_str_list(result_data.get("dependency_dirs_present"))
            unreadable_files = _as_str_list(result_data.get("unreadable_files"))
            issues = set(_as_str_list(result_data.get("issues")))
            if candidate_files:
                items.append(
                    "Manually confirm repository review priority for candidate files: "
                    + ", ".join(candidate_files[:5])
                    + "."
                )
            if entrypoint_candidates:
                items.append(
                    "Manually inspect top-level entrypoint files before following deeper shared dependencies: "
                    + ", ".join(entrypoint_candidates[:5])
                    + "."
                )
            if entrypoint_flow_summaries:
                items.append(
                    "Manually trace entrypoint-to-dependency chains such as: "
                    + ", ".join(entrypoint_flow_summaries[:3])
                    + "."
                )
            if entrypoint_review_lanes:
                items.append(
                    "Manually review prioritized repository lanes such as: "
                    + ", ".join(entrypoint_review_lanes[:3])
                    + "."
                )
            if risk_family_lane_summaries:
                items.append(
                    "Manually review entrypoint risk-family lanes such as: "
                    + ", ".join(risk_family_lane_summaries[:3])
                    + "."
                )
            if entrypoint_function_family_priorities:
                items.append(
                    "Manually review prioritized function families per entrypoint such as: "
                    + ", ".join(entrypoint_function_family_priorities[:3])
                    + "."
                )
            if shared_dependency_files:
                items.append(
                    "Manually inspect shared dependency hubs imported by multiple local files: "
                    + ", ".join(shared_dependency_files[:4])
                    + "."
                )
            if risk_linked_files:
                items.append(
                    "Manually inspect repo-linked risky files before narrowing to a single contract: "
                    + ", ".join(risk_linked_files[:4])
                    + "."
                )
            if dependency_dirs_present:
                items.append(
                    "Manually separate first-party audit scope from dependency directories: "
                    + ", ".join(dependency_dirs_present[:4])
                    + "."
                )
            if "inventory_scan_truncated" in issues:
                items.append("Manually confirm that the bounded repository inventory did not omit in-scope contract files.")
            if unreadable_files:
                items.append(
                    "Manually inspect unreadable contract files from the scoped repository inventory: "
                    + ", ".join(unreadable_files[:5])
                    + "."
                )
        elif evidence.tool_name == "contract_compile_tool":
            if result.get("status") == "observed_issue" or int(result_data.get("error_count", 0) or 0) > 0:
                items.append("Resolve compiler-facing issues before trusting downstream static analysis.")
        elif evidence.tool_name == "contract_surface_tool":
            if _as_str_list(result_data.get("unguarded_state_changing_functions")):
                items.append(
                    "Manually review access control for externally reachable state-changing functions: "
                    + ", ".join(_as_str_list(result_data.get("unguarded_state_changing_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("delegatecall_functions")):
                items.append(
                    "Manually review delegatecall usage in: "
                    + ", ".join(_as_str_list(result_data.get("delegatecall_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("role_management_functions")):
                items.append(
                    "Manually review role-management paths in: "
                    + ", ".join(_as_str_list(result_data.get("role_management_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("rescue_or_sweep_functions")):
                items.append(
                    "Manually review rescue or sweep paths in: "
                    + ", ".join(_as_str_list(result_data.get("rescue_or_sweep_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("share_accounting_functions")):
                items.append(
                    "Manually review vault share-accounting paths in: "
                    + ", ".join(_as_str_list(result_data.get("share_accounting_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("collateral_management_functions")):
                items.append(
                    "Manually review collateral-management or borrow paths in: "
                    + ", ".join(_as_str_list(result_data.get("collateral_management_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("liquidation_functions")):
                items.append(
                    "Manually review liquidation and seize paths in: "
                    + ", ".join(_as_str_list(result_data.get("liquidation_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("liquidation_fee_functions")):
                items.append(
                    "Manually review liquidation-fee, bonus, or penalty allocation paths in: "
                    + ", ".join(_as_str_list(result_data.get("liquidation_fee_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("reserve_dependency_functions")):
                items.append(
                    "Manually review reserve-derived pricing paths in: "
                    + ", ".join(_as_str_list(result_data.get("reserve_dependency_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("fee_collection_functions")):
                items.append(
                    "Manually review protocol-fee or skim paths in: "
                    + ", ".join(_as_str_list(result_data.get("fee_collection_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("reserve_buffer_functions")):
                items.append(
                    "Manually review reserve-buffer or insurance-fund coverage paths in: "
                    + ", ".join(_as_str_list(result_data.get("reserve_buffer_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("reserve_accounting_functions")):
                items.append(
                    "Manually review reserve-accounting and reserve-sync paths in: "
                    + ", ".join(_as_str_list(result_data.get("reserve_accounting_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("debt_accounting_functions")):
                items.append(
                    "Manually review debt-accounting and accrual paths in: "
                    + ", ".join(_as_str_list(result_data.get("debt_accounting_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("bad_debt_socialization_functions")):
                items.append(
                    "Manually review bad-debt writeoff or socialization paths in: "
                    + ", ".join(_as_str_list(result_data.get("bad_debt_socialization_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("pause_control_functions")):
                items.append(
                    "Manually review pause or unpause authority in: "
                    + ", ".join(_as_str_list(result_data.get("pause_control_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("selfdestruct_functions")):
                items.append(
                    "Manually review destructive lifecycle paths in: "
                    + ", ".join(_as_str_list(result_data.get("selfdestruct_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("proxy_delegatecall_functions")):
                items.append(
                    "Manually review proxy-like delegatecall paths in: "
                    + ", ".join(_as_str_list(result_data.get("proxy_delegatecall_functions"))[:5])
                    + "."
                )
            if _as_str_list(result_data.get("storage_slot_write_functions")):
                items.append(
                    "Manually review storage-slot writes in: "
                    + ", ".join(_as_str_list(result_data.get("storage_slot_write_functions"))[:5])
                    + "."
                )
        elif evidence.tool_name == "contract_pattern_check_tool":
            for issue in _as_str_list(result_data.get("issues")):
                item = _manual_review_item_for_contract_issue(issue)
                if item:
                    items.append(item)
        elif evidence.tool_name == "slither_audit_tool":
            detector_counts = _as_count_summary(result_data.get("detector_name_counts"))
            if detector_counts:
                items.append(f"Manually inspect Slither detector findings: {detector_counts}.")
        elif evidence.tool_name == "echidna_audit_tool":
            if bool(result_data.get("analysis_applicable")):
                failing_tests = _as_str_list(result_data.get("failing_tests"))
                if failing_tests:
                    items.append(
                        "Manually inspect Echidna failing checks: "
                        + ", ".join(failing_tests[:5])
                        + "."
                    )
                else:
                    items.append("Manually confirm that the bounded Echidna harness matches the intended contract invariants.")
        elif evidence.tool_name == "foundry_audit_tool":
            if int(result_data.get("inspect_contracts_succeeded", 0) or 0) > 0:
                contract_names = _as_str_list(result_data.get("contract_names"))
                if contract_names:
                    items.append(
                        "Manually review Foundry structural output for: "
                        + ", ".join(contract_names[:5])
                        + "."
                    )
        elif evidence.tool_name == "contract_testbed_tool":
            testbed_name = _as_optional_str(result_data.get("testbed_name")) or "contract_testbed"
            anomaly_count = int(result_data.get("anomaly_count", 0) or 0)
            if anomaly_count > 0:
                items.append(
                    f"Compare the live contract against bounded anomaly cases from {testbed_name} before stronger conclusions."
                )
            if int(result_data.get("repo_case_count", 0) or 0) > 0:
                items.append(
                    f"Manually compare repository entrypoint lanes and shared dependencies against the bounded repo casebook {testbed_name}."
                )
    return ordered_unique(items)[:12]


def build_exploratory_findings(session: ResearchSession) -> list[str]:
    if session.research_mode != ResearchMode.SANDBOXED_EXPLORATORY:
        return []

    findings: list[str] = []
    if session.selected_pack_name:
        findings.append(f"Experiment pack: {session.selected_pack_name}.")
    if session.sandbox_spec is not None:
        findings.append(
            f"Exploration profile: {session.sandbox_spec.exploration_profile.value}."
        )
    if session.executed_pack_steps:
        findings.append(
            f"Executed pack steps: {', '.join(session.executed_pack_steps)}."
        )
    if session.exploratory_rounds_executed:
        findings.append(
            f"Exploratory rounds executed: {session.exploratory_rounds_executed}."
        )
    findings.extend(session.exploratory_round_summaries)
    if session.research_target is not None:
        findings.append(
            f"Bounded research target: {session.research_target.target_kind} -> {session.research_target.target_reference}."
        )
    if session.explored_hypothesis_ids:
        findings.append(
            f"Explored branches: {', '.join(session.explored_hypothesis_ids)}."
        )
    findings.extend(
        f"{evidence.tool_name or evidence.source}: {evidence.conclusion or evidence.summary}"
        for evidence in session.evidence
    )
    return ordered_unique(findings)


def build_dead_end_summary(session: ResearchSession) -> list[str]:
    items: list[str] = []
    evidence_ids = {evidence.hypothesis_id for evidence in session.evidence}
    for hypothesis in session.hypotheses:
        if hypothesis.status == HypothesisStatus.REJECTED:
            items.append(f"Rejected branch: {hypothesis.summary}")
            continue
        if (
            hypothesis.hypothesis_id in session.explored_hypothesis_ids
            and hypothesis.status == HypothesisStatus.CLOSED
            and hypothesis.hypothesis_id not in evidence_ids
        ):
            items.append(f"Closed without useful local evidence: {hypothesis.summary}")
            continue
        if (
            hypothesis.branch_type == BranchType.NULL
            and hypothesis.status == HypothesisStatus.CLOSED
            and hypothesis.hypothesis_id in evidence_ids
        ):
            items.append(
                f"Null-style branch stayed conservative and did not justify escalation: {hypothesis.summary}"
            )

    if session.critic_result is not None:
        for reason in session.critic_result.rejection_reasons:
            stripped = reason.strip()
            if stripped:
                items.append(f"Critic rejection reason: {stripped}")

    return ordered_unique(items)


def build_next_defensive_leads(session: ResearchSession) -> list[str]:
    items: list[str] = []
    if session.cryptography_result is not None:
        for question in session.cryptography_result.defensive_questions[:2]:
            stripped = question.strip()
            if stripped:
                items.append(f"Tighten next check: {stripped}")
    if session.strategy_result is not None:
        for check in session.strategy_result.primary_checks[:2]:
            stripped = check.strip()
            if stripped:
                items.append(f"Next bounded check: {stripped}")
        if session.strategy_result.escalation_local_tools:
            items.append(
                "If manual review justifies a follow-up, escalate through: "
                + ", ".join(session.strategy_result.escalation_local_tools)
                + "."
            )
    signal_items = build_local_signal_summary(session)
    if signal_items and not signal_items[0].startswith("No anomaly-bearing local signal"):
        items.append(
            "Re-run the strongest bounded signal under a narrower null control before making stronger claims."
        )
    if session.selected_pack_name:
        items.append(
            f"Preserve pack provenance and continue with bounded follow-up under {session.selected_pack_name} only if the signal survives review."
        )

    return ordered_unique(items)


def build_evidence_summary(raw_result: dict[str, object]) -> str:
    tool_name = str(raw_result.get("tool_name", "unknown_tool"))
    result = raw_result.get("result", {})
    if not isinstance(result, dict):
        return f"{tool_name} returned an unexpected result structure."
    result_data = result.get("result_data", {})
    if not isinstance(result_data, dict):
        result_data = {}

    if tool_name == "curve_metadata_tool":
        curve_name = result_data.get("curve_name", "unknown")
        recognized = result_data.get("recognized", False)
        return (
            f"curve_metadata_tool inspected curve input and reported curve_name={curve_name}, "
            f"recognized={recognized}. This is local metadata evidence only."
        )

    if tool_name == "ecc_curve_parameter_tool":
        return (
            "ecc_curve_parameter_tool normalized ECC domain metadata and reported "
            f"curve_name={result_data.get('curve_name', 'unknown')} with "
            f"supports_on_curve_check={result_data.get('supports_on_curve_check', False)}."
        )

    if tool_name == "point_descriptor_tool":
        return (
            "point_descriptor_tool described point payload shape, including coordinate lengths "
            f"x={result_data.get('x_length', 0)} and y={result_data.get('y_length', 0)}."
        )

    if tool_name == "ecc_point_format_tool":
        return (
            "ecc_point_format_tool classified point/public-key input as "
            f"{result_data.get('input_kind', 'unknown')} with encoding "
            f"{result_data.get('encoding', 'unknown')}."
        )

    if tool_name == "ecc_consistency_check_tool":
        return (
            "ecc_consistency_check_tool performed bounded ECC format checks and returned "
            f"format_consistent={result_data.get('format_consistent', False)} with "
            f"on_curve={result_data.get('on_curve', 'not_checked')}."
        )

    if tool_name == "symbolic_check_tool":
        return (
            "symbolic_check_tool attempted local symbolic parsing and returned "
            f"parsed={result_data.get('parsed', False)} with normalized form "
            f"{result_data.get('normalized_form', 'unavailable')}."
        )

    if tool_name == "property_invariant_tool":
        return (
            "property_invariant_tool executed a bounded local property-based search and returned "
            f"property_holds={result_data.get('property_holds', 'unknown')} with "
            f"counterexample={result_data.get('counterexample', 'none')}."
        )

    if tool_name == "formal_constraint_tool":
        return (
            "formal_constraint_tool executed a bounded local formal equality check and returned "
            f"property_holds={result_data.get('property_holds', 'unknown')} with "
            f"counterexample={result_data.get('counterexample', 'none')}."
        )

    if tool_name == "sage_symbolic_tool":
        return (
            "sage_symbolic_tool attempted the bounded advanced symbolic path and returned "
            f"status={result.get('status', 'unknown')} with normalized form "
            f"{result_data.get('normalized_form', 'unavailable')}."
        )

    if tool_name == "finite_field_check_tool":
        return (
            "finite_field_check_tool executed a bounded modular consistency check and returned "
            f"consistent={result_data.get('consistent', False)} under modulus "
            f"{result_data.get('modulus', 'unknown')}."
        )

    if tool_name == "fuzz_mutation_tool":
        return (
            "fuzz_mutation_tool executed bounded deterministic local mutations and returned "
            f"anomaly_count={result_data.get('anomaly_count', 0)} over "
            f"{result_data.get('mutations_generated', 0)} mutations."
        )

    if tool_name == "ecc_testbed_tool":
        return (
            "ecc_testbed_tool executed a built-in bounded ECC testbed sweep and returned "
            f"anomaly_count={result_data.get('anomaly_count', 0)} over "
            f"{result_data.get('case_count', 0)} cases."
        )

    if tool_name == "deterministic_experiment_tool":
        return (
            "deterministic_experiment_tool executed a bounded repeatability check and returned "
            f"repeatability={result_data.get('repeatability', False)} for "
            f"{result_data.get('experiment_type', 'unknown_experiment')}."
        )

    matched_keywords = ", ".join(result_data.get("matched_keywords", [])) or "none"
    return (
        "placeholder_math_tool recorded preliminary text-level signals. "
        f"Matched keywords: {matched_keywords}. This remains bounded evidence only."
    )


def build_evidence_conclusion(raw_result: dict[str, object]) -> str:
    result = raw_result.get("result", {})
    if not isinstance(result, dict):
        return f"{raw_result.get('tool_name', 'unknown_tool')} did not return a structured result."
    conclusion = result.get("conclusion")
    if isinstance(conclusion, str) and conclusion.strip():
        return conclusion.strip()
    return "Local tool completed without a concise conclusion."


def extract_evidence_notes(raw_result: dict[str, object]) -> list[str]:
    notes: list[str] = []
    metadata = raw_result.get("tool_metadata")
    if isinstance(metadata, dict):
        notes.append(
            f"tool_category={metadata.get('category', 'unknown')}; deterministic={metadata.get('deterministic', True)}"
        )
    experiment_spec = raw_result.get("experiment_spec")
    if isinstance(experiment_spec, dict):
        notes.append(
            f"experiment_type={experiment_spec.get('experiment_type', 'unknown')}; target_kind={experiment_spec.get('target_kind', 'unknown')}"
        )
    if raw_result.get("validated_payload") is not None:
        notes.append("payload_validated=True")

    result = raw_result.get("result", {})
    if isinstance(result, dict):
        value = result.get("notes")
        if isinstance(value, list):
            notes.extend(str(item) for item in value if str(item).strip())
        elif isinstance(value, str) and value.strip():
            notes.append(value.strip())
        result_data = result.get("result_data", {})
        if isinstance(result_data, dict):
            for key in ("curve_name", "input_kind", "encoding"):
                field = result_data.get(key)
                if isinstance(field, str) and field.strip():
                    notes.append(f"{key}={field.strip()}")
            for key in ("issues", "errors"):
                field = result_data.get(key)
                if isinstance(field, list):
                    notes.extend(str(item) for item in field if str(item).strip())
                elif isinstance(field, str) and field.strip():
                    notes.append(field.strip())
    sandbox_payload = raw_result.get("sandbox")
    if isinstance(sandbox_payload, dict):
        target_profile = sandbox_payload.get("target_profile")
        if isinstance(target_profile, str) and target_profile.strip():
            notes.append(f"target_profile={target_profile.strip()}")
        sandbox_notes = sandbox_payload.get("notes")
        if isinstance(sandbox_notes, list):
            notes.extend(str(item) for item in sandbox_notes if str(item).strip())
    return notes


def collect_artifact_references(session: ResearchSession) -> list[RunArtifactReference]:
    references: list[RunArtifactReference] = []
    seen_paths: set[str] = set()
    for evidence in session.evidence:
        for artifact_path in evidence.artifact_paths:
            path = artifact_path.strip()
            if not path or path in seen_paths:
                continue
            seen_paths.add(path)
            artifact_file = Path(path)
            references.append(
                RunArtifactReference(
                    workspace_id=evidence.workspace_id,
                    artifact_path=path,
                    description=evidence.summary,
                    generating_tool=evidence.tool_name,
                    experiment_type=evidence.experiment_type,
                    file_hash=hash_file(artifact_file) if artifact_file.exists() else None,
                )
            )
    return references


def unique_metadata_snapshots(session: ResearchSession) -> list[dict[str, Any]]:
    snapshots: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for evidence in session.evidence:
        metadata = evidence.tool_metadata_snapshot
        if not isinstance(metadata, dict):
            continue
        key = repr(sorted(metadata.items()))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        snapshots.append(metadata)
    return snapshots


def should_fallback_from_sage(
    *,
    job: ComputeJob,
    raw_result: dict[str, object],
) -> bool:
    if job.tool_name != "sage_symbolic_tool":
        return False
    result = raw_result.get("result", {})
    if not isinstance(result, dict):
        return True
    return str(result.get("status", "")).lower() in {"unavailable", "error", "invalid_input"}


def append_result_note(raw_result: dict[str, object], note: str) -> None:
    result = raw_result.get("result")
    if not isinstance(result, dict):
        return
    notes = result.get("notes")
    if not isinstance(notes, list):
        notes = []
        result["notes"] = notes
    if note not in notes:
        notes.append(note)


def _manual_review_item_for_contract_issue(issue: str) -> str | None:
    family, _, detail = issue.partition(":")
    target = detail.strip()
    if family == "floating_pragma":
        return "Manually review floating pragma usage and confirm the intended compiler range."
    if family == "missing_pragma":
        return "Manually review compiler expectations because the contract source does not declare a pragma."
    if family == "selfdestruct_usage":
        return "Manually review destructive lifecycle behavior and decommission paths."
    if family == "tx_origin_usage":
        return "Manually review any tx.origin-dependent logic before trusting authorization assumptions."
    if family == "unguarded_admin_surface" and target:
        return f"Manually review access control on `{target}`."
    if family == "unguarded_role_management_surface" and target:
        return f"Manually review role-management authorization in `{target}`."
    if family == "unguarded_pause_control_surface" and target:
        return f"Manually review pause or unpause authorization in `{target}`."
    if family == "unguarded_privileged_state_change" and target:
        return f"Manually review privileged state-changing authority in `{target}`."
    if family == "asset_exit_without_balance_validation":
        return "Manually review asset-exit paths for missing balance or allowance validation."
    if family == "unguarded_rescue_or_sweep_flow":
        return "Manually review rescue or sweep flows for missing authorization boundaries."
    if family == "unguarded_rescue_or_sweep_surface" and target:
        return f"Manually review rescue or sweep authority in `{target}`."
    if family == "unguarded_upgrade_surface" and target:
        return f"Manually review upgrade authorization on `{target}`."
    if family == "proxy_fallback_delegatecall_review_required" and target:
        return f"Manually review proxy fallback delegatecall behavior in `{target}`."
    if family == "proxy_storage_collision_review_required" and target:
        return f"Manually review storage-slot isolation and collision assumptions in `{target}`."
    if family == "storage_slot_write_review_required" and target:
        return f"Manually review storage-slot writes in `{target}`."
    if family == "public_initializer_surface" and target:
        return f"Manually review public initializer exposure on `{target}`."
    if family == "unchecked_external_call_surface" and target:
        return f"Manually review unchecked low-level call handling in `{target}`."
    if family == "user_supplied_call_target" and target:
        return f"Manually review user-supplied external call targets in `{target}`."
    if family == "user_supplied_delegatecall_target" and target:
        return f"Manually review user-supplied delegatecall targets in `{target}`."
    if family == "unguarded_delegatecall_surface" and target:
        return f"Manually review unguarded delegatecall behavior in `{target}`."
    if family == "unguarded_selfdestruct_surface" and target:
        return f"Manually review unguarded selfdestruct behavior in `{target}`."
    if family == "tx_origin_auth_surface" and target:
        return f"Manually review tx.origin-based authorization in `{target}`."
    if family == "reentrancy_review_required" and target:
        return f"Manually review reentrancy-adjacent sequencing in `{target}`."
    if family == "external_call_in_loop" and target:
        return f"Manually review loop-driven external call behavior in `{target}`."
    if family == "state_transition_after_external_call" and target:
        return f"Manually review state transitions after external calls in `{target}`."
    if family == "accounting_update_after_external_call" and target:
        return f"Manually review balance, allowance, or claim-accounting updates after external calls in `{target}`."
    if family == "withdrawal_without_balance_validation" and target:
        return f"Manually review withdrawal or claim-like balance validation in `{target}`."
    if family == "share_mint_without_asset_backing_review" and target:
        return f"Manually review share minting and asset-backing assumptions in `{target}`."
    if family == "share_redeem_without_share_validation" and target:
        return f"Manually review share redemption validation in `{target}`."
    if family == "protocol_fee_without_reserve_sync_review" and target:
        return f"Manually review protocol-fee or skim behavior in `{target}` for missing reserve synchronization."
    if family == "reserve_accounting_drift_review_required" and target:
        return f"Manually review reserve-accounting drift assumptions in `{target}`."
    if family == "debt_state_transition_review_required" and target:
        return f"Manually review debt-state transitions and accrual assumptions in `{target}`."
    if family == "unchecked_token_transfer_surface" and target:
        return f"Manually review ERC20 transfer return handling in `{target}`."
    if family == "unchecked_token_transfer_from_surface" and target:
        return f"Manually review ERC20 transferFrom return handling in `{target}`."
    if family == "unchecked_approve_surface" and target:
        return f"Manually review ERC20 approve return handling in `{target}`."
    if family == "approve_race_review_required" and target:
        return f"Manually review allowance reset and approve race conditions in `{target}`."
    if family == "vault_conversion_review_required" and target:
        return f"Manually review asset-share conversion assumptions in `{target}`."
    if family == "signature_replay_review_required" and target:
        return f"Manually review replay protection, nonce use, and signature invalidation in `{target}`."
    if family == "collateral_ratio_review_required" and target:
        return f"Manually review collateral-ratio and health-factor validation in `{target}`."
    if family == "liquidation_without_fresh_price_review" and target:
        return f"Manually review liquidation pricing freshness in `{target}`."
    if family == "arbitrary_from_transfer_surface" and target:
        return f"Manually review arbitrary `from` transfer surfaces in `{target}`."
    if family == "assembly_review_required" and target:
        return f"Manually review inline assembly in `{target}`."
    if family == "entropy_source_review_required" and target:
        return f"Manually review randomness and entropy assumptions in `{target}`."
    if family == "oracle_staleness_review_required" and target:
        return f"Manually review oracle freshness and staleness handling in `{target}`."
    if family == "reserve_spot_dependency_review_required" and target:
        return f"Manually review reserve-derived spot pricing assumptions in `{target}`."
    if family == "missing_zero_address_validation" and target:
        return f"Manually review zero-address validation in `{target}`."
    if family == "unvalidated_implementation_target" and target:
        return f"Manually review implementation target validation in `{target}`."
    return None


def _contract_testbed_focus_line(testbed_name: str | None) -> str | None:
    mapping = {
        "repo_upgrade_casebook": "Compare the repository against bounded proxy, upgrade, and storage-layout casebook lanes.",
        "repo_asset_flow_casebook": "Compare the repository against bounded asset-flow, rescue, and vault-style casebook lanes.",
        "repo_oracle_casebook": "Compare the repository against bounded oracle, price, collateral, and liquidation casebook lanes.",
        "repo_protocol_accounting_casebook": "Compare the repository against bounded protocol-fee, reserve-sync, and debt-accounting casebook lanes.",
        "repo_governance_timelock_casebook": "Compare the repository against bounded governance, timelock, guardian, and queued-upgrade casebook lanes.",
        "repo_rewards_distribution_casebook": "Compare the repository against bounded reward-index, emission, claim, and reserve-backed distribution casebook lanes.",
        "repo_stablecoin_collateral_casebook": "Compare the repository against bounded stablecoin mint, redemption, collateral, reserve, and liquidation casebook lanes.",
        "repo_amm_liquidity_casebook": "Compare the repository against bounded AMM swap, liquidity, reserve, fee-growth, and oracle-sync casebook lanes.",
        "repo_bridge_custody_casebook": "Compare the repository against bounded bridge relay, custody, proof, withdrawal-finalization, and replay-protection casebook lanes.",
        "repo_staking_rebase_casebook": "Compare the repository against bounded staking, rebase, queued withdrawal, slash, and validator-reward casebook lanes.",
        "repo_keeper_auction_casebook": "Compare the repository against bounded keeper reward, auction settlement, liquidation, oracle, and reserve-buffer casebook lanes.",
        "repo_treasury_vesting_casebook": "Compare the repository against bounded treasury release, vesting schedule, beneficiary payout, sweep, and timelock casebook lanes.",
        "repo_insurance_recovery_casebook": "Compare the repository against bounded insurance-fund depletion, deficit absorption, reserve recovery, and emergency-settlement casebook lanes.",
        "reentrancy_review_corpus": "Compare the contract against bounded reentrancy-style corpus cases.",
        "access_control_corpus": "Compare the contract against bounded access-control corpus cases.",
        "asset_flow_corpus": "Compare the contract against bounded asset-flow and fund-movement corpus cases.",
        "authorization_flow_corpus": "Compare the contract against bounded authorization-flow and privileged-control corpus cases.",
        "dangerous_call_corpus": "Compare the contract against bounded dangerous-call corpus cases.",
        "upgrade_surface_corpus": "Compare the contract against bounded upgrade-surface corpus cases.",
        "proxy_storage_corpus": "Compare the contract against bounded proxy and storage-layout corpus cases.",
        "upgrade_validation_corpus": "Compare the contract against bounded implementation-validation corpus cases.",
        "time_entropy_corpus": "Compare the contract against bounded time-and-entropy corpus cases.",
        "token_interaction_corpus": "Compare the contract against bounded token interaction corpus cases.",
        "approval_review_corpus": "Compare the contract against bounded approval and allowance corpus cases.",
        "accounting_review_corpus": "Compare the contract against bounded accounting and withdrawal-order corpus cases.",
        "vault_share_corpus": "Compare the contract against bounded vault-share and asset-conversion corpus cases.",
        "signature_review_corpus": "Compare the contract against bounded signature-validation corpus cases.",
        "oracle_review_corpus": "Compare the contract against bounded oracle dependency corpus cases.",
        "collateral_liquidation_corpus": "Compare the contract against bounded collateral-ratio, liquidation, and reserve-pricing corpus cases.",
        "reserve_fee_accounting_corpus": "Compare the contract against bounded protocol-fee, reserve-sync, and debt-accounting corpus cases.",
        "loop_payout_corpus": "Compare the contract against bounded payout-loop and batch distribution corpus cases.",
        "assembly_review_corpus": "Compare the contract against bounded inline assembly corpus cases.",
        "state_machine_corpus": "Compare the contract against bounded state-machine corpus cases.",
    }
    if not testbed_name:
        return None
    return mapping.get(testbed_name)


def _record_repo_priority_summary(
    *,
    lane_candidates: dict[tuple[str, str], dict[str, Any]],
    summary: str,
    reason_prefix: str,
    weight: int,
    priority: str,
) -> None:
    entrypoint, fragments = _parse_repo_priority_summary(summary)
    if not entrypoint:
        return
    for fragment in fragments:
        family_label, via_source = _split_repo_priority_fragment(fragment)
        family = _normalize_contract_repo_family(family_label)
        if family is None:
            continue
        reason = reason_prefix + (f" via {via_source}" if via_source else "")
        lane_label = f"{entrypoint} => {fragment}"
        _record_repo_lane_candidate(
            lane_candidates=lane_candidates,
            entrypoint=entrypoint,
            family=family,
            lane_label=lane_label,
            reason=reason,
            weight=weight,
            priority=priority,
        )


def _record_repo_review_lane(
    *,
    lane_candidates: dict[tuple[str, str], dict[str, Any]],
    lane: str,
    weight: int,
    priority: str,
) -> None:
    path_part, separator, marker_part = lane.partition(" => ")
    if not separator:
        return
    entrypoint = path_part.split(" -> ", 1)[0].strip()
    if not entrypoint:
        return
    for raw_marker in [item.strip() for item in marker_part.split(",") if item.strip()]:
        family = _normalize_contract_repo_family(raw_marker)
        if family is None:
            continue
        _record_repo_lane_candidate(
            lane_candidates=lane_candidates,
            entrypoint=entrypoint,
            family=family,
            lane_label=lane.strip(),
            reason=f"review lane converges on {raw_marker}",
            weight=weight,
            priority=priority,
        )


def _record_repo_lane_candidate(
    *,
    lane_candidates: dict[tuple[str, str], dict[str, Any]],
    entrypoint: str,
    family: str,
    lane_label: str,
    reason: str,
    weight: int,
    priority: str,
) -> None:
    key = (entrypoint.strip(), family)
    candidate = lane_candidates.get(key)
    if candidate is None:
        candidate = {
            "entrypoint": entrypoint.strip(),
            "family": family,
            "lane_label": lane_label.strip(),
            "score": 0,
            "priority_rank": _contract_repo_priority_rank(priority),
            "supporting_signals": [],
        }
        lane_candidates[key] = candidate
    if len(lane_label.strip()) > len(candidate["lane_label"]):
        candidate["lane_label"] = lane_label.strip()
    candidate["score"] += weight
    candidate["priority_rank"] = min(candidate["priority_rank"], _contract_repo_priority_rank(priority))
    if reason not in candidate["supporting_signals"]:
        candidate["supporting_signals"].append(reason)


def _add_repo_family_support(
    family_supports: dict[str, list[dict[str, Any]]],
    *,
    family: str | None,
    text: str,
    weight: int,
    priority: str,
) -> None:
    normalized_family = _normalize_contract_repo_family(family)
    normalized_text = text.strip()
    if normalized_family is None or not normalized_text:
        return
    existing = family_supports[normalized_family]
    if any(item["text"] == normalized_text for item in existing):
        return
    existing.append({"text": normalized_text, "weight": weight, "priority": priority})


def _add_surface_family_supports(
    family_supports: dict[str, list[dict[str, Any]]],
    result_data: dict[str, Any],
) -> None:
    if "upgrade/control" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="upgrade/control",
            text="privileged or externally reachable state-changing functions were found",
            weight=2,
            priority="medium",
        )
    if "asset-flow" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="asset-flow",
            text="externally reachable asset-flow, state-transition, or accounting surfaces were found",
            weight=2,
            priority="medium",
        )
    if "reserve/fee/debt" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="reserve/fee/debt",
            text="protocol-fee, reserve-accounting, or debt-state surfaces were found",
            weight=2,
            priority="medium",
        )
    if "proxy/storage" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="proxy/storage",
            text="proxy, delegatecall, or storage-layout surfaces were found",
            weight=2,
            priority="medium",
        )
    if "token/allowance" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="token/allowance",
            text="token transfer or allowance surfaces were found",
            weight=2,
            priority="medium",
        )
    if "vault/share" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="vault/share",
            text="vault share-accounting or asset-conversion surfaces were found",
            weight=2,
            priority="medium",
        )
    if "permit/signature" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="permit/signature",
            text="signature-validation or permit-style surfaces were found",
            weight=2,
            priority="medium",
        )
    if "oracle/price" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="oracle/price",
            text="oracle or price-dependent surfaces were found",
            weight=2,
            priority="medium",
        )
    if "collateral/liquidation" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="collateral/liquidation",
            text="collateral, liquidation, or reserve-dependent protocol surfaces were found",
            weight=2,
            priority="medium",
        )
    if "entropy/time" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="entropy/time",
            text="timestamp or entropy-dependent paths were found",
            weight=2,
            priority="medium",
        )
    if "assembly" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="assembly",
            text="inline assembly paths were found",
            weight=2,
            priority="medium",
        )
    if "lifecycle/destruction" in _surface_families(result_data):
        _add_repo_family_support(
            family_supports,
            family="lifecycle/destruction",
            text="destructive lifecycle paths were found",
            weight=2,
            priority="high",
        )


def _surface_families(result_data: dict[str, Any]) -> set[str]:
    families: set[str] = set()
    if _as_str_list(result_data.get("privileged_functions")) or _as_str_list(result_data.get("unguarded_state_changing_functions")):
        families.add("upgrade/control")
    if any(_as_str_list(result_data.get(key)) for key in ("role_management_functions", "pause_control_functions", "role_guarded_functions")):
        families.add("upgrade/control")
    if any(
        _as_str_list(result_data.get(key))
        for key in (
            "low_level_call_functions",
            "call_with_value_functions",
            "state_transition_functions",
            "loop_functions",
            "deposit_like_functions",
            "asset_exit_functions",
            "rescue_or_sweep_functions",
            "accounting_mutation_functions",
        )
    ):
        families.add("asset-flow")
    if any(
        _as_str_list(result_data.get(key))
        for key in (
            "fee_collection_functions",
            "reserve_buffer_functions",
            "reserve_accounting_functions",
            "debt_accounting_functions",
            "bad_debt_socialization_functions",
        )
    ):
        families.add("reserve/fee/debt")
    if any(
        _as_str_list(result_data.get(key))
        for key in (
            "delegatecall_functions",
            "proxy_delegatecall_functions",
            "storage_slot_write_functions",
            "implementation_reference_functions",
        )
    ) or any(result_data.get(key) for key in ("implementation_slot_constant_present", "storage_gap_present")):
        families.add("proxy/storage")
    if any(_as_str_list(result_data.get(key)) for key in ("token_transfer_functions", "token_transfer_from_functions", "approve_functions")):
        families.add("token/allowance")
    if any(_as_str_list(result_data.get(key)) for key in ("share_accounting_functions", "vault_conversion_functions")):
        families.add("vault/share")
    if _as_str_list(result_data.get("signature_validation_functions")):
        families.add("permit/signature")
    if _as_str_list(result_data.get("oracle_dependency_functions")):
        families.add("oracle/price")
    if any(
        _as_str_list(result_data.get(key))
        for key in (
            "collateral_management_functions",
            "liquidation_functions",
            "liquidation_fee_functions",
            "reserve_dependency_functions",
        )
    ):
        families.add("collateral/liquidation")
    if any(_as_str_list(result_data.get(key)) for key in ("timestamp_functions", "entropy_source_functions")):
        families.add("entropy/time")
    if _as_str_list(result_data.get("assembly_functions")):
        families.add("assembly")
    if _as_str_list(result_data.get("selfdestruct_functions")):
        families.add("lifecycle/destruction")
    return families


def _add_pattern_family_supports(
    family_supports: dict[str, list[dict[str, Any]]],
    prioritized: list[Any],
) -> None:
    for item in prioritized:
        if not isinstance(item, dict):
            continue
        family = _normalize_contract_repo_family(_as_optional_str(item.get("family")))
        summary = _as_optional_str(item.get("summary"))
        priority = _as_optional_str(item.get("priority")) or "medium"
        if family is None or summary is None:
            continue
        weight = {"high": 5, "medium": 3, "low": 1}.get(priority, 1)
        _add_repo_family_support(
            family_supports,
            family=family,
            text=f"{priority} bounded pattern signal: {summary}",
            weight=weight,
            priority=priority,
        )


def _add_testbed_family_supports(
    family_supports: dict[str, list[dict[str, Any]]],
    result_data: dict[str, Any],
) -> None:
    anomaly_count = int(result_data.get("anomaly_count", 0) or 0)
    if anomaly_count <= 0:
        return
    testbed_name = _as_optional_str(result_data.get("testbed_name"))
    families = _contract_testbed_families(testbed_name)
    if not families:
        return
    for family in families:
        _add_repo_family_support(
            family_supports,
            family=family,
            text=f"bounded {testbed_name} cases surfaced anomaly-bearing signals",
            weight=3,
            priority="medium",
        )


def _parse_repo_priority_summary(summary: str) -> tuple[str, list[str]]:
    entrypoint, separator, rest = summary.partition(" => ")
    if not separator:
        return "", []
    fragments = [fragment.strip() for fragment in rest.split(",") if fragment.strip()]
    return entrypoint.strip(), fragments


def _split_repo_priority_fragment(fragment: str) -> tuple[str, str | None]:
    if " via " not in fragment:
        return fragment.strip(), None
    family_label, via_source = fragment.split(" via ", 1)
    return family_label.strip(), via_source.strip() or None


def _normalize_contract_repo_family(label: str | None) -> str | None:
    normalized = (label or "").strip().lower()
    if not normalized:
        return None
    family_map = {
        "upgrade/admin": "upgrade/control",
        "upgrade": "upgrade/control",
        "initialize": "upgrade/control",
        "tx.origin": "upgrade/control",
        "withdraw/claim": "asset-flow",
        "rescue/sweep": "asset-flow",
        "accounting": "asset-flow",
        "accounting/state": "asset-flow",
        "low-level": "asset-flow",
        "value-transfer": "asset-flow",
        "state-transition": "asset-flow",
        "reentrancy": "asset-flow",
        "fee/reserve/debt": "reserve/fee/debt",
        "protocol-fee": "reserve/fee/debt",
        "reserve-sync": "reserve/fee/debt",
        "debt": "reserve/fee/debt",
        "accrual": "reserve/fee/debt",
        "token/allowance": "token/allowance",
        "token-transfer": "token/allowance",
        "token-transferfrom": "token/allowance",
        "approve": "token/allowance",
        "permit/signature": "permit/signature",
        "permit": "permit/signature",
        "signature": "permit/signature",
        "oracle/price": "oracle/price",
        "oracle": "oracle/price",
        "collateral/liquidation": "collateral/liquidation",
        "collateral": "collateral/liquidation",
        "liquidation": "collateral/liquidation",
        "reserve": "collateral/liquidation",
        "vault/share": "vault/share",
        "vault-share": "vault/share",
        "vault-assets": "vault/share",
        "delegatecall": "proxy/storage",
        "proxy-delegate": "proxy/storage",
        "proxy/storage": "proxy/storage",
        "storage-slot-write": "proxy/storage",
        "implementation-ref": "proxy/storage",
        "entropy": "entropy/time",
        "timestamp": "entropy/time",
        "assembly": "assembly",
        "selfdestruct": "lifecycle/destruction",
        "lifecycle/destruction": "lifecycle/destruction",
        "upgrade/control": "upgrade/control",
        "asset-flow": "asset-flow",
        "entropy/time": "entropy/time",
    }
    if normalized in family_map:
        return family_map[normalized]
    issue_family_map = {
        "floating_pragma": "upgrade/control",
        "missing_pragma": "upgrade/control",
        "tx_origin_usage": "upgrade/control",
        "unguarded_admin_surface": "upgrade/control",
        "unguarded_role_management_surface": "upgrade/control",
        "unguarded_pause_control_surface": "upgrade/control",
        "unguarded_privileged_state_change": "upgrade/control",
        "unguarded_upgrade_surface": "upgrade/control",
        "public_initializer_surface": "upgrade/control",
        "missing_zero_address_validation": "upgrade/control",
        "unchecked_external_call_surface": "asset-flow",
        "user_supplied_call_target": "asset-flow",
        "reentrancy_review_required": "asset-flow",
        "external_call_in_loop": "asset-flow",
        "state_transition_after_external_call": "asset-flow",
        "asset_exit_without_balance_validation": "asset-flow",
        "unguarded_rescue_or_sweep_flow": "asset-flow",
        "unguarded_rescue_or_sweep_surface": "asset-flow",
        "accounting_update_after_external_call": "asset-flow",
        "withdrawal_without_balance_validation": "asset-flow",
        "protocol_fee_without_reserve_sync_review": "reserve/fee/debt",
        "reserve_accounting_drift_review_required": "reserve/fee/debt",
        "debt_state_transition_review_required": "reserve/fee/debt",
        "bad_debt_socialization_review_required": "reserve/fee/debt",
        "unchecked_token_transfer_surface": "token/allowance",
        "unchecked_token_transfer_from_surface": "token/allowance",
        "unchecked_approve_surface": "token/allowance",
        "approve_race_review_required": "token/allowance",
        "arbitrary_from_transfer_surface": "token/allowance",
        "share_mint_without_asset_backing_review": "vault/share",
        "share_redeem_without_share_validation": "vault/share",
        "vault_conversion_review_required": "vault/share",
        "signature_replay_review_required": "permit/signature",
        "oracle_staleness_review_required": "oracle/price",
        "collateral_ratio_review_required": "collateral/liquidation",
        "liquidation_without_fresh_price_review": "collateral/liquidation",
        "liquidation_fee_allocation_review_required": "collateral/liquidation",
        "reserve_spot_dependency_review_required": "collateral/liquidation",
        "entropy_source_review_required": "entropy/time",
        "assembly_review_required": "assembly",
        "delegatecall_usage": "proxy/storage",
        "user_supplied_delegatecall_target": "proxy/storage",
        "unguarded_delegatecall_surface": "proxy/storage",
        "proxy_fallback_delegatecall_review_required": "proxy/storage",
        "proxy_storage_collision_review_required": "proxy/storage",
        "storage_slot_write_review_required": "proxy/storage",
        "unvalidated_implementation_target": "proxy/storage",
        "selfdestruct_usage": "lifecycle/destruction",
        "unguarded_selfdestruct_surface": "lifecycle/destruction",
        "tx_origin_auth_surface": "upgrade/control",
    }
    return issue_family_map.get(normalized)


def _contract_testbed_families(testbed_name: str | None) -> list[str]:
    mapping = {
        "repo_upgrade_casebook": ["proxy/storage", "upgrade/control"],
        "repo_asset_flow_casebook": ["asset-flow", "vault/share"],
        "repo_oracle_casebook": ["oracle/price", "collateral/liquidation"],
        "repo_protocol_accounting_casebook": ["reserve/fee/debt", "collateral/liquidation"],
        "repo_vault_permission_casebook": ["vault/share", "permit/signature", "token/allowance"],
        "repo_governance_timelock_casebook": ["upgrade/control", "proxy/storage"],
        "repo_rewards_distribution_casebook": ["asset-flow", "reserve/fee/debt", "vault/share"],
        "repo_stablecoin_collateral_casebook": ["oracle/price", "collateral/liquidation", "reserve/fee/debt"],
        "repo_amm_liquidity_casebook": ["asset-flow", "reserve/fee/debt", "oracle/price"],
        "repo_bridge_custody_casebook": ["asset-flow", "permit/signature", "upgrade/control"],
        "repo_staking_rebase_casebook": ["vault/share", "reserve/fee/debt", "asset-flow"],
        "repo_keeper_auction_casebook": ["collateral/liquidation", "oracle/price", "asset-flow"],
        "repo_treasury_vesting_casebook": ["asset-flow", "upgrade/control", "vault/share"],
        "repo_insurance_recovery_casebook": ["reserve/fee/debt", "asset-flow", "upgrade/control"],
        "access_control_corpus": ["upgrade/control"],
        "authorization_flow_corpus": ["upgrade/control"],
        "dangerous_call_corpus": ["asset-flow"],
        "reentrancy_review_corpus": ["asset-flow"],
        "asset_flow_corpus": ["asset-flow"],
        "accounting_review_corpus": ["asset-flow"],
        "reserve_fee_accounting_corpus": ["reserve/fee/debt"],
        "state_machine_corpus": ["asset-flow"],
        "loop_payout_corpus": ["asset-flow"],
        "upgrade_surface_corpus": ["proxy/storage"],
        "proxy_storage_corpus": ["proxy/storage"],
        "upgrade_validation_corpus": ["proxy/storage"],
        "token_interaction_corpus": ["token/allowance"],
        "approval_review_corpus": ["token/allowance"],
        "vault_share_corpus": ["vault/share"],
        "signature_review_corpus": ["permit/signature"],
        "oracle_review_corpus": ["oracle/price"],
        "collateral_liquidation_corpus": ["collateral/liquidation"],
        "time_entropy_corpus": ["entropy/time"],
        "assembly_review_corpus": ["assembly"],
    }
    return ordered_unique(mapping.get((testbed_name or "").strip(), []))


def _is_contract_benchmark_pack(pack_name: str | None) -> bool:
    return (pack_name or "").strip() in {
        "contract_static_benchmark_pack",
        "repo_casebook_benchmark_pack",
        "protocol_casebook_benchmark_pack",
        "upgrade_control_benchmark_pack",
        "vault_permission_benchmark_pack",
        "lending_protocol_benchmark_pack",
        "governance_timelock_benchmark_pack",
        "reward_distribution_benchmark_pack",
        "stablecoin_collateral_benchmark_pack",
        "amm_liquidity_benchmark_pack",
        "bridge_custody_benchmark_pack",
        "staking_rebase_benchmark_pack",
        "keeper_auction_benchmark_pack",
        "treasury_vesting_benchmark_pack",
        "insurance_recovery_benchmark_pack",
    }


def _contract_testbed_family(testbed_name: str | None) -> str | None:
    families = _contract_testbed_families(testbed_name)
    return families[0] if families else None


def build_before_after_comparison(session: ResearchSession) -> list[str]:
    if session.comparative_report is None or session.comparative_report.cross_session_comparison is None:
        return []
    comparison = session.comparative_report.cross_session_comparison
    items = [
        "Baseline session: "
        + comparison.baseline_session_id
        + (
            f" ({comparison.baseline_source_path})"
            if comparison.baseline_source_path
            else ""
        ),
        comparison.summary,
    ]
    items.extend(f"Improved: {item}" for item in comparison.improvements)
    items.extend(f"Regression risk: {item}" for item in comparison.regressions)
    items.extend(f"Stable: {item}" for item in comparison.stable_findings)
    return ordered_unique(items)


def build_remediation_delta_summary(session: ResearchSession) -> list[str]:
    comparison = (
        session.comparative_report.cross_session_comparison
        if session.comparative_report is not None
        else None
    )
    validation_lines = build_contract_remediation_validation(session)
    follow_up_lines = build_contract_remediation_follow_up(session)

    items: list[str] = []
    if comparison is not None:
        improved_count = len(comparison.improvements)
        regression_count = len(comparison.regressions)
        stable_count = len(comparison.stable_findings)
        if regression_count:
            state = "regression-risk"
        elif improved_count:
            state = "narrowed"
        elif stable_count:
            state = "stable"
        else:
            state = "inconclusive"
        items.append(
            "Remediation delta - before/after posture: "
            f"baseline={comparison.baseline_session_id}; state={state}; "
            f"improved={improved_count}; regressions={regression_count}; stable={stable_count}."
        )
        if comparison.improvements:
            items.append(
                "Remediation delta - strongest improvement: "
                + _trim_sentence(comparison.improvements[0], 240)
            )
        if comparison.regressions:
            items.append(
                "Remediation delta - recheck first: "
                + _trim_sentence(comparison.regressions[0], 240)
            )
        elif comparison.stable_findings:
            items.append(
                "Remediation delta - stable carry-over: "
                + _trim_sentence(comparison.stable_findings[0], 240)
            )

    if validation_lines:
        items.append(
            "Remediation delta - local safer-control signal: "
            + _trim_sentence(validation_lines[0], 240)
        )
    if follow_up_lines:
        items.append(
            "Remediation delta - next replay: "
            + _trim_sentence(follow_up_lines[0], 240)
        )

    return ordered_unique(items)[:5]


def build_regression_flags(session: ResearchSession) -> list[str]:
    if session.comparative_report is None or session.comparative_report.cross_session_comparison is None:
        return []
    comparison = session.comparative_report.cross_session_comparison
    items = [f"Baseline session: {comparison.baseline_session_id}"]
    items.extend(comparison.regressions)
    if not comparison.regressions:
        items.append("No explicit regression-like deltas were recorded against the baseline session.")
    return ordered_unique(items)


def _contract_repo_priority_rank(priority: str) -> int:
    return {"high": 0, "medium": 1, "low": 2}.get(priority, 3)


def _contract_repo_priority_label(priority_rank: int, score: int) -> str:
    if priority_rank <= 0 or score >= 11:
        return "High"
    if priority_rank <= 1 or score >= 6:
        return "Medium"
    return "Low"


def _is_ecc_session(session: ResearchSession) -> bool:
    if session.research_target is not None and session.research_target.target_kind in {
        "curve",
        "point",
        "ecc_consistency",
        "testbed",
        "finite_field",
    }:
        return True
    ecc_tools = {
        "curve_metadata_tool",
        "ecc_curve_parameter_tool",
        "ecc_point_format_tool",
        "ecc_consistency_check_tool",
        "point_descriptor_tool",
        "ecc_testbed_tool",
        "fuzz_mutation_tool",
        "finite_field_check_tool",
    }
    return any((evidence.tool_name or "") in ecc_tools for evidence in session.evidence)


def _ordered_ecc_family_keys(support_map: dict[str, set[str]]) -> list[str]:
    priority = {
        "encoding": 0,
        "subgroup/cofactor/twist": 1,
        "family transitions": 2,
        "domain completeness": 3,
    }
    return sorted(support_map, key=lambda item: (priority.get(item, 99), item))


def _ecc_support_coverage_label(labels: list[str], has_residual_risk: bool) -> str:
    if len(labels) >= 3 and not has_residual_risk:
        return "broad"
    if len(labels) >= 2:
        return "partial"
    return "narrow"


def _ecc_families_for_testbed(testbed_name: str | None) -> list[str]:
    normalized = (testbed_name or "").strip().lower()
    mapping = {
        "encoding_edge_corpus": ["encoding"],
        "subgroup_cofactor_corpus": ["subgroup/cofactor/twist"],
        "curve_family_corpus": ["family transitions"],
        "curve_domain_corpus": ["domain completeness"],
        "twist_hygiene_corpus": ["subgroup/cofactor/twist", "family transitions"],
        "domain_completeness_corpus": ["domain completeness"],
        "family_transition_corpus": ["family transitions", "encoding"],
    }
    if normalized in mapping:
        return mapping[normalized]
    if normalized in {"x25519", "curve25519", "ed25519"}:
        return ["subgroup/cofactor/twist", "family transitions"]
    if normalized in {"secp256k1", "secp256r1", "prime256v1", "p-256", "p256", "secp384r1", "p-384", "p384", "secp521r1", "p-521", "p521"}:
        return ["domain completeness"]
    return []


def _ecc_families_from_text(text: str) -> set[str]:
    lowered = text.lower()
    families: set[str] = set()
    if any(token in lowered for token in ("encoding", "compressed", "uncompressed", "public-key", "point format")):
        families.add("encoding")
    if any(token in lowered for token in ("subgroup", "cofactor", "torsion", "twist", "x25519", "ed25519", "curve25519", "25519-family")):
        families.add("subgroup/cofactor/twist")
    if any(token in lowered for token in ("family", "montgomery", "edwards", "weierstrass", "25519")):
        families.add("family transitions")
    if any(token in lowered for token in ("domain", "registry", "generator", "order", "metadata completeness")):
        families.add("domain completeness")
    return families


def _collect_ecc_family_support(session: ResearchSession) -> dict[str, set[str]]:
    support_map: dict[str, set[str]] = defaultdict(set)

    for evidence in session.evidence:
        tool_name = evidence.tool_name or evidence.source
        _, result_data = _extract_result(evidence)
        issues = result_data.get("issues", [])
        issue_text = " ".join(str(item) for item in issues) if isinstance(issues, list) else ""

        if tool_name == "ecc_curve_parameter_tool":
            support_map["domain completeness"].add("curve-metadata")
            support_map["family transitions"].add("curve-metadata")
        elif tool_name == "ecc_point_format_tool":
            support_map["encoding"].add("point-format")
            likely_family = _as_optional_str(result_data.get("likely_curve_family")) or ""
            if likely_family in {"montgomery", "edwards", "curve25519", "25519", "secp"}:
                support_map["family transitions"].add("point-format")
        elif tool_name == "ecc_consistency_check_tool":
            support_map["encoding"].add("consistency")
            if result_data.get("on_curve_checked") is not None:
                support_map["family transitions"].add("consistency")
            if result_data.get("x_in_field_range") is not None or result_data.get("y_in_field_range") is not None:
                support_map["domain completeness"].add("consistency")
        elif tool_name == "ecc_testbed_tool":
            testbed_name = _as_optional_str(result_data.get("testbed_name"))
            for family in _ecc_families_for_testbed(testbed_name):
                support_map[family].add("testbed")

        for family in _ecc_families_from_text(issue_text):
            if tool_name == "ecc_testbed_tool":
                support_map[family].add("testbed")
            elif tool_name == "ecc_consistency_check_tool":
                support_map[family].add("consistency")
            elif tool_name == "ecc_point_format_tool":
                support_map[family].add("point-format")
            elif tool_name == "ecc_curve_parameter_tool":
                support_map[family].add("curve-metadata")

    return {family: labels for family, labels in support_map.items() if labels}


def _collect_ecc_residual_labels(session: ResearchSession) -> set[str]:
    residual_labels: set[str] = set()
    for line in build_ecc_residual_risk(session):
        residual_labels.update(_ecc_families_from_text(line))
    return residual_labels


def _collect_ecc_comparison_state(session: ResearchSession) -> dict[str, str]:
    state: dict[str, str] = {}
    if session.comparative_report is None or session.comparative_report.cross_session_comparison is None:
        return state

    comparison = session.comparative_report.cross_session_comparison
    buckets = [
        ("narrowed", comparison.improvements),
        ("regression risk", comparison.regressions),
        ("stable", comparison.stable_findings),
    ]
    for label, lines in buckets:
        for line in lines:
            for family in _ecc_families_from_text(line):
                state[family] = label
    return state


def _is_smart_contract_session(session: ResearchSession) -> bool:
    if session.research_target is not None and session.research_target.target_kind in {
        "smart_contract",
        "smart_contract_testbed",
    }:
        return True
    return any(
        (evidence.target_kind or "").startswith("smart_contract")
        or (evidence.tool_name or "").startswith("contract_")
        or evidence.tool_name == "slither_audit_tool"
        for evidence in session.evidence
    )


def _first_contract_result(session: ResearchSession, tool_name: str) -> dict[str, Any] | None:
    for evidence in session.evidence:
        if evidence.tool_name != tool_name:
            continue
        _, result_data = _extract_result(evidence)
        return result_data
    return None


def _ecc_testbed_focus_label(testbed_name: str | None) -> str:
    normalized = (testbed_name or "").strip().lower()
    mapping = {
        "point_anomaly_corpus": "point parsing and anomaly review",
        "coordinate_shape_corpus": "coordinate-shape review",
        "curve_alias_corpus": "curve-alias normalization",
        "curve_domain_corpus": "curve-domain completeness",
        "encoding_edge_corpus": "encoding-edge review",
        "subgroup_cofactor_corpus": "subgroup and cofactor hygiene",
        "curve_family_corpus": "curve-family handling",
        "twist_hygiene_corpus": "twist-hygiene review",
        "domain_completeness_corpus": "domain-metadata completeness",
        "family_transition_corpus": "family-transition handling",
    }
    if normalized in mapping:
        return mapping[normalized]
    if normalized in {"x25519", "curve25519", "ed25519"}:
        return "25519-family subgroup and family hygiene"
    if normalized in {"secp256k1", "secp256r1", "prime256v1", "p-256", "p256", "secp384r1", "p-384", "p384", "secp521r1", "p-521", "p521"}:
        return "curve-domain completeness"
    return "bounded ECC review"


def _ecc_benchmark_pack_label(pack_name: str | None) -> str | None:
    mapping = {
        "ecc_family_depth_benchmark_pack": "ECC family-depth benchmark",
        "ecc_subgroup_hygiene_benchmark_pack": "ECC subgroup-hygiene benchmark",
        "ecc_domain_completeness_benchmark_pack": "ECC domain-completeness benchmark",
    }
    return mapping.get((pack_name or "").strip())


def _extract_result(evidence: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    result = evidence.raw_result.get("result", {})
    if not isinstance(result, dict):
        result = {}
    result_data = result.get("result_data", {})
    if not isinstance(result_data, dict):
        result_data = {}
    return result, result_data


def _as_optional_str(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _as_count_summary(value: Any) -> str:
    if not isinstance(value, dict):
        return ""
    pairs = [
        (str(key).strip(), int(count))
        for key, count in value.items()
        if str(key).strip()
    ]
    pairs = [(key, count) for key, count in pairs if count > 0]
    if not pairs:
        return ""
    ordered_pairs = sorted(pairs, key=lambda item: (-item[1], item[0]))
    return ", ".join(f"{key}={count}" for key, count in ordered_pairs[:5])


def _first_matching_line(lines: Iterable[str], needles: tuple[str, ...]) -> str | None:
    normalized_needles = tuple(needle.lower() for needle in needles)
    for line in lines:
        lowered = line.lower()
        if any(needle in lowered for needle in normalized_needles):
            return line
    return None


def _trim_sentence(text: str, max_length: int) -> str:
    stripped = " ".join(str(text).strip().split())
    if len(stripped) <= max_length:
        return stripped
    return stripped[: max_length - 3].rstrip(" ,;:.") + "..."
