from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.agent_results import (
    CryptographyAgentResult,
    HypothesisAgentResult,
    HypothesisBranch,
    MathAgentResult,
    StrategyAgentResult,
)
from app.models.seed import ResearchSeed
from app.types import BranchType


class HypothesisAgent(BaseAgent):
    """Expands a formalized seed into bounded testable branches."""

    prompt_name = "hypothesis_agent.txt"

    def run(
        self,
        *,
        seed: ResearchSeed,
        math_formalization: MathAgentResult,
        cryptography_profile: CryptographyAgentResult | None = None,
        strategy_profile: StrategyAgentResult | None = None,
        max_hypotheses: int = 2,
        round_index: int = 1,
        follow_up_context: str | None = None,
    ) -> HypothesisAgentResult:
        branches: list[HypothesisBranch] = []
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

        for variant_index in range(1, max_hypotheses + 1):
            response = self.gateway.generate(
                agent_name=self.route_name,
                system_prompt=self.load_prompt(),
                user_prompt=user_prompt,
                metadata={
                    "agent": "hypothesis",
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
                    "variant_index": variant_index,
                    "round_index": round_index,
                    "follow_up_context": follow_up_context or "",
                },
            )
            sections = self.parse_labeled_sections(response)
            branch_type = BranchType(
                sections.get("branch type", BranchType.EXPLORATORY.value).strip().lower()
            )
            priority = int(sections.get("priority", str(variant_index)).strip())
            branch = HypothesisBranch(
                summary=sections.get("summary", "Hypothesis unavailable."),
                rationale=sections.get("rationale", "No rationale provided."),
                planned_test=sections.get("planned test", "Manual review required."),
                branch_type=branch_type,
                priority=priority,
            )
            branches.append(branch)

        return HypothesisAgentResult(branches=branches)
