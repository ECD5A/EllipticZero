from __future__ import annotations

TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "brand.subtitle": "Sandboxed Research Audit Engine",
        "menu.hint": "Arrow keys move selection. Enter confirms.",
        "menu.start_research.label": "START RESEARCH",
        "menu.start_research.desc": "Choose domain, optional curve, enter your idea, and run.",
        "menu.advanced.label": "ADVANCED / INTERNAL",
        "menu.advanced.desc": "Replay, routing, registries, and system check.",
        "menu.new_session.label": "NEW RESEARCH SESSION",
        "menu.new_session.desc": "Start from a free-form seed and run a bounded local research flow.",
        "menu.replay.label": "REPLAY SESSION",
        "menu.replay.desc": "Inspect or re-execute a saved session, manifest, or reproducibility bundle.",
        "menu.routing.label": "LLM ROUTING",
        "menu.routing.desc": "Inspect the shared default route and any optional per-agent overrides.",
        "menu.tools.label": "TOOL REGISTRY",
        "menu.tools.desc": "Inspect built-in and plugin-provided tools available to the local executor.",
        "menu.curves.label": "CURVE REGISTRY",
        "menu.curves.desc": "Inspect supported named curves, aliases, families, and usage categories.",
        "menu.return.label": "RETURN",
        "menu.return.desc": "Go back to the main research flow.",
        "menu.exit.label": "EXIT",
        "menu.exit.desc": "Close the EllipticZero interactive console.",
        "console.closed": "EllipticZero console closed.",
        "status.plugins": "plugins {count}",
        "status.built_in": "built-in {count}",
        "status.plugin_tools": "plugin tools {count}",
        "status.language": "{value}",
        "status.local_lab": "local sandbox",
        "status.traces_on": "traces on",
        "status.bundles_on": "bundles on",
        "status.reports_structured": "reports structured",
        "hint.replay": "Arrow keys move selection. Enter confirms. Esc returns.",
        "hint.curve_helper": "Arrow keys move selection. Enter confirms. Esc returns to domain selection.",
        "hint.toggle_language": "F2 or L switches language.",
        "hint.return_toggle": "Enter returns. F2 or L switches language.",
        "screen.advanced.title": "ADVANCED / INTERNAL",
        "screen.advanced.subtitle": "Internal research surfaces stay available, but the main product flow remains language, curve, idea, run, and report.",
        "screen.new_session.title": "NEW RESEARCH SESSION",
        "screen.new_session.subtitle": "Free-form seed stays primary. Optional helpers only add context.",
        "screen.replay.title": "REPLAY SESSION",
        "screen.replay.subtitle": "Dry-run inspects saved provenance. Re-execution creates a new local run with replay metadata.",
        "screen.routing.title": "LLM ROUTING",
        "screen.routing.subtitle": "The default path stays shared. Per-agent overrides remain available for advanced research setups.",
        "screen.tools.title": "TOOL REGISTRY",
        "screen.tools.subtitle": "Inspectable local tools available to the bounded executor and plugin system.",
        "screen.curves.title": "CURVE REGISTRY",
        "screen.curves.subtitle": "Supported named curves, aliases, families, and bounded metadata used by local ECC tooling.",
        "screen.curve_helper.title": "OPTIONAL CURVE HELPER",
        "screen.curve_helper.subtitle": "This helper adds context only. The seed itself stays primary.",
        "screen.seed_input.title": "RESEARCH IDEA",
        "screen.seed_input.subtitle": "Describe the bounded local question you want the session to investigate.",
        "screen.session_complete.title": "SESSION COMPLETE",
        "screen.session_complete.subtitle": "Evidence, traces, and reproducibility outputs were stored locally.",
        "screen.replay_result.title": "REPLAY RESULT",
        "screen.replay_result.subtitle": "Replay preserves provenance. Dry-run inspects only; re-execution creates a fresh local run.",
        "block.session_workflow": "SESSION WORKFLOW",
        "block.run_stages": "RUN STAGES",
        "block.tool_summary": "TOOL SUMMARY",
        "block.routing_summary": "ROUTING SUMMARY",
        "block.curve_summary": "CURVE SUMMARY",
        "block.helper_curve_context": "HELPER CURVE CONTEXT",
        "block.run_summary": "RUN SUMMARY",
        "block.local_outputs": "LOCAL OUTPUTS",
        "block.replay_summary": "REPLAY SUMMARY",
        "block.replay_outputs": "REPLAY OUTPUTS",
        "block.replay_notes": "REPLAY NOTES",
        "block.summary": "SUMMARY",
        "block.confidence_rationale": "CONFIDENCE CALIBRATION",
        "block.ecc_benchmark_summary": "ECC BENCHMARK SUMMARY",
        "block.ecc_review_focus": "ECC REVIEW FOCUS",
        "block.ecc_residual_risk": "ECC RESIDUAL RISK",
        "block.ecc_signal_consensus": "ECC SIGNAL CONSENSUS",
        "block.ecc_validation_matrix": "ECC VALIDATION MATRIX",
        "block.ecc_comparison_focus": "ECC COMPARISON FOCUS",
        "block.contract_overview": "CONTRACT OVERVIEW",
        "block.contract_inventory": "CONTRACT INVENTORY",
        "block.contract_protocol_map": "PROTOCOL MAP",
        "block.contract_protocol_invariants": "PROTOCOL INVARIANTS",
        "block.contract_signal_consensus": "SIGNAL CONSENSUS",
        "block.contract_validation_matrix": "VALIDATION MATRIX",
        "block.contract_benchmark_posture": "BENCHMARK POSTURE",
        "block.contract_benchmark_pack_summary": "BENCHMARK PACK SUMMARY",
        "block.contract_benchmark_case_summaries": "BENCHMARK CASE SUMMARIES",
        "block.contract_repo_priorities": "REPO-SCALE PRIORITIES",
        "block.contract_repo_triage": "REPO TRIAGE",
        "block.contract_casebook_coverage": "CASEBOOK COVERAGE",
        "block.contract_casebook_coverage_matrix": "CASEBOOK COVERAGE MATRIX",
        "block.contract_casebook_case_studies": "CASE STUDY SUMMARY",
        "block.contract_casebook_priority_cases": "CASEBOOK PRIORITY CASES",
        "block.contract_casebook_gaps": "CASEBOOK GAPS",
        "block.contract_casebook_benchmark_support": "CASEBOOK BENCHMARK POSTURE",
        "block.contract_casebook_triage": "CASEBOOK TRIAGE",
        "block.contract_toolchain_alignment": "TOOLCHAIN ALIGNMENT",
        "block.contract_review_queue": "REVIEW QUEUE",
        "block.contract_compile": "COMPILE STATUS",
        "block.contract_surface": "CONTRACT SURFACE",
        "block.contract_priority_findings": "PRIORITY FINDINGS",
        "block.contract_finding_cards": "FINDING CARDS",
        "block.contract_static_findings": "STATIC FINDINGS",
        "block.contract_testbeds": "CONTRACT TESTBEDS",
        "block.contract_remediation_validation": "REMEDIATION VALIDATION",
        "block.contract_review_focus": "REVIEW FOCUS",
        "block.contract_remediation_guidance": "DEFENSIVE REMEDIATION",
        "block.contract_remediation_follow_up": "REMEDIATION FOLLOW-UP",
        "block.contract_residual_risk": "RESIDUAL RISK",
        "block.contract_exit_criteria": "EXIT CRITERIA",
        "block.contract_manual_review": "CONTRACT MANUAL REVIEW",
        "block.agent_contributions": "AGENT CONTRIBUTIONS",
        "block.local_experiments": "LOCAL EXPERIMENTS",
        "block.local_signals": "LOCAL SIGNALS",
        "block.dead_ends": "DEAD ENDS",
        "block.next_defensive_leads": "NEXT DEFENSIVE LEADS",
        "block.tested_hypotheses": "TESTED HYPOTHESES",
        "block.tool_usage": "TOOL USAGE",
        "block.comparative_findings": "COMPARATIVE FINDINGS",
        "block.anomalies": "ANOMALIES",
        "block.recommendations": "RECOMMENDATIONS",
        "block.manual_review_items": "MANUAL REVIEW ITEMS",
        "workflow.entry_mode.label": "ENTRY MODE",
        "workflow.entry_mode.value": "Free-form seed with optional curve helper.",
        "workflow.entry_mode.value.ecc": "Free-form seed with optional curve helper.",
        "workflow.entry_mode.value.smart_contract": "Contract code from file or paste, plus a free-form audit idea.",
        "workflow.local_execution.label": "LOCAL EXECUTION",
        "workflow.local_execution.value": "Tools run only through the approved registry and executor.",
        "workflow.run_outputs.label": "RUN OUTPUTS",
        "workflow.run_outputs.value": "Session JSON, trace JSONL, bundle, and comparative report.",
        "stage.1": "[1/4] Formalizing session scope",
        "stage.2": "[2/4] Expanding and critiquing hypotheses",
        "stage.3": "[3/4] Executing approved local tools",
        "stage.4": "[4/4] Recording evidence and artifacts",
        "label.total_tools": "TOTAL TOOLS",
        "label.shared_provider": "SHARED PROVIDER",
        "label.shared_model": "SHARED MODEL",
        "label.routing_mode": "ROUTING MODE",
        "label.fallback_provider": "FALLBACK PROVIDER",
        "label.built_in_tools": "BUILT-IN TOOLS",
        "label.plugin_tools": "PLUGIN TOOLS",
        "label.deterministic_tools": "DETERMINISTIC TOOLS",
        "label.known_curves": "KNOWN CURVES",
        "label.registered_aliases": "REGISTERED ALIASES",
        "label.curve_families": "CURVE FAMILIES",
        "label.on_curve_support": "ON-CURVE CHECK SUPPORT",
        "label.canonical_name": "CANONICAL NAME",
        "label.aliases": "ALIASES",
        "label.family_usage": "FAMILY / USAGE",
        "label.description": "DESCRIPTION",
        "label.session_id": "SESSION ID",
        "label.helper_curve": "HELPER CURVE",
        "label.confidence": "CONFIDENCE",
        "label.hypotheses_evidence": "HYPOTHESES / EVIDENCE",
        "label.plugins": "PLUGINS",
        "label.session_json": "SESSION JSON",
        "label.trace_jsonl": "TRACE JSONL",
        "label.bundle_directory": "BUNDLE DIRECTORY",
        "label.comparative_report": "COMPARATIVE REPORT",
        "label.source_type": "SOURCE TYPE",
        "label.source_path": "SOURCE PATH",
        "label.dry_run": "DRY RUN",
        "label.reexecuted": "REEXECUTED",
        "label.success": "SUCCESS",
        "label.generated_session": "GENERATED SESSION",
        "label.generated_trace": "GENERATED TRACE",
        "label.generated_bundle": "GENERATED BUNDLE",
        "table.name": "NAME",
        "table.agent": "AGENT",
        "table.provider": "PROVIDER",
        "table.model": "MODEL",
        "table.routing_mode": "MODE",
        "table.category": "CATEGORY",
        "table.mode": "MODE",
        "table.source": "SOURCE",
        "table.description": "DESCRIPTION",
        "table.curve": "CURVE",
        "table.family": "FAMILY",
        "table.field": "FIELD",
        "table.usage": "USAGE",
        "value.none": "none",
        "value.auto": "auto",
        "value.shared": "shared",
        "value.override": "override",
        "value.shared_default": "shared-default",
        "value.mixed_overrides": "mixed-overrides",
        "value.unavailable": "unavailable",
        "curve_helper.auto.label": "AUTO / NO CURVE HELPER",
        "curve_helper.auto.desc": "Keep the free-form seed as the only input and let orchestration infer the target.",
        "curve_helper.secp256k1.label": "SECP256K1",
        "curve_helper.secp256k1.desc": "Popular short-Weierstrass curve used in blockchain and signature workflows.",
        "curve_helper.secp256r1.label": "SECP256R1 / P-256",
        "curve_helper.secp256r1.desc": "Widely used standard curve for general-purpose signatures and key handling.",
        "curve_helper.ed25519.label": "ED25519",
        "curve_helper.ed25519.desc": "Modern Edwards-curve signature family for descriptive and bounded local checks.",
        "curve_helper.x25519.label": "X25519 / CURVE25519",
        "curve_helper.x25519.desc": "Key-exchange-oriented 25519 family entry for metadata and consistency analysis.",
        "replay.option.session.label": "SESSION.JSON",
        "replay.option.session.desc": "Load a previously saved research session snapshot.",
        "replay.option.manifest.label": "MANIFEST.JSON",
        "replay.option.manifest.desc": "Load a run manifest and reconstruct a conservative replay plan.",
        "replay.option.bundle.label": "BUNDLE DIRECTORY",
        "replay.option.bundle.desc": "Load a reproducibility bundle with session, trace, and manifest files.",
        "replay.option.return.label": "RETURN",
        "replay.option.return.desc": "Go back to the main console menu.",
        "prompt.seed": "seed >",
        "prompt.seed_hint": "Enter the idea that agents and local tools should investigate locally. Type /lang to switch language.",
        "prompt.author_optional": "author (optional, Enter skips) >",
        "prompt.path": "path (/lang switches language) >",
        "prompt.replay_author": "author for replay run (optional) >",
        "prompt.dry_run": "inspect only? [y/N]",
        "prompt.pause": "Press Enter to continue...",
        "message.seed_required": "A research idea is required to start a session.",
        "message.input_rejected": "Input rejected: {error}",
        "message.replay_path_required": "Replay path is required.",
        "message.replay_rejected": "Replay rejected: {error}",
        "report.summary": "Summary",
        "report.confidence_rationale": "Confidence Calibration",
        "report.ecc_benchmark_summary": "ECC Benchmark Summary",
        "report.ecc_review_focus": "ECC Review Focus",
        "report.ecc_residual_risk": "ECC Residual Risk",
        "report.ecc_signal_consensus": "ECC Signal Consensus",
        "report.ecc_validation_matrix": "ECC Validation Matrix",
        "report.ecc_comparison_focus": "ECC Comparison Focus",
        "report.contract_overview": "Contract Overview",
        "report.contract_inventory": "Contract Inventory",
        "report.contract_protocol_map": "Protocol Map",
        "report.contract_protocol_invariants": "Protocol Invariants",
        "report.contract_signal_consensus": "Signal Consensus",
        "report.contract_validation_matrix": "Validation Matrix",
        "report.contract_benchmark_posture": "Benchmark Posture",
        "report.contract_benchmark_pack_summary": "Benchmark Pack Summary",
        "report.contract_benchmark_case_summaries": "Benchmark Case Summaries",
        "report.contract_repo_priorities": "Repo-Scale Priorities",
        "report.contract_repo_triage": "Repo Triage",
        "report.contract_casebook_coverage": "Casebook Coverage",
        "report.contract_casebook_coverage_matrix": "Casebook Coverage Matrix",
        "report.contract_casebook_case_studies": "Case Study Summary",
        "report.contract_casebook_priority_cases": "Casebook Priority Cases",
        "report.contract_casebook_gaps": "Casebook Gaps",
        "report.contract_casebook_benchmark_support": "Casebook Benchmark Posture",
        "report.contract_casebook_triage": "Casebook Triage",
        "report.contract_toolchain_alignment": "Toolchain Alignment",
        "report.contract_review_queue": "Review Queue",
        "report.contract_compile": "Compile Status",
        "report.contract_surface": "Contract Surface",
        "report.contract_priority_findings": "Priority Findings",
        "report.contract_finding_cards": "Finding Cards",
        "report.contract_static_findings": "Static Findings",
        "report.contract_testbeds": "Contract Testbeds",
        "report.contract_remediation_validation": "Remediation Validation",
        "report.contract_review_focus": "Review Focus",
        "report.contract_remediation_guidance": "Defensive Remediation",
        "report.contract_remediation_follow_up": "Remediation Follow-Up",
        "report.contract_residual_risk": "Residual Risk",
        "report.contract_exit_criteria": "Exit Criteria",
        "report.contract_manual_review": "Contract Manual Review",
        "report.tested_hypotheses": "Tested Hypotheses",
        "report.tool_usage": "Tool Usage",
        "report.comparative_findings": "Comparative Findings",
        "report.anomalies": "Anomalies",
        "report.recommendations": "Recommendations",
        "report.manual_review_items": "Manual Review Items",
        "report.session_id": "Session ID",
        "report.stored_session": "Stored Session",
        "report.stored_trace": "Stored Trace",
        "report.bundle": "Reproducibility Bundle",
        "report.comparative_analysis": "Comparative Analysis",
        "report.comparative_generated": "generated",
        "report.comparative_limited": "limited",
        "report.comparative_report": "Comparative Report",
        "report.plugins": "Plugins",
        "report.confidence": "Confidence",
        "replay.replay_id": "Replay ID",
        "replay.replay_source": "Replay Source",
        "replay.replay_path": "Replay Path",
        "replay.replay_session": "Replay Session",
        "replay.generated_session": "Generated Session",
        "replay.generated_trace": "Generated Trace",
        "replay.generated_bundle": "Generated Bundle",
        "replay.notes": "Notes",
        "menu.doctor.label": "SYSTEM CHECK",
        "menu.doctor.desc": "Inspect local runtime readiness for providers, tools, plugins, storage, compiler and static-analysis adapters, and advanced math.",
        "screen.doctor.title": "SYSTEM CHECK",
        "screen.doctor.subtitle": "Bounded local self-check for provider configuration, tool registry, plugins, storage, compiler and static-analysis adapters, and Sage readiness.",
        "block.doctor_summary": "SYSTEM SUMMARY",
        "label.overall_status": "OVERALL STATUS",
        "label.active_provider": "ACTIVE PROVIDER",
        "label.registry_tools": "REGISTRY TOOLS",
        "label.loaded_plugins": "LOADED PLUGINS",
        "label.failed_plugins": "FAILED PLUGINS",
        "value.enabled": "enabled",
        "value.disabled": "disabled",
        "doctor.report_id": "Doctor Report ID",
        "doctor.overall_status": "Overall Status",
        "doctor.summary_label": "Summary",
        "doctor.status.ok": "ok",
        "doctor.status.warning": "warning",
        "doctor.status.error": "error",
        "doctor.status.info": "info",
        "doctor.summary.ok": "Runtime readiness check passed. Core local workflows appear ready.",
        "doctor.summary.warning": "Runtime readiness check passed with warnings. Core workflows remain usable, but some capabilities need attention.",
        "doctor.summary.error": "Runtime readiness check found blocking issues. Review the failed checks before relying on this runtime.",
        "doctor.summary.info": "Runtime readiness check completed with informational notes only.",
        "doctor.check.provider.title": "Provider Configuration",
        "doctor.check.provider.mock": "Mock provider is active, so local smoke runs are ready without external API credentials.",
        "doctor.check.provider.ready": "Configured provider '{provider}' has the required API credential available.",
        "doctor.check.provider.missing_key": "Configured provider '{provider}' is missing the required API credential from '{env}'.",
        "doctor.check.provider.unknown": "Configured provider '{provider}' is not recognized by the current routing layer.",
        "doctor.check.provider_smoke.title": "Hosted Provider Smoke Path",
        "doctor.check.provider_smoke.mock": "Mock mode is active; hosted smoke validation becomes available once a hosted provider and API key are configured.",
        "doctor.check.provider_smoke.ready": "Hosted smoke path for provider '{provider}' is ready for a bounded live check.",
        "doctor.check.provider_smoke.missing_key": "Hosted smoke path for provider '{provider}' cannot run until '{env}' is available.",
        "doctor.check.registry.title": "Tool Registry",
        "doctor.check.registry.ready": "The approved local tool registry is populated and ready with {count} tools.",
        "doctor.check.registry.missing": "The approved local tool registry is missing {count} required built-in tools.",
        "doctor.check.plugins.title": "Plugin Loading",
        "doctor.check.plugins.loaded": "{count} local plugin(s) loaded through the bounded registry adapter.",
        "doctor.check.plugins.none": "Plugin loading is enabled, but no local plugins were discovered.",
        "doctor.check.plugins.failed": "{failed} plugin(s) failed to load while {loaded} plugin(s) loaded successfully.",
        "doctor.check.plugins.disabled": "Local plugin loading is disabled by the current configuration.",
        "doctor.check.storage.title": "Storage and Reproducibility Paths",
        "doctor.check.storage.ready": "Session, trace, bundle, and math artifact directories are writable.",
        "doctor.check.storage.failed": "One or more local storage directories are not writable.",
        "doctor.check.sage.title": "Advanced Math / Sage",
        "doctor.check.sage.available": "Advanced math is enabled and Sage binary '{binary}' is available locally.",
        "doctor.check.sage.unavailable": "Advanced math is enabled, but Sage binary '{binary}' is not available locally. Deterministic fallback paths remain usable.",
        "doctor.check.sage.disabled": "Advanced math support is enabled, but Sage integration is disabled in configuration.",
        "doctor.check.sage.advanced_math_disabled": "Advanced math support is disabled in configuration.",
        "doctor.check.contract_compiler.title": "Smart-Contract Compiler",
        "doctor.check.contract_compiler.available": "A local Solidity compiler adapter is ready through '{binary}'.",
        "doctor.check.contract_compiler.unavailable": "No local solc-compatible compiler was found on PATH or in the managed project toolchain. Compile-path checks remain unavailable.",
        "doctor.check.contract_compiler.disabled": "Local smart-contract compile checks are disabled in the current configuration.",
        "doctor.check.slither.title": "Smart-Contract Static Analyzer",
        "doctor.check.slither.available": "A local Slither-based static analyzer is ready through '{binary}'.",
        "doctor.check.slither.unavailable": "The Slither adapter or its required local Solidity compiler is unavailable, so external static-analysis checks remain unavailable.",
        "doctor.check.slither.disabled": "Local Slither-based smart-contract analysis is disabled in the current configuration.",
        "doctor.check.echidna.title": "Smart-Contract Echidna Adapter",
        "doctor.check.echidna.available": "A local Echidna adapter is ready through '{binary}'.",
        "doctor.check.echidna.unavailable": "The Echidna adapter or its required local Solidity compiler is unavailable, so invariant and assertion fuzzing checks remain unavailable.",
        "doctor.check.echidna.disabled": "Local Echidna-based smart-contract fuzzing is disabled in the current configuration.",
        "doctor.check.foundry.title": "Smart-Contract Foundry Adapter",
        "doctor.check.foundry.available": "A local Foundry/Forge adapter is ready through '{binary}'.",
        "doctor.check.foundry.unavailable": "The Foundry adapter or its required local Solidity compiler is unavailable, so Forge-based contract checks remain unavailable.",
        "doctor.check.foundry.disabled": "Local Foundry/Forge contract analysis is disabled in the current configuration.",
        "doctor.check.local_research.title": "Local Research Adapters",
        "doctor.check.local_research.ready": "The local research adapter layer is ready for bounded sandboxed experiments.",
        "doctor.check.local_research.partial": "Some optional local research adapters are unavailable; the sandboxed research lab remains partially ready.",
        "doctor.directory.ready": "ready",
        "doctor.directory.failed": "not ready",
        "doctor.detail.default_provider": "Default provider: {value}",
        "doctor.detail.default_model": "Default model: {value}",
        "doctor.detail.fallback_provider": "Fallback provider: {value}",
        "doctor.detail.api_env": "API key environment variable: {value}",
        "doctor.detail.live_smoke_command": "Live smoke command: {value}",
        "doctor.detail.smoke_timeout": "Live smoke timeout seconds: {value}",
        "doctor.detail.smoke_max_tokens": "Live smoke max request tokens: {value}",
        "doctor.detail.smart_contract_compile_enabled": "Smart-contract compile checks enabled: {value}",
        "doctor.detail.managed_solc_dir": "Managed solc directory: {value}",
        "doctor.detail.managed_solc_version": "Preferred managed solc version: {value}",
        "doctor.detail.solc_binary": "Preferred solc binary: {value}",
        "doctor.detail.solcjs_binary": "Fallback solcjs binary: {value}",
        "doctor.detail.contract_compile_timeout": "Compiler timeout seconds: {value}",
        "doctor.detail.installed_managed_compilers": "Installed managed compilers: {value}",
        "doctor.detail.resolved_managed_compiler_binary": "Resolved managed compiler binary: {value}",
        "doctor.detail.resolved_managed_compiler_version": "Resolved managed compiler version: {value}",
        "doctor.detail.resolved_compiler_binary": "Resolved compiler binary: {value}",
        "doctor.detail.compiler_version": "Compiler version: {value}",
        "doctor.detail.slither_enabled": "Slither-based analysis enabled: {value}",
        "doctor.detail.slither_binary": "Preferred Slither binary: {value}",
        "doctor.detail.slither_timeout": "Slither timeout seconds: {value}",
        "doctor.detail.echidna_enabled": "Echidna-based fuzzing enabled: {value}",
        "doctor.detail.echidna_binary": "Preferred Echidna binary: {value}",
        "doctor.detail.echidna_timeout": "Echidna timeout seconds: {value}",
        "doctor.detail.echidna_test_limit": "Echidna test limit: {value}",
        "doctor.detail.echidna_seq_len": "Echidna sequence length: {value}",
        "doctor.detail.foundry_enabled": "Foundry-based analysis enabled: {value}",
        "doctor.detail.forge_binary": "Preferred Forge binary: {value}",
        "doctor.detail.foundry_timeout": "Foundry timeout seconds: {value}",
        "doctor.detail.resolved_analyzer_binary": "Resolved analyzer binary: {value}",
        "doctor.detail.analyzer_version": "Analyzer version: {value}",
        "doctor.detail.total_tools": "Total tools: {value}",
        "doctor.detail.built_in_tools": "Built-in tools: {value}",
        "doctor.detail.plugin_tools": "Plugin tools: {value}",
        "doctor.detail.deterministic_tools": "Deterministic tools: {value}",
        "doctor.detail.synthetic_targets": "Synthetic targets: {value}",
        "doctor.detail.experiment_packs": "Experiment packs: {value}",
        "doctor.detail.required_tools": "Required built-ins: {value}",
        "doctor.detail.missing_tools": "Missing built-ins: {value}",
        "doctor.detail.plugin_directory": "Plugin directory: {value}",
        "doctor.detail.loaded_plugins": "Loaded plugins: {value}",
        "doctor.detail.failed_plugins": "Failed plugins: {value}",
        "doctor.detail.failed_plugin_note": "Failed plugin {plugin}: {note}",
        "doctor.detail.disabled_by_config": "Plugin loading is disabled by configuration.",
        "doctor.detail.directory_status": "{name}: {path} ({status})",
        "doctor.detail.storage_failures": "Storage errors: {value}",
        "doctor.detail.advanced_math": "Advanced math: {value}",
        "doctor.detail.sage_enabled": "Sage integration: {value}",
        "doctor.detail.sage_binary": "Sage binary: {value}",
        "doctor.detail.sage_timeout": "Sage timeout (s): {value}",
        "cli.enter_idea": "Enter research idea: ",
        "cli.error.choose_one_replay": "Replay rejected: choose only one replay source.\n",
        "cli.error.replay_and_idea": "Replay rejected: do not combine a new idea with replay arguments.\n",
        "cli.error.doctor_and_replay": "System check rejected: do not combine --doctor with replay arguments.\n",
        "cli.error.doctor_and_idea": "System check rejected: do not combine --doctor with a new idea.\n",
        "cli.error.doctor_and_interactive": "System check rejected: use --doctor for the direct CLI report or open the interactive console and choose SYSTEM CHECK.\n",
        "cli.error.replay_rejected": "Replay rejected: {error}\n",
        "cli.error.input_rejected": "Input rejected: {error}\n",
        "live_smoke.title": "Hosted Provider Smoke Test",
        "live_smoke.provider": "Provider",
        "live_smoke.model": "Model",
        "live_smoke.timeout": "Timeout (s)",
        "live_smoke.max_request_tokens": "Max request tokens",
        "live_smoke.result": "Result",
        "list.synthetic_targets.title": "Built-in Synthetic Research Targets",
        "list.experiment_packs.title": "Built-in Experiment Packs",
        "hint.domain_select": "Arrow keys move selection. Enter confirms. Esc returns.",
        "screen.domain.title": "RESEARCH DOMAIN",
        "screen.domain.subtitle": "Choose whether this bounded session starts from ECC research or a smart-contract audit target.",
        "screen.contract_source.title": "CONTRACT SOURCE",
        "screen.contract_source.subtitle": "Drop a local file, paste a file path, or paste contract code. Solidity/Vyper is inferred automatically.",
        "workflow.domain.label": "DOMAIN",
        "workflow.domain.value.ecc": "ECC research",
        "workflow.domain.value.smart_contract": "Smart contract audit",
        "domain.ecc.label": "ECC RESEARCH",
        "domain.ecc.desc": "Curves, points, symbolic checks, and finite-field consistency in the local sandbox.",
        "domain.smart_contract.label": "SMART CONTRACT AUDIT",
        "domain.smart_contract.desc": "Local static audit for contract code, risky surfaces, and bounded review patterns.",
        "prompt.contract.idea": "audit idea (/lang switches language) >",
        "prompt.contract.file": "file path or code (/back, /cancel, /lang) >",
        "prompt.contract.input_hint": "Drop a file, paste a path, or press Enter for multiline code. /back returns. /cancel leaves the session. /lang switches language.",
        "prompt.contract.paste_hint": "Paste contract code below. Empty line finishes. /back returns. /cancel leaves the session. /lang switches language.",
        "message.contract_path_invalid": "Contract file not found: {path}",
        "message.contract_code_required": "Smart contract code is required for pasted audit input.",
        "message.contract_source_invalid": "Input was not recognized as a readable file path or contract code snippet.",
    },
    "ru": {
        "brand.subtitle": "Консоль локального исследовательского аудита",
        "menu.hint": "Стрелки меняют выбор. Enter подтверждает.",
        "menu.start_research.label": "ЗАПУСК ИССЛЕДОВАНИЯ",
        "menu.start_research.desc": "Выбрать домен, кривую при желании, ввести идею и запустить.",
        "menu.advanced.label": "РАСШИРЕННОЕ / СЛУЖЕБНОЕ",
        "menu.advanced.desc": "Повтор, маршрутизация, реестры и проверка системы.",
        "menu.new_session.label": "НОВАЯ СЕССИЯ",
        "menu.new_session.desc": "Запустить новую исследовательскую сессию на основе свободной идеи.",
        "menu.replay.label": "ПОВТОР СЕССИИ",
        "menu.replay.desc": "Проверить или воспроизвести сохранённую сессию, манифест или пакет воспроизводимости.",
        "menu.routing.label": "МАРШРУТИЗАЦИЯ LLM",
        "menu.routing.desc": "Показать общий маршрут по умолчанию и возможные отдельные настройки для ролей.",
        "menu.tools.label": "РЕЕСТР ИНСТРУМЕНТОВ",
        "menu.tools.desc": "Открыть перечень встроенных и плагинных инструментов локального исполнителя.",
        "menu.curves.label": "РЕЕСТР КРИВЫХ",
        "menu.curves.desc": "Просмотреть поддерживаемые кривые, алиасы, семейства и сценарии применения.",
        "menu.return.label": "НАЗАД",
        "menu.return.desc": "Вернуться к главному циклу исследования.",
        "menu.exit.label": "ВЫХОД",
        "menu.exit.desc": "Закрыть интерактивную консоль EllipticZero.",
        "console.closed": "Консоль EllipticZero закрыта.",
        "status.plugins": "плагинов {count}",
        "status.built_in": "встроен. {count}",
        "status.plugin_tools": "плагин. {count}",
        "status.language": "{value}",
        "status.local_lab": "локальная песочница",
        "status.traces_on": "трассировки вкл",
        "status.bundles_on": "пакеты вкл",
        "status.reports_structured": "строгие отчёты",
        "hint.replay": "Стрелки меняют выбор. Enter подтверждает. Esc возвращает назад.",
        "hint.curve_helper": "Стрелки меняют выбор. Enter подтверждает. Esc возвращает к выбору домена.",
        "hint.toggle_language": "F2 или L переключает язык.",
        "hint.return_toggle": "Enter возвращает назад. F2 или L переключает язык.",
        "screen.advanced.title": "РАСШИРЕННЫЕ РЕЖИМЫ",
        "screen.advanced.subtitle": "Внутренние и служебные экраны остаются доступными, но главный цикл остаётся простым: язык, кривая, идея, запуск, отчёт.",
        "screen.new_session.title": "НОВАЯ СЕССИЯ",
        "screen.new_session.subtitle": "Свободная идея остаётся основой. Подсказки лишь добавляют контекст.",
        "screen.replay.title": "ПОВТОР СЕССИИ",
        "screen.replay.subtitle": "Режим просмотра только проверяет сохранённые данные запуска. Повторный запуск создаёт новую локальную сессию.",
        "screen.routing.title": "МАРШРУТИЗАЦИЯ LLM",
        "screen.routing.subtitle": "По умолчанию все роли используют общий провайдер и модель. Отдельные настройки по ролям остаются для продвинутых сценариев.",
        "screen.tools.title": "РЕЕСТР ИНСТРУМЕНТОВ",
        "screen.tools.subtitle": "Доступные локальные инструменты, подключённые к ограниченному исполнителю и системе плагинов.",
        "screen.curves.title": "РЕЕСТР КРИВЫХ",
        "screen.curves.subtitle": "Поддерживаемые кривые, алиасы, семейства и ECC-метаданные для локальных проверок.",
        "screen.curve_helper.title": "ВСПОМОГАТЕЛЬНАЯ КРИВАЯ",
        "screen.curve_helper.subtitle": "Подсказка даёт контекст, но не заменяет исходную идею.",
        "screen.seed_input.title": "ИСХОДНАЯ ИДЕЯ",
        "screen.seed_input.subtitle": "Опишите локальный ограниченный вопрос, который сессия должна исследовать.",
        "screen.session_complete.title": "СЕССИЯ ЗАВЕРШЕНА",
        "screen.session_complete.subtitle": "Доказательная база, файлы трассировки и артефакты сохранены локально.",
        "screen.replay_result.title": "РЕЗУЛЬТАТ ПОВТОРА",
        "screen.replay_result.subtitle": "Повтор сохраняет исходные данные запуска. Режим просмотра ничего не исполняет, а повторный запуск создаёт новую локальную сессию.",
        "block.session_workflow": "СХЕМА СЕССИИ",
        "block.run_stages": "ЭТАПЫ ВЫПОЛНЕНИЯ",
        "block.tool_summary": "СВОДКА ИНСТРУМЕНТОВ",
        "block.routing_summary": "СВОДКА МАРШРУТИЗАЦИИ",
        "block.curve_summary": "СВОДКА КРИВЫХ",
        "block.helper_curve_context": "КОНТЕКСТ КРИВОЙ",
        "block.run_summary": "СВОДКА СЕССИИ",
        "block.local_outputs": "ЛОКАЛЬНЫЕ ФАЙЛЫ",
        "block.replay_summary": "СВОДКА ПОВТОРА",
        "block.replay_outputs": "ФАЙЛЫ ПОВТОРА",
        "block.replay_notes": "ПРИМЕЧАНИЯ",
        "block.summary": "ИТОГ",
        "block.confidence_rationale": "КАЛИБРОВКА УВЕРЕННОСТИ",
        "block.contract_overview": "ОБЗОР КОНТРАКТА",
        "block.contract_inventory": "ИНВЕНТАРИЗАЦИЯ КОНТРАКТОВ",
        "block.contract_protocol_map": "КАРТА ПРОТОКОЛА",
        "block.contract_protocol_invariants": "ИНВАРИАНТЫ ПРОТОКОЛА",
        "block.contract_signal_consensus": "СОГЛАСОВАННОСТЬ СИГНАЛОВ",
        "block.contract_validation_matrix": "МАТРИЦА ВАЛИДАЦИИ",
        "block.contract_benchmark_posture": "BENCHMARK-СТАТУС",
        "block.contract_benchmark_pack_summary": "СВОДКА BENCHMARK-ПАКЕТА",
        "block.contract_benchmark_case_summaries": "СВОДКА ПО BENCHMARK-КЕЙСАМ",
        "block.contract_repo_priorities": "ПРИОРИТЕТЫ ПО РЕПОЗИТОРИЮ",
        "block.contract_repo_triage": "ТРИАЖ ПО РЕПОЗИТОРИЮ",
        "block.contract_casebook_coverage": "ПОКРЫТИЕ CASEBOOK",
        "block.contract_casebook_coverage_matrix": "МАТРИЦА ПОКРЫТИЯ CASEBOOK",
        "block.contract_casebook_case_studies": "СВОДКА ПО CASE STUDY",
        "block.contract_casebook_priority_cases": "КЛЮЧЕВЫЕ CASEBOOK-КЕЙСЫ",
        "block.contract_casebook_gaps": "ПРОБЕЛЫ CASEBOOK",
        "block.contract_casebook_benchmark_support": "BENCHMARK-СТАТУС CASEBOOK",
        "block.contract_casebook_triage": "ТРИАЖ CASEBOOK",
        "block.contract_toolchain_alignment": "СВЯЗКА ИНСТРУМЕНТОВ",
        "block.contract_review_queue": "ОЧЕРЕДЬ ПРОВЕРКИ",
        "block.contract_compile": "СТАТУС КОМПИЛЯЦИИ",
        "block.contract_surface": "ПОВЕРХНОСТЬ КОНТРАКТА",
        "block.contract_priority_findings": "ПРИОРИТЕТНЫЕ СИГНАЛЫ",
        "block.contract_finding_cards": "КАРТОЧКИ НАХОДОК",
        "block.contract_static_findings": "СТАТИЧЕСКИЕ НАХОДКИ",
        "block.contract_testbeds": "ТЕСТОВЫЕ КОНТРАКТЫ",
        "block.contract_remediation_validation": "ПРОВЕРКА ЗАЩИТНОЙ ДОРАБОТКИ",
        "block.contract_review_focus": "ФОКУС ПРОВЕРКИ",
        "block.contract_remediation_guidance": "ЗАЩИТНЫЕ ДОРАБОТКИ",
        "block.contract_remediation_follow_up": "ПОВТОРНАЯ ПРОВЕРКА ПОСЛЕ ДОРАБОТКИ",
        "block.contract_exit_criteria": "КРИТЕРИИ ЗАВЕРШЕНИЯ",
        "block.contract_manual_review": "РУЧНАЯ ПРОВЕРКА КОНТРАКТА",
        "block.agent_contributions": "ВКЛАД АГЕНТОВ",
        "block.local_experiments": "ЛОКАЛЬНЫЕ ЭКСПЕРИМЕНТЫ",
        "block.local_signals": "ЛОКАЛЬНЫЕ СИГНАЛЫ",
        "block.dead_ends": "ТУПИКОВЫЕ ВЕТКИ",
        "block.next_defensive_leads": "СЛЕДУЮЩИЕ ЗАЩИТНЫЕ НАПРАВЛЕНИЯ",
        "block.tested_hypotheses": "ПРОВЕРЕННЫЕ ГИПОТЕЗЫ",
        "block.tool_usage": "ИСПОЛЬЗОВАНИЕ ИНСТРУМЕНТОВ",
        "block.comparative_findings": "СРАВНИТЕЛЬНЫЕ ВЫВОДЫ",
        "block.anomalies": "АНОМАЛИИ",
        "block.recommendations": "РЕКОМЕНДАЦИИ",
        "block.manual_review_items": "ТРЕБУЕТСЯ РУЧНАЯ ПРОВЕРКА",
        "workflow.entry_mode.label": "ТОЧКА ВХОДА",
        "workflow.entry_mode.value": "Свободная идея с необязательной подсказкой по кривой.",
        "workflow.entry_mode.value.ecc": "Свободная идея с необязательной подсказкой по кривой.",
        "workflow.entry_mode.value.smart_contract": "Код контракта из файла или вставки плюс свободная идея аудита.",
        "workflow.local_execution.label": "ЛОКАЛЬНОЕ ИСПОЛНЕНИЕ",
        "workflow.local_execution.value": "Инструменты запускаются только через утверждённый реестр и локальный исполнитель.",
        "workflow.run_outputs.label": "ФАЙЛЫ ЗАПУСКА",
        "workflow.run_outputs.value": "файл session.json, файл trace.jsonl, пакет воспроизводимости и сравнительный отчёт.",
        "stage.1": "[1/4] Формализация исследовательской идеи",
        "stage.2": "[2/4] Развитие и критика гипотез",
        "stage.3": "[3/4] Выполнение утверждённых локальных инструментов",
        "stage.4": "[4/4] Фиксация доказательной базы и артефактов",
        "label.total_tools": "ИНСТРУМЕНТОВ ВСЕГО",
        "label.shared_provider": "ОБЩИЙ ПРОВАЙДЕР",
        "label.shared_model": "ОБЩАЯ МОДЕЛЬ",
        "label.routing_mode": "РЕЖИМ МАРШРУТИЗАЦИИ",
        "label.fallback_provider": "РЕЗЕРВНЫЙ ПРОВАЙДЕР",
        "label.built_in_tools": "ВСТРОЕННЫХ",
        "label.plugin_tools": "ПЛАГИННЫХ",
        "label.deterministic_tools": "ДЕТЕРМИНИР.",
        "label.known_curves": "КРИВЫХ ВСЕГО",
        "label.registered_aliases": "АЛИАСОВ",
        "label.curve_families": "СЕМЕЙСТВ",
        "label.on_curve_support": "ON-CURVE CHECK",
        "label.canonical_name": "КАНОНИЧЕСКОЕ ИМЯ",
        "label.aliases": "АЛИАСЫ",
        "label.family_usage": "СЕМЕЙСТВО / РОЛЬ",
        "label.description": "ОПИСАНИЕ",
        "label.session_id": "ID СЕССИИ",
        "label.helper_curve": "КРИВАЯ-ПОДСКАЗКА",
        "label.confidence": "УРОВЕНЬ УВЕРЕННОСТИ",
        "label.hypotheses_evidence": "ГИПОТЕЗЫ / ДОКАЗАТЕЛЬСТВА",
        "label.plugins": "ПЛАГИНЫ",
        "label.session_json": "ФАЙЛ СЕССИИ",
        "label.trace_jsonl": "ФАЙЛ ТРАССИРОВКИ",
        "label.bundle_directory": "КАТАЛОГ ПАКЕТА",
        "label.comparative_report": "СРАВНИТЕЛЬНЫЙ ОТЧЁТ",
        "label.source_type": "ТИП ИСТОЧНИКА",
        "label.source_path": "ПУТЬ ИСТОЧНИКА",
        "label.dry_run": "ТОЛЬКО ПРОСМОТР",
        "label.reexecuted": "ПОВТОРНЫЙ ЗАПУСК",
        "label.success": "УСПЕХ",
        "label.generated_session": "НОВАЯ СЕССИЯ",
        "label.generated_trace": "НОВАЯ ТРАССИРОВКА",
        "label.generated_bundle": "НОВЫЙ ПАКЕТ",
        "table.name": "ИНСТРУМЕНТ",
        "table.agent": "АГЕНТ",
        "table.provider": "ПРОВАЙДЕР",
        "table.model": "МОДЕЛЬ",
        "table.routing_mode": "РЕЖИМ",
        "table.category": "КАТЕГОРИЯ",
        "table.mode": "РЕЖИМ",
        "table.source": "ИСТОЧНИК",
        "table.description": "ОПИСАНИЕ",
        "table.curve": "КРИВАЯ",
        "table.family": "СЕМЕЙСТВО",
        "table.field": "ПОЛЕ",
        "table.usage": "ПРИМЕНЕНИЕ",
        "value.none": "нет",
        "value.auto": "авто",
        "value.shared": "общий",
        "value.override": "переопределение",
        "value.shared_default": "общий по умолчанию",
        "value.mixed_overrides": "смешанный с переопределениями",
        "value.unavailable": "недоступно",
        "curve_helper.auto.label": "АВТО / БЕЗ ПОДСКАЗКИ",
        "curve_helper.auto.desc": "Оставить только свободную идею и позволить системе самой определить фокус исследования.",
        "curve_helper.secp256k1.label": "SECP256K1",
        "curve_helper.secp256k1.desc": "Популярная короткая кривая Вейерштрасса для блокчейн- и подписи-подобных сценариев.",
        "curve_helper.secp256r1.label": "SECP256R1 / P-256",
        "curve_helper.secp256r1.desc": "Широко используемая стандартная кривая для подписей и работы с ключами.",
        "curve_helper.ed25519.label": "ED25519",
        "curve_helper.ed25519.desc": "Современное семейство Edwards для описательных и локальных ограниченных проверок.",
        "curve_helper.x25519.label": "X25519 / CURVE25519",
        "curve_helper.x25519.desc": "Семейство 25519 для обмена ключами, метаданных и проверок согласованности.",
        "replay.option.session.label": "ФАЙЛ СЕССИИ",
        "replay.option.session.desc": "Загрузить ранее сохранённый снимок исследовательской сессии.",
        "replay.option.manifest.label": "ФАЙЛ МАНИФЕСТА",
        "replay.option.manifest.desc": "Загрузить манифест запуска и восстановить консервативный план повтора.",
        "replay.option.bundle.label": "КАТАЛОГ ПАКЕТА",
        "replay.option.bundle.desc": "Загрузить пакет воспроизводимости с сессией, трассировкой и манифестом.",
        "replay.option.return.label": "НАЗАД",
        "replay.option.return.desc": "Вернуться в главное меню консоли.",
        "prompt.seed": "исходная идея >",
        "prompt.seed_hint": "Введите идею, которую агенты и локальные инструменты должны проверить локально. /lang переключает язык.",
        "prompt.author_optional": "автор (необязательно, Enter пропускает) >",
        "prompt.path": "путь (/lang переключает язык) >",
        "prompt.replay_author": "автор для повтора (необязательно) >",
        "prompt.dry_run": "только просмотр? [д/Н]",
        "prompt.pause": "Нажмите Enter, чтобы продолжить...",
        "message.seed_required": "Для запуска сессии требуется исходная идея.",
        "message.input_rejected": "Ввод отклонён: {error}",
        "message.replay_path_required": "Нужно указать путь к источнику повтора.",
        "message.replay_rejected": "Повтор отклонён: {error}",
        "report.summary": "Краткий вывод",
        "report.confidence_rationale": "Калибровка уверенности",
        "report.contract_overview": "Обзор контракта",
        "report.contract_inventory": "Инвентаризация контрактов",
        "report.contract_protocol_map": "Карта протокола",
        "report.contract_protocol_invariants": "Инварианты протокола",
        "report.contract_signal_consensus": "Согласованность сигналов",
        "report.contract_validation_matrix": "Матрица валидации",
        "report.contract_benchmark_posture": "Benchmark-статус",
        "report.contract_benchmark_pack_summary": "Сводка benchmark-пакета",
        "report.contract_benchmark_case_summaries": "Сводка по benchmark-кейсам",
        "report.contract_repo_priorities": "Приоритеты по репозиторию",
        "report.contract_repo_triage": "Триаж по репозиторию",
        "report.contract_casebook_coverage": "Покрытие casebook",
        "report.contract_casebook_coverage_matrix": "Матрица покрытия casebook",
        "report.contract_casebook_case_studies": "Сводка по case study",
        "report.contract_casebook_priority_cases": "Ключевые casebook-кейсы",
        "report.contract_casebook_gaps": "Пробелы casebook",
        "report.contract_casebook_benchmark_support": "Benchmark-статус casebook",
        "report.contract_casebook_triage": "Триаж casebook",
        "report.contract_toolchain_alignment": "Связка инструментов",
        "report.contract_review_queue": "Очередь проверки",
        "report.contract_compile": "Статус компиляции",
        "report.contract_surface": "Поверхность контракта",
        "report.contract_priority_findings": "Приоритетные сигналы",
        "report.contract_finding_cards": "Карточки находок",
        "report.contract_static_findings": "Статические находки",
        "report.contract_testbeds": "Тестовые контракты",
        "report.contract_remediation_validation": "Проверка защитной доработки",
        "report.contract_review_focus": "Фокус проверки",
        "report.contract_remediation_guidance": "Защитные доработки",
        "report.contract_remediation_follow_up": "Повторная проверка после доработки",
        "report.contract_exit_criteria": "Критерии завершения",
        "report.contract_manual_review": "Ручная проверка контракта",
        "report.tested_hypotheses": "Проверенные гипотезы",
        "report.tool_usage": "Использование инструментов",
        "report.comparative_findings": "Сравнительные выводы",
        "report.anomalies": "Аномалии",
        "report.recommendations": "Рекомендации",
        "report.manual_review_items": "Требуется ручная проверка",
        "report.session_id": "ID сессии",
        "report.stored_session": "Сохранённый файл сессии",
        "report.stored_trace": "Сохранённый файл трассировки",
        "report.bundle": "Пакет воспроизводимости",
        "report.comparative_analysis": "Сравнительный анализ",
        "report.comparative_generated": "сгенерирован",
        "report.comparative_limited": "ограничен",
        "report.comparative_report": "Сравнительный отчёт",
        "report.plugins": "Плагины",
        "report.confidence": "Уровень уверенности",
        "replay.replay_id": "ID повтора",
        "replay.replay_source": "Источник повтора",
        "replay.replay_path": "Путь к источнику",
        "replay.replay_session": "Исходная сессия",
        "replay.generated_session": "Новый файл сессии",
        "replay.generated_trace": "Новый файл трассировки",
        "replay.generated_bundle": "Новый пакет",
        "replay.notes": "Примечания",
        "menu.doctor.label": "ПРОВЕРКА СИСТЕМЫ",
        "menu.doctor.desc": "Проверить готовность провайдера, инструментов, плагинов, локальных путей, компиляторных адаптеров, статического анализа и Sage.",
        "screen.doctor.title": "ПРОВЕРКА СИСТЕМЫ",
        "screen.doctor.subtitle": "Локальная проверка провайдера, реестра инструментов, плагинов, путей хранения, компиляторных адаптеров, статического анализа и состояния Sage.",
        "block.doctor_summary": "СВОДКА СИСТЕМЫ",
        "label.overall_status": "ОБЩИЙ СТАТУС",
        "label.active_provider": "АКТИВНЫЙ ПРОВАЙДЕР",
        "label.registry_tools": "ИНСТРУМЕНТОВ В РЕЕСТРЕ",
        "label.loaded_plugins": "ЗАГРУЖЕННЫЕ ПЛАГИНЫ",
        "label.failed_plugins": "ОШИБКИ ПЛАГИНОВ",
        "value.enabled": "включено",
        "value.disabled": "выключено",
        "doctor.report_id": "ID отчёта проверки",
        "doctor.overall_status": "Общий статус",
        "doctor.summary_label": "Итог",
        "doctor.status.ok": "норма",
        "doctor.status.warning": "внимание",
        "doctor.status.error": "ошибка",
        "doctor.status.info": "справка",
        "doctor.summary.ok": "Проверка готовности пройдена. Ключевые локальные сценарии готовы к работе.",
        "doctor.summary.warning": "Проверка готовности пройдена с предупреждениями. Основной контур остаётся рабочим, но есть места, требующие внимания.",
        "doctor.summary.error": "Проверка готовности нашла блокирующие проблемы. Перед нормальным запуском их нужно исправить.",
        "doctor.summary.info": "Проверка готовности завершена справочными пометками.",
        "doctor.check.provider.title": "Конфигурация провайдера",
        "doctor.check.provider.mock": "Активен режим mock, поэтому локальные проверочные сценарии готовы без внешних API-ключей.",
        "doctor.check.provider.ready": "Для провайдера '{provider}' доступен требуемый API-ключ.",
        "doctor.check.provider.missing_key": "Для провайдера '{provider}' не найден требуемый API-ключ из '{env}'.",
        "doctor.check.provider.unknown": "Провайдер '{provider}' неизвестен текущему контуру маршрутизации.",
        "doctor.check.registry.title": "Реестр инструментов",
        "doctor.check.registry.ready": "Утверждённый локальный реестр инструментов заполнен и готов: {count} инструментов.",
        "doctor.check.registry.missing": "В утверждённом реестре не хватает {count} обязательных встроенных инструментов.",
        "doctor.check.plugins.title": "Загрузка плагинов",
        "doctor.check.plugins.loaded": "Через ограниченный адаптер реестра загружено {count} локальных плагинов.",
        "doctor.check.plugins.none": "Загрузка плагинов включена, но локальные плагины не обнаружены.",
        "doctor.check.plugins.failed": "Не удалось загрузить {failed} плагин(ов), при этом {loaded} плагин(ов) загружено успешно.",
        "doctor.check.plugins.disabled": "Локальная загрузка плагинов отключена текущей конфигурацией.",
        "doctor.check.storage.title": "Локальные пути и воспроизводимость",
        "doctor.check.storage.ready": "Каталоги сессий, трассировок, пакетов и математических артефактов доступны для записи.",
        "doctor.check.storage.failed": "Один или несколько локальных каталогов недоступны для записи.",
        "doctor.check.sage.title": "Расширенная математика / Sage",
        "doctor.check.sage.available": "Расширенная математика включена, и бинарник Sage '{binary}' доступен локально.",
        "doctor.check.sage.unavailable": "Расширенная математика включена, но бинарник Sage '{binary}' локально не найден. Детерминированные резервные пути при этом остаются доступны.",
        "doctor.check.sage.disabled": "Расширенная математика включена, но интеграция с Sage отключена в конфигурации.",
        "doctor.check.sage.advanced_math_disabled": "Расширенная математика отключена в конфигурации.",
        "doctor.check.contract_compiler.title": "Компилятор смарт-контрактов",
        "doctor.check.contract_compiler.available": "Локальный адаптер компиляции Solidity готов к работе через '{binary}'.",
        "doctor.check.contract_compiler.unavailable": "Совместимый с solc локальный компилятор не найден ни в PATH, ни в управляемом контуре проекта. Проверки компиляции пока недоступны.",
        "doctor.check.contract_compiler.disabled": "Локальные проверки компиляции смарт-контрактов отключены в текущей конфигурации.",
        "doctor.check.slither.title": "Статический анализатор смарт-контрактов",
        "doctor.check.slither.available": "Локальный статический анализатор на базе Slither готов к работе через '{binary}'.",
        "doctor.check.slither.unavailable": "Адаптер Slither или требуемый локальный Solidity-компилятор недоступен, поэтому внешние статические проверки пока недоступны.",
        "doctor.check.slither.disabled": "Локальный анализ смарт-контрактов на базе Slither отключён в текущей конфигурации.",
        "doctor.check.echidna.title": "Адаптер Echidna для смарт-контрактов",
        "doctor.check.echidna.available": "Локальный адаптер Echidna готов к работе через '{binary}'.",
        "doctor.check.echidna.unavailable": "Адаптер Echidna или требуемый локальный Solidity-компилятор недоступен, поэтому фаззинг инвариантов и проверки утверждений пока недоступны.",
        "doctor.check.echidna.disabled": "Локальный фаззинг смарт-контрактов через Echidna отключён в текущей конфигурации.",
        "doctor.check.foundry.title": "Адаптер Foundry для смарт-контрактов",
        "doctor.check.foundry.available": "Локальный адаптер Foundry/Forge готов к работе через '{binary}'.",
        "doctor.check.foundry.unavailable": "Адаптер Foundry или требуемый локальный Solidity-компилятор недоступен, поэтому проверки через Forge пока недоступны.",
        "doctor.check.foundry.disabled": "Локальный анализ смарт-контрактов через Foundry/Forge отключён в текущей конфигурации.",
        "doctor.check.local_research.title": "Локальные исследовательские адаптеры",
        "doctor.check.local_research.ready": "Слой локальных исследовательских адаптеров готов к ограниченным экспериментам в песочнице.",
        "doctor.check.local_research.partial": "Часть опциональных локальных исследовательских адаптеров недоступна, но лаборатория остаётся частично готовой.",
        "doctor.directory.ready": "готово",
        "doctor.directory.failed": "не готово",
        "doctor.detail.default_provider": "Базовый провайдер: {value}",
        "doctor.detail.default_model": "Базовая модель: {value}",
        "doctor.detail.fallback_provider": "Резервный провайдер: {value}",
        "doctor.detail.api_env": "Переменная окружения для API-ключа: {value}",
        "doctor.detail.smart_contract_compile_enabled": "Проверки компиляции смарт-контрактов: {value}",
        "doctor.detail.managed_solc_dir": "Каталог управляемого solc: {value}",
        "doctor.detail.managed_solc_version": "Предпочтительная версия управляемого solc: {value}",
        "doctor.detail.solc_binary": "Предпочитаемый бинарник solc: {value}",
        "doctor.detail.solcjs_binary": "Резервный бинарник solcjs: {value}",
        "doctor.detail.contract_compile_timeout": "Таймаут компилятора (с): {value}",
        "doctor.detail.installed_managed_compilers": "Установленные управляемые компиляторы: {value}",
        "doctor.detail.resolved_managed_compiler_binary": "Найденный управляемый бинарник компилятора: {value}",
        "doctor.detail.resolved_managed_compiler_version": "Найденная версия управляемого компилятора: {value}",
        "doctor.detail.resolved_compiler_binary": "Найденный бинарник компилятора: {value}",
        "doctor.detail.compiler_version": "Версия компилятора: {value}",
        "doctor.detail.slither_enabled": "Анализ через Slither: {value}",
        "doctor.detail.slither_binary": "Предпочитаемый бинарник Slither: {value}",
        "doctor.detail.slither_timeout": "Таймаут Slither (с): {value}",
        "doctor.detail.echidna_enabled": "Фаззинг через Echidna: {value}",
        "doctor.detail.echidna_binary": "Предпочитаемый бинарник Echidna: {value}",
        "doctor.detail.echidna_timeout": "Таймаут Echidna (с): {value}",
        "doctor.detail.echidna_test_limit": "Лимит тестов Echidna: {value}",
        "doctor.detail.echidna_seq_len": "Длина последовательности Echidna: {value}",
        "doctor.detail.foundry_enabled": "Анализ через Foundry: {value}",
        "doctor.detail.forge_binary": "Предпочитаемый бинарник Forge: {value}",
        "doctor.detail.foundry_timeout": "Таймаут Foundry (с): {value}",
        "doctor.detail.resolved_analyzer_binary": "Найденный бинарник анализатора: {value}",
        "doctor.detail.analyzer_version": "Версия анализатора: {value}",
        "doctor.detail.total_tools": "Всего инструментов: {value}",
        "doctor.detail.built_in_tools": "Встроенных инструментов: {value}",
        "doctor.detail.plugin_tools": "Плагинных инструментов: {value}",
        "doctor.detail.deterministic_tools": "Детерминированных инструментов: {value}",
        "doctor.detail.synthetic_targets": "Синтетические цели: {value}",
        "doctor.detail.experiment_packs": "Экспериментальные пакеты: {value}",
        "doctor.detail.required_tools": "Обязательные встроенные инструменты: {value}",
        "doctor.detail.missing_tools": "Отсутствующие встроенные инструменты: {value}",
        "doctor.detail.plugin_directory": "Каталог плагинов: {value}",
        "doctor.detail.loaded_plugins": "Загруженные плагины: {value}",
        "doctor.detail.failed_plugins": "Плагины с ошибкой: {value}",
        "doctor.detail.failed_plugin_note": "Плагин {plugin}: {note}",
        "doctor.detail.disabled_by_config": "Загрузка плагинов отключена конфигурацией.",
        "doctor.detail.directory_status": "{name}: {path} ({status})",
        "doctor.detail.storage_failures": "Ошибки хранения: {value}",
        "doctor.detail.advanced_math": "Расширенная математика: {value}",
        "doctor.detail.sage_enabled": "Интеграция с Sage: {value}",
        "doctor.detail.sage_binary": "Бинарник Sage: {value}",
        "doctor.detail.sage_timeout": "Таймаут Sage (с): {value}",
        "cli.enter_idea": "Введите исходную идею: ",
        "cli.error.choose_one_replay": "Повтор отклонён: выберите только один источник повтора.\n",
        "cli.error.replay_and_idea": "Повтор отклонён: не совмещайте новую идею с аргументами повтора.\n",
        "cli.error.doctor_and_replay": "Проверка системы отклонена: не совмещайте --doctor с аргументами повтора.\n",
        "cli.error.doctor_and_idea": "Проверка системы отклонена: не совмещайте --doctor с новой идеей.\n",
        "cli.error.doctor_and_interactive": "Проверка системы отклонена: для прямого отчёта используйте --doctor, а в интерактивной консоли выберите пункт ПРОВЕРКА СИСТЕМЫ.\n",
        "cli.error.replay_rejected": "Повтор отклонён: {error}\n",
        "cli.error.input_rejected": "Ввод отклонён: {error}\n",
        "live_smoke.title": "Проверка внешнего провайдера",
        "live_smoke.provider": "Провайдер",
        "live_smoke.model": "Модель",
        "live_smoke.result": "Результат",
        "list.synthetic_targets.title": "Встроенные синтетические исследовательские цели",
        "list.experiment_packs.title": "Встроенные экспериментальные пакеты",
    },
}

