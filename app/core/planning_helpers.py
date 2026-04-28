from __future__ import annotations

from pathlib import Path

from app.config import AppConfig
from app.core.seed_parsing import (
    extract_contract_code,
    extract_contract_language,
    extract_contract_name,
    extract_contract_root,
    extract_contract_source_label,
    extract_curve_name,
    extract_expression,
    extract_expression_pair,
    extract_modular_payload,
    extract_point_coordinates,
    extract_public_key_hex,
)
from app.models import (
    ExperimentPack,
    ExperimentPackStep,
    ExperimentSpec,
    ExperimentType,
    Hypothesis,
    ResearchMode,
    ResearchSession,
    ResearchTarget,
    ToolPlan,
)
from app.tools.smart_contract_utils import (
    build_contract_outline,
    detect_echidna_property_functions,
    has_assertion_surface,
)
from app.types import BranchType

FIXED_TARGET_ORIGINS = {"synthetic", "explicit_domain"}


def uses_fixed_research_target(research_target: ResearchTarget | None) -> bool:
    return research_target is not None and research_target.target_origin in FIXED_TARGET_ORIGINS


def build_tool_plan(
    *,
    config: AppConfig,
    session: ResearchSession,
    seed_text: str,
    hypothesis: Hypothesis,
    research_target: ResearchTarget | None = None,
) -> ToolPlan:
    combined_text = f"{seed_text} {hypothesis.summary} {hypothesis.planned_test or ''}"
    target_kind = (
        research_target.target_kind
        if uses_fixed_research_target(research_target)
        else determine_target_kind(
            seed_text=seed_text,
            planned_test=hypothesis.planned_test or "",
            summary=hypothesis.summary,
        )
    )
    tool_name, selected_by_roles = resolve_tool_name_for_hypothesis(
        config=config,
        session=session,
        hypothesis=hypothesis,
        target_kind=target_kind,
        combined_text=combined_text,
    )
    return ToolPlan(
        tool_name=tool_name,
        reason=(
            f"Selected {tool_name} because the hypothesis appears "
            f"{target_kind}-oriented under bounded local analysis."
            if not uses_fixed_research_target(research_target)
            else (
                f"Selected {tool_name} because fixed target "
                f"{research_target.synthetic_target_name or research_target.target_reference} "
                f"declared a bounded {target_kind} profile."
            )
        )
        + (
            f" Role-guidance: {', '.join(selected_by_roles)} influenced the selection."
            if selected_by_roles
            else ""
        ),
        priority=hypothesis.priority,
        expected_output=expected_output_for_tool(
            tool_name=tool_name,
            target_kind=target_kind,
        ),
        deterministic_expected=True,
        selected_by_roles=selected_by_roles,
    )


def build_standard_smart_contract_tool_plans(
    *,
    config: AppConfig,
    session: ResearchSession,
    seed_text: str,
    hypothesis: Hypothesis,
    research_target: ResearchTarget | None = None,
) -> list[ToolPlan]:
    primary_plan = build_tool_plan(
        config=config,
        session=session,
        seed_text=seed_text,
        hypothesis=hypothesis,
        research_target=research_target,
    )
    combined_text = f"{seed_text} {hypothesis.summary} {hypothesis.planned_test or ''}"
    target_kind = (
        research_target.target_kind
        if uses_fixed_research_target(research_target)
        else determine_target_kind(
            seed_text=seed_text,
            planned_test=hypothesis.planned_test or "",
            summary=hypothesis.summary,
        )
    )
    if target_kind != "smart_contract":
        return [primary_plan]

    language = (
        extract_contract_language(seed_text)
        or extract_contract_language(combined_text)
        or "solidity"
    ).strip().lower()
    contract_code = extract_contract_code(seed_text) or extract_contract_code(combined_text) or ""
    contract_root = extract_contract_root(seed_text) or extract_contract_root(combined_text)
    stack = [
        "contract_parser_tool",
        "contract_compile_tool",
        "contract_surface_tool",
        "contract_pattern_check_tool",
        "slither_audit_tool",
        "foundry_audit_tool",
    ]
    if language != "solidity":
        stack = [
            "contract_parser_tool",
            "contract_surface_tool",
            "contract_pattern_check_tool",
        ]
    elif _smart_contract_should_include_echidna(text=combined_text, contract_code=contract_code):
        stack.append("echidna_audit_tool")

    if contract_root:
        stack.insert(0, "contract_inventory_tool")
    if language == "solidity" and select_smart_contract_testbed_reference(
        text=combined_text,
        preferred_testbeds=normalized_testbed_hints(session),
        prefer_repo_casebooks=bool(contract_root),
    ):
        stack.append("contract_testbed_tool")

    role_hints = normalized_role_tool_hints(session)
    plans = [primary_plan]
    for tool_name in stack:
        if tool_name == primary_plan.tool_name:
            continue
        selected_by_roles = [
            role_name
            for role_name, hinted_tools in role_hints.items()
            if tool_name in hinted_tools
        ]
        plans.append(
            ToolPlan(
                tool_name=tool_name,
                reason=(
                    f"Added {tool_name} as part of the bounded smart-contract audit stack "
                    "to preserve compile, surface, and static-review coverage."
                )
                + (
                    f" Role-guidance: {', '.join(selected_by_roles)} influenced the inclusion."
                    if selected_by_roles
                    else ""
                ),
                priority=hypothesis.priority,
                expected_output=expected_output_for_tool(
                    tool_name=tool_name,
                    target_kind=target_kind,
                ),
                deterministic_expected=True,
                selected_by_roles=selected_by_roles,
            )
        )
    return plans


def build_pack_tool_plan(
    *,
    hypothesis: Hypothesis,
    pack: ExperimentPack,
    step: ExperimentPackStep,
) -> ToolPlan:
    return ToolPlan(
        tool_name=step.preferred_tool,
        reason=(
            f"Experiment pack {pack.pack_name} selected step {step.step_id} ({step.title}) "
            "to structure a bounded local research workflow."
        ),
        priority=hypothesis.priority,
        expected_output=step.description,
        deterministic_expected=step.deterministic_expected,
    )


def expected_output_for_tool(*, tool_name: str, target_kind: str) -> str:
    tool_specific = {
        "contract_inventory_tool": "bounded contract repository inventory with scoped file, pragma, and candidate review summaries",
        "contract_parser_tool": "bounded contract outline with parsed contracts, functions, and imports",
        "contract_compile_tool": "bounded compile result with compiler version, diagnostics, and compiled contract names",
        "contract_surface_tool": "bounded contract surface summary with reachable functions and review areas",
        "contract_pattern_check_tool": "bounded built-in contract pattern findings and review signals",
        "slither_audit_tool": "bounded Slither detector findings and normalized severity counts",
        "echidna_audit_tool": "bounded Echidna property or assertion result with failing-test summaries",
        "foundry_audit_tool": "bounded Foundry build and structural inspection result with method and storage-layout signals",
        "contract_testbed_tool": "bounded smart-contract corpus sweep result",
    }
    if tool_name in tool_specific:
        return tool_specific[tool_name]
    return {
        "curve": "recognized curve metadata and canonical registry entry",
        "point": "ECC point/public-key format descriptor",
        "ecc_consistency": "bounded ECC format or on-curve consistency result",
        "smart_contract": "bounded smart-contract compile, static-analysis, parse, surface, or pattern-check result",
        "smart_contract_testbed": "bounded smart-contract corpus sweep result",
        "symbolic": "bounded advanced symbolic normalization or deterministic fallback",
        "testbed": "bounded ECC testbed sweep result",
        "finite_field": "bounded modular consistency result",
        "experiment": "deterministic repeatability result",
        "generic": "preliminary text-level local classification",
    }.get(target_kind, "bounded local output")


