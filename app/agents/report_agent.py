from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.agent_results import ReportAgentResult
from app.models.report import ResearchReport
from app.models.session import ResearchSession
from app.types import ConfidenceLevel


class ReportAgent(BaseAgent):
    """Produces the final bounded session report."""

    prompt_name = "report_agent.txt"

    def run(
        self,
        *,
        session: ResearchSession,
        evidence_summary: str,
        confidence: ConfidenceLevel,
    ) -> tuple[ReportAgentResult, ResearchReport]:
        response = self.gateway.generate(
            agent_name=self.route_name,
            system_prompt=self.load_prompt(),
            user_prompt=session.seed.raw_text,
            metadata={
                "agent": "report",
                "seed": session.seed.raw_text,
                "evidence_summary": evidence_summary,
                "keyword_hit_count": sum(
                    int(
                        evidence.raw_result.get("result", {})
                        .get("result_data", {})
                        .get("keyword_hit_count", 0)
                    )
                    for evidence in session.evidence
                ),
                "tool_name": (
                    ", ".join(
                        evidence.tool_name
                        for evidence in session.evidence
                        if evidence.tool_name
                    )
                    or "unknown_tool"
                ),
                "crypto_surface_summary": (
                    session.cryptography_result.surface_summary
                    if session.cryptography_result is not None
                    else ""
                ),
                "strategy_summary": (
                    session.strategy_result.strategy_summary
                    if session.strategy_result is not None
                    else ""
                ),
                "research_mode": session.research_mode.value,
                "research_target": (
                    session.research_target.target_reference
                    if session.research_target is not None
                    else ""
                ),
            },
        )
        summary_lines: list[str] = []
        anomalies: list[str] = []
        recommendations: list[str] = []
        confidence_hint = confidence

        for line in response.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith("Summary:"):
                summary_lines.append(stripped.removeprefix("Summary:").strip())
            elif stripped.startswith("Anomaly:"):
                anomalies.append(stripped.removeprefix("Anomaly:").strip())
            elif stripped.startswith("Recommendation:"):
                recommendations.append(stripped.removeprefix("Recommendation:").strip())
            elif stripped.startswith("Confidence Hint:"):
                confidence_hint = ConfidenceLevel(
                    stripped.removeprefix("Confidence Hint:").strip().lower()
                )

        summary = " ".join(summary_lines).strip() or evidence_summary

        result = ReportAgentResult(
            summary=summary,
            anomalies=anomalies,
            recommendations=recommendations,
            confidence_hint=confidence_hint,
        )
        report = ResearchReport(
            session_id=session.session_id,
            seed_text=session.seed.raw_text,
            summary=result.summary,
            research_mode=session.research_mode.value,
            research_target=(
                session.research_target.target_reference
                if session.research_target is not None
                else None
            ),
            anomalies=result.anomalies,
            recommendations=result.recommendations,
            confidence=confidence,
        )
        return result, report