TRANSLATIONS["ru"].update(
    {
        "hint.domain_select": "Стрелки меняют выбор. Enter подтверждает. Esc возвращает назад.",
        "screen.domain.title": "ДОМЕН ИССЛЕДОВАНИЯ",
        "screen.domain.subtitle": "Выберите, запускается ли ограниченная сессия как ECC-исследование или как аудит смарт-контракта.",
        "screen.contract_source.title": "ИСТОЧНИК КОНТРАКТА",
        "screen.contract_source.subtitle": "Перетащите локальный файл, вставьте путь к файлу или код контракта. Solidity/Vyper определяется автоматически.",
        "workflow.domain.label": "ДОМЕН",
        "workflow.domain.value.ecc": "ECC-исследование",
        "workflow.domain.value.smart_contract": "Аудит смарт-контрактов",
        "domain.ecc.label": "ECC-ИССЛЕДОВАНИЕ",
        "domain.ecc.desc": "Кривые, точки, символические проверки и согласованность конечных полей в локальной песочнице.",
        "domain.smart_contract.label": "АУДИТ СМАРТ-КОНТРАКТОВ",
        "domain.smart_contract.desc": "Локальный статический аудит кода контракта, рискованных поверхностей и ограниченных шаблонов проверки.",
        "prompt.contract.idea": "идея аудита (/lang переключает язык) >",
        "prompt.contract.file": "путь, файл или сниппет кода (/back, /cancel, /lang) >",
        "prompt.contract.input_hint": "Перетащите локальный файл, вставьте путь, вставьте однострочный сниппет или нажмите Enter для многострочного ввода. /back возвращает назад. /cancel отменяет сессию. /lang переключает язык.",
        "prompt.contract.paste_hint": "Вставьте код контракта ниже. Пустая строка завершает ввод. /back возвращает назад. /cancel отменяет сессию. /lang переключает язык.",
        "message.contract_path_invalid": "Файл контракта не найден: {path}",
        "message.contract_code_required": "Для вставки нужен код смарт-контракта.",
        "message.contract_source_invalid": "Ввод не распознан как читаемый путь к файлу или сниппет кода контракта.",
    }
)

