from __future__ import annotations

from app.models.session import ResearchSession
from app.types import ConfidenceLevel, HypothesisStatus


def infer_confidence(session: ResearchSession) -> ConfidenceLevel:
    """
    Assign bounded confidence from the currently recorded evidence.

    V1 remains intentionally conservative. A single placeholder local run cannot
    justify a strong research claim.
    """

    if not session.evidence:
        return ConfidenceLevel.MANUAL_REVIEW_REQUIRED

    evidence_count = len(session.evidence)
    tool_count = len({(evidence.tool_name or evidence.source).strip() for evidence in session.evidence})
    repo_casebook_support = any(
        evidence.raw_result.get("result", {}).get("result_data", {}).get("repo_case_count", 0)
        for evidence in session.evidence
        if (evidence.tool_name or "") == "contract_testbed_tool"
    )
    external_static_support = any(
        (evidence.tool_name or "") in {"slither_audit_tool", "echidna_audit_tool", "foundry_audit_tool"}
        for evidence in session.evidence
    )

    if any(
        hypothesis.status == HypothesisStatus.NEEDS_MANUAL_REVIEW
        for hypothesis in session.hypotheses
    ):
        return ConfidenceLevel.MANUAL_REVIEW_REQUIRED

    if any(
        hypothesis.status == HypothesisStatus.REJECTED for hypothesis in session.hypotheses
    ) and not any(
        hypothesis.status == HypothesisStatus.CLOSED for hypothesis in session.hypotheses
    ):
        return ConfidenceLevel.LOW

    if any(
        evidence.raw_result.get("result", {}).get("result_data", {}).get(
            "manual_review_recommended",
            False,
        )
        for evidence in session.evidence
    ):
        return ConfidenceLevel.INCONCLUSIVE

    if any(
        hypothesis.status == HypothesisStatus.VALIDATED
        for hypothesis in session.hypotheses
    ):
        if evidence_count >= 5 and tool_count >= 4 and (repo_casebook_support or external_static_support):
            return ConfidenceLevel.HIGH
        if evidence_count >= 3 and tool_count >= 2:
            return ConfidenceLevel.MEDIUM

    if any(
        hypothesis.status == HypothesisStatus.OBSERVED_SIGNAL
        for hypothesis in session.hypotheses
    ):
        return ConfidenceLevel.INCONCLUSIVE

    if any(
        hypothesis.status == HypothesisStatus.CLOSED
        for hypothesis in session.hypotheses
    ):
        return ConfidenceLevel.LOW

    return ConfidenceLevel.INCONCLUSIVE