def build_experiment_spec(
    *,
    config: AppConfig,
    session: ResearchSession,
    seed_text: str,
    formalization: str,
    hypothesis: Hypothesis,
    tool_plan: ToolPlan,
    research_target: ResearchTarget | None = None,
) -> ExperimentSpec:
    target_kind = (
        research_target.target_kind
        if uses_fixed_research_target(research_target)
        else determine_target_kind(
            seed_text=seed_text,
            planned_test=hypothesis.planned_test or "",
            summary=hypothesis.summary,
        )
    )
    if tool_plan.tool_name == "property_invariant_tool":
        experiment_type = ExperimentType.PROPERTY_INVARIANT_CHECK
    elif tool_plan.tool_name == "contract_inventory_tool":
        experiment_type = ExperimentType.SMART_CONTRACT_INVENTORY_CHECK
    elif tool_plan.tool_name == "contract_compile_tool":
        experiment_type = ExperimentType.SMART_CONTRACT_COMPILE_CHECK
    elif tool_plan.tool_name == "slither_audit_tool":
        experiment_type = ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK
    elif tool_plan.tool_name == "echidna_audit_tool":
        experiment_type = ExperimentType.SMART_CONTRACT_FUZZ_CHECK
    elif tool_plan.tool_name == "foundry_audit_tool":
        experiment_type = ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK
    elif tool_plan.tool_name == "formal_constraint_tool":
        experiment_type = ExperimentType.FORMAL_CONSTRAINT_CHECK
    elif tool_plan.tool_name == "fuzz_mutation_tool":
        experiment_type = ExperimentType.FUZZ_MUTATION_SCAN
    elif tool_plan.tool_name == "ecc_testbed_tool":
        experiment_type = ExperimentType.ECC_TESTBED_SWEEP
    elif tool_plan.tool_name == "curve_metadata_tool":
        experiment_type = ExperimentType.CURVE_METADATA_MATH_CHECK
    elif tool_plan.tool_name == "point_descriptor_tool":
        experiment_type = ExperimentType.POINT_STRUCTURE_CHECK
    elif tool_plan.tool_name == "contract_parser_tool":
        experiment_type = ExperimentType.SMART_CONTRACT_PARSE
    elif tool_plan.tool_name == "contract_surface_tool":
        experiment_type = ExperimentType.SMART_CONTRACT_SURFACE_CHECK
    elif tool_plan.tool_name == "contract_pattern_check_tool":
        experiment_type = ExperimentType.SMART_CONTRACT_PATTERN_CHECK
    elif tool_plan.tool_name == "contract_testbed_tool":
        experiment_type = ExperimentType.SMART_CONTRACT_TESTBED_SWEEP
    else:
        experiment_type = {
            "curve": ExperimentType.ECC_CURVE_PARAMETER_CHECK,
            "point": ExperimentType.ECC_POINT_FORMAT_CHECK,
            "ecc_consistency": ExperimentType.ECC_CONSISTENCY_CHECK,
            "smart_contract": ExperimentType.SMART_CONTRACT_PARSE,
            "smart_contract_testbed": ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
            "symbolic": ExperimentType.SYMBOLIC_SIMPLIFICATION,
            "testbed": ExperimentType.ECC_TESTBED_SWEEP,
            "finite_field": ExperimentType.FINITE_FIELD_CHECK,
            "experiment": ExperimentType.DETERMINISTIC_REPEAT_CHECK,
            "generic": ExperimentType.PLACEHOLDER_SIGNAL_SCAN,
        }.get(target_kind, ExperimentType.PLACEHOLDER_SIGNAL_SCAN)
    if tool_plan.tool_name == "contract_testbed_tool":
        target_kind = "smart_contract_testbed"
        target_reference = (
            research_target.target_reference
            if uses_fixed_research_target(research_target)
            else select_smart_contract_testbed_reference(
                text=f"{seed_text} {formalization} {hypothesis.summary} {hypothesis.planned_test or ''}",
                preferred_testbeds=normalized_testbed_hints(session),
                prefer_repo_casebooks=bool(
                    extract_contract_root(seed_text)
                    or extract_contract_root(formalization)
                    or extract_contract_root(hypothesis.summary)
                    or extract_contract_root(hypothesis.planned_test or "")
                ),
            )
            or "reentrancy_review_corpus"
        )
    else:
        target_reference = (
            research_target.target_reference
            if uses_fixed_research_target(research_target)
            else target_reference_for_kind(
                target_kind=target_kind,
                seed_text=seed_text,
                formalization=formalization,
                hypothesis=hypothesis,
                session=session,
            )
        )

    return ExperimentSpec(
        experiment_type=experiment_type,
        target_kind=target_kind,
        target_reference=target_reference,
        parameters={
            "formalization": formalization,
            "hypothesis_summary": hypothesis.summary,
            "planned_test": hypothesis.planned_test or "",
            "target_origin": research_target.target_origin if research_target is not None else "inferred",
            "synthetic_target_name": (
                research_target.synthetic_target_name
                if research_target is not None
                else None
            ),
        },
        repeat_count=3 if target_kind == "experiment" else 1,
        deterministic_required=tool_plan.deterministic_expected,
    )


def build_pack_experiment_spec(
    *,
    seed_text: str,
    formalization: str,
    hypothesis: Hypothesis,
    tool_plan: ToolPlan,
    step: ExperimentPackStep,
    research_target: ResearchTarget | None,
    pack: ExperimentPack,
) -> ExperimentSpec:
    inferred_target_kind = (
        research_target.target_kind
        if uses_fixed_research_target(research_target)
        else determine_target_kind(
            seed_text=seed_text,
            planned_test=hypothesis.planned_test or "",
            summary=hypothesis.summary,
        )
    )
    target_kind = inferred_target_kind
    if tool_plan.tool_name == "contract_testbed_tool":
        default_pack_casebook = {
            "repo_casebook_benchmark_pack": "repo_asset_flow_casebook",
            "protocol_casebook_benchmark_pack": "repo_protocol_accounting_casebook",
        }.get(pack.pack_name)
        target_kind = "smart_contract_testbed"
        target_reference = (
            step.target_reference_override
            or (
                research_target.target_reference
                if uses_fixed_research_target(research_target)
                else select_smart_contract_testbed_reference(
                    text=f"{seed_text} {formalization} {hypothesis.summary} {hypothesis.planned_test or ''} {pack.description}",
                    prefer_repo_casebooks=bool(
                        step.requires_contract_root
                        or extract_contract_root(seed_text)
                        or extract_contract_root(formalization)
                        or extract_contract_root(hypothesis.summary)
                        or extract_contract_root(hypothesis.planned_test or "")
                    ),
                )
            )
            or default_pack_casebook
            or "reentrancy_review_corpus"
        )
    else:
        target_reference = (
            step.target_reference_override
            or (
                research_target.target_reference
                if uses_fixed_research_target(research_target)
                else target_reference_for_kind(
                    target_kind=target_kind,
                    seed_text=seed_text,
                    formalization=formalization,
                    hypothesis=hypothesis,
                )
            )
        )
    return ExperimentSpec(
        experiment_type=step.experiment_type,
        target_kind=target_kind,
        target_reference=target_reference,
        parameters={
            "formalization": formalization,
            "hypothesis_summary": hypothesis.summary,
            "planned_test": hypothesis.planned_test or "",
            "target_origin": research_target.target_origin if research_target is not None else "inferred",
            "synthetic_target_name": (
                research_target.synthetic_target_name
                if research_target is not None
                else None
            ),
            "experiment_pack_name": pack.pack_name,
            "experiment_pack_step_id": step.step_id,
            "experiment_pack_step_title": step.title,
        },
        repeat_count=3 if step.experiment_type == ExperimentType.DETERMINISTIC_REPEAT_CHECK else 1,
        deterministic_required=tool_plan.deterministic_expected,
    )


def determine_target_kind(
    *,
    seed_text: str,
    planned_test: str,
    summary: str,
) -> str:
    combined = f"{seed_text} {planned_test} {summary}"
    lowered = combined.lower()
    if (
        not _seed_has_direct_domain_signal(seed_text)
        and _looks_like_generic_agent_scaffold(planned_test=planned_test, summary=summary)
    ):
        return "generic"
    contract_like = extract_contract_code(combined) is not None or any(
        token in lowered
        for token in (
            "pragma solidity",
            "contract ",
            "interface ",
            "library ",
            "solidity",
            "vyper",
            "reentrancy",
            "delegatecall",
            "tx.origin",
            "selfdestruct",
            "access control",
            "payable function",
            "контракт",
            "смарт",
            "солидити",
            "права доступа",
        )
    )
    if contract_like and any(token in lowered for token in ("corpus", "suite", "testbed")):
        return "smart_contract_testbed"
    if (
        any(token in lowered for token in ("corpus", "suite"))
        or "testbed target" in lowered
        or "testbed corpus" in lowered
        or "built-in testbed" in lowered
    ):
        return "testbed"
    if contract_like:
        return "smart_contract"
    if extract_modular_payload(combined) is not None or any(
        token in lowered for token in ("finite field", "modular", "modulo", " mod ", "конечное поле", "модуль")
    ):
        return "finite_field"
    if extract_public_key_hex(combined) is not None or any(
        token in lowered
        for token in (
            "public key",
            "pubkey",
            "compressed",
            "uncompressed",
            "prefix",
            "on-curve",
            "сжат",
            "несжат",
            "префикс",
            "на кривой",
        )
    ):
        return "ecc_consistency" if any(
            token in lowered
            for token in ("consistency", "check", "on-curve", "shape", "prefix", "malformed", "провер", "префикс")
        ) else "point"
    if extract_curve_name(combined):
        if any(
            token in lowered
            for token in ("parameter", "domain", "generator", "order", "cofactor", "alias", "metadata")
        ):
            return "curve"
        if any(
            token in lowered for token in ("consistency", "check", "shape", "on-curve", "format")
        ):
            return "ecc_consistency"
        return "curve"
    if any(token in lowered for token in ("curve", "крив", "ecc", "montgomery", "edwards", "weierstrass")):
        return "ecc_consistency" if any(
            token in lowered for token in ("consistency", "check", "shape", "on-curve", "format", "провер", "формат")
        ) else "curve"
    if extract_point_coordinates(combined) != (None, None):
        return "ecc_consistency" if any(
            token in lowered for token in ("consistency", "check", "on-curve", "shape")
        ) else "point"
    if extract_expression(combined):
        return "symbolic"
    if any(token in lowered for token in ("point", "coordinate", "точк", "координат")):
        return "ecc_consistency" if any(
            token in lowered for token in ("consistency", "check", "shape", "провер", "формат")
        ) else "point"
    if any(token in lowered for token in ("repeat", "deterministic", "consistency", "normalize")):
        return "experiment"
    return "generic"