TRANSLATIONS["en"]["prompt.contract.paste_hint"] = (
    "Paste contract code below. /done finishes. /back returns. "
    "/cancel leaves the session. /lang switches language."
)
TRANSLATIONS["en"]["prompt.contract.file"] = "file path or code (/back, /cancel, /lang) >"
TRANSLATIONS["en"]["prompt.contract.input_hint"] = (
    "Drop a file, paste a path, or press Enter for multiline code. "
    "/back returns. /cancel leaves the session. /lang switches language."
)
TRANSLATIONS["ru"]["prompt.contract.paste_hint"] = (
    "Вставьте код контракта ниже. /done завершает ввод. "
    "/back возвращает назад. /cancel отменяет сессию. /lang переключает язык."
)
TRANSLATIONS["ru"]["prompt.contract.file"] = "путь к файлу или код (/back, /cancel, /lang) >"
TRANSLATIONS["ru"]["prompt.contract.input_hint"] = (
    "Перетащите файл, вставьте путь или нажмите Enter для многострочного кода. "
    "/back возвращает назад. /cancel отменяет сессию. /lang переключает язык."
)
TRANSLATIONS["ru"]["block.contract_inventory"] = "ИНВЕНТАРИЗАЦИЯ КОНТРАКТОВ"
TRANSLATIONS["ru"]["report.contract_inventory"] = "Инвентаризация контрактов"

