from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.agents import (
    CriticAgent,
    CryptographyAgent,
    HypothesisAgent,
    MathAgent,
    ReportAgent,
    StrategyAgent,
)
from app.cli import InteractiveConsole, should_launch_interactive
from app.cli.i18n import localize_error, normalize_language, t
from app.cli.text_rendering import (
    render_doctor_report,
    render_evaluation_summary,
    render_experiment_packs,
    render_live_smoke_result,
    render_replay_result,
    render_report,
    render_routing_summary,
    render_run_evaluation_summary,
    render_synthetic_targets,
)
from app.compute.executor import ComputeExecutor
from app.compute.runners import (
    ContractCompileRunner,
    ContractTestbedRunner,
    ECCTestbedRunner,
    EchidnaRunner,
    FormalRunner,
    FoundryRunner,
    FuzzRunner,
    PropertyRunner,
    SageRunner,
    SlitherRunner,
    SympyRunner,
)
from app.config import AppConfig
from app.core.doctor import SystemDoctor
from app.core.experiment_packs import ExperimentPackRegistry
from app.core.golden_cases import (
    GoldenCaseError,
    list_golden_cases,
    prepare_golden_case_run,
    render_golden_cases,
)
from app.core.orchestrator import ResearchOrchestrator
from app.core.provider_privacy import (
    build_provider_context_preview,
    render_provider_context_preview,
)
from app.core.replay_loader import ReplayLoader
from app.core.replay_planner import ReplayPlanner
from app.core.report_markdown import (
    render_report_markdown_export_result,
    write_report_markdown_file,
)
from app.core.research_targets import ResearchTargetRegistry
from app.core.sandbox_executor import SandboxExecutor
from app.core.sarif_export import render_sarif_export_result, write_sarif_file
from app.core.seed_parsing import build_smart_contract_seed
from app.llm.gateway import LLMGateway
from app.llm.live_smoke import resolve_live_smoke_model
from app.llm.providers import HOSTED_PROVIDER_NAMES, SUPPORTED_PROVIDER_NAMES
from app.logger import configure_logging
from app.models.replay_request import ReplayRequest
from app.models.sandbox import ResearchMode
from app.plugins.loader import PluginLoader
from app.storage.math_artifacts import MathArtifactStore
from app.storage.reproducibility_bundle import ReproducibilityBundleStore
from app.storage.session_store import SessionStore
from app.storage.trace_writer import TraceWriter
from app.tools.builtin import (
    ContractCompileTool,
    ContractInventoryTool,
    ContractParserTool,
    ContractPatternCheckTool,
    ContractSurfaceTool,
    ContractTestbedTool,
    CurveMetadataTool,
    DeterministicExperimentTool,
    ECCConsistencyCheckTool,
    ECCCurveParameterTool,
    ECCPointFormatTool,
    ECCTestbedTool,
    EchidnaAuditTool,
    FiniteFieldCheckTool,
    FormalConstraintTool,
    FoundryAuditTool,
    FuzzMutationTool,
    PlaceholderMathTool,
    PointDescriptorTool,
    PropertyInvariantTool,
    SageSymbolicTool,
    SlitherAuditTool,
    SymbolicCheckTool,
)
from app.tools.registry import ToolRegistry
from app.tools.smart_contract_utils import infer_contract_language