def _seed_has_direct_domain_signal(seed_text: str) -> bool:
    """Return whether the original seed itself contains a recognizable anchor."""

    lowered = seed_text.lower()
    if (
        extract_contract_code(seed_text) is not None
        or extract_modular_payload(seed_text) is not None
        or extract_public_key_hex(seed_text) is not None
        or extract_curve_name(seed_text) is not None
        or extract_point_coordinates(seed_text) != (None, None)
        or extract_expression(seed_text) is not None
    ):
        return True
    direct_tokens = (
        "curve",
        "ecc",
        "family",
        "montgomery",
        "edwards",
        "weierstrass",
        "point",
        "coordinate",
        "compressed",
        "uncompressed",
        "prefix",
        "on-curve",
        "signature",
        "ecdsa",
        "ecdh",
        "scalar",
        "subgroup",
        "cofactor",
        "torsion",
        "finite field",
        "modular",
        "contract",
        "solidity",
        "vyper",
        "reentrancy",
        "delegatecall",
        "tx.origin",
        "access control",
        "крив",
        "точк",
        "координат",
        "сжат",
        "несжат",
        "префикс",
        "подпис",
        "скаляр",
        "подгрупп",
        "кофактор",
        "конечное поле",
        "модуль",
        "контракт",
        "смарт",
        "солидити",
        "реентерабель",
        "права доступа",
    )
    return any(token in lowered for token in direct_tokens)


def _looks_like_generic_agent_scaffold(*, planned_test: str, summary: str) -> bool:
    """Detect generic fallback wording so unknown seeds stay neutral."""

    combined = f"{planned_test} {summary}".lower()
    generic_markers = (
        "seed can be reduced to a bounded and testable property",
        "preliminary text-level local classification",
        "detect technical focus terms",
        "ambiguous terminology",
        "underspecified implementation context",
    )
    return any(marker in combined for marker in generic_markers)


def tool_name_for_target_kind(
    *,
    config: AppConfig,
    target_kind: str,
    combined_text: str = "",
) -> str:
    lowered = combined_text.lower()
    embedded_contract_code = extract_contract_code(combined_text)
    if embedded_contract_code:
        lowered = lowered.replace(embedded_contract_code.lower(), " ")
    if target_kind == "testbed":
        return "ecc_testbed_tool"
    if target_kind == "smart_contract_testbed":
        return "contract_testbed_tool"
    if target_kind == "smart_contract":
        if any(
            token in lowered
            for token in (
                "echidna",
                "property",
                "properties",
                "assertion",
                "assertions",
                "invariant",
                "invariants",
                "fuzz",
                "fuzzing",
                "counterexample",
                "harness",
            )
        ):
            return "echidna_audit_tool"
        if any(
            token in lowered
            for token in (
                "foundry",
                "forge",
                "storage layout",
                "storage-layout",
                "method identifiers",
                "methodidentifiers",
                "remapping",
                "project build",
            )
        ):
            return "foundry_audit_tool"
        if any(
            token in lowered
            for token in (
                "slither",
                "detector",
                "detectors",
                "static analysis",
                "static analyzer",
                "severity",
            )
        ):
            return "slither_audit_tool"
        if any(
            token in lowered
            for token in ("repository", "repo", "inventory", "scope", "file inventory", "contract root")
        ):
            return "contract_inventory_tool"
        if any(
            token in lowered
            for token in (
                "compile",
                "compiler",
                "solc",
                "syntax",
                "build",
                "bytecode",
                "import",
                "pragma",
                "inheritance",
                "abstract",
            )
        ):
            return "contract_compile_tool"
        if any(
            token in lowered
            for token in (
                "reentrancy",
                "delegatecall",
                "tx.origin",
                "selfdestruct",
                "unchecked call",
                "access control",
                "owner",
                "admin",
                "privilege",
                "pattern",
                "allowance",
                "approve",
                "accounting",
                "balance",
                "balances",
                "claim",
                "redeem",
                "insufficient",
                "zero address",
                "zero-address",
                "implementation validation",
                "state machine",
                "state transition",
                "status",
                "phase",
            )
        ):
            return "contract_pattern_check_tool"
        if any(
            token in lowered
            for token in ("surface", "public", "external", "payable", "modifier", "function")
        ):
            return "contract_surface_tool"
        return "contract_parser_tool"
    if target_kind in {"point", "ecc_consistency"} and any(
        token in lowered for token in ("fuzz", "mutation", "mutate")
    ):
        return "fuzz_mutation_tool"
    if target_kind == "symbolic" and any(
        token in lowered for token in ("constraint", "proof", "prove", "smt", "solver")
    ):
        return "formal_constraint_tool"
    if target_kind == "symbolic" and any(
        token in lowered for token in ("property-based", "property based", "counterexample", "invariant")
    ):
        return "property_invariant_tool"
    return {
        "curve": "ecc_curve_parameter_tool",
        "point": "ecc_point_format_tool",
        "ecc_consistency": "ecc_consistency_check_tool",
        "symbolic": (
            "sage_symbolic_tool"
            if config.advanced_math_enabled and config.sage.enabled
            else "symbolic_check_tool"
        ),
        "finite_field": "finite_field_check_tool",
        "experiment": "deterministic_experiment_tool",
        "generic": "placeholder_math_tool",
    }.get(target_kind, "placeholder_math_tool")


