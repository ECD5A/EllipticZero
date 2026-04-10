from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.agent_results import CryptographyAgentResult, MathAgentResult
from app.models.seed import ResearchSeed


class CryptographyAgent(BaseAgent):
    """Profiles ECC-facing defensive research surfaces and likely anomaly classes."""

    prompt_name = "cryptography_agent.txt"

    def run(
        self,
        *,
        seed: ResearchSeed,
        math_formalization: MathAgentResult,
        round_index: int = 1,
        follow_up_context: str | None = None,
    ) -> CryptographyAgentResult:
        user_prompt = seed.raw_text
        if follow_up_context:
            user_prompt = (
                f"{seed.raw_text}\n\nFollow-up context for exploratory round {round_index}:\n"
                f"{follow_up_context}"
            )
        response = self.gateway.generate(
            agent_name=self.route_name,
            system_prompt=self.load_prompt(),
            user_prompt=user_prompt,
            metadata={
                "agent": "cryptography",
                "seed": seed.raw_text,
                "math_summary": math_formalization.formalization_summary,
                "round_index": round_index,
                "follow_up_context": follow_up_context or "",
            },
        )
        sections = self.parse_labeled_sections(response)
        return CryptographyAgentResult(
            surface_summary=sections.get("surface summary", "Cryptographic surface summary unavailable."),
            focus_areas=[
                line.lstrip("- ").strip()
                for line in sections.get("focus areas", "").splitlines()
                if line.strip()
            ],
            preferred_tool_families=[
                line.lstrip("- ").strip()
                for line in sections.get("preferred tool families", "").splitlines()
                if line.strip()
            ],
            preferred_local_tools=[
                line.lstrip("- ").strip()
                for line in sections.get("preferred local tools", "").splitlines()
                if line.strip()
            ],
            preferred_testbeds=[
                line.lstrip("- ").strip()
                for line in sections.get("preferred testbeds", "").splitlines()
                if line.strip()
            ],
            defensive_questions=[
                line.lstrip("- ").strip()
                for line in sections.get("defensive questions", "").splitlines()
                if line.strip()
            ],
        )
