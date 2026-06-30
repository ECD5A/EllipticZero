# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

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
        user_prompt = self.context_prompt(
            seed,
            ("Math formalization", math_formalization.formalization_summary),
            (
                "Cryptography or contract surface",
                cryptography_profile.surface_summary if cryptography_profile is not None else None,
            ),
            (
                "Research strategy",
                strategy_profile.strategy_summary if strategy_profile is not None else None,
            ),
            (f"Follow-up context for exploratory round {round_index}", follow_up_context),
        )

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
            branch_type = self._parse_branch_type(sections.get("branch type", ""))
            priority = self._parse_priority(
                sections.get("priority", ""),
                default=variant_index,
            )
            branch = HypothesisBranch(
                summary=sections.get("summary", "Hypothesis unavailable."),
                rationale=sections.get("rationale", "No rationale provided."),
                planned_test=sections.get("planned test", "Manual review required."),
                branch_type=branch_type,
                priority=priority,
            )
            branches.append(branch)

        return HypothesisAgentResult(branches=branches)

    def _parse_branch_type(self, value: str) -> BranchType:
        try:
            return BranchType(value.strip().lower())
        except ValueError:
            return BranchType.EXPLORATORY

    def _parse_priority(self, value: str, *, default: int) -> int:
        try:
            return max(1, int(value.strip()))
        except (TypeError, ValueError):
            return max(1, default)