def resolve_tool_name_for_hypothesis(
    *,
    config: AppConfig,
    session: ResearchSession,
    hypothesis: Hypothesis,
    target_kind: str,
    combined_text: str,
) -> tuple[str, list[str]]:
    lowered = combined_text.lower()
    embedded_contract_code = extract_contract_code(combined_text)
    if embedded_contract_code:
        lowered = lowered.replace(embedded_contract_code.lower(), " ")
    family_hints = normalized_tool_family_hints(session)
    strategy_text = strategy_guidance_text(session)
    role_tool_hints = normalized_role_tool_hints(session)
    exploratory_role_guidance = session.research_mode == ResearchMode.SANDBOXED_EXPLORATORY
    candidates: list[tuple[str, list[str]]] = []

    def add_candidate(tool_name: str, roles: list[str]) -> None:
        for index, (existing_tool, existing_roles) in enumerate(candidates):
            if existing_tool == tool_name:
                merged_roles = list(dict.fromkeys([*existing_roles, *roles]))
                candidates[index] = (existing_tool, merged_roles)
                return
        candidates.append((tool_name, list(dict.fromkeys(roles))))

    if target_kind == "curve" and any(
        token in lowered
        for token in (
            "family transition",
            "curve family transition",
            "montgomery",
            "edwards",
            "short-weierstrass",
            "short weierstrass",
            "registry completeness",
            "metadata completeness",
            "generator completeness",
            "order completeness",
            "domain completeness",
            "twist hygiene",
            "twist safety",
        )
    ):
        if "ecc_testbed_tool" in role_tool_hints["CryptographyAgent"]:
            add_candidate("ecc_testbed_tool", ["CryptographyAgent"])
    if target_kind == "curve" and any(
        token in lowered for token in ("alias", "metadata", "named-curve", "named curve", "registry")
    ):
        if "curve_metadata_tool" in role_tool_hints["CryptographyAgent"] or "curve_metadata" in family_hints:
            add_candidate("curve_metadata_tool", ["CryptographyAgent"])
    if target_kind == "curve" and any(
        token in lowered for token in ("domain", "generator", "order", "cofactor", "family", "completeness")
    ):
        if "ecc_testbed_tool" in role_tool_hints["CryptographyAgent"]:
            add_candidate("ecc_testbed_tool", ["CryptographyAgent"])

    if target_kind in {"point", "ecc_consistency"}:
        if exploratory_role_guidance and hypothesis.branch_type == BranchType.NULL and any(
            token in lowered for token in ("format", "shape", "coordinate", "prefix", "malformed", "parsing")
        ):
            if (
                "point_descriptor_tool" in role_tool_hints["StrategyAgent"]
                or "point_descriptor_tool" in role_tool_hints["CryptographyAgent"]
            ):
                add_candidate("point_descriptor_tool", ["StrategyAgent"])

        if exploratory_role_guidance and any(
            token in family_hints for token in ("bounded_testbed", "testbed")
        ) and any(token in lowered for token in ("corpus", "suite", "testbed", "validation", "parser", "anomaly")):
            if "ecc_testbed_tool" in role_tool_hints["CryptographyAgent"]:
                add_candidate("ecc_testbed_tool", ["CryptographyAgent"])

        if exploratory_role_guidance and any(
            token in family_hints for token in ("deterministic_fuzz_mutation", "fuzz_mutation", "fuzz")
        ) and any(token in lowered for token in ("malformed", "mutation", "fuzz", "prefix", "parser", "parsing")):
            if "fuzz_mutation_tool" in role_tool_hints["CryptographyAgent"]:
                add_candidate("fuzz_mutation_tool", ["CryptographyAgent"])

        if exploratory_role_guidance and any(
            token in lowered
            for token in ("consistency", "check", "on-curve", "range", "field", "validate", "validation")
        ):
            roles: list[str] = []
            if "ecc_consistency_check_tool" in role_tool_hints["CryptographyAgent"]:
                roles.append("CryptographyAgent")
            if "ecc_consistency_check_tool" in role_tool_hints["StrategyAgent"]:
                roles.append("StrategyAgent")
            if roles:
                add_candidate("ecc_consistency_check_tool", roles)

    if target_kind == "symbolic":
        if any(token in lowered for token in ("constraint", "proof", "prove", "smt", "solver")):
            if "formal_constraint_tool" in role_tool_hints["StrategyAgent"]:
                add_candidate("formal_constraint_tool", ["StrategyAgent"])
        if any(token in lowered for token in ("property-based", "property based", "counterexample", "invariant")):
            if "property_invariant_tool" in role_tool_hints["StrategyAgent"]:
                add_candidate("property_invariant_tool", ["StrategyAgent"])
        if any(token in lowered for token in ("symbolic", "normalize", "equivalence", "simplify")):
            roles: list[str] = []
            symbolic_tool_name = (
                "sage_symbolic_tool"
                if config.advanced_math_enabled and config.sage.enabled
                else "symbolic_check_tool"
            )
            if (
                symbolic_tool_name in role_tool_hints["CryptographyAgent"]
                or "symbolic_check_tool" in role_tool_hints["CryptographyAgent"]
            ):
                roles.append("CryptographyAgent")
            if (
                symbolic_tool_name in role_tool_hints["StrategyAgent"]
                or "symbolic_check_tool" in role_tool_hints["StrategyAgent"]
            ):
                roles.append("StrategyAgent")
            if roles:
                add_candidate(symbolic_tool_name, roles)
        if "symbolic_or_formal" in family_hints and any(
            token in strategy_text for token in ("bounded local strategy", "least invasive local checks")
        ):
            add_candidate(
                "sage_symbolic_tool"
                if config.advanced_math_enabled and config.sage.enabled
                else "symbolic_check_tool",
                ["CryptographyAgent", "StrategyAgent"],
            )

    if target_kind == "smart_contract":
        if any(
            token in lowered
            for token in (
                "echidna",
                "property",
                "properties",
                "assertion",
                "assertions",
                "invariant",
                "invariants",
                "fuzz",
                "fuzzing",
                "counterexample",
                "harness",
            )
        ):
            roles = []
            if "echidna_audit_tool" in role_tool_hints["CryptographyAgent"]:
                roles.append("CryptographyAgent")
            if "echidna_audit_tool" in role_tool_hints["StrategyAgent"]:
                roles.append("StrategyAgent")
            if roles:
                add_candidate("echidna_audit_tool", roles)
        if any(
            token in lowered
            for token in (
                "foundry",
                "forge",
                "storage layout",
                "storage-layout",
                "method identifiers",
                "methodidentifiers",
                "remapping",
                "project build",
            )
        ):
            roles = []
            if "foundry_audit_tool" in role_tool_hints["CryptographyAgent"]:
                roles.append("CryptographyAgent")
            if "foundry_audit_tool" in role_tool_hints["StrategyAgent"]:
                roles.append("StrategyAgent")
            if roles:
                add_candidate("foundry_audit_tool", roles)
        if any(
            token in lowered
            for token in (
                "slither",
                "detector",
                "detectors",
                "static analysis",
                "static analyzer",
                "severity",
            )
        ):
            roles = []
            if "slither_audit_tool" in role_tool_hints["CryptographyAgent"]:
                roles.append("CryptographyAgent")
            if "slither_audit_tool" in role_tool_hints["StrategyAgent"]:
                roles.append("StrategyAgent")
            if roles:
                add_candidate("slither_audit_tool", roles)
        if any(
            token in lowered
            for token in (
                "compile",
                "compiler",
                "solc",
                "syntax",
                "build",
                "bytecode",
                "import",
                "pragma",
                "inheritance",
                "abstract",
            )
        ):
            roles: list[str] = []
            if "contract_compile_tool" in role_tool_hints["CryptographyAgent"]:
                roles.append("CryptographyAgent")
            if "contract_compile_tool" in role_tool_hints["StrategyAgent"]:
                roles.append("StrategyAgent")
            if roles:
                add_candidate("contract_compile_tool", roles)
        if any(token in lowered for token in ("parse", "structure", "pragma", "contract", "interface", "library")):
            roles: list[str] = []
            if "contract_parser_tool" in role_tool_hints["CryptographyAgent"]:
                roles.append("CryptographyAgent")
            if "contract_parser_tool" in role_tool_hints["StrategyAgent"]:
                roles.append("StrategyAgent")
            if roles:
                add_candidate("contract_parser_tool", roles)
        if any(
            token in lowered
            for token in ("surface", "surfaces", "public", "external", "payable", "modifier", "owner", "admin", "access")
        ):
            roles = []
            if "contract_surface_tool" in role_tool_hints["CryptographyAgent"]:
                roles.append("CryptographyAgent")
            if "contract_surface_tool" in role_tool_hints["StrategyAgent"]:
                roles.append("StrategyAgent")
            if roles:
                add_candidate("contract_surface_tool", roles)
        if any(
            token in lowered
            for token in (
                "reentrancy",
                "delegatecall",
                "tx.origin",
                "selfdestruct",
                "pattern",
                "review",
                "erc20",
                "token",
                "transferfrom",
                "allowance",
                "approve",
                "assembly",
                "zero address",
                "zero-address",
                "implementation validation",
                "state machine",
                "state transition",
                "status",
                "phase",
            )
        ):
            roles = []
            if "contract_pattern_check_tool" in role_tool_hints["CryptographyAgent"]:
                roles.append("CryptographyAgent")
            if "contract_pattern_check_tool" in role_tool_hints["StrategyAgent"]:
                roles.append("StrategyAgent")
            if roles:
                add_candidate("contract_pattern_check_tool", roles)

    if target_kind == "smart_contract_testbed":
        roles: list[str] = []
        if "contract_testbed_tool" in role_tool_hints["CryptographyAgent"]:
            roles.append("CryptographyAgent")
        if "contract_testbed_tool" in role_tool_hints["StrategyAgent"]:
            roles.append("StrategyAgent")
        if roles:
            add_candidate("contract_testbed_tool", roles)

    if exploratory_role_guidance and target_kind == "testbed":
        roles: list[str] = []
        if "ecc_testbed_tool" in role_tool_hints["CryptographyAgent"]:
            roles.append("CryptographyAgent")
        if "ecc_testbed_tool" in role_tool_hints["StrategyAgent"]:
            roles.append("StrategyAgent")
        if roles:
            add_candidate("ecc_testbed_tool", roles)

    if candidates:
        return choose_role_guided_candidate(session=session, candidates=candidates)
    return tool_name_for_target_kind(config=config, target_kind=target_kind, combined_text=combined_text), []


def normalized_tool_family_hints(session: ResearchSession) -> set[str]:
    if session.cryptography_result is None:
        return set()

    normalized: set[str] = set()
    for item in session.cryptography_result.preferred_tool_families:
        key = item.strip().lower().replace("-", "_").replace(" ", "_")
        if key:
            normalized.add(key)
    return normalized