def build_orchestrator(config: AppConfig) -> ResearchOrchestrator:
    gateway = LLMGateway.from_config(config)
    sympy_runner = SympyRunner(enabled=config.local_research.sympy_enabled)
    sage_runner = SageRunner(
        enabled=config.advanced_math_enabled and config.sage.enabled,
        binary=config.sage.binary,
        timeout_seconds=config.sage.timeout_seconds,
    )
    property_runner = PropertyRunner(
        enabled=config.local_research.property_enabled,
        max_examples=config.local_research.property_max_examples,
    )
    contract_compile_runner = ContractCompileRunner(
        enabled=config.local_research.smart_contract_compile_enabled,
        managed_solc_dir=config.local_research.managed_solc_dir,
        managed_solc_version=config.local_research.managed_solc_version,
        solc_binary=config.local_research.solc_binary,
        solcjs_binary=config.local_research.solcjs_binary,
        timeout_seconds=config.local_research.smart_contract_compile_timeout_seconds,
    )
    slither_runner = SlitherRunner(
        enabled=config.local_research.slither_enabled,
        managed_solc_dir=config.local_research.managed_solc_dir,
        managed_solc_version=config.local_research.managed_solc_version,
        slither_binary=config.local_research.slither_binary,
        solc_binary=config.local_research.solc_binary,
        timeout_seconds=config.local_research.slither_timeout_seconds,
    )
    echidna_runner = EchidnaRunner(
        enabled=config.local_research.echidna_enabled,
        managed_solc_dir=config.local_research.managed_solc_dir,
        managed_solc_version=config.local_research.managed_solc_version,
        echidna_binary=config.local_research.echidna_binary,
        solc_binary=config.local_research.solc_binary,
        timeout_seconds=config.local_research.echidna_timeout_seconds,
        test_limit=config.local_research.echidna_test_limit,
        seq_len=config.local_research.echidna_seq_len,
    )
    foundry_runner = FoundryRunner(
        enabled=config.local_research.foundry_enabled,
        managed_solc_dir=config.local_research.managed_solc_dir,
        managed_solc_version=config.local_research.managed_solc_version,
        forge_binary=config.local_research.forge_binary,
        solc_binary=config.local_research.solc_binary,
        timeout_seconds=config.local_research.foundry_timeout_seconds,
    )
    formal_runner = FormalRunner(
        enabled=config.local_research.formal_enabled,
        backend=config.local_research.formal_backend,
        timeout_seconds=config.local_research.formal_timeout_seconds,
    )
    fuzz_runner = FuzzRunner(
        enabled=config.local_research.fuzz_enabled,
        max_mutations=config.local_research.fuzz_max_mutations,
        seed=config.local_research.fuzz_seed,
    )
    contract_testbed_runner = ContractTestbedRunner(
        enabled=config.local_research.smart_contract_testbeds_enabled
    )
    ecc_testbed_runner = ECCTestbedRunner(enabled=config.local_research.ecc_testbeds_enabled)
    registry = ToolRegistry()
    registry.register(ContractCompileTool(runner=contract_compile_runner))
    registry.register(ContractInventoryTool())
    registry.register(SlitherAuditTool(runner=slither_runner))
    registry.register(EchidnaAuditTool(runner=echidna_runner))
    registry.register(FoundryAuditTool(runner=foundry_runner))
    registry.register(ContractParserTool())
    registry.register(ContractSurfaceTool())
    registry.register(ContractPatternCheckTool())
    registry.register(ContractTestbedTool(runner=contract_testbed_runner))
    registry.register(CurveMetadataTool())
    registry.register(ECCCurveParameterTool())
    registry.register(ECCPointFormatTool())
    registry.register(ECCConsistencyCheckTool())
    registry.register(PointDescriptorTool())
    registry.register(SageSymbolicTool(runner=sage_runner))
    registry.register(SymbolicCheckTool(runner=sympy_runner))
    registry.register(PropertyInvariantTool(runner=property_runner))
    registry.register(FormalConstraintTool(runner=formal_runner))
    registry.register(FiniteFieldCheckTool())
    registry.register(FuzzMutationTool(runner=fuzz_runner))
    registry.register(ECCTestbedTool(runner=ecc_testbed_runner))
    registry.register(DeterministicExperimentTool())
    registry.register(PlaceholderMathTool())
    plugin_loader = PluginLoader(
        directory=config.plugins.directory,
        enabled=config.plugins.enabled,
        allow_local_plugins=config.plugins.allow_local_plugins,
    )
    plugin_metadata = plugin_loader.load_into_registry(registry)
    executor = ComputeExecutor(registry=registry)
    target_registry = ResearchTargetRegistry()
    experiment_pack_registry = ExperimentPackRegistry()

    return ResearchOrchestrator(
        config=config,
        math_agent=MathAgent(gateway=gateway),
        cryptography_agent=CryptographyAgent(gateway=gateway),
        strategy_agent=StrategyAgent(gateway=gateway),
        hypothesis_agent=HypothesisAgent(gateway=gateway),
        critic_agent=CriticAgent(gateway=gateway),
        report_agent=ReportAgent(gateway=gateway),
        executor=executor,
        sandbox_executor=SandboxExecutor(
            executor=executor,
            target_registry=target_registry,
            max_job_timeout_seconds=config.tool_timeout_seconds,
            property_max_examples=config.local_research.property_max_examples,
            fuzz_max_mutations=config.local_research.fuzz_max_mutations,
            formal_timeout_seconds=config.local_research.formal_timeout_seconds,
            max_testbed_cases=8,
        ),
        math_artifact_store=MathArtifactStore(config.storage.math_artifacts_dir),
        bundle_store=ReproducibilityBundleStore(config.storage.bundles_dir),
        session_store=SessionStore(config.storage.sessions_dir),
        trace_writer=TraceWriter(config.storage.traces_dir),
        target_registry=target_registry,
        experiment_pack_registry=experiment_pack_registry,
        plugin_metadata=plugin_metadata,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="EllipticZero Research Lab CLI for bounded smart-contract audits and defensive ECC research"
    )
    parser.add_argument("idea", nargs="?", help="Free-form research idea")
    parser.add_argument("--author", help="Optional author name")
    parser.add_argument(
        "--domain",
        choices=["smart_contract_audit", "ecc_research"],
        help="Select the bounded research domain for a new session.",
    )
    parser.add_argument(
        "--contract-file",
        help="Local Solidity/Vyper source file for SMART CONTRACT AUDIT runs.",
    )
    parser.add_argument(
        "--contract-code",
        help="Inline Solidity/Vyper source for SMART CONTRACT AUDIT runs.",
    )
    parser.add_argument(
        "--contract-language",
        choices=["solidity", "vyper"],
        help="Hint the contract language for SMART CONTRACT AUDIT runs.",
    )
    parser.add_argument(
        "--contract-root",
        help="Optional local repo or contract-root directory for SMART CONTRACT AUDIT inventory and scoping.",
    )
    parser.add_argument(
        "--provider",
        choices=SUPPORTED_PROVIDER_NAMES,
        help="Override the configured LLM provider",
    )
    parser.add_argument("--replay-session", help="Replay from a saved session.json file")
    parser.add_argument("--replay-manifest", help="Replay from a saved manifest.json file")
    parser.add_argument("--replay-bundle", help="Replay from a reproducibility bundle directory")
    parser.add_argument(
        "--compare-session",
        help="Compare a new run against a saved baseline session.json file.",
    )
    parser.add_argument(
        "--compare-manifest",
        help="Compare a new run against a saved baseline manifest.json file when the session snapshot is recoverable.",
    )
    parser.add_argument(
        "--compare-bundle",
        help="Compare a new run against a saved baseline reproducibility bundle when the session snapshot is recoverable.",
    )
    parser.add_argument(
        "--dry-run-replay",
        action="store_true",
        help="Inspect replayability without re-executing local tools",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Launch the interactive Research Noir console",
    )
    parser.add_argument(
        "--lang",
        choices=["en", "ru"],
        help="Override the configured interface language",
    )
    parser.add_argument(
        "--model",
        help="Override the shared default model used by all agent roles unless explicitly routed.",
    )
    parser.add_argument(
        "--doctor",
        action="store_true",
        help="Run a bounded system self-check instead of a research session",
    )
    parser.add_argument(
        "--show-routing",
        action="store_true",
        help="Show the effective shared/per-agent LLM routing plan and exit",
    )
    parser.add_argument(
        "--research-mode",
        choices=[mode.value for mode in ResearchMode],
        help="Select the bounded research execution mode for this run",
    )
    parser.add_argument(
        "--synthetic-target",
        help="Select a built-in safe synthetic research target for a new session",
    )
    parser.add_argument(
        "--list-synthetic-targets",
        action="store_true",
        help="List built-in safe synthetic research targets and exit",
    )
    parser.add_argument(
        "--pack",
        help="Select a built-in experiment pack for a new session",
    )
    parser.add_argument(
        "--list-packs",
        action="store_true",
        help="List built-in experiment packs and exit",
    )
    parser.add_argument(
        "--list-golden-cases",
        action="store_true",
        help="List safe built-in golden evaluator cases and exit",
    )
    parser.add_argument(
        "--evaluation-summary",
        action="store_true",
        help="Show a compact no-key evaluator summary and exit",
    )
    parser.add_argument(
        "--evaluation-summary-format",
        choices=["text", "json"],
        default="text",
        help="Output format for --evaluation-summary.",
    )
    parser.add_argument(
        "--provider-context-preview",
        action="store_true",
        help="Preview what prepared context could be sent to hosted providers for a direct run and exit.",
    )
    parser.add_argument(
        "--provider-context-preview-format",
        choices=["text", "json"],
        default="text",
        help="Output format for --provider-context-preview.",
    )
    parser.add_argument(
        "--export-sarif",
        help="Write SARIF 2.1.0 review output from one saved session, manifest, or bundle and exit.",
    )
    parser.add_argument(
        "--export-report-md",
        help="Write a Markdown report from one saved session, manifest, or bundle and exit.",
    )
    parser.add_argument(
        "--golden-case",
        help="Run a safe built-in golden evaluator case by case id",
    )
    parser.add_argument(
        "--live-provider-smoke",
        choices=HOSTED_PROVIDER_NAMES,
        help="Run a bounded live hosted-provider smoke test and exit.",
    )
    parser.add_argument(
        "--live-smoke-model",
        help="Explicit model name for the hosted-provider smoke test.",
    )
    llm_group = parser.add_argument_group(
        "advanced llm routing",
        "Optional per-agent overrides. Leave unset to keep the shared default provider/model for every role.",
    )
    for role_prefix, role_name in (
        ("math", "math_agent"),
        ("cryptography", "cryptography_agent"),
        ("strategy", "strategy_agent"),
        ("hypothesis", "hypothesis_agent"),
        ("critic", "critic_agent"),
        ("report", "report_agent"),
    ):
        llm_group.add_argument(
            f"--{role_prefix}-provider",
            dest=f"{role_name}_provider",
            choices=SUPPORTED_PROVIDER_NAMES,
            help=f"Override provider for {role_name}.",
        )
        llm_group.add_argument(
            f"--{role_prefix}-model",
            dest=f"{role_name}_model",
            help=f"Override model for {role_name}.",
        )
    return parser