TRANSLATIONS["ru"]["block.contract_residual_risk"] = "ОСТАТОЧНЫЙ РИСК"
TRANSLATIONS["ru"]["report.contract_residual_risk"] = "Остаточный риск"

TRANSLATIONS["ru"]["block.ecc_benchmark_summary"] = "ECC-БЕНЧМАРК"
TRANSLATIONS["ru"]["block.ecc_review_focus"] = "ФОКУС ECC-ПРОВЕРКИ"
TRANSLATIONS["ru"]["block.ecc_residual_risk"] = "ОСТАТОЧНЫЙ ECC-РИСК"
TRANSLATIONS["ru"]["block.ecc_signal_consensus"] = "СОГЛАСОВАННОСТЬ ECC-СИГНАЛОВ"
TRANSLATIONS["ru"]["block.ecc_validation_matrix"] = "МАТРИЦА ECC-ВАЛИДАЦИИ"
TRANSLATIONS["ru"]["block.ecc_comparison_focus"] = "ECC-СРАВНЕНИЕ ДО / ПОСЛЕ"
TRANSLATIONS["ru"]["report.ecc_benchmark_summary"] = "ECC-бенчмарк"
TRANSLATIONS["ru"]["report.ecc_review_focus"] = "Фокус ECC-проверки"
TRANSLATIONS["ru"]["report.ecc_residual_risk"] = "Остаточный ECC-риск"
TRANSLATIONS["ru"]["report.ecc_signal_consensus"] = "Согласованность ECC-сигналов"
TRANSLATIONS["ru"]["report.ecc_validation_matrix"] = "Матрица ECC-валидации"
TRANSLATIONS["ru"]["report.ecc_comparison_focus"] = "ECC-сравнение до / после"
TRANSLATIONS["ru"]["doctor.check.provider_smoke.title"] = "Путь проверочного запуска внешнего провайдера"
TRANSLATIONS["ru"]["doctor.check.provider_smoke.mock"] = "Активен режим mock: внешний проверочный запуск будет доступен после выбора внешнего провайдера и ключа API."
TRANSLATIONS["ru"]["doctor.check.provider_smoke.ready"] = "Путь проверочного запуска для провайдера '{provider}' готов к ограниченной live-проверке."
TRANSLATIONS["ru"]["doctor.check.provider_smoke.missing_key"] = "Путь проверочного запуска для провайдера '{provider}' не готов, пока не доступен '{env}'."
TRANSLATIONS["ru"]["doctor.detail.live_smoke_command"] = "Команда проверочного запуска: {value}"
TRANSLATIONS["ru"]["doctor.detail.smoke_timeout"] = "Тайм-аут проверочного запуска (с): {value}"
TRANSLATIONS["ru"]["doctor.detail.smoke_max_tokens"] = "Максимум токенов в проверочном запуске: {value}"
TRANSLATIONS["ru"]["live_smoke.timeout"] = "Тайм-аут (с)"
TRANSLATIONS["ru"]["live_smoke.max_request_tokens"] = "Максимум токенов"