def normalized_role_tool_hints(session: ResearchSession) -> dict[str, set[str]]:
    normalized = {
        "CryptographyAgent": set(),
        "StrategyAgent": set(),
    }
    if session.cryptography_result is not None:
        for item in [
            *session.cryptography_result.preferred_tool_families,
            *session.cryptography_result.preferred_local_tools,
        ]:
            normalized_hint = normalize_tool_hint(item)
            if normalized_hint:
                normalized["CryptographyAgent"].add(normalized_hint)
    if session.strategy_result is not None:
        for item in session.strategy_result.escalation_local_tools:
            normalized_hint = normalize_tool_hint(item)
            if normalized_hint:
                normalized["StrategyAgent"].add(normalized_hint)
    return normalized


def normalize_tool_hint(value: str) -> str | None:
    key = value.strip().lower().replace("-", "_").replace(" ", "_")
    if not key:
        return None
    mapping = {
        "curve_metadata": "curve_metadata_tool",
        "curve_metadata_tool": "curve_metadata_tool",
        "curve_parameters": "ecc_curve_parameter_tool",
        "domain_parameters": "ecc_curve_parameter_tool",
        "ecc_curve_parameter_tool": "ecc_curve_parameter_tool",
        "point_descriptor": "point_descriptor_tool",
        "point_structure": "point_descriptor_tool",
        "point_descriptor_tool": "point_descriptor_tool",
        "point_format": "ecc_point_format_tool",
        "ecc_point_format_tool": "ecc_point_format_tool",
        "ecc_consistency": "ecc_consistency_check_tool",
        "ecc_consistency_check_tool": "ecc_consistency_check_tool",
        "symbolic_or_formal": "symbolic_check_tool",
        "symbolic_check_tool": "symbolic_check_tool",
        "sage_symbolic_tool": "sage_symbolic_tool",
        "property_based": "property_invariant_tool",
        "property_invariant_tool": "property_invariant_tool",
        "formal": "formal_constraint_tool",
        "solver": "formal_constraint_tool",
        "smt": "formal_constraint_tool",
        "formal_constraint_tool": "formal_constraint_tool",
        "deterministic_fuzz_mutation": "fuzz_mutation_tool",
        "fuzz_mutation": "fuzz_mutation_tool",
        "fuzz": "fuzz_mutation_tool",
        "fuzz_mutation_tool": "fuzz_mutation_tool",
        "smart_contract_inventory": "contract_inventory_tool",
        "contract_inventory_tool": "contract_inventory_tool",
        "smart_contract_parse": "contract_parser_tool",
        "contract_parser_tool": "contract_parser_tool",
        "smart_contract_surface": "contract_surface_tool",
        "contract_surface_tool": "contract_surface_tool",
        "smart_contract_static_analysis": "slither_audit_tool",
        "slither": "slither_audit_tool",
        "slither_audit_tool": "slither_audit_tool",
        "smart_contract_invariant_analysis": "echidna_audit_tool",
        "echidna": "echidna_audit_tool",
        "echidna_audit_tool": "echidna_audit_tool",
        "smart_contract_foundry_analysis": "foundry_audit_tool",
        "foundry": "foundry_audit_tool",
        "forge": "foundry_audit_tool",
        "foundry_audit_tool": "foundry_audit_tool",
        "smart_contract_pattern_review": "contract_pattern_check_tool",
        "contract_pattern_check_tool": "contract_pattern_check_tool",
        "smart_contract_testbed": "contract_testbed_tool",
        "contract_testbed_tool": "contract_testbed_tool",
        "bounded_testbed": "ecc_testbed_tool",
        "testbed": "ecc_testbed_tool",
        "ecc_testbed_tool": "ecc_testbed_tool",
        "finite_field": "finite_field_check_tool",
        "finite_field_check_tool": "finite_field_check_tool",
        "deterministic_probe": "deterministic_experiment_tool",
        "deterministic_experiment_tool": "deterministic_experiment_tool",
    }
    return mapping.get(key, key if key.endswith("_tool") else None)


def choose_role_guided_candidate(
    *,
    session: ResearchSession,
    candidates: list[tuple[str, list[str]]],
) -> tuple[str, list[str]]:
    used_tools = {job.tool_name for job in session.jobs}
    for tool_name, roles in candidates:
        if tool_name not in used_tools:
            return tool_name, roles
    return candidates[0]


def strategy_guidance_text(session: ResearchSession) -> str:
    if session.strategy_result is None:
        return ""
    return " ".join(
        [
            session.strategy_result.strategy_summary,
            *session.strategy_result.primary_checks,
            *session.strategy_result.null_controls,
            *session.strategy_result.stop_conditions,
        ]
    ).lower()


