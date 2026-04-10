from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from app.core.seed_parsing import extract_contract_code
from app.llm.providers.base import BaseLLMProvider


class MockLLMProvider(BaseLLMProvider):
    """Deterministic provider for local development and tests."""

    provider_name = "mock"

    def generate(
        self,
        *,
        model: str,
        timeout_seconds: int,
        max_request_tokens: int,
        system_prompt: str,
        user_prompt: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        del model, timeout_seconds, max_request_tokens, system_prompt, user_prompt
        data = dict(metadata or {})
        agent = str(data.get("agent", "")).strip().lower()
        seed = str(data.get("seed", "")).strip()
        round_index = int(data.get("round_index", 1))
        follow_up_context = str(data.get("follow_up_context", "")).strip()
        smart_contract_seed = self._is_smart_contract_seed(seed)

        if agent == "math":
            if smart_contract_seed:
                focus = self._smart_contract_focus(seed)
                if round_index > 1 and follow_up_context:
                    return (
                        f"Formalization Summary: Round {round_index} reframes the contract-audit seed around {focus} "
                        "while preserving bounded local static-review assumptions.\n"
                        "Key Objects:\n"
                        "- contract entry points and privileged surfaces\n"
                        "- externally reachable value or control-flow boundaries\n"
                        "- bounded review questions supported by local static tooling\n"
                        "Testable Elements:\n"
                        "- compare the earlier signal against a narrower contract review pass\n"
                        "- preserve null explanations when the code remains underspecified\n"
                        "- keep follow-up claims limited to local static evidence"
                    )
                return (
                    f"Formalization Summary: Formalize the seed around {focus} while preserving bounded contract-audit language.\n"
                    "Key Objects:\n"
                    "- contract entry points and visibility boundaries\n"
                    "- privileged or value-moving operations\n"
                    "- locally reviewable control-flow or access assumptions\n"
                    "Testable Elements:\n"
                    "- parse the contract into a structural outline\n"
                    "- map the exposed surface before deeper pattern checks\n"
                    "- keep initial findings descriptive and review-oriented"
                )
            focus = self._focus_label(seed)
            if round_index > 1 and follow_up_context:
                return (
                    f"Formalization Summary: Round {round_index} reframes the seed around follow-up evidence "
                    f"linked to {focus} while preserving bounded local claims.\n"
                    "Key Objects:\n"
                    "- prior bounded evidence from earlier exploratory rounds\n"
                    "- refined elliptic-curve anomaly or consistency focus\n"
                    "- locally testable follow-up observables\n"
                    "Testable Elements:\n"
                    "- compare earlier signals against a stricter local check\n"
                    "- isolate whether the follow-up context strengthens or weakens the lead\n"
                    "- preserve null explanations when the new evidence remains inconclusive"
                )
            return (
                f"Formalization Summary: Formalize the seed around {focus} while preserving the "
                "original wording and avoiding proof claims.\n"
                "Key Objects:\n"
                "- seed-defined elliptic-curve context\n"
                "- implementation or anomaly surface described by the user\n"
                "- bounded local observables linked to the seed\n"
                "Testable Elements:\n"
                "- classify technical focus terms in the seed\n"
                "- record whether implementation language appears\n"
                "- identify whether anomaly language is present without claiming an anomaly"
            )

        if agent == "cryptography":
            if smart_contract_seed:
                preferred_tool_families, preferred_local_tools, preferred_testbeds = self._contract_preferences(seed)
                return (
                    "Surface Summary: Map the seed to bounded smart-contract audit surfaces such as access control, "
                    "external call boundaries, privileged state transitions, and static pattern-review targets.\n"
                    "Focus Areas:\n"
                    "- externally reachable write paths and payable functions\n"
                    "- low-level call, delegatecall, tx.origin, and selfdestruct usage\n"
                    "- contract-review surfaces that justify cautious manual follow-up\n"
                    "Preferred Tool Families:\n"
                    + self._bullet_lines(preferred_tool_families)
                    + "\nPreferred Local Tools:\n"
                    + self._bullet_lines(preferred_local_tools)
                    + "\nPreferred Testbeds:\n"
                    + self._bullet_lines(preferred_testbeds)
                    + "\n"
                    "Defensive Questions:\n"
                    "- which contract surfaces are externally reachable and privilege-sensitive\n"
                    "- which bounded pattern checks can be run locally first\n"
                    "- where should findings stay manual-review only"
                )
            preferred_tool_families, preferred_local_tools, preferred_testbeds = self._cryptography_preferences(seed)
            if round_index > 1 and follow_up_context:
                return (
                    "Surface Summary: Reframe the earlier signal as a bounded ECC defensive surface with emphasis "
                    "on parser behavior, point-validation assumptions, and inconsistency handling under follow-up checks.\n"
                    "Focus Areas:\n"
                    "- point or public-key parsing behavior under stricter follow-up\n"
                    "- on-curve and format-validation assumptions\n"
                    "- benign underspecification versus persistent anomaly signals\n"
                    "Preferred Tool Families:\n"
                    + self._bullet_lines(preferred_tool_families)
                    + "\nPreferred Local Tools:\n"
                    + self._bullet_lines(preferred_local_tools)
                    + "\nPreferred Testbeds:\n"
                    + self._bullet_lines(preferred_testbeds)
                    + "\n"
                    "Defensive Questions:\n"
                    "- does the earlier signal survive a narrower local check\n"
                    "- can a formatting or parsing ambiguity explain the signal\n"
                    "- should the branch remain manual-review only"
                )
            return (
                "Surface Summary: Map the seed to bounded ECC defensive surfaces such as point parsing, curve metadata, "
                "symbolic consistency, modular consistency, or implementation-side validation behavior.\n"
                "Focus Areas:\n"
                "- parser and validator boundary conditions\n"
                "- curve-domain normalization and alias handling\n"
                "- local mathematical consistency claims that can be checked safely\n"
                "Preferred Tool Families:\n"
                + self._bullet_lines(preferred_tool_families)
                + "\nPreferred Local Tools:\n"
                + self._bullet_lines(preferred_local_tools)
                + "\nPreferred Testbeds:\n"
                + self._bullet_lines(preferred_testbeds)
                + "\n"
                "Defensive Questions:\n"
                "- is the seed describing a real cryptographic surface or only vague terminology\n"
                "- which local tool family can check the claim safely first\n"
                "- where should null explanations be preserved"
            )

        if agent == "strategy":
            if smart_contract_seed:
                escalation_tools = [
                    "contract_compile_tool",
                    "slither_audit_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                ]
                return (
                    "Strategy Summary: Start with a bounded compile or structural parse, then map the exposed surface, "
                    "and only after that run static analyzer and pattern checks that may justify manual review.\n"
                    "Primary Checks:\n"
                    "- compile or parse the contract into a locally checkable structure\n"
                    "- map public, external, payable, and privileged surfaces\n"
                    "Escalation Local Tools:\n"
                    + self._bullet_lines(escalation_tools)
                    + "\n"
                    "Null Controls:\n"
                    "- demonstration-only code with no sensitive state transitions\n"
                    "- benign admin surface that is already modifier-guarded\n"
                    "Stop Conditions:\n"
                    "- only generic contract structure was observed\n"
                    "- no bounded static finding rises above manual-review level"
                )
            escalation_tools = self._strategy_escalation_tools(seed)
            if round_index > 1 and follow_up_context:
                return (
                    "Strategy Summary: Run a stricter second-pass local check, compare it against a conservative null "
                    "control, and stop if the signal remains weak or collapses into formatting noise.\n"
                    "Primary Checks:\n"
                    "- rerun the strongest local consistency path under narrower assumptions\n"
                    "- compare the result against a null-style local explanation\n"
                    "Escalation Local Tools:\n"
                    + self._bullet_lines(escalation_tools)
                    + "\n"
                    "Null Controls:\n"
                    "- ambiguous input handling\n"
                    "- insufficiently specific seed language\n"
                    "Stop Conditions:\n"
                    "- no new local evidence beyond the prior round\n"
                    "- only manual review remains justified"
                )
            return (
                "Strategy Summary: Start with the least invasive local checks, preserve null controls, and escalate "
                "only when bounded evidence becomes more specific.\n"
                "Primary Checks:\n"
                "- classify the seed into a bounded ECC surface\n"
                "- run one local tool family that matches that surface\n"
                "- keep the first report evidence-first and low-confidence\n"
                "Escalation Local Tools:\n"
                + self._bullet_lines(escalation_tools)
                + "\n"
                "Null Controls:\n"
                "- terminology ambiguity\n"
                "- missing implementation detail\n"
                "- benign metadata mismatch\n"
                "Stop Conditions:\n"
                "- no bounded local tool applies\n"
                "- evidence remains inconclusive after the first useful pass"
            )

        if agent == "hypothesis":
            if smart_contract_seed:
                variant_index = int(data.get("variant_index", 1))
                if variant_index == 1:
                    return (
                        "Summary: Investigate whether the contract exposes externally reachable functions, payable paths, "
                        "or privileged state transitions that warrant bounded manual review.\n"
                        "Rationale: Surface-first inspection keeps the initial audit conservative and anchored in static evidence.\n"
                        "Planned Test: Parse the contract and map public, external, payable, and privileged surfaces.\n"
                        "Branch Type: core\n"
                        "Priority: 1"
                    )
                return (
                    "Summary: Investigate whether bounded static pattern checks reveal review-worthy usage of "
                    "delegatecall, tx.origin, selfdestruct, or reentrancy-like call ordering.\n"
                    "Rationale: Pattern checks should stay review-oriented and never be treated as proof of exploitability.\n"
                    "Planned Test: Run bounded local pattern checks after structural parsing and surface mapping.\n"
                    "Branch Type: exploratory\n"
                    "Priority: 2"
                )
            variant_index = int(data.get("variant_index", 1))
            if round_index > 1:
                if variant_index == 1:
                    return (
                        "Summary: Probe whether the strongest earlier signal survives a stricter follow-up check "
                        "using the same bounded local sandbox, with emphasis on consistency rather than novelty.\n"
                        "Rationale: A second-round branch should only deepen a lead when earlier evidence suggests "
                        "a concrete inconsistency worth rechecking under a narrower condition set.\n"
                        "Planned Test: Re-run a stricter local consistency or anomaly check using the follow-up "
                        "context to determine whether the earlier signal persists.\n"
                        "Branch Type: exploratory\n"
                        "Priority: 1"
                    )
                return (
                    "Summary: Test whether the earlier signal collapses under a conservative null explanation such "
                    "as ambiguous terminology, benign formatting noise, or insufficient specificity in the seed.\n"
                    "Rationale: A bounded research loop remains useful only when it actively challenges its own "
                    "strongest apparent lead instead of compounding weak signals.\n"
                    "Planned Test: Compare the follow-up signal against a simpler local explanation and record "
                    "whether manual review remains the only justified outcome.\n"
                    "Branch Type: null\n"
                    "Priority: 2"
                )
            if variant_index == 1:
                return (
                    "Summary: Investigate whether the seed can be reduced to a bounded and testable property "
                    "of an elliptic-curve object, point representation, or cryptographic implementation.\n"
                    "Rationale: This branch stays close to the original seed, encourages disciplined "
                    "formalization, and allows a local tool to produce preliminary evidence without claiming a result.\n"
                    "Planned Test: Run a controlled local classification pass to detect technical focus terms, "
                    "implementation indicators, and anomaly-related language connected to the seed.\n"
                    "Branch Type: core\n"
                    "Priority: 1"
                )
            return (
                "Summary: Investigate whether the apparent issue is better explained by ambiguous terminology, "
                "missing curve parameters, or underspecified implementation context rather than a true anomaly.\n"
                "Rationale: This branch acts as a null-style explanation that reduces overreach and helps reject "
                "weak interpretations before stronger claims are considered.\n"
                "Planned Test: Compare the seed language against basic local signals for specificity and report "
                "whether the idea appears sufficiently bounded for deeper computation.\n"
                "Branch Type: null\n"
                "Priority: 2"
            )

        if agent == "critic":
            branch_count = int(data.get("branch_count", 0))
            accepted = ", ".join(str(index) for index in range(branch_count)) or "0"
            if round_index > 1:
                return (
                    "Critique Summary: The follow-up branches remain acceptable only as bounded exploratory leads; "
                    "they should strengthen or weaken prior local signals without upgrading them to proof.\n"
                    f"Accepted Branches: {accepted}\n"
                    "Rejected Branches:\n"
                    "Rejection Reasons:"
                )
            return (
                "Critique Summary: The expanded branches are acceptable for preliminary testing only when "
                "their outputs are treated as early evidence rather than proof and when weak signals remain bounded.\n"
                f"Accepted Branches: {accepted}\n"
                "Rejected Branches:\n"
                "Rejection Reasons:"
            )

        if agent == "report":
            if smart_contract_seed:
                tool_name = str(data.get("tool_name", "contract_parser_tool")).strip()
                return (
                    "Summary: The session preserved the original smart-contract audit seed, ran bounded local static analysis, "
                    "and recorded review-oriented evidence without claiming a validated exploit path.\n"
                    f"Anomaly: {tool_name} produced bounded review signals only; manual review remains more important than overclaiming.\n"
                    "Recommendation: Extend the local smart-contract audit toolset with deeper static and invariant checks.\n"
                    "Recommendation: Keep contract findings tied to local evidence and reviewable source locations.\n"
                    "Recommendation: Require manual review before escalating any bounded signal into a security claim.\n"
                    "Confidence Hint: inconclusive"
                )
            keyword_hits = data.get("keyword_hit_count", 0)
            tool_name = str(data.get("tool_name", "local_tool")).strip()
            anomaly_line = (
                f"Anomaly: {tool_name} found anomaly-related language, but this is not evidence of a real cryptographic anomaly."
                if keyword_hits
                else f"Anomaly: No substantive anomaly signal was established by {tool_name}."
            )
            return (
                "Summary: The session preserved the original seed, produced bounded hypotheses, ran a registry-controlled "
                "local compute job, and recorded preliminary evidence without claiming a validated mathematical or cryptographic result.\n"
                f"{anomaly_line}\n"
                "Recommendation: Extend the built-in local toolset with deeper domain-specific elliptic-curve analysis.\n"
                "Recommendation: Add rerun-capable evidence collection before upgrading confidence.\n"
                "Recommendation: Request manual review whenever the seed remains underspecified after formalization.\n"
                "Confidence Hint: inconclusive"
            )

        return (
            "Formalization Summary: Mock provider fallback.\n"
            "Key Objects:\n"
            "- unknown\n"
            "Testable Elements:\n"
            "- manual review required"
        )

    def _focus_label(self, seed: str) -> str:
        lowered = seed.lower()
        if "implementation" in lowered or "library" in lowered or "code" in lowered:
            return "implementation behavior"
        if "anomaly" in lowered or "anomal" in lowered:
            return "possible anomaly signals"
        if "point" in lowered:
            return "elliptic-curve point behavior"
        if "curve" in lowered or self._extract_curve_names(lowered):
            return "elliptic-curve properties"
        return "a bounded elliptic-curve research question"

    def _extract_curve_names(self, seed: str) -> list[str]:
        return re.findall(r"(secp256k1|curve25519|ed25519|p-?256|p-?384|p-?521)", seed)

    def _is_smart_contract_seed(self, seed: str) -> bool:
        lowered = seed.lower()
        return any(
            token in lowered
            for token in (
                "[ez_domain: smart_contract_audit]",
                "pragma solidity",
                "contract ",
                "interface ",
                "library ",
                "delegatecall",
                "tx.origin",
                "selfdestruct",
                "solidity",
                "vyper",
            )
        )

    def _smart_contract_focus(self, seed: str) -> str:
        lowered = seed.lower()
        if any(token in lowered for token in ("delegatecall", "tx.origin", "selfdestruct", "reentrancy")):
            return "bounded smart-contract risk patterns"
        if any(token in lowered for token in ("access", "owner", "admin", "modifier", "privilege")):
            return "contract access-control boundaries"
        return "smart-contract surface and control-flow review"

    def _bullet_lines(self, items: list[str]) -> str:
        normalized = items or ["symbolic_check_tool"]
        return "\n".join(f"- {item}" for item in normalized)

    def _cryptography_preferences(self, seed: str) -> tuple[list[str], list[str], list[str]]:
        lowered = seed.lower()
        if any(
            token in lowered
            for token in ("subgroup", "cofactor", "torsion", "small subgroup", "cofactor clearing", "twist")
        ):
            return (
                ["curve_metadata", "ecc_consistency", "bounded testbed"],
                ["curve_metadata_tool", "ecc_consistency_check_tool", "ecc_testbed_tool"],
                ["subgroup_cofactor_corpus", "curve_family_corpus"],
            )
        if any(
            token in lowered
            for token in ("family", "montgomery", "edwards", "25519 family", "curve family", "x25519", "ed25519")
        ):
            return (
                ["curve_metadata", "bounded testbed", "ecc_consistency"],
                ["curve_metadata_tool", "ecc_testbed_tool", "ecc_consistency_check_tool"],
                ["curve_family_corpus", "encoding_edge_corpus"],
            )
        if any(token in lowered for token in ("parser", "parsing", "prefix", "malformed", "compressed", "uncompressed")):
            return (
                ["ecc_consistency", "bounded testbed", "deterministic fuzz mutation"],
                ["ecc_consistency_check_tool", "ecc_testbed_tool", "fuzz_mutation_tool"],
                ["point_anomaly_corpus", "coordinate_shape_corpus", "encoding_edge_corpus"],
            )
        if any(token in lowered for token in ("domain", "generator", "order", "cofactor", "alias", "metadata", "registry")):
            return (
                ["curve_metadata", "bounded testbed", "ecc_consistency"],
                ["curve_metadata_tool", "ecc_curve_parameter_tool", "ecc_testbed_tool"],
                ["curve_alias_corpus", "curve_domain_corpus", "subgroup_cofactor_corpus"],
            )
        if any(token in lowered for token in ("constraint", "proof", "prove", "invariant", "counterexample", "symbolic")):
            return (
                ["symbolic_or_formal", "property_based"],
                ["symbolic_check_tool", "formal_constraint_tool", "property_invariant_tool"],
                [],
            )
        if any(token in lowered for token in ("finite field", "modular", "modulo")):
            return (
                ["finite_field", "deterministic_probe"],
                ["finite_field_check_tool", "deterministic_experiment_tool"],
                [],
            )
        return (
            ["ecc_consistency", "curve_metadata", "symbolic_or_formal"],
            ["ecc_consistency_check_tool", "curve_metadata_tool", "symbolic_check_tool"],
            ["point_anomaly_corpus"],
        )

    def _contract_preferences(self, seed: str) -> tuple[list[str], list[str], list[str]]:
        lowered = seed.lower()
        embedded_contract_code = extract_contract_code(seed)
        if embedded_contract_code:
            lowered = lowered.replace(embedded_contract_code.lower(), " ")
        if any(
            token in lowered
            for token in ("echidna", "property", "properties", "assertion", "assertions", "invariant", "invariants", "fuzz", "fuzzing", "counterexample", "harness")
        ):
            return (
                ["smart_contract_invariant_analysis", "smart_contract_pattern_review", "smart_contract_surface"],
                ["echidna_audit_tool", "contract_pattern_check_tool", "contract_surface_tool"],
                ["state_machine_corpus"],
            )
        if any(
            token in lowered
            for token in ("foundry", "forge", "storage layout", "storage-layout", "method identifiers", "methodidentifiers", "remapping")
        ):
            return (
                ["smart_contract_foundry_analysis", "smart_contract_compile", "smart_contract_surface"],
                ["foundry_audit_tool", "contract_compile_tool", "contract_surface_tool"],
                [],
            )
        if any(
            token in lowered
            for token in ("compile", "compiler", "solc", "syntax", "build", "bytecode", "import", "pragma")
        ):
            return (
                ["smart_contract_compile", "smart_contract_parse", "smart_contract_surface"],
                ["contract_compile_tool", "contract_parser_tool", "contract_surface_tool"],
                [],
            )
        if any(
            token in lowered
            for token in ("slither", "detector", "detectors", "static analysis", "static analyzer", "severity")
        ):
            return (
                ["smart_contract_static_analysis", "smart_contract_pattern_review", "smart_contract_surface"],
                ["slither_audit_tool", "contract_pattern_check_tool", "contract_surface_tool"],
                ["dangerous_call_corpus"],
            )
        if any(token in lowered for token in ("delegatecall", "tx.origin", "selfdestruct", "reentrancy")):
            return (
                ["smart_contract_static_analysis", "smart_contract_pattern_review", "smart_contract_testbed"],
                ["slither_audit_tool", "contract_pattern_check_tool", "contract_testbed_tool"],
                ["dangerous_call_corpus" if any(token in lowered for token in ("delegatecall", "tx.origin", "selfdestruct")) else "reentrancy_review_corpus"],
            )
        if any(token in lowered for token in ("erc20", "token", "transferfrom", "allowance", "approve", "assembly")):
            return (
                ["smart_contract_pattern_review", "smart_contract_surface", "smart_contract_testbed"],
                ["contract_pattern_check_tool", "contract_surface_tool", "contract_testbed_tool"],
                ["token_interaction_corpus" if any(token in lowered for token in ("erc20", "token", "transferfrom", "allowance", "approve")) else "assembly_review_corpus"],
            )
        if any(token in lowered for token in ("public", "external", "payable", "modifier", "access", "owner", "admin")):
            return (
                ["smart_contract_surface", "smart_contract_pattern_review", "smart_contract_testbed"],
                ["contract_surface_tool", "contract_pattern_check_tool", "contract_testbed_tool"],
                ["access_control_corpus"],
            )
        return (
            ["smart_contract_compile", "smart_contract_parse", "smart_contract_surface"],
            ["contract_compile_tool", "contract_parser_tool", "contract_surface_tool"],
            ["access_control_corpus"],
        )

    def _strategy_escalation_tools(self, seed: str) -> list[str]:
        lowered = seed.lower()
        if any(token in lowered for token in ("constraint", "proof", "prove", "solver", "smt")):
            return ["formal_constraint_tool", "property_invariant_tool"]
        if any(token in lowered for token in ("invariant", "counterexample", "property-based", "property based")):
            return ["property_invariant_tool", "formal_constraint_tool"]
        if any(token in lowered for token in ("parser", "parsing", "prefix", "malformed", "shape", "coordinate")):
            return ["point_descriptor_tool", "ecc_consistency_check_tool", "ecc_testbed_tool"]
        if any(token in lowered for token in ("mutation", "fuzz", "mutate")):
            return ["fuzz_mutation_tool", "ecc_testbed_tool"]
        if any(token in lowered for token in ("domain", "alias", "metadata", "registry")):
            return ["curve_metadata_tool", "ecc_testbed_tool"]
        if any(
            token in lowered
            for token in ("echidna", "property", "properties", "assertion", "assertions", "invariant", "invariants", "counterexample")
        ):
            return ["echidna_audit_tool", "contract_pattern_check_tool", "contract_surface_tool"]
        if any(
            token in lowered
            for token in ("slither", "detector", "detectors", "static analysis", "static analyzer", "reentrancy")
        ):
            return ["slither_audit_tool", "contract_pattern_check_tool", "contract_surface_tool"]
        if any(
            token in lowered
            for token in ("foundry", "forge", "storage layout", "storage-layout", "method identifiers", "methodidentifiers")
        ):
            return ["foundry_audit_tool", "contract_compile_tool", "contract_surface_tool"]
        return ["symbolic_check_tool", "deterministic_experiment_tool"]