TRANSLATIONS["en"]["block.before_after_comparison"] = "BEFORE / AFTER COMPARISON"
TRANSLATIONS["en"]["block.regression_flags"] = "REGRESSION FLAGS"
TRANSLATIONS["en"]["report.before_after_comparison"] = "Before / After Comparison"
TRANSLATIONS["en"]["report.regression_flags"] = "Regression Flags"
TRANSLATIONS["ru"]["block.before_after_comparison"] = "СРАВНЕНИЕ ДО / ПОСЛЕ"
TRANSLATIONS["ru"]["block.regression_flags"] = "ФЛАГИ РЕГРЕССИЙ"
TRANSLATIONS["ru"]["report.before_after_comparison"] = "Сравнение до / после"
TRANSLATIONS["ru"]["report.regression_flags"] = "Флаги регрессий"


TRANSLATIONS["en"]["block.evidence_profile"] = "EVIDENCE PROFILE"
TRANSLATIONS["en"]["block.calibration_blockers"] = "CALIBRATION BLOCKERS"
TRANSLATIONS["en"]["block.reproducibility_summary"] = "REPRODUCIBILITY SUMMARY"
TRANSLATIONS["en"]["block.ecc_benchmark_delta"] = "ECC BENCHMARK DELTA"
TRANSLATIONS["en"]["report.evidence_profile"] = "Evidence Profile"
TRANSLATIONS["en"]["report.calibration_blockers"] = "Calibration Blockers"
TRANSLATIONS["en"]["report.reproducibility_summary"] = "Reproducibility Summary"
TRANSLATIONS["en"]["report.ecc_benchmark_delta"] = "ECC Benchmark Delta"
TRANSLATIONS["ru"]["block.evidence_profile"] = "ПРОФИЛЬ ДОКАЗАТЕЛЬСТВ"
TRANSLATIONS["ru"]["block.calibration_blockers"] = "ОГРАНИЧИТЕЛИ КАЛИБРОВКИ"
TRANSLATIONS["ru"]["block.reproducibility_summary"] = "СВОДКА ВОСПРОИЗВОДИМОСТИ"
TRANSLATIONS["ru"]["block.ecc_benchmark_delta"] = "ИЗМЕНЕНИЕ ECC-БЕНЧМАРКА"
TRANSLATIONS["ru"]["report.evidence_profile"] = "Профиль доказательств"
TRANSLATIONS["ru"]["report.calibration_blockers"] = "Ограничители калибровки"
TRANSLATIONS["ru"]["report.reproducibility_summary"] = "Сводка воспроизводимости"
TRANSLATIONS["ru"]["report.ecc_benchmark_delta"] = "Изменение ECC-бенчмарка"