def target_reference_for_kind(
    *,
    target_kind: str,
    seed_text: str,
    formalization: str,
    hypothesis: Hypothesis,
    session: ResearchSession | None = None,
) -> str:
    combined = f"{seed_text} {formalization} {hypothesis.summary} {hypothesis.planned_test or ''}"
    if target_kind == "curve":
        return extract_curve_name(combined) or "unknown_curve"
    if target_kind == "point":
        public_key_hex = extract_public_key_hex(combined)
        if public_key_hex:
            return public_key_hex
        x_value, y_value = extract_point_coordinates(combined)
        if x_value and y_value:
            return f"x={x_value}, y={y_value}"
        return "point_like_payload"
    if target_kind == "ecc_consistency":
        public_key_hex = extract_public_key_hex(combined)
        if public_key_hex:
            return public_key_hex
        x_value, y_value = extract_point_coordinates(combined)
        if x_value and y_value:
            return f"x={x_value}, y={y_value}"
        return extract_curve_name(combined) or "ecc_consistency_target"
    if target_kind == "smart_contract":
        contract_name = extract_contract_name(combined)
        if contract_name:
            return contract_name
        source_label = extract_contract_source_label(combined)
        if source_label:
            return source_label
        language = extract_contract_language(combined)
        if language:
            return f"{language}_contract_source"
        return "smart_contract_source"
    if target_kind == "smart_contract_testbed":
        hinted_testbeds = normalized_testbed_hints(session)
        lowered = combined.lower()
        if "reentrancy_review_corpus" in hinted_testbeds or any(
            token in lowered for token in ("reentrancy", "withdraw", "nonreentrant")
        ):
            return "reentrancy_review_corpus"
        if "access_control_corpus" in hinted_testbeds or any(
            token in lowered for token in ("access control", "owner", "admin", "initialize", "privilege")
        ):
            return "access_control_corpus"
        if "vault_share_corpus" in hinted_testbeds or any(
            token in lowered
            for token in (
                "vault",
                "erc4626",
                "previewdeposit",
                "previewredeem",
                "converttoshares",
                "converttoassets",
                "totalassets",
                "share accounting",
                "price per share",
            )
        ):
            return "vault_share_corpus"
        if "asset_flow_corpus" in hinted_testbeds or any(
            token in lowered
            for token in ("asset flow", "fund flow", "deposit", "withdraw", "claim", "sweep", "rescue", "treasury flow")
        ):
            return "asset_flow_corpus"
        if "authorization_flow_corpus" in hinted_testbeds or any(
            token in lowered
            for token in ("grantrole", "revoke role", "revokeRole", "operator", "guardian", "manager", "pause", "unpause", "authorization flow")
        ):
            return "authorization_flow_corpus"
        if "dangerous_call_corpus" in hinted_testbeds or any(
            token in lowered for token in ("delegatecall", "tx.origin", "selfdestruct", "dangerous call")
        ):
            return "dangerous_call_corpus"
        if "proxy_storage_corpus" in hinted_testbeds or any(
            token in lowered
            for token in ("storage layout", "storage slot", "slot write", "eip1967", "uups", "storage collision")
        ):
            return "proxy_storage_corpus"
        if "upgrade_surface_corpus" in hinted_testbeds or any(
            token in lowered for token in ("upgrade", "implementation", "proxy", "beacon", "logic")
        ):
            return "upgrade_surface_corpus"
        if "time_entropy_corpus" in hinted_testbeds or any(
            token in lowered for token in ("timestamp", "blockhash", "prevrandao", "entropy", "random", "lottery")
        ):
            return "time_entropy_corpus"
        if "reserve_fee_accounting_corpus" in hinted_testbeds or any(
            token in lowered
            for token in (
                "protocol fee",
                "protocolfee",
                "skim",
                "reserve accounting",
                "reserve sync",
                "reserve factor",
                "reservefactor",
                "reserve buffer",
                "reservebuffer",
                "insurance fund",
                "insurancefund",
                "debt accounting",
                "bad debt",
                "baddebt",
                "bad debt socialization",
                "socialized debt",
                "socialize",
                "write off",
                "writeoff",
                "absorb debt",
                "deficit",
                "interest accrual",
                "accrual",
            )
        ):
            return "reserve_fee_accounting_corpus"
        if "token_interaction_corpus" in hinted_testbeds or any(
            token in lowered for token in ("erc20", "token", "transferfrom", "allowance", "approve")
        ):
            return "token_interaction_corpus"
        if "accounting_review_corpus" in hinted_testbeds or any(
            token in lowered for token in ("accounting", "balance", "balances", "claim", "redeem", "insufficient")
        ):
            return "accounting_review_corpus"
        if "signature_review_corpus" in hinted_testbeds or any(
            token in lowered for token in ("signature", "permit", "ecrecover", "meta-tx", "meta transaction", "nonce")
        ):
            return "signature_review_corpus"
        if "collateral_liquidation_corpus" in hinted_testbeds or any(
            token in lowered
            for token in (
                "collateral",
                "liquidation",
                "liquidation fee",
                "liquidation bonus",
                "keeper fee",
                "seize bonus",
                "health factor",
                "healthfactor",
                "ltv",
                "reserve ratio",
                "borrow limit",
                "borrow cap",
                "close factor",
            )
        ):
            return "collateral_liquidation_corpus"
        if "oracle_review_corpus" in hinted_testbeds or any(
            token in lowered for token in ("oracle", "price feed", "chainlink", "latestRoundData", "twap", "stale price")
        ):
            return "oracle_review_corpus"
        if "loop_payout_corpus" in hinted_testbeds or any(
            token in lowered for token in ("batch payout", "batch payment", "airdrop", "distribution", "loop payout", "multi-send")
        ):
            return "loop_payout_corpus"
        if "assembly_review_corpus" in hinted_testbeds or "assembly" in lowered:
            return "assembly_review_corpus"
        return "access_control_corpus"
    if target_kind == "symbolic":
        return extract_expression(combined) or "x + y - y"
    if target_kind == "testbed":
        hinted_testbeds = normalized_testbed_hints(session)
        lowered = combined.lower()
        if "twist_hygiene_corpus" in hinted_testbeds or any(
            token in lowered
            for token in ("twist hygiene", "twist-safe", "twist safe", "twist safety")
        ):
            return "twist_hygiene_corpus"
        if "family_transition_corpus" in hinted_testbeds or any(
            token in lowered
            for token in (
                "family transition",
                "curve family transition",
                "montgomery",
                "edwards",
                "short-weierstrass",
                "short weierstrass",
            )
        ):
            return "family_transition_corpus"
        if "domain_completeness_corpus" in hinted_testbeds or any(
            token in lowered
            for token in (
                "domain completeness",
                "registry completeness",
                "metadata completeness",
                "generator completeness",
                "order completeness",
            )
        ):
            return "domain_completeness_corpus"
        if "encoding_edge_corpus" in hinted_testbeds or any(
            token in lowered
            for token in ("encoding", "compressed", "uncompressed", "prefix", "hybrid", "ed25519", "x25519")
        ):
            return "encoding_edge_corpus"
        if "subgroup_cofactor_corpus" in hinted_testbeds or any(
            token in lowered
            for token in ("subgroup", "cofactor", "torsion", "small subgroup", "cofactor clearing", "twist")
        ):
            return "subgroup_cofactor_corpus"
        if "curve_family_corpus" in hinted_testbeds or any(
            token in lowered
            for token in ("family", "montgomery", "edwards", "25519 family", "curve family")
        ):
            return "curve_family_corpus"
        if "coordinate_shape_corpus" in hinted_testbeds or any(
            token in lowered for token in ("coordinate", "x=", "y=", "shape", "length")
        ):
            return "coordinate_shape_corpus"
        if "curve_domain_corpus" in hinted_testbeds or any(
            token in lowered
            for token in ("domain", "generator", "order", "cofactor", "family", "completeness")
        ):
            return "curve_domain_corpus"
        if "curve_alias_corpus" in hinted_testbeds or any(
            token in lowered for token in ("curve", "alias", "registry")
        ):
            return "curve_alias_corpus"
        return "point_anomaly_corpus"
    if target_kind == "finite_field":
        modulus, left, right = extract_modular_payload(combined) or (7, 10, 3)
        return f"left={left}, right={right}, modulus={modulus}"
    if target_kind == "experiment":
        return "deterministic_local_consistency"
    return "seed_text"


def normalized_testbed_hints(session: ResearchSession | None) -> set[str]:
    if session is None or session.cryptography_result is None:
        return set()
    normalized: set[str] = set()
    for item in session.cryptography_result.preferred_testbeds:
        key = item.strip().lower().replace("-", "_").replace(" ", "_")
        mapping = {
            "point_anomaly": "point_anomaly_corpus",
            "point_anomaly_corpus": "point_anomaly_corpus",
            "curve_alias": "curve_alias_corpus",
            "curve_alias_corpus": "curve_alias_corpus",
            "encoding_edge": "encoding_edge_corpus",
            "encoding_edge_corpus": "encoding_edge_corpus",
            "coordinate_shape": "coordinate_shape_corpus",
            "coordinate_shape_corpus": "coordinate_shape_corpus",
            "subgroup_cofactor": "subgroup_cofactor_corpus",
            "subgroup_cofactor_corpus": "subgroup_cofactor_corpus",
            "curve_domain": "curve_domain_corpus",
            "curve_domain_corpus": "curve_domain_corpus",
            "curve_family": "curve_family_corpus",
            "curve_family_corpus": "curve_family_corpus",
            "twist_hygiene": "twist_hygiene_corpus",
            "twist_hygiene_corpus": "twist_hygiene_corpus",
            "domain_completeness": "domain_completeness_corpus",
            "domain_completeness_corpus": "domain_completeness_corpus",
            "family_transition": "family_transition_corpus",
            "family_transition_corpus": "family_transition_corpus",
            "repo_upgrade_casebook": "repo_upgrade_casebook",
            "repo_asset_flow_casebook": "repo_asset_flow_casebook",
            "repo_oracle_casebook": "repo_oracle_casebook",
            "reentrancy_review": "reentrancy_review_corpus",
            "reentrancy_review_corpus": "reentrancy_review_corpus",
            "access_control": "access_control_corpus",
            "access_control_corpus": "access_control_corpus",
            "vault_share": "vault_share_corpus",
            "vault_share_corpus": "vault_share_corpus",
            "asset_flow": "asset_flow_corpus",
            "asset_flow_corpus": "asset_flow_corpus",
            "authorization_flow": "authorization_flow_corpus",
            "authorization_flow_corpus": "authorization_flow_corpus",
            "dangerous_call": "dangerous_call_corpus",
            "dangerous_call_corpus": "dangerous_call_corpus",
            "upgrade_surface": "upgrade_surface_corpus",
            "upgrade_surface_corpus": "upgrade_surface_corpus",
            "proxy_storage": "proxy_storage_corpus",
            "proxy_storage_corpus": "proxy_storage_corpus",
            "upgrade_validation": "upgrade_validation_corpus",
            "upgrade_validation_corpus": "upgrade_validation_corpus",
            "time_entropy": "time_entropy_corpus",
            "time_entropy_corpus": "time_entropy_corpus",
            "token_interaction": "token_interaction_corpus",
            "token_interaction_corpus": "token_interaction_corpus",
            "signature_review": "signature_review_corpus",
            "signature_review_corpus": "signature_review_corpus",
            "oracle_review": "oracle_review_corpus",
            "oracle_review_corpus": "oracle_review_corpus",
            "collateral_liquidation": "collateral_liquidation_corpus",
            "collateral_liquidation_corpus": "collateral_liquidation_corpus",
            "reserve_fee_accounting": "reserve_fee_accounting_corpus",
            "reserve_fee_accounting_corpus": "reserve_fee_accounting_corpus",
            "loop_payout": "loop_payout_corpus",
            "loop_payout_corpus": "loop_payout_corpus",
            "repo_governance_timelock_casebook": "repo_governance_timelock_casebook",
            "repo_rewards_distribution_casebook": "repo_rewards_distribution_casebook",
            "repo_stablecoin_collateral_casebook": "repo_stablecoin_collateral_casebook",
            "repo_amm_liquidity_casebook": "repo_amm_liquidity_casebook",
            "repo_bridge_custody_casebook": "repo_bridge_custody_casebook",
            "repo_staking_rebase_casebook": "repo_staking_rebase_casebook",
            "repo_keeper_auction_casebook": "repo_keeper_auction_casebook",
            "repo_treasury_vesting_casebook": "repo_treasury_vesting_casebook",
            "repo_insurance_recovery_casebook": "repo_insurance_recovery_casebook",
            "repo_protocol_accounting_casebook": "repo_protocol_accounting_casebook",
            "approval_review": "approval_review_corpus",
            "approval_review_corpus": "approval_review_corpus",
            "accounting_review": "accounting_review_corpus",
            "accounting_review_corpus": "accounting_review_corpus",
            "assembly_review": "assembly_review_corpus",
            "assembly_review_corpus": "assembly_review_corpus",
            "state_machine": "state_machine_corpus",
            "state_machine_corpus": "state_machine_corpus",
        }
        normalized_hint = mapping.get(key)
        if normalized_hint:
            normalized.add(normalized_hint)
    return normalized


