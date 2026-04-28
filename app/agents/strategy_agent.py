from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.agent_results import (
    CryptographyAgentResult,
    MathAgentResult,
    StrategyAgentResult,
)
from app.models.seed import ResearchSeed


class StrategyAgent(BaseAgent):
    """Shapes bounded local experiment strategy and null controls for the seed."""

    prompt_name = "strategy_agent.txt"

    def run(
        self,
        *,
        seed: ResearchSeed,
        math_formalization: MathAgentResult,
        cryptography_profile: CryptographyAgentResult,
        round_index: int = 1,
        follow_up_context: str | None = None,
    ) -> StrategyAgentResult:
        user_prompt = self.seed_prompt(seed)
        if follow_up_context:
            user_prompt = (
                f"{self.seed_prompt(seed)}\n\nFollow-up context for exploratory round {round_index}:\n"
                f"{follow_up_context}"
            )
        response = self.gateway.generate(
            agent_name=self.route_name,
            system_prompt=self.load_prompt(),
            user_prompt=user_prompt,
            metadata={
                "agent": "strategy",
                "seed": seed.raw_text,
                "domain": seed.domain or "",
                "math_summary": math_formalization.formalization_summary,
                "crypto_surface_summary": cryptography_profile.surface_summary,
                "round_index": round_index,
                "follow_up_context": follow_up_context or "",
            },
        )
        sections = self.parse_labeled_sections(response)
        return StrategyAgentResult(
            strategy_summary=sections.get("strategy summary", "Bounded local strategy unavailable."),
            primary_checks=[
                line.lstrip("- ").strip()
                for line in sections.get("primary checks", "").splitlines()
                if line.strip()
            ],
            escalation_local_tools=[
                line.lstrip("- ").strip()
                for line in sections.get("escalation local tools", "").splitlines()
                if line.strip()
            ],
            null_controls=[
                line.lstrip("- ").strip()
                for line in sections.get("null controls", "").splitlines()
                if line.strip()
            ],
            stop_conditions=[
                line.lstrip("- ").strip()
                for line in sections.get("stop conditions", "").splitlines()
                if line.strip()
            ],
        )