TRANSLATIONS["en"]["block.validation_posture"] = "VALIDATION POSTURE"
TRANSLATIONS["en"]["block.shared_follow_up"] = "SHARED FOLLOW-UP"
TRANSLATIONS["en"]["block.ecc_review_queue"] = "ECC REVIEW QUEUE"
TRANSLATIONS["en"]["block.ecc_exit_criteria"] = "ECC EXIT CRITERIA"
TRANSLATIONS["en"]["report.validation_posture"] = "Validation Posture"
TRANSLATIONS["en"]["report.shared_follow_up"] = "Shared Follow-Up"
TRANSLATIONS["en"]["report.ecc_review_queue"] = "ECC Review Queue"
TRANSLATIONS["en"]["report.ecc_exit_criteria"] = "ECC Exit Criteria"
TRANSLATIONS["ru"]["block.validation_posture"] = "ПОЗИЦИЯ ВАЛИДАЦИИ"
TRANSLATIONS["ru"]["block.shared_follow_up"] = "ОБЩИЙ ПОСЛЕДУЮЩИЙ ШАГ"
TRANSLATIONS["ru"]["block.ecc_review_queue"] = "ОЧЕРЕДЬ ECC-ПРОВЕРКИ"
TRANSLATIONS["ru"]["block.ecc_exit_criteria"] = "УСЛОВИЯ ЗАВЕРШЕНИЯ ECC"
TRANSLATIONS["ru"]["report.validation_posture"] = "Позиция валидации"
TRANSLATIONS["ru"]["report.shared_follow_up"] = "Общий последующий шаг"
TRANSLATIONS["ru"]["report.ecc_review_queue"] = "Очередь ECC-проверки"
TRANSLATIONS["ru"]["report.ecc_exit_criteria"] = "Условия завершения ECC"
TRANSLATIONS["en"]["doctor.check.plugins.blocked"] = "{blocked} plugin(s) were blocked by bounded local safety checks while {loaded} plugin(s) loaded successfully."
TRANSLATIONS["en"]["doctor.detail.local_plugin_policy"] = "Local plugin policy enabled: {value}"
TRANSLATIONS["en"]["doctor.detail.plugin_safety_gate"] = "Unsafe plugin path layouts, symlinks, and out-of-root files are blocked by the bounded local safety gate."
TRANSLATIONS["en"]["doctor.detail.plugin_safety_failures"] = "Blocked plugin paths: {value}"
TRANSLATIONS["en"]["doctor.detail.export_roots"] = "Approved export roots: {value}"
TRANSLATIONS["en"]["doctor.detail.export_policy"] = "Bundle export copies only session snapshots, traces, and artifact references that resolve inside approved local storage roots."
TRANSLATIONS["ru"]["doctor.check.plugins.blocked"] = "{blocked} плагин(ов) были заблокированы ограниченной локальной проверкой безопасности, при этом {loaded} плагин(ов) загружено успешно."
TRANSLATIONS["ru"]["doctor.detail.local_plugin_policy"] = "Политика локальных плагинов включена: {value}"
TRANSLATIONS["ru"]["doctor.detail.plugin_safety_gate"] = "Небезопасные пути плагинов, симлинки и файлы вне корневого каталога блокируются ограниченной локальной проверкой безопасности."
TRANSLATIONS["ru"]["doctor.detail.plugin_safety_failures"] = "Заблокированные пути плагинов: {value}"
TRANSLATIONS["ru"]["doctor.detail.export_roots"] = "Разрешённые корни экспорта: {value}"
TRANSLATIONS["ru"]["doctor.detail.export_policy"] = "При экспорте пакета копируются только те снимки сессий, трассы и ссылки на артефакты, которые разрешаются внутри утверждённых локальных каталогов хранения."