def run_live_provider_smoke(
    *,
    config: AppConfig,
    provider_name: str,
    model_name: str | None,
    language: str,
) -> str:
    gateway = LLMGateway.from_config(config)
    provider = gateway.providers[provider_name]
    model = resolve_live_smoke_model(
        provider_name=provider_name,
        configured_default_model=config.llm.default_model,
        explicit_model=model_name,
    )
    timeout_seconds = min(config.llm.timeout_seconds, 30)
    max_request_tokens = min(config.llm.max_request_tokens, 512)
    output = provider.generate(
        model=model,
        timeout_seconds=timeout_seconds,
        max_request_tokens=max_request_tokens,
        system_prompt=(
            "You are a bounded hosted-provider smoke test for EllipticZero. "
            "Return one short line confirming the provider path is alive."
        ),
        user_prompt="Reply with one short line: LIVE SMOKE OK.",
        metadata={"agent": "live_smoke", "purpose": "hosted_provider_smoke"},
    )
    return render_live_smoke_result(
        language=language,
        provider=provider_name,
        model=model,
        timeout_seconds=timeout_seconds,
        max_request_tokens=max_request_tokens,
        output=output,
    )


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    config = AppConfig.load()
    if args.lang:
        config.ui_language = args.lang
    if args.provider:
        config.llm.default_provider = args.provider
    if args.model:
        config.llm.default_model = args.model
    if args.live_provider_smoke:
        config.llm.default_provider = args.live_provider_smoke
    if args.live_smoke_model:
        config.llm.default_model = args.live_smoke_model
    if args.research_mode:
        config.research.default_mode = ResearchMode(args.research_mode)
    for role_name in (
        "math_agent",
        "cryptography_agent",
        "strategy_agent",
        "hypothesis_agent",
        "critic_agent",
        "report_agent",
    ):
        provider_override = getattr(args, f"{role_name}_provider", None)
        model_override = getattr(args, f"{role_name}_model", None)
        if provider_override:
            getattr(config.agents, role_name).provider = provider_override
        if model_override:
            getattr(config.agents, role_name).model = model_override

    language = normalize_language(config.ui_language)
    replay_paths = {
        "session": args.replay_session,
        "manifest": args.replay_manifest,
        "bundle": args.replay_bundle,
    }
    selected_replay = [
        (source_type, source_path)
        for source_type, source_path in replay_paths.items()
        if source_path
    ]
    comparison_paths = {
        "session": args.compare_session,
        "manifest": args.compare_manifest,
        "bundle": args.compare_bundle,
    }
    selected_comparison = [
        (source_type, source_path)
        for source_type, source_path in comparison_paths.items()
        if source_path
    ]

    if args.show_routing:
        print(render_routing_summary(config, language=language))
        return 0

    if args.evaluation_summary:
        if (
            args.idea
            or args.interactive
            or selected_comparison
            or args.doctor
            or args.live_provider_smoke
            or args.golden_case
            or args.list_golden_cases
            or args.list_packs
            or args.list_synthetic_targets
            or args.synthetic_target
            or args.pack
            or args.contract_file
            or args.contract_code
            or args.contract_root
            or args.contract_language
            or args.export_sarif
            or args.export_report_md
            or args.provider_context_preview
        ):
            parser.exit(
                status=2,
                message="Evaluation summary is a direct no-key CLI path and cannot be combined with run, provider, contract, pack, comparison, or listing arguments.\n",
            )
        if len(selected_replay) > 1:
            parser.exit(status=2, message=t(language, "cli.error.choose_one_replay"))
        if selected_replay:
            source_type, source_path = selected_replay[0]
            request = ReplayRequest(
                source_type=source_type,
                source_path=source_path,
                dry_run=True,
                reexecute=False,
                preserve_original_seed=True,
            )
            try:
                loaded = ReplayLoader().load(request)
            except ValueError as exc:
                parser.exit(status=2, message=t(language, "cli.error.replay_rejected", error=str(exc)))
            print(
                render_run_evaluation_summary(
                    language=language,
                    loaded_source=loaded,
                    output_format=args.evaluation_summary_format,
                )
            )
            return 0
        print(
            render_evaluation_summary(
                language=language,
                golden_cases=list_golden_cases(),
                pack_names=ExperimentPackRegistry().names(),
                provider_names=SUPPORTED_PROVIDER_NAMES,
                output_format=args.evaluation_summary_format,
            )
        )
        return 0

    if args.provider_context_preview:
        if (
            args.interactive
            or selected_replay
            or selected_comparison
            or args.doctor
            or args.live_provider_smoke
            or args.list_golden_cases
            or args.list_packs
            or args.list_synthetic_targets
            or args.synthetic_target
            or args.export_sarif
            or args.export_report_md
        ):
            parser.exit(
                status=2,
                message="Provider context preview is a direct no-call path and cannot be combined with interactive, replay, comparison, doctor, live-smoke, listing, synthetic target, or export arguments.\n",
            )
        try:
            preview_seed, preview_pack = _prepare_preview_seed(args)
        except ValueError as exc:
            parser.exit(status=2, message=f"Provider context preview rejected: {exc}\n")
        preview = build_provider_context_preview(
            config=config,
            seed_text=preview_seed,
            selected_pack_name=preview_pack,
        )
        print(
            render_provider_context_preview(
                preview=preview,
                language=language,
                output_format=args.provider_context_preview_format,
            )
        )
        return 0

    if args.export_sarif or args.export_report_md:
        if (
            args.idea
            or args.interactive
            or selected_comparison
            or args.doctor
            or args.live_provider_smoke
            or args.golden_case
            or args.list_golden_cases
            or args.list_packs
            or args.list_synthetic_targets
            or args.synthetic_target
            or args.pack
            or args.contract_file
            or args.contract_code
            or args.contract_root
            or args.contract_language
        ):
            parser.exit(
                status=2,
                message="Saved-run export requires exactly one replay source and cannot be combined with run, provider, contract, pack, comparison, doctor, or listing arguments.\n",
            )
        if len(selected_replay) != 1:
            parser.exit(
                status=2,
                message="Saved-run export requires exactly one of --replay-session, --replay-manifest, or --replay-bundle.\n",
            )
        source_type, source_path = selected_replay[0]
        request = ReplayRequest(
            source_type=source_type,
            source_path=source_path,
            dry_run=True,
            reexecute=False,
            preserve_original_seed=True,
        )
        try:
            loaded = ReplayLoader().load(request)
            rendered_messages: list[str] = []
            if args.export_sarif:
                output_path, result_count = write_sarif_file(
                    loaded_source=loaded,
                    output_path=args.export_sarif,
                )
                rendered_messages.append(
                    render_sarif_export_result(
                        output_path=output_path,
                        result_count=result_count,
                        language=language,
                    )
                )
            if args.export_report_md:
                output_path = write_report_markdown_file(
                    loaded_source=loaded,
                    output_path=args.export_report_md,
                )
                rendered_messages.append(
                    render_report_markdown_export_result(
                        output_path=output_path,
                        language=language,
                    )
                )
        except ValueError as exc:
            parser.exit(status=2, message=t(language, "cli.error.replay_rejected", error=str(exc)))
        print("\n\n".join(rendered_messages))
        return 0

    if args.live_provider_smoke and args.interactive:
        parser.exit(status=2, message="Hosted smoke test is a direct CLI path and cannot be combined with --interactive.\n")
    if args.live_provider_smoke and selected_replay:
        parser.exit(status=2, message="Hosted smoke test cannot be combined with replay arguments.\n")
    if args.live_provider_smoke and args.idea:
        parser.exit(status=2, message="Hosted smoke test cannot be combined with a research idea.\n")
    if args.live_provider_smoke and args.doctor:
        parser.exit(status=2, message="Hosted smoke test cannot be combined with --doctor.\n")
    if args.live_provider_smoke and selected_comparison:
        parser.exit(status=2, message="Hosted smoke test cannot be combined with baseline comparison arguments.\n")
    if args.live_provider_smoke and (args.list_golden_cases or args.golden_case):
        parser.exit(status=2, message="Hosted smoke test cannot be combined with golden case arguments.\n")

    configure_logging(config.log_level)
    orchestrator = build_orchestrator(config)

    if args.list_golden_cases:
        print(render_golden_cases(language=language))
        return 0

    if args.list_packs:
        print(render_experiment_packs(orchestrator, language=language))
        return 0

    if args.list_synthetic_targets:
        print(render_synthetic_targets(orchestrator, language=language))
        return 0

    if len(selected_replay) > 1:
        parser.exit(status=2, message=t(language, "cli.error.choose_one_replay"))
    if len(selected_comparison) > 1:
        parser.exit(status=2, message="Comparison rejected: choose only one baseline comparison source.\n")
    if selected_replay and args.idea:
        parser.exit(status=2, message=t(language, "cli.error.replay_and_idea"))
    if selected_replay and selected_comparison:
        parser.exit(status=2, message="Replay rejected: do not combine replay and baseline comparison arguments.\n")
    if selected_replay and args.synthetic_target:
        parser.exit(status=2, message="Synthetic target selection is available only for new sessions.\n")
    if selected_replay and args.pack:
        parser.exit(status=2, message="Experiment pack selection is available only for new sessions.\n")
    if selected_replay and args.golden_case:
        parser.exit(status=2, message="Golden case selection is available only for new sessions.\n")
    if selected_replay and args.contract_file:
        parser.exit(status=2, message="Smart-contract source selection is available only for new sessions.\n")
    if selected_replay and args.contract_code:
        parser.exit(status=2, message="Smart-contract source selection is available only for new sessions.\n")
    if args.doctor and selected_replay:
        parser.exit(status=2, message=t(language, "cli.error.doctor_and_replay"))
    if args.doctor and args.idea:
        parser.exit(status=2, message=t(language, "cli.error.doctor_and_idea"))
    if args.doctor and args.interactive:
        parser.exit(status=2, message=t(language, "cli.error.doctor_and_interactive"))
    if args.doctor and args.synthetic_target:
        parser.exit(status=2, message="Synthetic target selection is not used with --doctor.\n")
    if args.doctor and args.pack:
        parser.exit(status=2, message="Experiment pack selection is not used with --doctor.\n")
    if args.doctor and args.golden_case:
        parser.exit(status=2, message="Golden case selection is not used with --doctor.\n")
    if args.doctor and args.contract_file:
        parser.exit(status=2, message="Smart-contract source selection is not used with --doctor.\n")
    if args.doctor and args.contract_code:
        parser.exit(status=2, message="Smart-contract source selection is not used with --doctor.\n")
    if args.doctor and selected_comparison:
        parser.exit(status=2, message="System check rejected: do not combine --doctor with baseline comparison arguments.\n")
    if args.doctor:
        doctor_report = SystemDoctor(
            config=config,
            orchestrator=orchestrator,
            language=language,
        ).run()
        print(render_doctor_report(doctor_report, language=language))
        return 0
    if args.live_provider_smoke:
        try:
            print(
                run_live_provider_smoke(
                    config=config,
                    provider_name=args.live_provider_smoke,
                    model_name=args.live_smoke_model,
                    language=language,
                )
            )
        except RuntimeError as exc:
            parser.exit(
                status=2,
                message=(
                    f"Hosted smoke test failed for provider '{args.live_provider_smoke}' "
                    f"with model '{args.live_smoke_model or config.llm.default_model}': {exc}\n"
                ),
            )
        return 0

    golden_run = None
    if args.golden_case:
        if args.idea:
            parser.exit(status=2, message="Golden case selection cannot be combined with a free-form research idea.\n")
        if args.domain:
            parser.exit(status=2, message="Golden case selection already defines the research domain.\n")
        if args.contract_file or args.contract_code or args.contract_root or args.contract_language:
            parser.exit(status=2, message="Golden case selection cannot be combined with smart-contract source arguments.\n")
        if args.synthetic_target:
            parser.exit(status=2, message="Golden case selection already defines any required synthetic target.\n")
        if args.pack:
            parser.exit(status=2, message="Golden case selection already defines the experiment pack.\n")
        if selected_comparison:
            parser.exit(status=2, message="Golden case selection cannot be combined with baseline comparison arguments.\n")
        if args.interactive:
            parser.exit(status=2, message="Golden case selection is a direct CLI path and cannot be combined with --interactive.\n")
        try:
            golden_run = prepare_golden_case_run(args.golden_case)
        except GoldenCaseError as exc:
            parser.exit(status=2, message=f"Golden case rejected: {exc}\n")

    if should_launch_interactive(
        interactive_flag=args.interactive,
        has_idea=bool(args.idea) or bool(selected_comparison) or bool(golden_run),
        has_replay_source=bool(selected_replay),
        stdin_isatty=sys.stdin.isatty(),
        stdout_isatty=sys.stdout.isatty(),
    ):
        if selected_comparison:
            parser.exit(status=2, message="Interactive mode does not yet accept baseline comparison arguments.\n")
        return InteractiveConsole(orchestrator, language=language).run()
    if selected_replay:
        source_type, source_path = selected_replay[0]
        request = ReplayRequest(
            source_type=source_type,
            source_path=source_path,
            dry_run=args.dry_run_replay,
            reexecute=not args.dry_run_replay,
            preserve_original_seed=True,
        )
        loader = ReplayLoader()
        planner = ReplayPlanner()
        try:
            loaded = loader.load(request)
            plan = planner.build_plan(
                loaded_source=loaded,
                available_tools=orchestrator.executor.registry.names(),
                preserve_original_seed=request.preserve_original_seed,
            )
            replay_result = planner.execute(
                request=request,
                plan=plan,
                orchestrator=orchestrator,
                author=args.author,
            )
        except ValueError as exc:
            parser.exit(status=2, message=t(language, "cli.error.replay_rejected", error=str(exc)))

        print(render_replay_result(replay_result, language=language))
        return 0

    comparison_baseline = None
    comparison_source_type = None
    comparison_source_path = None
    if selected_comparison:
        comparison_source_type, comparison_source_path = selected_comparison[0]
        comparison_request = ReplayRequest(
            source_type=comparison_source_type,
            source_path=comparison_source_path,
            dry_run=True,
            reexecute=False,
            preserve_original_seed=True,
        )
        try:
            comparison_loaded = ReplayLoader().load(comparison_request)
        except ValueError as exc:
            parser.exit(
                status=2,
                message=f"Comparison rejected: {exc}\n",
            )
        comparison_baseline = comparison_loaded.session
        if comparison_baseline is None:
            parser.exit(
                status=2,
                message=(
                    "Comparison rejected: the selected baseline source did not contain a recoverable session snapshot.\n"
                ),
            )

    selected_pack_name = args.pack
    selected_synthetic_target_name = args.synthetic_target
    if golden_run is not None:
        prepared_seed = golden_run.seed_text
        selected_pack_name = golden_run.experiment_pack_name
        selected_synthetic_target_name = golden_run.synthetic_target_name
    else:
        idea = args.idea or input(t(language, "cli.enter_idea")).strip()
        prepared_seed = idea
    if golden_run is None and args.domain == "smart_contract_audit":
        if args.contract_file and args.contract_code:
            parser.exit(status=2, message="SMART CONTRACT AUDIT accepts either --contract-file or --contract-code, not both.\n")
        contract_source_label: str | None = None
        contract_root_label: str | None = None
        if args.contract_file:
            contract_path = Path(args.contract_file)
            if not contract_path.exists() or not contract_path.is_file():
                parser.exit(status=2, message=f"Contract file not found: {contract_path}\n")
            try:
                contract_code = contract_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                contract_code = contract_path.read_text(encoding="utf-8-sig")
            contract_source_label = str(contract_path)
            if args.contract_root:
                contract_root_path = Path(args.contract_root)
                if not contract_root_path.exists() or not contract_root_path.is_dir():
                    parser.exit(status=2, message=f"Contract root directory not found: {contract_root_path}\n")
                contract_root_label = str(contract_root_path.resolve())
            else:
                contract_root_label = str(contract_path.parent.resolve())
        elif args.contract_code:
            contract_code = args.contract_code
            contract_source_label = "<inline>"
            if args.contract_root:
                contract_root_path = Path(args.contract_root)
                if not contract_root_path.exists() or not contract_root_path.is_dir():
                    parser.exit(status=2, message=f"Contract root directory not found: {contract_root_path}\n")
                contract_root_label = str(contract_root_path.resolve())
        else:
            parser.exit(status=2, message="SMART CONTRACT AUDIT requires --contract-file or --contract-code in direct CLI mode.\n")
        prepared_seed = build_smart_contract_seed(
            idea_text=idea,
            contract_code=contract_code,
            language=infer_contract_language(
                source_label=contract_source_label,
                hinted_language=args.contract_language,
                contract_code=contract_code,
            ),
            source_label=contract_source_label,
            contract_root=contract_root_label,
        )

    try:
        session = orchestrator.run_session(
            seed_text=prepared_seed,
            author=args.author,
            domain=args.domain,
            research_mode=args.research_mode,
            synthetic_target_name=selected_synthetic_target_name,
            experiment_pack_name=selected_pack_name,
            comparison_baseline=comparison_baseline,
            comparison_baseline_source_type=comparison_source_type,
            comparison_baseline_source_path=comparison_source_path,
        )
    except ValueError as exc:
        parser.exit(
            status=2,
            message=t(language, "cli.error.input_rejected", error=localize_error(language, exc)),
        )

    session_path = session.session_file_path or str(
        Path(config.storage.sessions_dir) / f"{session.session_id}.json"
    )
    assert session.report is not None

    print(
        render_report(
            language=language,
            research_mode=session.research_mode.value,
            selected_pack_name=session.selected_pack_name,
            recommended_pack_names=session.recommended_pack_names,
            executed_pack_steps=session.executed_pack_steps,
            session_path=session_path,
            trace_path=session.trace_file_path,
            bundle_path=session.bundle_dir,
            comparative_report_path=session.comparative_report_file_path,
            comparative_generated=bool(
                session.comparative_report and session.comparative_report.analysis_generated
            ),
            plugin_summary=(
                ", ".join(
                    f"{item.plugin_name}:{item.load_status}" for item in session.plugin_metadata
                )
                if session.plugin_metadata
                else None
            ),
            session_id=session.session_id,
            report_summary=session.report.summary,
            evidence_profile=session.report.evidence_profile,
            evidence_coverage_summary=session.report.evidence_coverage_summary,
            validation_posture=session.report.validation_posture,
            shared_follow_up=session.report.shared_follow_up,
            calibration_blockers=session.report.calibration_blockers,
            reproducibility_summary=session.report.reproducibility_summary,
            toolchain_fingerprint_summary=session.report.toolchain_fingerprint_summary,
            secret_redaction_summary=session.report.secret_redaction_summary,
            quality_gates=session.report.quality_gates,
            hardening_summary=session.report.hardening_summary,
            ecc_triage_snapshot=session.report.ecc_triage_snapshot,
            ecc_benchmark_summary=session.report.ecc_benchmark_summary,
            ecc_benchmark_posture=session.report.ecc_benchmark_posture,
            ecc_family_coverage=session.report.ecc_family_coverage,
            ecc_coverage_matrix=session.report.ecc_coverage_matrix,
            ecc_benchmark_case_summaries=session.report.ecc_benchmark_case_summaries,
            ecc_review_focus=session.report.ecc_review_focus,
            ecc_residual_risk=session.report.ecc_residual_risk,
            ecc_signal_consensus=session.report.ecc_signal_consensus,
            ecc_validation_matrix=session.report.ecc_validation_matrix,
            ecc_comparison_focus=session.report.ecc_comparison_focus,
            ecc_benchmark_delta=session.report.ecc_benchmark_delta,
            ecc_regression_summary=session.report.ecc_regression_summary,
            ecc_review_queue=session.report.ecc_review_queue,
            ecc_exit_criteria=session.report.ecc_exit_criteria,
            contract_overview=session.report.contract_overview,
            contract_inventory_summary=session.report.contract_inventory_summary,
            contract_protocol_map=session.report.contract_protocol_map,
            contract_protocol_invariants=session.report.contract_protocol_invariants,
            contract_signal_consensus=session.report.contract_signal_consensus,
            contract_validation_matrix=session.report.contract_validation_matrix,
            contract_benchmark_posture=session.report.contract_benchmark_posture,
            contract_benchmark_pack_summary=session.report.contract_benchmark_pack_summary,
            contract_benchmark_case_summaries=session.report.contract_benchmark_case_summaries,
            contract_repo_priorities=session.report.contract_repo_priorities,
            contract_repo_triage=session.report.contract_repo_triage,
            contract_casebook_coverage=session.report.contract_casebook_coverage,
            contract_casebook_coverage_matrix=session.report.contract_casebook_coverage_matrix,
            contract_casebook_case_studies=session.report.contract_casebook_case_studies,
            contract_casebook_priority_cases=session.report.contract_casebook_priority_cases,
            contract_casebook_gaps=session.report.contract_casebook_gaps,
            contract_casebook_benchmark_support=session.report.contract_casebook_benchmark_support,
            contract_casebook_triage=session.report.contract_casebook_triage,
            contract_toolchain_alignment=session.report.contract_toolchain_alignment,
            contract_review_queue=session.report.contract_review_queue,
            contract_compile_summary=session.report.contract_compile_summary,
            contract_surface_summary=session.report.contract_surface_summary,
            contract_priority_findings=session.report.contract_priority_findings,
            contract_finding_cards=session.report.contract_finding_cards,
            contract_known_case_matches=session.report.contract_known_case_matches,
            contract_static_findings=session.report.contract_static_findings,
            contract_testbed_findings=session.report.contract_testbed_findings,
            contract_remediation_validation=session.report.contract_remediation_validation,
            contract_review_focus=session.report.contract_review_focus,
            contract_remediation_guidance=session.report.contract_remediation_guidance,
            contract_remediation_follow_up=session.report.contract_remediation_follow_up,
            contract_residual_risk=session.report.contract_residual_risk,
            contract_exit_criteria=session.report.contract_exit_criteria,
            contract_manual_review_items=session.report.contract_manual_review_items,
            contract_triage_snapshot=session.report.contract_triage_snapshot,
            remediation_delta_summary=session.report.remediation_delta_summary,
            before_after_comparison=session.report.before_after_comparison,
            regression_flags=session.report.regression_flags,
            tested_hypotheses=session.report.tested_hypotheses,
            tool_usage_summary=session.report.tool_usage_summary,
            comparative_findings=session.report.comparative_findings,
            anomalies=session.report.anomalies,
            recommendations=session.report.recommendations,
            manual_review_items=session.report.manual_review_items,
            confidence_rationale=session.report.confidence_rationale,
            confidence=session.report.confidence.value,
        )
    )
    return 0


