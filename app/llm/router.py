from __future__ import annotations

from dataclasses import dataclass

from app.config import AppConfig
from app.llm.budget import BudgetPolicy


@dataclass(slots=True, frozen=True)
class RouteDecision:
    provider: str
    model: str
    fallback_provider: str | None
    fallback_model: str | None
    budget: BudgetPolicy


@dataclass(slots=True, frozen=True)
class RouteOverviewRow:
    agent_name: str
    provider: str
    model: str
    mode: str


ROUTED_AGENT_ROLES: tuple[str, ...] = (
    "math_agent",
    "cryptography_agent",
    "strategy_agent",
    "hypothesis_agent",
    "critic_agent",
    "report_agent",
)


class ModelRouter:
    """Config-driven routing for per-agent model selection."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config

    def select(self, agent_name: str) -> RouteDecision:
        agent_route = self.config.agents.get_for_agent(agent_name)
        provider = agent_route.provider or self.config.llm.default_provider
        model = agent_route.model or self.config.llm.default_model
        fallback_provider = self.config.llm.fallback_provider
        fallback_model = self.config.llm.fallback_model
        if fallback_provider and not fallback_model:
            fallback_model = self.config.llm.default_model

        return RouteDecision(
            provider=provider,
            model=model,
            fallback_provider=fallback_provider,
            fallback_model=fallback_model,
            budget=BudgetPolicy(
                max_request_tokens=self.config.llm.max_request_tokens,
                max_total_requests_per_session=self.config.llm.max_total_requests_per_session,
                timeout_seconds=self.config.llm.timeout_seconds,
            ),
        )


def _route_mode(
    *,
    default_provider: str,
    default_model: str,
    provider: str,
    model: str,
) -> str:
    if provider == default_provider and model == default_model:
        return "shared"
    return "override"


def build_route_overview(config: AppConfig) -> list[RouteOverviewRow]:
    router = ModelRouter(config)
    rows: list[RouteOverviewRow] = []
    for agent_name in ROUTED_AGENT_ROLES:
        decision = router.select(agent_name)
        rows.append(
            RouteOverviewRow(
                agent_name=agent_name,
                provider=decision.provider,
                model=decision.model,
                mode=_route_mode(
                    default_provider=config.llm.default_provider,
                    default_model=config.llm.default_model,
                    provider=decision.provider,
                    model=decision.model,
                ),
            )
        )
    return rows


def summarize_route_mode(config: AppConfig) -> str:
    rows = build_route_overview(config)
    override_count = sum(1 for row in rows if row.mode == "override")
    if override_count == 0:
        return "shared-default"
    return f"mixed ({override_count} override{'s' if override_count != 1 else ''})"