TRANSLATIONS["en"]["block.quality_gates"] = "QUALITY GATES"
TRANSLATIONS["en"]["block.hardening_summary"] = "HARDENING SUMMARY"
TRANSLATIONS["en"]["block.ecc_benchmark_posture"] = "ECC BENCHMARK POSTURE"
TRANSLATIONS["en"]["block.ecc_family_coverage"] = "ECC FAMILY COVERAGE"
TRANSLATIONS["en"]["block.ecc_benchmark_case_summaries"] = "ECC BENCHMARK CASE SUMMARIES"
TRANSLATIONS["en"]["block.ecc_regression_summary"] = "ECC REGRESSION SUMMARY"
TRANSLATIONS["en"]["report.quality_gates"] = "Quality Gates"
TRANSLATIONS["en"]["report.hardening_summary"] = "Hardening Summary"
TRANSLATIONS["en"]["report.ecc_benchmark_posture"] = "ECC Benchmark Posture"
TRANSLATIONS["en"]["report.ecc_family_coverage"] = "ECC Family Coverage"
TRANSLATIONS["en"]["report.ecc_benchmark_case_summaries"] = "ECC Benchmark Case Summaries"
TRANSLATIONS["en"]["report.ecc_regression_summary"] = "ECC Regression Summary"
TRANSLATIONS["ru"]["block.quality_gates"] = "КРИТЕРИИ КАЧЕСТВА"
TRANSLATIONS["ru"]["block.hardening_summary"] = "СВОДКА ПО УКРЕПЛЕНИЮ"
TRANSLATIONS["ru"]["block.ecc_benchmark_posture"] = "ECC-БЕНЧМАРК: СТАТУС"
TRANSLATIONS["ru"]["block.ecc_family_coverage"] = "ПОКРЫТИЕ ECC-СЕМЕЙСТВ"
TRANSLATIONS["ru"]["block.ecc_benchmark_case_summaries"] = "СВОДКА ECC-БЕНЧМАРК-КЕЙСОВ"
TRANSLATIONS["ru"]["block.ecc_regression_summary"] = "ECC-РЕГРЕССИИ И ДЕЛЬТЫ"
TRANSLATIONS["ru"]["report.quality_gates"] = "Критерии качества"
TRANSLATIONS["ru"]["report.hardening_summary"] = "Сводка по укреплению"
TRANSLATIONS["ru"]["report.ecc_benchmark_posture"] = "ECC-бенчмарк: статус"
TRANSLATIONS["ru"]["report.ecc_family_coverage"] = "Покрытие ECC-семейств"
TRANSLATIONS["ru"]["report.ecc_benchmark_case_summaries"] = "Сводка ECC-бенчмарк-кейсов"
TRANSLATIONS["ru"]["report.ecc_regression_summary"] = "ECC-регрессии и дельты"