def select_smart_contract_testbed_reference(
    *,
    text: str,
    preferred_testbeds: set[str] | None = None,
    prefer_repo_casebooks: bool = False,
) -> str | None:
    preferred = preferred_testbeds or set()
    lowered = text.lower()

    def _match_by_text() -> str | None:
        if any(token in lowered for token in ("state machine", "state transition", "status", "phase", "stage")):
            return "state_machine_corpus"
        if any(
            token in lowered
            for token in (
                "vault",
                "erc4626",
                "previewdeposit",
                "previewredeem",
                "converttoshares",
                "converttoassets",
                "totalassets",
                "share accounting",
                "price per share",
            )
        ):
            return "vault_share_corpus"
        if any(
            token in lowered
            for token in (
                "permit",
                "signature",
                "nonce",
                "allowance",
                "approve",
                "spender",
                "asset flow",
                "fund flow",
                "deposit",
                "withdraw",
                "claim",
                "sweep",
                "rescue",
                "treasury flow",
            )
        ):
            return "asset_flow_corpus"
        if any(
            token in lowered
            for token in ("grantrole", "revoke role", "operator", "guardian", "manager", "pause", "unpause", "authorization flow")
        ):
            return "authorization_flow_corpus"
        if any(
            token in lowered
            for token in (
                "storage layout",
                "storage-layout",
                "storage slot",
                "slot write",
                "eip1967",
                "uups",
                "storage collision",
                "proxy storage",
            )
        ):
            return "proxy_storage_corpus"
        if any(
            token in lowered
            for token in ("zero address", "zero-address", "implementation validation", "code length", "upgrade target")
        ):
            return "upgrade_validation_corpus"
        if any(
            token in lowered
            for token in (
                "protocol fee",
                "protocolfee",
                "skim",
                "reserve accounting",
                "reserve sync",
                "reserve factor",
                "reservefactor",
                "reserve buffer",
                "reservebuffer",
                "insurance fund",
                "insurancefund",
                "debt accounting",
                "bad debt",
                "baddebt",
                "bad debt socialization",
                "socialized debt",
                "socialize",
                "write off",
                "writeoff",
                "absorb debt",
                "deficit",
                "interest accrual",
                "accrual",
            )
        ):
            return "reserve_fee_accounting_corpus"
        if any(token in lowered for token in ("approve", "allowance", "spender", "approval")):
            return "approval_review_corpus"
        if any(
            token in lowered
            for token in ("accounting", "balance", "balances", "claim", "redeem", "insufficient balance", "withdraw ordering")
        ):
            return "accounting_review_corpus"
        if any(token in lowered for token in ("signature", "permit", "ecrecover", "meta-tx", "meta transaction", "nonce")):
            return "signature_review_corpus"
        if any(
            token in lowered
            for token in (
                "collateral",
                "liquidation",
                "liquidation fee",
                "liquidation bonus",
                "keeper fee",
                "seize bonus",
                "health factor",
                "healthfactor",
                "ltv",
                "reserve ratio",
                "borrow limit",
                "borrow cap",
                "close factor",
            )
        ):
            return "collateral_liquidation_corpus"
        if any(token in lowered for token in ("oracle", "price feed", "chainlink", "latestrounddata", "stale price", "twap")):
            return "oracle_review_corpus"
        if any(token in lowered for token in ("batch payout", "batch payment", "airdrop", "distribution", "loop payout", "multi-send")):
            return "loop_payout_corpus"
        if any(token in lowered for token in ("assembly", "yul", "sstore")):
            return "assembly_review_corpus"
        if any(token in lowered for token in ("token", "erc20", "transferfrom", "transfer from")):
            return "token_interaction_corpus"
        if any(token in lowered for token in ("timestamp", "entropy", "random", "lottery", "blockhash", "prevrandao")):
            return "time_entropy_corpus"
        if any(token in lowered for token in ("upgrade", "implementation", "proxy", "beacon")):
            return "upgrade_surface_corpus"
        if any(token in lowered for token in ("delegatecall", "tx.origin", "selfdestruct", "dangerous call")):
            return "dangerous_call_corpus"
        if any(token in lowered for token in ("owner", "admin", "access control", "privilege", "initializer")):
            return "access_control_corpus"
        if "reentrancy" in lowered:
            return "reentrancy_review_corpus"
        return None

    if prefer_repo_casebooks:
        if any(
            token in lowered
            for token in (
                "amm",
                "swap",
                "liquidity pool",
                "liquidity",
                "lp token",
                "lp fee",
                "pair",
                "twap",
                "price impact",
                "virtual reserve",
                "constant product",
                "x*y=k",
                "xyk",
            )
        ):
            return "repo_amm_liquidity_casebook"
        if any(
            token in lowered
            for token in (
                "bridge",
                "custody",
                "message relay",
                "relayer",
                "validator set",
                "finalize withdrawal",
                "deposit proof",
                "withdraw proof",
                "message proof",
                "bridge escrow",
                "bridge portal",
                "replay protection",
                "cross-chain",
                "cross chain",
            )
        ):
            return "repo_bridge_custody_casebook"
        if any(
            token in lowered
            for token in (
                "staking",
                "stake",
                "unstake",
                "withdrawal queue",
                "rebase",
                "validator reward",
                "validator rewards",
                "epoch",
                "slash",
                "restake",
                "rebasing",
            )
        ):
            return "repo_staking_rebase_casebook"
        if any(
            token in lowered
            for token in (
                "keeper",
                "auction",
                "settle auction",
                "auction house",
                "auction settlement",
                "keeper reward",
                "bid",
                "close factor",
            )
        ):
            return "repo_keeper_auction_casebook"
        if any(
            token in lowered
            for token in (
                "treasury release",
                "vesting",
                "cliff",
                "beneficiary release",
                "vesting schedule",
                "sweep treasury",
                "release vested",
                "treasury timelock",
            )
        ):
            return "repo_treasury_vesting_casebook"
        if any(
            token in lowered
            for token in (
                "recovery",
                "deficit absorption",
                "bad debt socialization",
                "socialized debt",
                "absorb deficit",
                "insurance fund",
                "reserve recovery",
                "emergency settlement",
                "recovery manager",
            )
        ):
            return "repo_insurance_recovery_casebook"
        if any(
            token in lowered
            for token in (
                "governance",
                "timelock",
                "proposal",
                "queue upgrade",
                "queue proposal",
                "execute proposal",
                "execute upgrade",
                "guardian",
                "emergency brake",
            )
        ):
            return "repo_governance_timelock_casebook"
        if any(
            token in lowered
            for token in (
                "reward index",
                "rewardindex",
                "reward debt",
                "rewarddebt",
                "reward emission",
                "emission rate",
                "notify reward",
                "reward distribution",
                "reward claim",
                "reward-claim",
                "claim reward",
                "claim rewards",
                "claimable rewards",
                "checkpoint reward",
                "accumulator",
            )
        ):
            return "repo_rewards_distribution_casebook"
        if any(
            token in lowered
            for token in (
                "stablecoin",
                "peg",
                "debt ceiling",
                "debtceiling",
                "redeem stablecoin",
                "mint against collateral",
                "mint-against-collateral",
                "overcollateralized",
                "redemption buffer",
                "collateral redemption",
            )
        ):
            return "repo_stablecoin_collateral_casebook"
        if any(
            token in lowered
            for token in (
                "protocol fee",
                "protocolfee",
                "skim",
                "reserve accounting",
                "reserve sync",
                "reserve factor",
                "reservefactor",
                "reserve buffer",
                "reservebuffer",
                "insurance fund",
                "insurancefund",
                "debt accounting",
                "bad debt",
                "baddebt",
                "bad debt socialization",
                "socialized debt",
                "socialize",
                "write off",
                "writeoff",
                "absorb debt",
                "deficit",
                "interest accrual",
                "accrual",
            )
        ):
            return "repo_protocol_accounting_casebook"
        if any(
            token in lowered
            for token in (
                "oracle",
                "price feed",
                "price oracle",
                "chainlink",
                "twap",
                "liquidation",
                "liquidation fee",
                "liquidation bonus",
                "collateral",
                "stale price",
            )
        ):
            return "repo_oracle_casebook"
        if any(
            token in lowered
            for token in (
                "upgrade",
                "implementation",
                "proxy",
                "beacon",
                "eip1967",
                "uups",
                "storage layout",
                "storage slot",
                "delegatecall",
            )
        ):
            return "repo_upgrade_casebook"
        if any(
            token in lowered
            for token in (
                "asset flow",
                "fund flow",
                "deposit",
                "withdraw",
                "claim",
                "sweep",
                "rescue",
                "treasury flow",
                "vault",
                "erc4626",
                "share accounting",
                "price per share",
                "converttoassets",
                "converttoshares",
            )
        ):
            return "repo_vault_permission_casebook"
    matched_by_text = _match_by_text()
    if matched_by_text:
        return matched_by_text
    if preferred:
        for name in (
            "repo_keeper_auction_casebook",
            "repo_treasury_vesting_casebook",
            "repo_insurance_recovery_casebook",
            "repo_amm_liquidity_casebook",
            "repo_bridge_custody_casebook",
            "repo_staking_rebase_casebook",
            "repo_governance_timelock_casebook",
            "repo_rewards_distribution_casebook",
            "repo_stablecoin_collateral_casebook",
            "repo_upgrade_casebook",
            "repo_asset_flow_casebook",
            "repo_oracle_casebook",
            "repo_protocol_accounting_casebook",
            "repo_vault_permission_casebook",
            "reserve_fee_accounting_corpus",
            "signature_review_corpus",
            "collateral_liquidation_corpus",
            "oracle_review_corpus",
            "loop_payout_corpus",
            "proxy_storage_corpus",
            "vault_share_corpus",
            "asset_flow_corpus",
            "authorization_flow_corpus",
            "upgrade_validation_corpus",
            "approval_review_corpus",
            "accounting_review_corpus",
            "state_machine_corpus",
            "upgrade_surface_corpus",
            "time_entropy_corpus",
            "token_interaction_corpus",
            "assembly_review_corpus",
            "dangerous_call_corpus",
            "access_control_corpus",
            "reentrancy_review_corpus",
        ):
            if name in preferred:
                return name
    return None


