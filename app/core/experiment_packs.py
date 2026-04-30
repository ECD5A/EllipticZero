from __future__ import annotations

from pathlib import Path

from app.core.seed_parsing import (
    extract_contract_language,
    extract_contract_root,
    extract_contract_source_label,
)
from app.models.experiment_pack import (
    ExperimentPack,
    ExperimentPackRecommendation,
    ExperimentPackStep,
)
from app.models.planning import ExperimentType
from app.models.sandbox import ResearchTarget


def _step(
    *,
    step_id: str,
    title: str,
    description: str,
    preferred_tool: str,
    experiment_type: ExperimentType,
    target_kinds: list[str],
    deterministic_expected: bool = True,
    requires_coordinate_payload: bool = False,
    requires_contract_root: bool = False,
    supported_contract_languages: list[str] | None = None,
    target_reference_override: str | None = None,
    notes: list[str] | None = None,
) -> ExperimentPackStep:
    return ExperimentPackStep(
        step_id=step_id,
        title=title,
        description=description,
        preferred_tool=preferred_tool,
        experiment_type=experiment_type,
        deterministic_expected=deterministic_expected,
        requires_coordinate_payload=requires_coordinate_payload,
        requires_contract_root=requires_contract_root,
        target_kinds=target_kinds,
        supported_contract_languages=list(supported_contract_languages or []),
        target_reference_override=target_reference_override,
        notes=list(notes or []),
    )