def _prepare_preview_seed(args: argparse.Namespace) -> tuple[str, str | None]:
    if args.golden_case:
        if args.idea:
            raise ValueError("do not combine --golden-case with a free-form research idea.")
        if args.domain or args.contract_file or args.contract_code or args.contract_root or args.contract_language:
            raise ValueError("do not combine --golden-case with domain or contract source arguments.")
        try:
            golden_run = prepare_golden_case_run(args.golden_case)
        except GoldenCaseError as exc:
            raise ValueError(str(exc)) from exc
        return golden_run.seed_text, golden_run.experiment_pack_name

    if args.domain == "smart_contract_audit":
        if not args.idea:
            raise ValueError("SMART CONTRACT AUDIT preview requires a free-form research idea.")
        if args.contract_file and args.contract_code:
            raise ValueError("SMART CONTRACT AUDIT accepts either --contract-file or --contract-code, not both.")
        if args.contract_file:
            contract_path = Path(args.contract_file)
            if not contract_path.exists() or not contract_path.is_file():
                raise ValueError(f"contract file not found: {contract_path}")
            try:
                contract_code = contract_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                contract_code = contract_path.read_text(encoding="utf-8-sig")
            contract_source_label = str(contract_path)
            contract_root_label = _contract_root_for_preview(args, contract_path.parent)
        elif args.contract_code:
            contract_code = args.contract_code
            contract_source_label = "<inline>"
            contract_root_label = _contract_root_for_preview(args, None)
        else:
            raise ValueError("SMART CONTRACT AUDIT preview requires --contract-file or --contract-code.")
        return (
            build_smart_contract_seed(
                idea_text=args.idea,
                contract_code=contract_code,
                language=infer_contract_language(
                    source_label=contract_source_label,
                    hinted_language=args.contract_language,
                    contract_code=contract_code,
                ),
                source_label=contract_source_label,
                contract_root=contract_root_label,
            ),
            args.pack,
        )

    if args.contract_file or args.contract_code or args.contract_root or args.contract_language:
        raise ValueError("contract source preview requires --domain smart_contract_audit.")
    if not args.idea:
        raise ValueError("provider context preview requires an idea, --golden-case, or smart-contract source.")
    return args.idea, args.pack


def _contract_root_for_preview(args: argparse.Namespace, default_root: Path | None) -> str | None:
    if args.contract_root:
        contract_root_path = Path(args.contract_root)
        if not contract_root_path.exists() or not contract_root_path.is_dir():
            raise ValueError(f"contract root directory not found: {contract_root_path}")
        return str(contract_root_path.resolve())
    if default_root is not None:
        return str(default_root.resolve())
    return None


if __name__ == "__main__":
    raise SystemExit(main())