def _smart_contract_should_include_echidna(*, text: str, contract_code: str) -> bool:
    lowered = text.lower()
    if any(
        token in lowered
        for token in (
            "echidna",
            "property",
            "properties",
            "assertion",
            "assertions",
            "invariant",
            "invariants",
            "fuzz",
            "fuzzing",
            "counterexample",
            "harness",
        )
    ):
        return True
    if not contract_code.strip():
        return False
    outline = build_contract_outline(contract_code=contract_code, language="solidity")
    return bool(detect_echidna_property_functions(outline) or has_assertion_surface(outline))


def build_tool_payload(
    *,
    config: AppConfig,
    tool_plan: ToolPlan,
    experiment_spec: ExperimentSpec,
    seed_text: str,
    formalization: str,
    hypothesis_summary: str,
    planned_test: str,
    research_target: ResearchTarget | None = None,
) -> dict[str, object]:
    source_seed_text = (
        research_target.target_reference
        if research_target is not None and research_target.target_origin == "synthetic"
        else seed_text
    )
    source_curve_name = research_target.curve_name if research_target is not None else None
    common = {
        "seed_text": source_seed_text,
        "formalization": formalization,
        "hypothesis_summary": hypothesis_summary,
        "planned_test": planned_test,
    }
    if tool_plan.tool_name == "ecc_curve_parameter_tool":
        curve_name = extract_curve_name(
            f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        )
        return {
            "curve_name": source_curve_name or curve_name or experiment_spec.target_reference,
        }
    if tool_plan.tool_name == "curve_metadata_tool":
        return {
            "curve_name": experiment_spec.target_reference,
        }
    if tool_plan.tool_name in {
        "contract_inventory_tool",
        "contract_compile_tool",
        "echidna_audit_tool",
        "foundry_audit_tool",
        "slither_audit_tool",
        "contract_parser_tool",
        "contract_surface_tool",
        "contract_pattern_check_tool",
    }:
        contract_code = extract_contract_code(source_seed_text)
        if contract_code is None:
            contract_code = extract_contract_code(
                f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
            )
        if tool_plan.tool_name == "contract_inventory_tool":
            source_label = extract_contract_source_label(source_seed_text)
            contract_root = extract_contract_root(source_seed_text)
            if contract_root is None and source_label:
                source_path = Path(source_label)
                contract_root = str(source_path.parent if source_path.suffix else source_path)
            return {
                "root_path": contract_root or experiment_spec.target_reference,
                "max_files": 64,
            }
        return {
            "contract_code": contract_code or source_seed_text,
            "language": extract_contract_language(source_seed_text) or "solidity",
            "source_label": extract_contract_source_label(source_seed_text) or experiment_spec.target_reference,
        }
    if tool_plan.tool_name == "contract_testbed_tool":
        return {
            "testbed_name": experiment_spec.target_reference,
            "case_limit": 8,
        }
    if tool_plan.tool_name == "point_descriptor_tool":
        x_value, y_value = extract_point_coordinates(source_seed_text)
        payload: dict[str, object] = {}
        if x_value and y_value:
            payload.update({"x": x_value, "y": y_value})
        else:
            payload["point_text"] = source_seed_text
        return payload
    if tool_plan.tool_name == "ecc_point_format_tool":
        public_key_hex = extract_public_key_hex(
            f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        )
        curve_name = extract_curve_name(
            f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        )
        if public_key_hex:
            return {"public_key_hex": public_key_hex, "curve_name": source_curve_name or curve_name}
        x_value, y_value = extract_point_coordinates(
            f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        )
        if x_value and y_value:
            return {"x": x_value, "y": y_value, "curve_name": source_curve_name or curve_name}
        return {"point_text": source_seed_text, "curve_name": source_curve_name or curve_name}
    if tool_plan.tool_name == "ecc_consistency_check_tool":
        combined = f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        public_key_hex = extract_public_key_hex(combined)
        curve_name = extract_curve_name(combined)
        if public_key_hex:
            return {
                "public_key_hex": public_key_hex,
                "curve_name": source_curve_name or curve_name,
                "check_on_curve": "on-curve" in combined.lower(),
            }
        x_value, y_value = extract_point_coordinates(combined)
        if x_value and y_value:
            return {
                "x": x_value,
                "y": y_value,
                "curve_name": source_curve_name or curve_name,
                "check_on_curve": True if (source_curve_name or curve_name) else False,
            }
        return {
            "point_text": source_seed_text,
            "curve_name": source_curve_name or curve_name,
            "check_on_curve": False,
        }
    if tool_plan.tool_name == "symbolic_check_tool":
        return {
            "expression": experiment_spec.target_reference,
        }
    if tool_plan.tool_name == "property_invariant_tool":
        left_expression, right_expression = extract_expression_pair(
            f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        )
        return {
            "left_expression": left_expression or "x + 1",
            "right_expression": right_expression or "1 + x",
            "domain_min": -8,
            "domain_max": 8,
            "max_examples": config.local_research.property_max_examples,
        }
    if tool_plan.tool_name == "formal_constraint_tool":
        left_expression, right_expression = extract_expression_pair(
            f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        )
        return {
            "left_expression": left_expression or "x + 1",
            "right_expression": right_expression or "1 + x",
            "domain_min": -8,
            "domain_max": 8,
        }
    if tool_plan.tool_name == "sage_symbolic_tool":
        return {
            "expression": experiment_spec.target_reference,
        }
    if tool_plan.tool_name == "finite_field_check_tool":
        modulus, left, right = extract_modular_payload(
            f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        ) or (7, 10, 3)
        return {
            "modulus": modulus,
            "left": left,
            "right": right,
            "operation": "equivalent_mod",
        }
    if tool_plan.tool_name == "fuzz_mutation_tool":
        public_key_hex = extract_public_key_hex(
            f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        )
        curve_name = extract_curve_name(
            f"{source_seed_text} {formalization} {hypothesis_summary} {planned_test}"
        )
        if public_key_hex:
            return {
                "target_kind": "point_hex",
                "seed_input": public_key_hex,
                "curve_name": source_curve_name or curve_name,
                "mutations": config.local_research.fuzz_max_mutations,
            }
        return {
            "target_kind": "curve_name",
            "seed_input": (source_curve_name or curve_name or experiment_spec.target_reference),
            "mutations": config.local_research.fuzz_max_mutations,
        }
    if tool_plan.tool_name == "ecc_testbed_tool":
        return {
            "testbed_name": experiment_spec.target_reference,
            "case_limit": 8,
        }
    if tool_plan.tool_name == "deterministic_experiment_tool":
        return {
            "experiment_type": "normalize_text",
            "value": f"{source_seed_text} {planned_test}".strip(),
            "repeats": experiment_spec.repeat_count,
        }
    return common
