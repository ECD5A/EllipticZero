from __future__ import annotations

from app.agents.base import BaseAgent
from app.models.agent_results import MathAgentResult
from app.models.seed import ResearchSeed


class MathAgent(BaseAgent):
    """Formalizes the user's seed into bounded research language."""

    prompt_name = "math_agent.txt"

    def run(
        self,
        seed: ResearchSeed,
        *,
        round_index: int = 1,
        follow_up_context: str | None = None,
    ) -> MathAgentResult:
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
                "agent": "math",
                "seed": seed.raw_text,
                "round_index": round_index,
                "follow_up_context": follow_up_context or "",
            },
        )
        sections = self.parse_labeled_sections(response)
        key_objects = [
            line.lstrip("- ").strip()
            for line in sections.get("key objects", "").splitlines()
            if line.strip()
        ]
        testable_elements = [
            line.lstrip("- ").strip()
            for line in sections.get("testable elements", "").splitlines()
            if line.strip()
        ]
        return MathAgentResult(
            formalization_summary=sections.get(
                "formalization summary",
                "Formalization unavailable.",
            ),
            key_objects=key_objects,
            testable_elements=testable_elements,
        )