class ExperimentPackRegistry:
    """Registry for built-in reusable bounded research workflow packs."""

    def __init__(self) -> None:
        self._packs: dict[str, ExperimentPack] = {
            pack.pack_name: pack for pack in self._built_in_packs()
        }

    def list_packs(self) -> list[ExperimentPack]:
        return [self._packs[name] for name in sorted(self._packs)]

    def names(self) -> list[str]:
        return sorted(self._packs)

    def resolve(self, pack_name: str) -> ExperimentPack | None:
        return self._packs.get(pack_name.strip())

    def require(self, pack_name: str) -> ExperimentPack:
        pack = self.resolve(pack_name)
        if pack is None:
            raise ValueError(f"Unknown experiment pack: {pack_name}")
        return pack

    def recommend(
        self,
        *,
        seed_text: str,
        research_target: ResearchTarget | None,
    ) -> list[ExperimentPackRecommendation]:
        lowered = seed_text.lower()
        target_kind = research_target.target_kind if research_target is not None else "generic"
        contract_root_available = self._contract_root_available(seed_text)
        recommendations: list[ExperimentPackRecommendation] = []

        if target_kind == "curve":
            recommendations.append(
                ExperimentPackRecommendation(
                    pack_name="curve_metadata_audit_pack",
                    reason="The current seed and normalized target focus on named-curve metadata or domain parameters.",
                    confidence_hint="high",
                    notes=["Useful for alias, family, parameter, and registry cross-checks."],
                )
            )
            if any(
                token in lowered
                for token in (
                    "family",
                    "montgomery",
                    "edwards",
                    "25519 family",
                    "curve family",
                    "family transition",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="ecc_family_depth_benchmark_pack",
                        reason="The current seed highlights family-specific handling or curve-family transitions that fit a bounded ECC family-depth benchmark pass.",
                        confidence_hint="high",
                        notes=["Best for short-Weierstrass vs Montgomery/Edwards transition review."],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "domain completeness",
                    "registry completeness",
                    "metadata completeness",
                    "generator",
                    "order",
                    "cofactor",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="ecc_domain_completeness_benchmark_pack",
                        reason="The current seed highlights curve-domain completeness or registry-coverage questions that fit a bounded ECC domain-completeness benchmark pass.",
                        confidence_hint="high",
                        notes=["Best for generator, order, cofactor, and family-limited metadata review."],
                    )
                )
        if target_kind in {"point", "ecc_consistency"}:
            recommendations.append(
                ExperimentPackRecommendation(
                    pack_name="point_format_inspection_pack",
                    reason="The current seed and normalized target focus on point/public-key format or bounded consistency checks.",
                    confidence_hint="high",
                    notes=["Combines descriptive point classification with bounded format validation."],
                )
            )
            if any(
                token in lowered
                for token in (
                    "subgroup",
                    "cofactor",
                    "torsion",
                    "twist",
                    "small subgroup",
                    "cofactor clearing",
                    "25519",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="ecc_subgroup_hygiene_benchmark_pack",
                        reason="The current seed highlights subgroup, cofactor, or twist-sensitive ECC handling that fits a bounded hygiene benchmark pass.",
                        confidence_hint="high",
                        notes=["Best for 25519-family subgroup, cofactor, and twist review lanes."],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "family transition",
                    "montgomery",
                    "edwards",
                    "short-weierstrass",
                    "short weierstrass",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="ecc_family_depth_benchmark_pack",
                        reason="The current seed highlights family-specific ECC handling transitions that fit a bounded family-depth benchmark pass.",
                        confidence_hint="high",
                        notes=["Useful when 25519-family or mixed-family assumptions drive the review."],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "domain completeness",
                    "registry completeness",
                    "metadata completeness",
                    "generator",
                    "order",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="ecc_domain_completeness_benchmark_pack",
                        reason="The current seed mixes point-oriented review with family-limited domain-metadata questions that fit a bounded ECC domain benchmark pass.",
                        confidence_hint="medium",
                        notes=["Useful when point validation depends on family-specific registry completeness."],
                    )
                )
        elif target_kind == "curve" and any(
            token in lowered
            for token in (
                "subgroup",
                "cofactor",
                "torsion",
                "twist",
                "small subgroup",
                "cofactor clearing",
                "25519",
            )
        ):
            recommendations.append(
                ExperimentPackRecommendation(
                    pack_name="ecc_subgroup_hygiene_benchmark_pack",
                    reason="The current seed highlights subgroup, cofactor, or twist-sensitive curve-family handling that fits a bounded hygiene benchmark pass.",
                    confidence_hint="high",
                    notes=["Best for family-level subgroup and twist assumptions even when the target is a named curve."],
                )
            )
        if target_kind == "symbolic":
            recommendations.append(
                ExperimentPackRecommendation(
                    pack_name="symbolic_consistency_pack",
                    reason="The current seed and normalized target focus on symbolic simplification or expression consistency.",
                    confidence_hint="high",
                    notes=["Useful for comparing deterministic symbolic normalization paths."],
                )
            )
        if target_kind in {"finite_field", "experiment"}:
            recommendations.append(
                ExperimentPackRecommendation(
                    pack_name="finite_field_consistency_pack",
                    reason="The current seed and normalized target focus on modular or repeatable local math checks.",
                    confidence_hint="high",
                    notes=["Combines modular consistency with repeatability-oriented local probing."],
                )
            )
        if any(
            token in lowered
            for token in (
                "compare",
                "comparison",
                "sweep",
                "cross-check",
                "cross check",
                "multiple tools",
            )
        ):
            recommendations.append(
                ExperimentPackRecommendation(
                    pack_name="comparative_tool_sweep_pack",
                    reason="The seed explicitly asks for comparative or multi-tool inspection.",
                    confidence_hint="high" if target_kind != "generic" else "medium",
                    notes=["Designed to gather multiple bounded local signals for the same target."],
                )
            )

        if target_kind == "smart_contract":
            recommendations.append(
                ExperimentPackRecommendation(
                    pack_name="contract_static_benchmark_pack",
                    reason="The current seed resolves to a scoped smart-contract audit target and fits a repeatable static benchmark baseline.",
                    confidence_hint="high",
                    notes=[
                        "Useful for parser, compile, surface, pattern, and external static cross-check coverage.",
                    ],
                )
            )
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
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="keeper_auction_benchmark_pack",
                        reason="The current seed highlights keeper, auction, bid, or liquidation-settlement lanes that fit a bounded keeper/auction benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for keeper reward, auction settlement, oracle freshness, and liquidation-settlement review lanes.",
                        ],
                    )
                )
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
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="treasury_vesting_benchmark_pack",
                        reason="The current seed highlights treasury, vesting, release, or schedule-control lanes that fit a bounded treasury/vesting benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for treasury sweep, release ordering, timelock authority, and vesting schedule review lanes.",
                        ],
                    )
                )
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
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="insurance_recovery_benchmark_pack",
                        reason="The current seed highlights insurance, deficit, recovery, or emergency-settlement lanes that fit a bounded insurance/recovery benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for insurance-fund depletion, deficit absorption, reserve recovery, and emergency-settlement review lanes.",
                        ],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "governance",
                    "timelock",
                    "proposal",
                    "queue upgrade",
                    "execute upgrade",
                    "guardian",
                    "emergency brake",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="governance_timelock_benchmark_pack",
                        reason="The current seed highlights governance, timelock, guardian, or queued upgrade execution lanes that fit a bounded governance/timelock benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for governance-controlled upgrade, guardian pause, timelock delay, and execution review lanes.",
                        ],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "reward index",
                    "reward debt",
                    "reward emission",
                    "emission rate",
                    "notify reward",
                    "reward distribution",
                    "reward claim",
                    "reward-claim",
                    "claim reward",
                    "claim rewards",
                    "rewards controller",
                    "checkpoint reward",
                    "accumulator",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="reward_distribution_benchmark_pack",
                        reason="The current seed highlights reward-index, emission, claim, or distribution-accounting lanes that fit a bounded rewards benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for reward-index, reward-debt, emission, claim, and reserve-backed distribution review lanes.",
                        ],
                    )
                )
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
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="amm_liquidity_benchmark_pack",
                        reason="The current seed highlights AMM, liquidity, router, reserve, or fee-accounting lanes that fit a bounded AMM/liquidity benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for swap pricing, reserve updates, LP accounting, fee growth, and oracle-sync review lanes.",
                        ],
                    )
                )
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
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="bridge_custody_benchmark_pack",
                        reason="The current seed highlights bridge, custody, relay, proof, or replay-protection lanes that fit a bounded bridge/custody benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for custody release, relay validation, withdrawal finalization, and replay-protection review lanes.",
                        ],
                    )
                )
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
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="staking_rebase_benchmark_pack",
                        reason="The current seed highlights staking, rebase, validator-reward, queue, or slash lanes that fit a bounded staking/rebase benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for rebase accounting, queued withdrawals, slash handling, validator reward accrual, and share-update review lanes.",
                        ],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "stablecoin",
                    "peg",
                    "debt ceiling",
                    "redemption buffer",
                    "redeem stablecoin",
                    "mint against collateral",
                    "mint-against-collateral",
                    "overcollateralized",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="stablecoin_collateral_benchmark_pack",
                        reason="The current seed highlights stablecoin mint, collateral, redemption, or peg-protection lanes that fit a bounded stablecoin benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for stablecoin minting, redemption, collateral, liquidation, reserve, and peg-defence review lanes.",
                        ],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "proxy",
                    "upgrade",
                    "uups",
                    "eip1967",
                    "delegatecall",
                    "implementation",
                    "storage slot",
                    "storage collision",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="upgrade_control_benchmark_pack",
                        reason="The current seed centers on upgrade, proxy, delegatecall, or storage-control lanes that fit a bounded upgrade/control benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for upgrade authority, implementation, delegatecall, and storage-slot review lanes.",
                        ],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "vault",
                    "permit",
                    "signature",
                    "allowance",
                    "share accounting",
                    "erc4626",
                    "redeem",
                    "previewdeposit",
                    "converttoshares",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="vault_permission_benchmark_pack",
                        reason="The current seed highlights vault, permit, signature, or allowance lanes that fit a bounded vault/permission benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for vault share-accounting, permit, signature replay, and allowance review lanes.",
                        ],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "lending",
                    "borrow",
                    "repay",
                    "collateral",
                    "liquidation",
                    "health factor",
                    "ltv",
                    "reserve",
                    "debt",
                    "protocol fee",
                    "insurance fund",
                    "bad debt",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="lending_protocol_benchmark_pack",
                        reason="The current seed maps to lending-style collateral, reserve, debt, or liquidation lanes that fit a bounded protocol benchmark pack.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Best for collateral, liquidation, reserve, protocol-fee, and debt-accounting review lanes.",
                        ],
                    )
                )
            if contract_root_available or any(
                token in lowered
                for token in (
                    "repo",
                    "repository",
                    "codebase",
                    "multi-file",
                    "multi file",
                    "scoped root",
                    "entrypoint lane",
                    "import graph",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="repo_casebook_benchmark_pack",
                        reason="The current seed appears repository-scoped and fits a bounded inventory plus repo-casebook benchmark pass.",
                        confidence_hint="high",
                        notes=[
                            "Useful for inventory, review-lane, static, and repo-casebook coverage.",
                        ],
                    )
                )
            if any(
                token in lowered
                for token in (
                    "vault",
                    "permit",
                    "signature",
                    "allowance",
                    "oracle",
                    "collateral",
                    "liquidation",
                    "protocol fee",
                    "reserve",
                    "debt",
                    "defi",
                    "erc4626",
                    "share accounting",
                    "amm",
                    "swap",
                    "liquidity",
                    "bridge",
                    "custody",
                    "staking",
                    "rebase",
                    "keeper",
                    "auction",
                    "treasury",
                    "vesting",
                    "insurance",
                    "recovery",
                )
            ):
                recommendations.append(
                    ExperimentPackRecommendation(
                        pack_name="protocol_casebook_benchmark_pack",
                        reason="The current seed highlights protocol-style smart-contract lanes that fit a deeper bounded casebook benchmark pass.",
                        confidence_hint="high" if contract_root_available else "medium",
                        notes=[
                            "Useful for vault, signature, oracle, collateral, reserve, and debt-family review lanes.",
                        ],
                    )
                )

        ordered: list[ExperimentPackRecommendation] = []
        seen: set[str] = set()
        confidence_rank = {"high": 0, "medium": 1, "low": 2}
        for item in sorted(
            recommendations,
            key=lambda recommendation: (
                confidence_rank[recommendation.confidence_hint],
                recommendation.pack_name,
            ),
        ):
            if item.pack_name in seen:
                continue
            seen.add(item.pack_name)
            ordered.append(item)
        return ordered

    def steps_for_execution(
        self,
        *,
        pack: ExperimentPack,
        research_target: ResearchTarget | None,
        seed_text: str | None = None,
        available_tools: list[str],
        advanced_math_enabled: bool,
        sage_enabled: bool,
    ) -> list[ExperimentPackStep]:
        target_kind = research_target.target_kind if research_target is not None else "generic"
        available = set(available_tools)
        contract_language = self._detect_contract_language(
            seed_text=seed_text,
            research_target=research_target,
        )
        has_contract_root = self._contract_root_available(seed_text)
        steps: list[ExperimentPackStep] = []

        for step in pack.steps:
            if step.target_kinds and target_kind not in step.target_kinds:
                continue
            if step.requires_coordinate_payload and not self._looks_coordinate_payload(research_target):
                continue
            if step.requires_contract_root and not has_contract_root:
                continue
            if (
                step.supported_contract_languages
                and contract_language is not None
                and contract_language not in step.supported_contract_languages
            ):
                continue
            if step.preferred_tool not in available:
                continue
            if step.preferred_tool == "sage_symbolic_tool" and not (advanced_math_enabled and sage_enabled):
                continue
            steps.append(step)
        return steps

    def _looks_coordinate_payload(self, research_target: ResearchTarget | None) -> bool:
        if research_target is None:
            return False
        lowered = research_target.target_reference.lower()
        return "x=" in lowered and "y=" in lowered

    def _detect_contract_language(
        self,
        *,
        seed_text: str | None,
        research_target: ResearchTarget | None,
    ) -> str | None:
        if seed_text:
            language = extract_contract_language(seed_text)
            if language:
                return language.strip().lower()
        if research_target is not None:
            language = extract_contract_language(research_target.target_reference)
            if language:
                return language.strip().lower()
        return None

    def _contract_root_available(self, seed_text: str | None) -> bool:
        if not seed_text:
            return False
        contract_root = extract_contract_root(seed_text)
        if contract_root:
            return True
        source_label = extract_contract_source_label(seed_text)
        if not source_label or source_label == "<inline>":
            return False
        source_path = Path(source_label)
        return bool(source_path.suffix)

    def _built_in_packs(self) -> list[ExperimentPack]:
        return [
            ExperimentPack(
                pack_name="curve_metadata_audit_pack",
                version="1.0",
                description="Inspect curve/domain metadata, aliases, parameter presence, and registry consistency.",
                target_kinds=["curve"],
                supported_tools=["ecc_curve_parameter_tool", "curve_metadata_tool"],
                default_experiment_types=[
                    ExperimentType.ECC_CURVE_PARAMETER_CHECK,
                    ExperimentType.CURVE_METADATA_MATH_CHECK,
                ],
                steps=[
                    _step(
                        step_id="domain_parameters",
                        title="Normalize domain parameters",
                        description="Normalize bounded ECC domain metadata, aliases, generator, order, and cofactor fields.",
                        preferred_tool="ecc_curve_parameter_tool",
                        experiment_type=ExperimentType.ECC_CURVE_PARAMETER_CHECK,
                        target_kinds=["curve"],
                    ),
                    _step(
                        step_id="registry_crosscheck",
                        title="Cross-check registry metadata",
                        description="Cross-check canonical curve metadata against the local registry entry.",
                        preferred_tool="curve_metadata_tool",
                        experiment_type=ExperimentType.CURVE_METADATA_MATH_CHECK,
                        target_kinds=["curve"],
                    ),
                ],
                notes=["Free-form input remains primary; this pack only structures bounded local checks."],
            ),
            ExperimentPack(
                pack_name="point_format_inspection_pack",
                version="1.0",
                description="Classify point/public-key-like payloads and run bounded ECC format consistency checks.",
                target_kinds=["point", "ecc_consistency"],
                supported_tools=["point_descriptor_tool", "ecc_point_format_tool", "ecc_consistency_check_tool"],
                default_experiment_types=[
                    ExperimentType.POINT_STRUCTURE_CHECK,
                    ExperimentType.ECC_POINT_FORMAT_CHECK,
                    ExperimentType.ECC_CONSISTENCY_CHECK,
                ],
                steps=[
                    _step(
                        step_id="coordinate_shape_probe",
                        title="Describe coordinate payload shape",
                        description="Describe coordinate lengths and shape when the point-like input is expressed as x/y coordinates.",
                        preferred_tool="point_descriptor_tool",
                        experiment_type=ExperimentType.POINT_STRUCTURE_CHECK,
                        target_kinds=["point", "ecc_consistency"],
                        requires_coordinate_payload=True,
                        notes=["Runs only for coordinate-style point targets."],
                    ),
                    _step(
                        step_id="format_descriptor",
                        title="Describe point format",
                        description="Classify compressed, uncompressed, coordinate, or malformed point-like payloads.",
                        preferred_tool="ecc_point_format_tool",
                        experiment_type=ExperimentType.ECC_POINT_FORMAT_CHECK,
                        target_kinds=["point", "ecc_consistency"],
                    ),
                    _step(
                        step_id="bounded_consistency",
                        title="Run bounded consistency checks",
                        description="Run safe bounded ECC format and optional on-curve consistency checks when supported.",
                        preferred_tool="ecc_consistency_check_tool",
                        experiment_type=ExperimentType.ECC_CONSISTENCY_CHECK,
                        target_kinds=["point", "ecc_consistency"],
                    ),
                ],
                notes=["Suitable for public-key parsing, coordinate-shape checks, and format anomalies."],
            ),
            ExperimentPack(
                pack_name="symbolic_consistency_pack",
                version="1.0",
                description="Compare deterministic symbolic normalization with the advanced Sage-compatible symbolic path when configured.",
                target_kinds=["symbolic"],
                supported_tools=["sage_symbolic_tool", "symbolic_check_tool"],
                default_experiment_types=[ExperimentType.SYMBOLIC_SIMPLIFICATION],
                steps=[
                    _step(
                        step_id="advanced_symbolic_path",
                        title="Attempt advanced symbolic path",
                        description="Attempt the bounded advanced symbolic normalization path when advanced math is configured.",
                        preferred_tool="sage_symbolic_tool",
                        experiment_type=ExperimentType.SYMBOLIC_SIMPLIFICATION,
                        target_kinds=["symbolic"],
                        notes=["Skipped automatically when advanced math or Sage integration is disabled."],
                    ),
                    _step(
                        step_id="deterministic_symbolic_crosscheck",
                        title="Run deterministic symbolic cross-check",
                        description="Run the deterministic symbolic normalization path for a bounded local comparison signal.",
                        preferred_tool="symbolic_check_tool",
                        experiment_type=ExperimentType.SYMBOLIC_SIMPLIFICATION,
                        target_kinds=["symbolic"],
                    ),
                ],
                notes=["Preserves graceful Sage fallback behavior."],
            ),
            ExperimentPack(
                pack_name="finite_field_consistency_pack",
                version="1.0",
                description="Run deterministic modular and repeatability-oriented checks for bounded finite-field style research.",
                target_kinds=["finite_field", "experiment"],
                supported_tools=["finite_field_check_tool", "deterministic_experiment_tool"],
                default_experiment_types=[
                    ExperimentType.FINITE_FIELD_CHECK,
                    ExperimentType.DETERMINISTIC_REPEAT_CHECK,
                ],
                steps=[
                    _step(
                        step_id="modular_consistency",
                        title="Run modular consistency check",
                        description="Perform a bounded modular or finite-field consistency check.",
                        preferred_tool="finite_field_check_tool",
                        experiment_type=ExperimentType.FINITE_FIELD_CHECK,
                        target_kinds=["finite_field", "experiment"],
                    ),
                    _step(
                        step_id="repeatability_probe",
                        title="Run deterministic repeatability probe",
                        description="Run a repeatability-oriented deterministic check to confirm stability of the local observation.",
                        preferred_tool="deterministic_experiment_tool",
                        experiment_type=ExperimentType.DETERMINISTIC_REPEAT_CHECK,
                        target_kinds=["finite_field", "experiment"],
                    ),
                ],
                notes=["Keeps all local arithmetic probes bounded and deterministic."],
            ),
            ExperimentPack(
                pack_name="comparative_tool_sweep_pack",
                version="1.0",
                description="Run several relevant bounded local tools against the same target to support cautious comparative reporting.",
                target_kinds=["curve", "point", "ecc_consistency", "symbolic", "finite_field"],
                supported_tools=[
                    "ecc_curve_parameter_tool",
                    "curve_metadata_tool",
                    "point_descriptor_tool",
                    "ecc_point_format_tool",
                    "ecc_consistency_check_tool",
                    "sage_symbolic_tool",
                    "symbolic_check_tool",
                    "finite_field_check_tool",
                ],
                default_experiment_types=[
                    ExperimentType.ECC_CURVE_PARAMETER_CHECK,
                    ExperimentType.CURVE_METADATA_MATH_CHECK,
                    ExperimentType.POINT_STRUCTURE_CHECK,
                    ExperimentType.ECC_POINT_FORMAT_CHECK,
                    ExperimentType.ECC_CONSISTENCY_CHECK,
                    ExperimentType.SYMBOLIC_SIMPLIFICATION,
                    ExperimentType.FINITE_FIELD_CHECK,
                ],
                steps=[
                    _step(
                        step_id="curve_parameters",
                        title="Normalize curve parameters",
                        description="Gather curve/domain parameter evidence for comparative reporting.",
                        preferred_tool="ecc_curve_parameter_tool",
                        experiment_type=ExperimentType.ECC_CURVE_PARAMETER_CHECK,
                        target_kinds=["curve"],
                    ),
                    _step(
                        step_id="curve_registry_crosscheck",
                        title="Cross-check curve registry entry",
                        description="Cross-check local curve registry metadata for comparative reporting.",
                        preferred_tool="curve_metadata_tool",
                        experiment_type=ExperimentType.CURVE_METADATA_MATH_CHECK,
                        target_kinds=["curve"],
                    ),
                    _step(
                        step_id="point_descriptor",
                        title="Describe coordinate payload shape",
                        description="Capture a descriptive coordinate-shape signal when the target is an x/y payload.",
                        preferred_tool="point_descriptor_tool",
                        experiment_type=ExperimentType.POINT_STRUCTURE_CHECK,
                        target_kinds=["point", "ecc_consistency"],
                        requires_coordinate_payload=True,
                        notes=["Runs only for coordinate-style targets."],
                    ),
                    _step(
                        step_id="point_format_descriptor",
                        title="Describe point/public-key format",
                        description="Capture a descriptive point/public-key classification signal.",
                        preferred_tool="ecc_point_format_tool",
                        experiment_type=ExperimentType.ECC_POINT_FORMAT_CHECK,
                        target_kinds=["point", "ecc_consistency"],
                    ),
                    _step(
                        step_id="point_consistency",
                        title="Run bounded point consistency checks",
                        description="Capture bounded ECC consistency signals for comparative reporting.",
                        preferred_tool="ecc_consistency_check_tool",
                        experiment_type=ExperimentType.ECC_CONSISTENCY_CHECK,
                        target_kinds=["point", "ecc_consistency"],
                    ),
                    _step(
                        step_id="advanced_symbolic",
                        title="Attempt advanced symbolic normalization",
                        description="Capture an advanced symbolic normalization signal when configured.",
                        preferred_tool="sage_symbolic_tool",
                        experiment_type=ExperimentType.SYMBOLIC_SIMPLIFICATION,
                        target_kinds=["symbolic"],
                    ),
                    _step(
                        step_id="deterministic_symbolic",
                        title="Run deterministic symbolic normalization",
                        description="Capture a deterministic symbolic normalization signal for comparison.",
                        preferred_tool="symbolic_check_tool",
                        experiment_type=ExperimentType.SYMBOLIC_SIMPLIFICATION,
                        target_kinds=["symbolic"],
                    ),
                    _step(
                        step_id="finite_field_probe",
                        title="Run finite-field consistency probe",
                        description="Capture a bounded modular consistency signal for comparative reporting.",
                        preferred_tool="finite_field_check_tool",
                        experiment_type=ExperimentType.FINITE_FIELD_CHECK,
                        target_kinds=["finite_field"],
                    ),
                ],
                notes=["Use this pack when the goal is to compare multiple bounded signals for one target."],
            ),
            ExperimentPack(
                pack_name="ecc_family_depth_benchmark_pack",
                version="1.0",
                description="Run a bounded ECC benchmark pass focused on family transitions, family-limited encodings, and cross-family handling assumptions.",
                target_kinds=["curve", "point", "ecc_consistency"],
                supported_tools=["ecc_curve_parameter_tool", "ecc_testbed_tool", "ecc_point_format_tool"],
                default_experiment_types=[
                    ExperimentType.ECC_CURVE_PARAMETER_CHECK,
                    ExperimentType.ECC_TESTBED_SWEEP,
                    ExperimentType.ECC_POINT_FORMAT_CHECK,
                ],
                steps=[
                    _step(
                        step_id="family_domain_parameters",
                        title="Normalize family-aware domain parameters",
                        description="Normalize bounded curve metadata before comparing short-Weierstrass and 25519-family assumptions.",
                        preferred_tool="ecc_curve_parameter_tool",
                        experiment_type=ExperimentType.ECC_CURVE_PARAMETER_CHECK,
                        target_kinds=["curve"],
                    ),
                    _step(
                        step_id="family_transition_benchmark",
                        title="Run family-transition benchmark",
                        description="Run the bounded ECC family-transition corpus to compare short-Weierstrass, Montgomery, and Edwards handling assumptions.",
                        preferred_tool="ecc_testbed_tool",
                        experiment_type=ExperimentType.ECC_TESTBED_SWEEP,
                        target_kinds=["curve", "point", "ecc_consistency"],
                        target_reference_override="family_transition_corpus",
                    ),
                    _step(
                        step_id="encoding_edge_benchmark",
                        title="Cross-check family-limited encodings",
                        description="Run bounded encoding-edge cases to confirm that family-limited point or key forms stay separated before deeper ECC conclusions.",
                        preferred_tool="ecc_testbed_tool",
                        experiment_type=ExperimentType.ECC_TESTBED_SWEEP,
                        target_kinds=["curve", "point", "ecc_consistency"],
                        target_reference_override="encoding_edge_corpus",
                    ),
                ],
                notes=["Best for mixed-family ECC review where short-Weierstrass assumptions must not bleed into 25519-family handling."],
            ),
            ExperimentPack(
                pack_name="ecc_subgroup_hygiene_benchmark_pack",
                version="1.0",
                description="Run a bounded ECC benchmark pass focused on subgroup, cofactor, torsion, and twist-sensitive family hygiene.",
                target_kinds=["curve", "point", "ecc_consistency"],
                supported_tools=["ecc_point_format_tool", "ecc_consistency_check_tool", "ecc_testbed_tool"],
                default_experiment_types=[
                    ExperimentType.ECC_POINT_FORMAT_CHECK,
                    ExperimentType.ECC_CONSISTENCY_CHECK,
                    ExperimentType.ECC_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="point_format_descriptor",
                        title="Describe point or key format",
                        description="Capture bounded point/public-key shape before subgroup- or cofactor-sensitive review.",
                        preferred_tool="ecc_point_format_tool",
                        experiment_type=ExperimentType.ECC_POINT_FORMAT_CHECK,
                        target_kinds=["point", "ecc_consistency"],
                    ),
                    _step(
                        step_id="bounded_consistency",
                        title="Run bounded ECC consistency checks",
                        description="Run safe bounded consistency checks before interpreting subgroup, cofactor, or twist-sensitive signals.",
                        preferred_tool="ecc_consistency_check_tool",
                        experiment_type=ExperimentType.ECC_CONSISTENCY_CHECK,
                        target_kinds=["point", "ecc_consistency"],
                    ),
                    _step(
                        step_id="subgroup_hygiene_benchmark",
                        title="Run subgroup and cofactor benchmark",
                        description="Run the bounded subgroup/cofactor corpus to compare family-level subgroup and cofactor assumptions.",
                        preferred_tool="ecc_testbed_tool",
                        experiment_type=ExperimentType.ECC_TESTBED_SWEEP,
                        target_kinds=["curve", "point", "ecc_consistency"],
                        target_reference_override="subgroup_cofactor_corpus",
                    ),
                    _step(
                        step_id="twist_hygiene_benchmark",
                        title="Run twist-hygiene benchmark",
                        description="Run the bounded twist-hygiene corpus to keep 25519-family twist assumptions separate from short-Weierstrass checks.",
                        preferred_tool="ecc_testbed_tool",
                        experiment_type=ExperimentType.ECC_TESTBED_SWEEP,
                        target_kinds=["curve", "point", "ecc_consistency"],
                        target_reference_override="twist_hygiene_corpus",
                    ),
                ],
                notes=["Best for subgroup, cofactor, torsion, and twist-sensitive ECC review."],
            ),
            ExperimentPack(
                pack_name="ecc_domain_completeness_benchmark_pack",
                version="1.0",
                description="Run a bounded ECC benchmark pass focused on registry completeness, domain fields, generator/order exposure, and family-limited metadata gaps.",
                target_kinds=["curve", "point", "ecc_consistency"],
                supported_tools=["ecc_curve_parameter_tool", "curve_metadata_tool", "ecc_testbed_tool"],
                default_experiment_types=[
                    ExperimentType.ECC_CURVE_PARAMETER_CHECK,
                    ExperimentType.CURVE_METADATA_MATH_CHECK,
                    ExperimentType.ECC_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="curve_parameters",
                        title="Normalize curve-domain parameters",
                        description="Gather bounded generator, order, cofactor, and alias metadata before deeper completeness review.",
                        preferred_tool="ecc_curve_parameter_tool",
                        experiment_type=ExperimentType.ECC_CURVE_PARAMETER_CHECK,
                        target_kinds=["curve"],
                    ),
                    _step(
                        step_id="registry_crosscheck",
                        title="Cross-check registry metadata",
                        description="Cross-check canonical curve metadata against the local registry before narrowing completeness claims.",
                        preferred_tool="curve_metadata_tool",
                        experiment_type=ExperimentType.CURVE_METADATA_MATH_CHECK,
                        target_kinds=["curve"],
                    ),
                    _step(
                        step_id="domain_completeness_benchmark",
                        title="Run domain-completeness benchmark",
                        description="Run the bounded domain-completeness corpus to compare generator, order, cofactor, and family-limited metadata exposure.",
                        preferred_tool="ecc_testbed_tool",
                        experiment_type=ExperimentType.ECC_TESTBED_SWEEP,
                        target_kinds=["curve", "point", "ecc_consistency"],
                        target_reference_override="domain_completeness_corpus",
                    ),
                    _step(
                        step_id="family_transition_crosscheck",
                        title="Run family-transition cross-check",
                        description="Run the bounded family-transition corpus to confirm that completeness claims stay within the correct ECC family.",
                        preferred_tool="ecc_testbed_tool",
                        experiment_type=ExperimentType.ECC_TESTBED_SWEEP,
                        target_kinds=["curve", "point", "ecc_consistency"],
                        target_reference_override="family_transition_corpus",
                    ),
                ],
                notes=["Best for registry-completeness and domain-metadata review where family transitions still matter."],
            ),
            ExperimentPack(
                pack_name="contract_static_benchmark_pack",
                version="1.0",
                description="Run a bounded static smart-contract benchmark pass across parse, compile, surface, and static-review layers.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_parser_tool",
                    "contract_compile_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_PARSE,
                    ExperimentType.SMART_CONTRACT_COMPILE_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                ],
                steps=[
                    _step(
                        step_id="parse_outline",
                        title="Parse contract outline",
                        description="Build a bounded structural contract outline before stronger smart-contract review claims.",
                        preferred_tool="contract_parser_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PARSE,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="compile_baseline",
                        title="Compile baseline",
                        description="Run the bounded compiler path to confirm parser-visible structure against compiler-visible structure.",
                        preferred_tool="contract_compile_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_COMPILE_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="surface_mapping",
                        title="Map reachable surface",
                        description="Map externally reachable, privileged, and stateful surfaces before static prioritization.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="pattern_review",
                        title="Run bounded pattern review",
                        description="Run built-in bounded static pattern review to capture primary issue families and local priorities.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="external_static_crosscheck",
                        title="Cross-check with external static analyzer",
                        description="Cross-check the bounded static pass with the supported external smart-contract analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                ],
                notes=[
                    "This pack stays single-contract friendly and does not require repo inventory.",
                    "Suitable as a repeatable baseline before repo-scale casebook work.",
                ],
            ),
            ExperimentPack(
                pack_name="repo_casebook_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass across inventory, review lanes, static signals, and matched repo casebooks.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="inventory_scope",
                        title="Build bounded contract inventory",
                        description="Build a bounded contract inventory with candidate files, shared dependencies, and entrypoint lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="repo_surface_map",
                        title="Map repo review surface",
                        description="Map externally reachable and stateful review surfaces before repo-casebook comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="repo_pattern_review",
                        title="Run repo static review",
                        description="Run bounded pattern review to connect issue families with repo review lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="repo_external_static_crosscheck",
                        title="Cross-check repo static posture",
                        description="Cross-check repo review lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="repo_casebook_match",
                        title="Run matched repo casebook",
                        description="Run the bounded repo-casebook layer to compare the scoped repository against matched benchmark lanes.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                    ),
                ],
                notes=[
                    "Best fit for multi-file Solidity repos or scoped contract roots.",
                    "Keeps repo-casebook matching bounded and replayable.",
                ],
            ),
            ExperimentPack(
                pack_name="protocol_casebook_benchmark_pack",
                version="1.0",
                description="Run a bounded protocol-style benchmark pass for vault, signature, oracle, collateral, reserve, and debt review lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="protocol_inventory_scope",
                        title="Build protocol inventory",
                        description="Build a bounded inventory before tracing protocol-style authority, asset, oracle, collateral, or reserve lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="protocol_surface_map",
                        title="Map protocol review surface",
                        description="Map protocol entrypoints, shared hubs, and stateful review surfaces before deeper benchmark comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="protocol_pattern_review",
                        title="Run protocol pattern review",
                        description="Run bounded static review across protocol-style issue families and function families.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="protocol_external_static_crosscheck",
                        title="Cross-check protocol static posture",
                        description="Cross-check protocol-style lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="protocol_casebook_match",
                        title="Run protocol casebook benchmark",
                        description="Run the bounded protocol repo-casebook layer to compare scoped protocol lanes against anchored benchmark cases.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                    ),
                ],
                notes=[
                    "Best fit for repo-scale protocol audits with vault, pricing, reserve, debt, and permission families.",
                ],
            ),
            ExperimentPack(
                pack_name="upgrade_control_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on upgrade authority, proxy, delegatecall, and storage-lane control paths.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="upgrade_inventory_scope",
                        title="Build upgrade inventory",
                        description="Build a bounded inventory before tracing proxy, delegatecall, and storage-slot control paths.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="upgrade_surface_map",
                        title="Map upgrade control surface",
                        description="Map externally reachable upgrade, privileged, and delegatecall-adjacent surfaces before deeper proxy review.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="upgrade_pattern_review",
                        title="Run upgrade pattern review",
                        description="Run bounded static review across proxy, upgrade, storage-slot, and privileged-control lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="upgrade_external_static_crosscheck",
                        title="Cross-check upgrade posture",
                        description="Cross-check upgrade-control lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="upgrade_casebook_match",
                        title="Run upgrade control casebook",
                        description="Run the bounded upgrade-control repo casebook to compare the scoped repository against anchored proxy and storage cases.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_upgrade_casebook",
                    ),
                ],
                notes=[
                    "Best fit for proxy, delegatecall, storage, upgrade authorization, and implementation review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="vault_permission_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on vault-share, permit, signature, and allowance lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="vault_inventory_scope",
                        title="Build vault and permission inventory",
                        description="Build a bounded inventory before tracing vault, permit, and allowance-style entrypoints.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="vault_surface_map",
                        title="Map vault and permission surface",
                        description="Map vault-share, signature, and token-allowance surfaces before deeper casebook comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="vault_pattern_review",
                        title="Run vault and permission pattern review",
                        description="Run bounded static review across vault accounting, permit replay, and allowance lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="vault_external_static_crosscheck",
                        title="Cross-check vault and permission posture",
                        description="Cross-check vault and permission lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="vault_casebook_match",
                        title="Run vault and permission casebook",
                        description="Run the bounded vault-permission repo casebook to compare the scoped repository against anchored permit, allowance, and share-accounting cases.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_vault_permission_casebook",
                    ),
                ],
                notes=[
                    "Best fit for ERC4626-style vaults, permit flows, allowance handling, and share-accounting review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="lending_protocol_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on lending-style collateral, liquidation, reserve, and debt-accounting lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="lending_inventory_scope",
                        title="Build lending protocol inventory",
                        description="Build a bounded inventory before tracing collateral, liquidation, reserve, and debt-accounting lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="lending_surface_map",
                        title="Map lending protocol surface",
                        description="Map pricing, collateral, reserve, liquidation, and debt-entry surfaces before deeper benchmark comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="lending_pattern_review",
                        title="Run lending protocol pattern review",
                        description="Run bounded static review across oracle, collateral, liquidation, reserve, fee, and debt-accounting lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="lending_external_static_crosscheck",
                        title="Cross-check lending protocol posture",
                        description="Cross-check lending protocol lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="lending_casebook_match",
                        title="Run lending protocol casebook",
                        description="Run the bounded lending-style repo casebook to compare the scoped repository against anchored collateral, reserve, fee, and debt scenarios.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_protocol_accounting_casebook",
                    ),
                ],
                notes=[
                    "Best fit for lending, collateralized debt, liquidation, reserve, insurance, and fee-accounting review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="governance_timelock_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on governance, timelock, guardian, and queued upgrade execution lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="governance_inventory_scope",
                        title="Build governance and timelock inventory",
                        description="Build a bounded inventory before tracing governance, timelock, guardian, and queued execution lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="governance_surface_map",
                        title="Map governance and timelock surface",
                        description="Map governance execution, guardian pause, upgrade, and storage-adjacent surfaces before deeper archetype comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="governance_pattern_review",
                        title="Run governance and timelock pattern review",
                        description="Run bounded static review across governance-controlled upgrade, pause, proxy, and execution lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="governance_external_static_crosscheck",
                        title="Cross-check governance and timelock posture",
                        description="Cross-check governance and timelock lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="governance_casebook_match",
                        title="Run governance and timelock casebook",
                        description="Run the bounded governance-timelock repo casebook to compare the scoped repository against anchored queued-upgrade and guardian-control cases.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_governance_timelock_casebook",
                    ),
                ],
                notes=[
                    "Best fit for governance-controlled upgrade execution, timelock delay, guardian pause, and queued proposal review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="reward_distribution_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on reward-index, emission, claim, and reserve-backed distribution lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="reward_inventory_scope",
                        title="Build reward distribution inventory",
                        description="Build a bounded inventory before tracing reward-index, claim, emission, and reserve-backed distribution lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="reward_surface_map",
                        title="Map reward distribution surface",
                        description="Map reward-index, share-accounting, claim, and reserve-distribution surfaces before deeper archetype comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="reward_pattern_review",
                        title="Run reward distribution pattern review",
                        description="Run bounded static review across claim ordering, reward debt, emission control, and reserve sweep lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="reward_external_static_crosscheck",
                        title="Cross-check reward distribution posture",
                        description="Cross-check reward distribution lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="reward_casebook_match",
                        title="Run reward distribution casebook",
                        description="Run the bounded rewards-distribution repo casebook to compare the scoped repository against anchored reward-index and reserve-backed claim cases.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_rewards_distribution_casebook",
                    ),
                ],
                notes=[
                    "Best fit for reward-index drift, reward-debt tracking, emissions, reserve-backed distribution, and claim-order review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="stablecoin_collateral_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on stablecoin mint, redemption, collateral, liquidation, and peg-defence lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="stablecoin_inventory_scope",
                        title="Build stablecoin and collateral inventory",
                        description="Build a bounded inventory before tracing stablecoin mint, redemption, collateral, reserve, and liquidation lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="stablecoin_surface_map",
                        title="Map stablecoin and collateral surface",
                        description="Map oracle, mint, redemption, collateral, reserve, and liquidation surfaces before deeper archetype comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="stablecoin_pattern_review",
                        title="Run stablecoin and collateral pattern review",
                        description="Run bounded static review across oracle freshness, collateral validation, redemption-buffer, reserve, and liquidation lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="stablecoin_external_static_crosscheck",
                        title="Cross-check stablecoin and collateral posture",
                        description="Cross-check stablecoin and collateral lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="stablecoin_casebook_match",
                        title="Run stablecoin and collateral casebook",
                        description="Run the bounded stablecoin-collateral repo casebook to compare the scoped repository against anchored mint, redemption, and liquidation scenarios.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_stablecoin_collateral_casebook",
                    ),
                ],
                notes=[
                    "Best fit for stablecoin minting, redemption, peg-defence, collateral, reserve, and liquidation review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="amm_liquidity_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on AMM swap, liquidity, reserve, fee-growth, and oracle-sync lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="amm_inventory_scope",
                        title="Build AMM and liquidity inventory",
                        description="Build a bounded inventory before tracing swap routing, liquidity, reserve, fee-growth, and oracle-sync lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="amm_surface_map",
                        title="Map AMM and liquidity surface",
                        description="Map swap, router, LP accounting, reserve, fee, and oracle-sync surfaces before deeper archetype comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="amm_pattern_review",
                        title="Run AMM and liquidity pattern review",
                        description="Run bounded static review across swap ordering, reserve updates, fee growth, LP burn, and oracle-dependent liquidity lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="amm_external_static_crosscheck",
                        title="Cross-check AMM and liquidity posture",
                        description="Cross-check AMM and liquidity lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="amm_casebook_match",
                        title="Run AMM and liquidity casebook",
                        description="Run the bounded AMM-liquidity repo casebook to compare the scoped repository against anchored swap, LP, reserve, and oracle-sync scenarios.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_amm_liquidity_casebook",
                    ),
                ],
                notes=[
                    "Best fit for swap routing, LP accounting, reserve updates, fee growth, price impact, and oracle-sync review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="bridge_custody_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on bridge custody, relay validation, proof, and replay-protection lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="bridge_inventory_scope",
                        title="Build bridge and custody inventory",
                        description="Build a bounded inventory before tracing relay, proof, custody, validator, and withdrawal-finalization lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="bridge_surface_map",
                        title="Map bridge and custody surface",
                        description="Map bridge portal, custody release, relay validation, replay-protection, and rescue surfaces before deeper archetype comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="bridge_pattern_review",
                        title="Run bridge and custody pattern review",
                        description="Run bounded static review across message proof, replay-protection, custody release, and relay authority lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="bridge_external_static_crosscheck",
                        title="Cross-check bridge and custody posture",
                        description="Cross-check bridge and custody lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="bridge_casebook_match",
                        title="Run bridge and custody casebook",
                        description="Run the bounded bridge-custody repo casebook to compare the scoped repository against anchored relay, proof, replay, and custody scenarios.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_bridge_custody_casebook",
                    ),
                ],
                notes=[
                    "Best fit for bridge relays, proof validation, withdrawal finalization, replay protection, and custody release review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="staking_rebase_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on staking, rebase, validator reward, slash, and withdrawal-queue lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="staking_inventory_scope",
                        title="Build staking and rebase inventory",
                        description="Build a bounded inventory before tracing stake, unstake, rebase, slash, validator reward, and withdrawal-queue lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="staking_surface_map",
                        title="Map staking and rebase surface",
                        description="Map staking, unstake queue, rebase, slash, validator reward, and share-update surfaces before deeper archetype comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="staking_pattern_review",
                        title="Run staking and rebase pattern review",
                        description="Run bounded static review across rebase accounting, queued withdrawals, slash handling, and validator reward lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="staking_external_static_crosscheck",
                        title="Cross-check staking and rebase posture",
                        description="Cross-check staking and rebase lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="staking_casebook_match",
                        title="Run staking and rebase casebook",
                        description="Run the bounded staking-rebase repo casebook to compare the scoped repository against anchored rebase, queue, slash, and validator-reward scenarios.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_staking_rebase_casebook",
                    ),
                ],
                notes=[
                    "Best fit for stake/rebase accounting, withdrawal queues, slash flows, and validator reward review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="keeper_auction_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on keeper incentives, auction settlement, liquidation, and oracle-freshness lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="keeper_inventory_scope",
                        title="Build keeper and auction inventory",
                        description="Build a bounded inventory before tracing keeper reward, auction settlement, oracle, and liquidation lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="keeper_surface_map",
                        title="Map keeper and auction surface",
                        description="Map keeper reward, auction house, bid settlement, oracle, and liquidation surfaces before deeper archetype comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="keeper_pattern_review",
                        title="Run keeper and auction pattern review",
                        description="Run bounded static review across liquidation settlement, keeper rewards, reserve buffers, and oracle freshness lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="keeper_external_static_crosscheck",
                        title="Cross-check keeper and auction posture",
                        description="Cross-check keeper and auction lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="keeper_casebook_match",
                        title="Run keeper and auction casebook",
                        description="Run the bounded keeper-auction repo casebook to compare the scoped repository against anchored keeper, auction, oracle, and settlement scenarios.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_keeper_auction_casebook",
                    ),
                ],
                notes=[
                    "Best fit for keeper incentives, auction settlement, oracle freshness, and liquidation review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="treasury_vesting_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on treasury release, vesting schedule, sweep, and timelock-control lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="treasury_inventory_scope",
                        title="Build treasury and vesting inventory",
                        description="Build a bounded inventory before tracing treasury sweep, beneficiary release, vesting schedule, and timelock authority lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="treasury_surface_map",
                        title="Map treasury and vesting surface",
                        description="Map treasury release, sweep, vesting schedule, and timelock-authority surfaces before deeper archetype comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="treasury_pattern_review",
                        title="Run treasury and vesting pattern review",
                        description="Run bounded static review across release ordering, vesting schedule mutation, beneficiary payout, and sweep-control lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="treasury_external_static_crosscheck",
                        title="Cross-check treasury and vesting posture",
                        description="Cross-check treasury and vesting lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="treasury_casebook_match",
                        title="Run treasury and vesting casebook",
                        description="Run the bounded treasury-vesting repo casebook to compare the scoped repository against anchored treasury release, sweep, and schedule-control scenarios.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_treasury_vesting_casebook",
                    ),
                ],
                notes=[
                    "Best fit for treasury release, vesting, beneficiary payout, and timelock-controlled sweep review lanes.",
                ],
            ),
            ExperimentPack(
                pack_name="insurance_recovery_benchmark_pack",
                version="1.0",
                description="Run a bounded repo-scale benchmark pass focused on insurance-fund depletion, deficit absorption, reserve recovery, and emergency-settlement lanes.",
                target_kinds=["smart_contract"],
                supported_tools=[
                    "contract_inventory_tool",
                    "contract_surface_tool",
                    "contract_pattern_check_tool",
                    "slither_audit_tool",
                    "contract_testbed_tool",
                ],
                default_experiment_types=[
                    ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                    ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                    ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                    ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                    ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                ],
                steps=[
                    _step(
                        step_id="insurance_inventory_scope",
                        title="Build insurance and recovery inventory",
                        description="Build a bounded inventory before tracing insurance-fund, deficit, recovery, reserve-buffer, and settlement lanes.",
                        preferred_tool="contract_inventory_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_INVENTORY_CHECK,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                    ),
                    _step(
                        step_id="insurance_surface_map",
                        title="Map insurance and recovery surface",
                        description="Map insurance-fund depletion, deficit absorption, reserve recovery, and settlement surfaces before deeper archetype comparison.",
                        preferred_tool="contract_surface_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_SURFACE_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="insurance_pattern_review",
                        title="Run insurance and recovery pattern review",
                        description="Run bounded static review across reserve depletion, deficit socialization, recovery paths, and emergency-settlement lanes.",
                        preferred_tool="contract_pattern_check_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_PATTERN_CHECK,
                        target_kinds=["smart_contract"],
                    ),
                    _step(
                        step_id="insurance_external_static_crosscheck",
                        title="Cross-check insurance and recovery posture",
                        description="Cross-check insurance and recovery lanes against the supported external static analyzer path.",
                        preferred_tool="slither_audit_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_STATIC_ANALYZER_CHECK,
                        target_kinds=["smart_contract"],
                        supported_contract_languages=["solidity"],
                    ),
                    _step(
                        step_id="insurance_casebook_match",
                        title="Run insurance and recovery casebook",
                        description="Run the bounded insurance-recovery repo casebook to compare the scoped repository against anchored deficit, reserve, and emergency-settlement scenarios.",
                        preferred_tool="contract_testbed_tool",
                        experiment_type=ExperimentType.SMART_CONTRACT_TESTBED_SWEEP,
                        target_kinds=["smart_contract"],
                        requires_contract_root=True,
                        supported_contract_languages=["solidity"],
                        target_reference_override="repo_insurance_recovery_casebook",
                    ),
                ],
                notes=[
                    "Best fit for insurance-fund depletion, deficit absorption, reserve recovery, and emergency-settlement review lanes.",
                ],
            ),
        ]
