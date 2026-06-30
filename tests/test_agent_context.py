from __future__ import annotations

from typing import Any

from app.agents.critic_agent import CriticAgent
from app.agents.cryptography_agent import CryptographyAgent
from app.agents.hypothesis_agent import HypothesisAgent
from app.agents.report_agent import ReportAgent
from app.agents.strategy_agent import StrategyAgent
from app.models.agent_results import MathAgentResult
from app.models.seed import ResearchSeed
from app.models.session import ResearchSession
from app.types import ConfidenceLevel


class _CapturingGateway:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(self, **kwargs: Any) -> str:
        self.calls.append(kwargs)
        responses = {
            "cryptography_agent": (
                "Surface Summary: contract surface\n"
                "Focus Areas:\n- access control\n"
                "Preferred Tool Families:\n- static analysis\n"
                "Preferred Local Tools:\n- slither_audit_tool\n"
                "Preferred Testbeds:\n- contract_static\n"
                "Defensive Questions:\n- Is authority bounded?"
            ),
            "strategy_agent": (
                "Strategy Summary: compile then inspect\n"
                "Primary Checks:\n- compile\n"
                "Escalation Local Tools:\n- slither_audit_tool\n"
                "Null Controls:\n- clean baseline\n"
                "Stop Conditions:\n- evidence exhausted"
            ),
            "hypothesis_agent": (
                "Summary: authority may be missing\n"
                "Rationale: exposed setter\n"
                "Planned Test: inspect access control\n"
                "Branch Type: core\n"
                "Priority: 1"
            ),
            "critic_agent": (
                "Critique Summary: branch is testable\n"
                "Accepted Branches: 1\n"
                "Rejected Branches:\n"
                "Rejection Reasons:"
            ),
            "report_agent": (
                "Summary: local evidence requires review\n"
                "Anomaly: authority signal\n"
                "Recommendation: inspect setter\n"
                "Confidence Hint: manual_review_required"
            ),
        }
        return responses[str(kwargs["agent_name"])]


def test_live_agent_prompts_receive_upstream_context_and_local_evidence() -> None:
    gateway = _CapturingGateway()
    seed = ResearchSeed(
        raw_text="Review the contract authority boundary.",
        domain="smart_contract_audit",
    )
    math_result = MathAgentResult(
        formalization_summary="formal authority model",
        key_objects=["owner"],
        testable_elements=["setter guard"],
    )

    crypto_result = CryptographyAgent(gateway=gateway).run(
        seed=seed,
        math_formalization=math_result,
        approved_local_tools=["contract_compile_tool", "slither_audit_tool"],
    )
    assert "formal authority model" in gateway.calls[-1]["user_prompt"]
    assert "setter guard" in gateway.calls[-1]["user_prompt"]
    assert "slither_audit_tool" in gateway.calls[-1]["user_prompt"]

    strategy_result = StrategyAgent(gateway=gateway).run(
        seed=seed,
        math_formalization=math_result,
        cryptography_profile=crypto_result,
        approved_local_tools=["contract_compile_tool", "slither_audit_tool"],
    )
    assert "contract surface" in gateway.calls[-1]["user_prompt"]
    assert "contract_compile_tool" in gateway.calls[-1]["user_prompt"]

    hypothesis_result = HypothesisAgent(gateway=gateway).run(
        seed=seed,
        math_formalization=math_result,
        cryptography_profile=crypto_result,
        strategy_profile=strategy_result,
        max_hypotheses=1,
    )
    assert "compile then inspect" in gateway.calls[-1]["user_prompt"]

    CriticAgent(gateway=gateway).run(
        seed=seed,
        math_formalization=math_result,
        hypothesis_result=hypothesis_result,
        cryptography_profile=crypto_result,
        strategy_profile=strategy_result,
    )
    assert "authority may be missing" in gateway.calls[-1]["user_prompt"]
    assert "inspect access control" in gateway.calls[-1]["user_prompt"]

    session = ResearchSession(seed=seed)
    ReportAgent(gateway=gateway).run(
        session=session,
        evidence_summary="Slither and compile evidence disagree.",
        confidence=ConfidenceLevel.MANUAL_REVIEW_REQUIRED,
    )
    assert "Slither and compile evidence disagree" in gateway.calls[-1]["user_prompt"]
    assert "manual_review_required" in gateway.calls[-1]["user_prompt"]


def test_agent_context_sections_are_bounded() -> None:
    gateway = _CapturingGateway()
    agent = CryptographyAgent(gateway=gateway)
    prompt = agent.context_prompt(
        ResearchSeed(raw_text="seed", domain="ecc_research"),
        ("Large context", "x" * (agent.max_context_section_chars + 100)),
    )

    assert "[context truncated]" in prompt
    assert len(prompt) < agent.max_context_section_chars + 500


def test_provider_seed_is_bounded_without_changing_local_session_seed() -> None:
    gateway = _CapturingGateway()
    agent = CryptographyAgent(gateway=gateway)
    raw_seed = "x" * (agent.max_provider_seed_chars + 10_000)
    seed = ResearchSeed(raw_text=raw_seed, domain="ecc_research")

    prompt = agent.seed_prompt(seed)

    assert "[provider seed truncated; full seed remains local]" in prompt
    assert len(prompt) < len(raw_seed)
    assert raw_seed not in prompt
    assert seed.raw_text == raw_seed


class _MalformedGateway:
    def generate(self, **kwargs: Any) -> str:
        agent_name = str(kwargs["agent_name"])
        if agent_name == "hypothesis_agent":
            return (
                "Summary: review branch\n"
                "Rationale: local signal\n"
                "Planned Test: run bounded check\n"
                "Branch Type: invented-type\n"
                "Priority: not-a-number"
            )
        if agent_name == "critic_agent":
            return (
                "Critique Summary: bounded review\n"
                "Accepted Branches: 1, invalid, -2\n"
                "Rejected Branches: none\n"
                "Rejection Reasons:"
            )
        return (
            "Summary: bounded result\n"
            "Anomaly: none\n"
            "Recommendation: preserve evidence\n"
            "Confidence Hint: impossible"
        )


def test_malformed_agent_labels_fall_back_without_crashing() -> None:
    gateway = _MalformedGateway()
    seed = ResearchSeed(raw_text="Review a bounded surface.", domain="ecc_research")
    math_result = MathAgentResult(formalization_summary="bounded model")

    hypotheses = HypothesisAgent(gateway=gateway).run(
        seed=seed,
        math_formalization=math_result,
        max_hypotheses=1,
    )
    assert hypotheses.branches[0].branch_type.value == "exploratory"
    assert hypotheses.branches[0].priority == 1

    critic = CriticAgent(gateway=gateway).run(
        seed=seed,
        math_formalization=math_result,
        hypothesis_result=hypotheses,
    )
    assert critic.accepted_branches == [1]
    assert critic.rejected_branches == []

    _, report = ReportAgent(gateway=gateway).run(
        session=ResearchSession(seed=seed),
        evidence_summary="bounded local evidence",
        confidence=ConfidenceLevel.INCONCLUSIVE,
    )
    assert report.confidence == ConfidenceLevel.INCONCLUSIVE


def test_critic_preserves_zero_based_branch_indexes() -> None:
    critic = CriticAgent(gateway=_MalformedGateway())

    assert critic._parse_indices("0, 1, invalid, -1, 1") == [0, 1]