# Final runtime-safe overrides for labels that previously had mojibake in late appends.
TRANSLATIONS["en"]["report.research_mode"] = "Research Mode"
TRANSLATIONS["en"]["report.experiment_pack"] = "Experiment Pack"
TRANSLATIONS["en"]["report.recommended_packs"] = "Recommended Packs"
TRANSLATIONS["en"]["report.executed_pack_steps"] = "Executed Pack Steps"
TRANSLATIONS["ru"]["report.research_mode"] = "Режим исследования"
TRANSLATIONS["ru"]["report.experiment_pack"] = "Экспериментальный пакет"
TRANSLATIONS["ru"]["report.recommended_packs"] = "Рекомендуемые пакеты"
TRANSLATIONS["ru"]["report.executed_pack_steps"] = "Выполненные шаги пакета"

TRANSLATIONS["ru"]["block.contract_inventory"] = "ИНВЕНТАРИЗАЦИЯ КОНТРАКТОВ"
TRANSLATIONS["ru"]["report.contract_inventory"] = "Инвентаризация контрактов"
TRANSLATIONS["ru"]["block.contract_residual_risk"] = "ОСТАТОЧНЫЙ РИСК"
TRANSLATIONS["ru"]["report.contract_residual_risk"] = "Остаточный риск"
TRANSLATIONS["ru"]["block.validation_posture"] = "ПОЗИЦИЯ ВАЛИДАЦИИ"
TRANSLATIONS["ru"]["report.validation_posture"] = "Позиция валидации"
TRANSLATIONS["ru"]["block.shared_follow_up"] = "ОБЩИЙ ПОСЛЕДУЮЩИЙ ШАГ"
TRANSLATIONS["ru"]["report.shared_follow_up"] = "Общий последующий шаг"
TRANSLATIONS["ru"]["block.ecc_review_queue"] = "ОЧЕРЕДЬ ECC-ПРОВЕРКИ"
TRANSLATIONS["ru"]["report.ecc_review_queue"] = "Очередь ECC-проверки"
TRANSLATIONS["ru"]["block.ecc_exit_criteria"] = "УСЛОВИЯ ЗАВЕРШЕНИЯ ECC"
TRANSLATIONS["ru"]["report.ecc_exit_criteria"] = "Условия завершения ECC"
TRANSLATIONS["en"]["block.ecc_coverage_matrix"] = "ECC COVERAGE MATRIX"
TRANSLATIONS["en"]["report.ecc_coverage_matrix"] = "ECC Coverage Matrix"
TRANSLATIONS["ru"]["block.ecc_coverage_matrix"] = "ECC-МАТРИЦА ПОКРЫТИЯ"
TRANSLATIONS["ru"]["report.ecc_coverage_matrix"] = "ECC-матрица покрытия"


TRANSLATIONS["en"]["block.evidence_coverage_summary"] = "EVIDENCE COVERAGE"
TRANSLATIONS["en"]["block.toolchain_fingerprint"] = "TOOLCHAIN FINGERPRINT"
TRANSLATIONS["en"]["block.secret_redaction_summary"] = "SECRET REDACTION"
TRANSLATIONS["en"]["report.evidence_coverage_summary"] = "Evidence Coverage"
TRANSLATIONS["en"]["report.toolchain_fingerprint"] = "Toolchain Fingerprint"
TRANSLATIONS["en"]["report.secret_redaction_summary"] = "Secret Redaction"
TRANSLATIONS["ru"]["block.evidence_coverage_summary"] = "ДОКАЗАТЕЛЬНОЕ ПОКРЫТИЕ"
TRANSLATIONS["ru"]["block.toolchain_fingerprint"] = "ОТПЕЧАТОК TOOLCHAIN"
TRANSLATIONS["ru"]["block.secret_redaction_summary"] = "РЕДАКТИРОВАНИЕ СЕКРЕТОВ"
TRANSLATIONS["ru"]["report.evidence_coverage_summary"] = "Доказательное покрытие"
TRANSLATIONS["ru"]["report.toolchain_fingerprint"] = "Отпечаток toolchain"
TRANSLATIONS["ru"]["report.secret_redaction_summary"] = "Редактирование секретов"


TRANSLATIONS["en"]["report.contract_triage_snapshot"] = "Repo Triage Snapshot"
TRANSLATIONS["en"]["report.remediation_delta_summary"] = "Remediation Delta Summary"
TRANSLATIONS["en"]["report.ecc_triage_snapshot"] = "ECC Triage Snapshot"
TRANSLATIONS["ru"]["report.contract_triage_snapshot"] = "Сводка триажа репозитория"
TRANSLATIONS["ru"]["report.remediation_delta_summary"] = "Сводка изменений после доработки"
TRANSLATIONS["ru"]["report.ecc_triage_snapshot"] = "Сводка ECC-триажа"


def normalize_language(language: str | None) -> str:
    if not language:
        return "en"
    normalized = language.strip().lower().replace("_", "-")
    if normalized.startswith("ru"):
        return "ru"
    return "en"


def t(language: str | None, key: str, **kwargs: object) -> str:
    normalized = normalize_language(language)
    template = TRANSLATIONS.get(normalized, TRANSLATIONS["en"]).get(key)
    if template is None:
        template = TRANSLATIONS["en"].get(key, key)
    return template.format(**kwargs)


def is_affirmative(language: str | None, value: str) -> bool:
    normalized = normalize_language(language)
    stripped = value.strip().lower()
    if normalized == "ru":
        return stripped.startswith(("д", "y"))
    return stripped.startswith(("y", "д"))
