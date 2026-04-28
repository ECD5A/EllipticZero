from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.agent_results import (
    CriticAgentResult,
    CryptographyAgentResult,
    HypothesisAgentResult,
    MathAgentResult,
    StrategyAgentResult,
)
from app.models.seed import ResearchSeed


class CriticAgent(BaseAgent):
    """Challenges weak reasoning and recommends bounded statuses."""

    prompt_name = "critic_agent.txt"

    def run(
        self,
        *,
        seed: ResearchSeed,
        math_formalization: MathAgentResult,
        hypothesis_result: HypothesisAgentResult,
        cryptography_profile: CryptographyAgentResult | None = None,
        strategy_profile: StrategyAgentResult | None = None,
        round_index: int = 1,
        follow_up_context: str | None = None,
    ) -> CriticAgentResult:
        user_prompt = self.seed_prompt(seed)
        guidance_parts: list[str] = []
        if cryptography_profile is not None:
            guidance_parts.append(
                f"Cryptography surface summary: {cryptography_profile.surface_summary}"
            )
        if strategy_profile is not None:
            guidance_parts.append(
                f"Strategy summary: {strategy_profile.strategy_summary}"
            )
        if follow_up_context:
            guidance_parts.append(
                f"Follow-up context for exploratory round {round_index}: {follow_up_context}"
            )
        if guidance_parts:
            user_prompt = f"{self.seed_prompt(seed)}\n\n" + "\n".join(guidance_parts)
        response = self.gateway.generate(
            agent_name=self.route_name,
            system_prompt=self.load_prompt(),
            user_prompt=user_prompt,
            metadata={
                "agent": "critic",
                "seed": seed.raw_text,
                "domain": seed.domain or "",
                "math_summary": math_formalization.formalization_summary,
                "crypto_surface_summary": (
                    cryptography_profile.surface_summary
                    if cryptography_profile is not None
                    else ""
                ),
                "strategy_summary": (
                    strategy_profile.strategy_summary
                    if strategy_profile is not None
                    else ""
                ),
                "branch_count": len(hypothesis_result.branches),
                "round_index": round_index,
                "follow_up_context": follow_up_context or "",
            },
        )
        sections = self.parse_labeled_sections(response)
        accepted = self._parse_indices(sections.get("accepted branches", ""))
        rejected = self._parse_indices(sections.get("rejected branches", ""))
        rejection_reasons = [
            line.lstrip("- ").strip()
            for line in sections.get("rejection reasons", "").splitlines()
            if line.strip()
        ]
        return CriticAgentResult(
            accepted_branches=accepted,
            rejected_branches=rejected,
            rejection_reasons=rejection_reasons,
            critique_summary=sections.get("critique summary", "Critique unavailable."),
        )

    def _parse_indices(self, value: str) -> list[int]:
        if not value.strip():
            return []
        return [int(item.strip()) for item in value.split(",") if item.strip()]
