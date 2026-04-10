from __future__ import annotations

from pathlib import Path

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
from app.core.orchestrator import ResearchOrchestrator
from app.llm.providers import SUPPORTED_PROVIDER_NAMES
from app.models.doctor import DoctorCheck, DoctorReport


class SystemDoctor:
    """Bounded runtime self-check for local EllipticZero readiness."""

    REQUIRED_TOOLS = {
        "contract_inventory_tool",
        "contract_compile_tool",
        "slither_audit_tool",
        "echidna_audit_tool",
        "foundry_audit_tool",
        "contract_parser_tool",
        "contract_surface_tool",
        "contract_pattern_check_tool",
        "contract_testbed_tool",
        "curve_metadata_tool",
        "ecc_curve_parameter_tool",
        "ecc_point_format_tool",
        "ecc_consistency_check_tool",
        "symbolic_check_tool",
        "property_invariant_tool",
        "formal_constraint_tool",
        "finite_field_check_tool",
        "fuzz_mutation_tool",
        "ecc_testbed_tool",
        "deterministic_experiment_tool",
        "placeholder_math_tool",
    }

    def __init__(
        self,
        *,
        config: AppConfig,
        orchestrator: ResearchOrchestrator,
        language: str = "en",
    ) -> None:
        self.config = config
        self.orchestrator = orchestrator
        self.language = _normalize_language(language)

    def run(self) -> DoctorReport:
        checks = [
            self._check_provider(),
            self._check_provider_smoke_path(),
            self._check_registry(),
            self._check_plugins(),
            self._check_storage(),
            self._check_sage(),
            self._check_contract_compiler(),
            self._check_slither_analyzer(),
            self._check_echidna_adapter(),
            self._check_foundry_adapter(),
            self._check_local_research(),
        ]
        overall_status = self._resolve_overall_status(checks)
        return DoctorReport(
            overall_status=overall_status,
            summary=t(self.language, f"doctor.summary.{overall_status}"),
            checks=checks,
        )

    def _check_provider(self) -> DoctorCheck:
        provider = self.config.llm.default_provider.strip().lower()
        fallback_provider = self.config.llm.fallback_provider or t(self.language, "value.none")
        details = [
            t(self.language, "doctor.detail.default_provider", value=provider),
            t(self.language, "doctor.detail.default_model", value=self.config.llm.default_model),
            t(self.language, "doctor.detail.fallback_provider", value=fallback_provider),
        ]
        supported = set(SUPPORTED_PROVIDER_NAMES)
        context = {
            "default_provider": provider,
            "default_model": self.config.llm.default_model,
            "fallback_provider": self.config.llm.fallback_provider or "",
            "fallback_model": self.config.llm.fallback_model or "",
        }
        if provider not in supported:
            return DoctorCheck(
                status="error",
                title=t(self.language, "doctor.check.provider.title"),
                summary=t(self.language, "doctor.check.provider.unknown", provider=provider),
                details=details,
                context=context,
            )
        if provider == "mock":
            return DoctorCheck(
                status="ok",
                title=t(self.language, "doctor.check.provider.title"),
                summary=t(self.language, "doctor.check.provider.mock"),
                details=details,
                context=context,
            )

        api_env = getattr(self.config.providers, provider).api_key_env
        details.append(
            t(
                self.language,
                "doctor.detail.api_env",
                value=api_env or t(self.language, "value.unavailable"),
            )
        )
        context["api_key_env"] = api_env or ""

        if not api_env or not self.config.provider_api_key(provider):
            return DoctorCheck(
                status="error",
                title=t(self.language, "doctor.check.provider.title"),
                summary=t(
                    self.language,
                    "doctor.check.provider.missing_key",
                    provider=provider,
                    env=api_env or "?",
                ),
                details=details,
                context=context,
            )

        return DoctorCheck(
            status="ok",
            title=t(self.language, "doctor.check.provider.title"),
            summary=t(self.language, "doctor.check.provider.ready", provider=provider),
            details=details,
            context=context,
        )

    def _check_provider_smoke_path(self) -> DoctorCheck:
        provider = self.config.llm.default_provider.strip().lower()
        model = self.config.llm.default_model
        timeout_cap = min(self.config.llm.timeout_seconds, 30)
        token_cap = min(self.config.llm.max_request_tokens, 512)
        provider_settings = getattr(self.config.providers, provider, None)
        api_env = provider_settings.api_key_env if provider_settings is not None else None
        smoke_command = (
            f"python -m app.main --live-provider-smoke {provider} --live-smoke-model {model}"
            if provider != "mock"
            else "python -m app.main --provider openai --live-provider-smoke openai --live-smoke-model gpt-4.1-mini"
        )
        details = [
            t(self.language, "doctor.detail.default_provider", value=provider),
            t(self.language, "doctor.detail.default_model", value=model),
            t(self.language, "doctor.detail.live_smoke_command", value=smoke_command),
            t(self.language, "doctor.detail.smoke_timeout", value=str(timeout_cap)),
            t(self.language, "doctor.detail.smoke_max_tokens", value=str(token_cap)),
        ]
        context = {
            "provider": provider,
            "model": model,
            "smoke_timeout_seconds": str(timeout_cap),
            "smoke_max_request_tokens": str(token_cap),
            "smoke_command": smoke_command,
        }
        if provider == "mock":
            return DoctorCheck(
                status="info",
                title=t(self.language, "doctor.check.provider_smoke.title"),
                summary=t(self.language, "doctor.check.provider_smoke.mock"),
                details=details,
                context=context,
            )
        if api_env:
            details.append(
                t(
                    self.language,
                    "doctor.detail.api_env",
                    value=api_env,
                )
            )
            context["api_key_env"] = api_env
        if not api_env or not self.config.provider_api_key(provider):
            return DoctorCheck(
                status="warning",
                title=t(self.language, "doctor.check.provider_smoke.title"),
                summary=t(
                    self.language,
                    "doctor.check.provider_smoke.missing_key",
                    provider=provider,
                    env=api_env or "?",
                ),
                details=details,
                context=context,
            )
        return DoctorCheck(
            status="ok",
            title=t(self.language, "doctor.check.provider_smoke.title"),
            summary=t(self.language, "doctor.check.provider_smoke.ready", provider=provider),
            details=details,
            context=context,
        )

    def _check_registry(self) -> DoctorCheck:
        metadata = self.orchestrator.executor.registry.list_metadata()
        tool_names = set(self.orchestrator.executor.registry.names())
        built_in_count = sum(1 for item in metadata if item.source_type == "built_in")
        plugin_count = sum(1 for item in metadata if item.source_type == "plugin")
        deterministic_count = sum(1 for item in metadata if item.deterministic)
        synthetic_targets = self.orchestrator.target_registry.list_synthetic_targets()
        experiment_packs = self.orchestrator.experiment_pack_registry.list_packs()
        missing_tools = sorted(self.REQUIRED_TOOLS - tool_names)

        details = [
            t(self.language, "doctor.detail.total_tools", value=str(len(metadata))),
            t(self.language, "doctor.detail.built_in_tools", value=str(built_in_count)),
            t(self.language, "doctor.detail.plugin_tools", value=str(plugin_count)),
            t(self.language, "doctor.detail.deterministic_tools", value=str(deterministic_count)),
            t(self.language, "doctor.detail.synthetic_targets", value=str(len(synthetic_targets))),
            t(self.language, "doctor.detail.experiment_packs", value=str(len(experiment_packs))),
            t(
                self.language,
                "doctor.detail.required_tools",
                value=", ".join(sorted(self.REQUIRED_TOOLS)),
            ),
        ]
        context = {
            "total_tools": str(len(metadata)),
            "built_in_tools": str(built_in_count),
            "plugin_tools": str(plugin_count),
            "deterministic_tools": str(deterministic_count),
            "synthetic_targets": str(len(synthetic_targets)),
            "experiment_packs": str(len(experiment_packs)),
        }
        if missing_tools:
            details.append(
                t(
                    self.language,
                    "doctor.detail.missing_tools",
                    value=", ".join(missing_tools),
                )
            )
            context["missing_tools"] = ",".join(missing_tools)
            return DoctorCheck(
                status="error",
                title=t(self.language, "doctor.check.registry.title"),
                summary=t(
                    self.language,
                    "doctor.check.registry.missing",
                    count=len(missing_tools),
                ),
                details=details,
                context=context,
            )

        return DoctorCheck(
            status="ok",
            title=t(self.language, "doctor.check.registry.title"),
            summary=t(self.language, "doctor.check.registry.ready", count=len(metadata)),
            details=details,
            context=context,
        )

    def _check_plugins(self) -> DoctorCheck:
        plugin_directory = self.config.plugins.directory
        loaded = [item for item in self.orchestrator.plugin_metadata if item.load_status == "loaded"]
        failed = [item for item in self.orchestrator.plugin_metadata if item.load_status != "loaded"]
        details = [
            t(self.language, "doctor.detail.plugin_directory", value=plugin_directory),
            t(
                self.language,
                "doctor.detail.local_plugin_policy",
                value=self._bool_text(self.config.plugins.allow_local_plugins),
            ),
            t(self.language, "doctor.detail.plugin_safety_gate"),
            t(
                self.language,
                "doctor.detail.loaded_plugins",
                value=", ".join(item.plugin_name for item in loaded) or t(self.language, "value.none"),
            ),
            t(
                self.language,
                "doctor.detail.failed_plugins",
                value=", ".join(item.plugin_name for item in failed) or t(self.language, "value.none"),
            ),
        ]
        context = {
            "plugin_directory": plugin_directory,
            "allow_local_plugins": str(self.config.plugins.allow_local_plugins).lower(),
            "loaded_plugins": ",".join(item.plugin_name for item in loaded),
            "failed_plugins": ",".join(item.plugin_name for item in failed),
        }
        blocked = [
            item
            for item in failed
            if any("safety checks" in note.lower() for note in item.notes)
        ]
        if blocked:
            details.append(
                t(
                    self.language,
                    "doctor.detail.plugin_safety_failures",
                    value=", ".join(item.plugin_name for item in blocked),
                )
            )
            context["blocked_plugins"] = ",".join(item.plugin_name for item in blocked)

        if not self.config.plugins.enabled or not self.config.plugins.allow_local_plugins:
            details.append(t(self.language, "doctor.detail.disabled_by_config"))
            return DoctorCheck(
                status="info",
                title=t(self.language, "doctor.check.plugins.title"),
                summary=t(self.language, "doctor.check.plugins.disabled"),
                details=details,
                context=context,
            )

        if failed:
            for item in failed:
                if item.notes:
                    details.append(
                        t(
                            self.language,
                            "doctor.detail.failed_plugin_note",
                            plugin=item.plugin_name,
                            note=item.notes[0],
                        )
                    )
            summary_key = (
                "doctor.check.plugins.blocked"
                if blocked
                else "doctor.check.plugins.failed"
            )
            return DoctorCheck(
                status="warning",
                title=t(self.language, "doctor.check.plugins.title"),
                summary=t(
                    self.language,
                    summary_key,
                    loaded=len(loaded),
                    failed=len(failed),
                    blocked=len(blocked),
                ),
                details=details,
                context=context,
            )

        if loaded:
            return DoctorCheck(
                status="ok",
                title=t(self.language, "doctor.check.plugins.title"),
                summary=t(self.language, "doctor.check.plugins.loaded", count=len(loaded)),
                details=details,
                context=context,
            )

        return DoctorCheck(
            status="info",
            title=t(self.language, "doctor.check.plugins.title"),
            summary=t(self.language, "doctor.check.plugins.none"),
            details=details,
            context=context,
        )

    def _check_storage(self) -> DoctorCheck:
        directories = {
            "sessions": Path(self.config.storage.sessions_dir),
            "traces": Path(self.config.storage.traces_dir),
            "bundles": Path(self.config.storage.bundles_dir),
            "math": Path(self.config.storage.math_artifacts_dir),
        }
        details: list[str] = []
        context: dict[str, str] = {}
        failures: list[str] = []

        for key, directory in directories.items():
            ready, error_text = self._probe_directory(directory)
            context[f"{key}_dir"] = str(directory)
            details.append(
                t(
                    self.language,
                    "doctor.detail.directory_status",
                    name=key,
                    path=str(directory),
                    status=t(
                        self.language,
                        "doctor.directory.ready" if ready else "doctor.directory.failed",
                    ),
                )
            )
            if not ready:
                failures.append(f"{key}:{error_text}")

        export_roots = [
            str(Path(self.config.storage.artifacts_dir)),
            str(Path(self.config.storage.math_artifacts_dir)),
            str(Path(self.config.storage.sessions_dir)),
            str(Path(self.config.storage.traces_dir)),
        ]
        details.append(
            t(
                self.language,
                "doctor.detail.export_roots",
                value=", ".join(export_roots),
            )
        )
        details.append(t(self.language, "doctor.detail.export_policy"))
        context["export_roots"] = "|".join(export_roots)

        if failures:
            details.append(
                t(
                    self.language,
                    "doctor.detail.storage_failures",
                    value=" | ".join(failures),
                )
            )
            return DoctorCheck(
                status="error",
                title=t(self.language, "doctor.check.storage.title"),
                summary=t(self.language, "doctor.check.storage.failed"),
                details=details,
                context=context,
            )

        return DoctorCheck(
            status="ok",
            title=t(self.language, "doctor.check.storage.title"),
            summary=t(self.language, "doctor.check.storage.ready"),
            details=details,
            context=context,
        )

    def _check_sage(self) -> DoctorCheck:
        runner = SageRunner(
            enabled=self.config.advanced_math_enabled and self.config.sage.enabled,
            binary=self.config.sage.binary,
            timeout_seconds=self.config.sage.timeout_seconds,
        )
        details = [
            t(
                self.language,
                "doctor.detail.advanced_math",
                value=self._bool_text(self.config.advanced_math_enabled),
            ),
            t(
                self.language,
                "doctor.detail.sage_enabled",
                value=self._bool_text(self.config.sage.enabled),
            ),
            t(self.language, "doctor.detail.sage_binary", value=self.config.sage.binary),
            t(
                self.language,
                "doctor.detail.sage_timeout",
                value=str(self.config.sage.timeout_seconds),
            ),
        ]
        context = {
            "advanced_math_enabled": str(self.config.advanced_math_enabled).lower(),
            "sage_enabled": str(self.config.sage.enabled).lower(),
            "sage_binary": self.config.sage.binary,
            "sage_timeout_seconds": str(self.config.sage.timeout_seconds),
        }
        if not self.config.advanced_math_enabled:
            return DoctorCheck(
                status="info",
                title=t(self.language, "doctor.check.sage.title"),
                summary=t(self.language, "doctor.check.sage.advanced_math_disabled"),
                details=details,
                context=context,
            )
        if not self.config.sage.enabled:
            return DoctorCheck(
                status="info",
                title=t(self.language, "doctor.check.sage.title"),
                summary=t(self.language, "doctor.check.sage.disabled"),
                details=details,
                context=context,
            )
        if runner.is_available():
            return DoctorCheck(
                status="ok",
                title=t(self.language, "doctor.check.sage.title"),
                summary=t(
                    self.language,
                    "doctor.check.sage.available",
                    binary=self.config.sage.binary,
                ),
                details=details,
                context=context,
            )
        return DoctorCheck(
            status="warning",
            title=t(self.language, "doctor.check.sage.title"),
            summary=t(
                self.language,
                "doctor.check.sage.unavailable",
                binary=self.config.sage.binary,
            ),
            details=details,
            context=context,
        )

    def _check_local_research(self) -> DoctorCheck:
        sympy_runner = SympyRunner(enabled=self.config.local_research.sympy_enabled)
        property_runner = PropertyRunner(
            enabled=self.config.local_research.property_enabled,
            max_examples=self.config.local_research.property_max_examples,
        )
        formal_runner = FormalRunner(
            enabled=self.config.local_research.formal_enabled,
            backend=self.config.local_research.formal_backend,
            timeout_seconds=self.config.local_research.formal_timeout_seconds,
        )
        fuzz_runner = FuzzRunner(
            enabled=self.config.local_research.fuzz_enabled,
            max_mutations=self.config.local_research.fuzz_max_mutations,
            seed=self.config.local_research.fuzz_seed,
        )
        foundry_runner = FoundryRunner(
            enabled=self.config.local_research.foundry_enabled,
            managed_solc_dir=self.config.local_research.managed_solc_dir,
            managed_solc_version=self.config.local_research.managed_solc_version,
            forge_binary=self.config.local_research.forge_binary,
            solc_binary=self.config.local_research.solc_binary,
            timeout_seconds=self.config.local_research.foundry_timeout_seconds,
        )
        echidna_runner = EchidnaRunner(
            enabled=self.config.local_research.echidna_enabled,
            managed_solc_dir=self.config.local_research.managed_solc_dir,
            managed_solc_version=self.config.local_research.managed_solc_version,
            echidna_binary=self.config.local_research.echidna_binary,
            solc_binary=self.config.local_research.solc_binary,
            timeout_seconds=self.config.local_research.echidna_timeout_seconds,
            test_limit=self.config.local_research.echidna_test_limit,
            seq_len=self.config.local_research.echidna_seq_len,
        )
        contract_testbed_runner = ContractTestbedRunner(
            enabled=self.config.local_research.smart_contract_testbeds_enabled
        )
        ecc_testbed_runner = ECCTestbedRunner(enabled=self.config.local_research.ecc_testbeds_enabled)

        statuses = {
            "sympy": sympy_runner.is_available(),
            "property": property_runner.is_available(),
            "formal": formal_runner.is_available(),
            "fuzz": fuzz_runner.is_available(),
            "echidna": echidna_runner.is_available(),
            "foundry": foundry_runner.is_available(),
            "smart_contract_testbeds": contract_testbed_runner.is_available(),
            "ecc_testbeds": ecc_testbed_runner.is_available(),
        }
        details = [
            f"sympy_enabled={self._bool_text(self.config.local_research.sympy_enabled)}",
            f"property_enabled={self._bool_text(self.config.local_research.property_enabled)}",
            f"property_max_examples={self.config.local_research.property_max_examples}",
            f"fuzz_enabled={self._bool_text(self.config.local_research.fuzz_enabled)}",
            f"fuzz_max_mutations={self.config.local_research.fuzz_max_mutations}",
            f"formal_enabled={self._bool_text(self.config.local_research.formal_enabled)}",
            f"formal_backend={self.config.local_research.formal_backend}",
            f"echidna_enabled={self._bool_text(self.config.local_research.echidna_enabled)}",
            f"echidna_binary={self.config.local_research.echidna_binary}",
            f"foundry_enabled={self._bool_text(self.config.local_research.foundry_enabled)}",
            f"forge_binary={self.config.local_research.forge_binary}",
            f"smart_contract_testbeds_enabled={self._bool_text(self.config.local_research.smart_contract_testbeds_enabled)}",
            f"ecc_testbeds_enabled={self._bool_text(self.config.local_research.ecc_testbeds_enabled)}",
            f"sympy_available={self._bool_text(statuses['sympy'])}",
            f"property_available={self._bool_text(statuses['property'])}",
            f"formal_available={self._bool_text(statuses['formal'])}",
            f"fuzz_available={self._bool_text(statuses['fuzz'])}",
            f"echidna_available={self._bool_text(statuses['echidna'])}",
            f"foundry_available={self._bool_text(statuses['foundry'])}",
            f"smart_contract_testbeds_available={self._bool_text(statuses['smart_contract_testbeds'])}",
            f"ecc_testbeds_available={self._bool_text(statuses['ecc_testbeds'])}",
        ]
        context = {key: str(value).lower() for key, value in statuses.items()}
        if statuses["property"] is False or statuses["formal"] is False:
            return DoctorCheck(
                status="warning",
                title=t(self.language, "doctor.check.local_research.title"),
                summary=t(self.language, "doctor.check.local_research.partial"),
                details=details,
                context=context,
            )
        return DoctorCheck(
            status="ok",
            title=t(self.language, "doctor.check.local_research.title"),
            summary=t(self.language, "doctor.check.local_research.ready"),
            details=details,
            context=context,
        )

    def _check_contract_compiler(self) -> DoctorCheck:
        runner = ContractCompileRunner(
            enabled=self.config.local_research.smart_contract_compile_enabled,
            managed_solc_dir=self.config.local_research.managed_solc_dir,
            managed_solc_version=self.config.local_research.managed_solc_version,
            solc_binary=self.config.local_research.solc_binary,
            solcjs_binary=self.config.local_research.solcjs_binary,
            timeout_seconds=self.config.local_research.smart_contract_compile_timeout_seconds,
        )
        resolved_binary = runner.resolved_binary()
        resolved_managed_binary = runner.resolved_managed_binary()
        resolved_managed_version = runner.resolved_managed_version()
        installed_managed_versions = runner.installed_managed_versions()
        version = runner.compiler_version() or t(self.language, "value.unavailable")
        details = [
            t(
                self.language,
                "doctor.detail.smart_contract_compile_enabled",
                value=self._bool_text(self.config.local_research.smart_contract_compile_enabled),
            ),
            t(
                self.language,
                "doctor.detail.managed_solc_dir",
                value=self.config.local_research.managed_solc_dir,
            ),
            t(
                self.language,
                "doctor.detail.managed_solc_version",
                value=self.config.local_research.managed_solc_version,
            ),
            t(self.language, "doctor.detail.solc_binary", value=self.config.local_research.solc_binary),
            t(self.language, "doctor.detail.solcjs_binary", value=self.config.local_research.solcjs_binary),
            t(
                self.language,
                "doctor.detail.contract_compile_timeout",
                value=str(self.config.local_research.smart_contract_compile_timeout_seconds),
            ),
            t(
                self.language,
                "doctor.detail.installed_managed_compilers",
                value=", ".join(installed_managed_versions) or t(self.language, "value.none"),
            ),
            t(
                self.language,
                "doctor.detail.resolved_managed_compiler_binary",
                value=resolved_managed_binary or t(self.language, "value.unavailable"),
            ),
            t(
                self.language,
                "doctor.detail.resolved_managed_compiler_version",
                value=resolved_managed_version or t(self.language, "value.unavailable"),
            ),
            t(
                self.language,
                "doctor.detail.resolved_compiler_binary",
                value=resolved_binary or t(self.language, "value.unavailable"),
            ),
            t(self.language, "doctor.detail.compiler_version", value=version),
        ]
        context = {
            "smart_contract_compile_enabled": str(self.config.local_research.smart_contract_compile_enabled).lower(),
            "managed_solc_dir": self.config.local_research.managed_solc_dir,
            "managed_solc_version": self.config.local_research.managed_solc_version,
            "solc_binary": self.config.local_research.solc_binary,
            "solcjs_binary": self.config.local_research.solcjs_binary,
            "installed_managed_versions": ",".join(installed_managed_versions),
            "resolved_managed_binary": resolved_managed_binary or "",
            "resolved_managed_version": resolved_managed_version or "",
            "resolved_binary": resolved_binary or "",
            "compiler_version": version,
        }
        if not self.config.local_research.smart_contract_compile_enabled:
            return DoctorCheck(
                status="info",
                title=t(self.language, "doctor.check.contract_compiler.title"),
                summary=t(self.language, "doctor.check.contract_compiler.disabled"),
                details=details,
                context=context,
            )
        if runner.is_available():
            return DoctorCheck(
                status="ok",
                title=t(self.language, "doctor.check.contract_compiler.title"),
                summary=t(
                    self.language,
                    "doctor.check.contract_compiler.available",
                    binary=resolved_binary or self.config.local_research.solc_binary,
                ),
                details=details,
                context=context,
            )
        return DoctorCheck(
            status="warning",
            title=t(self.language, "doctor.check.contract_compiler.title"),
            summary=t(self.language, "doctor.check.contract_compiler.unavailable"),
            details=details,
            context=context,
        )

    def _check_slither_analyzer(self) -> DoctorCheck:
        runner = SlitherRunner(
            enabled=self.config.local_research.slither_enabled,
            managed_solc_dir=self.config.local_research.managed_solc_dir,
            managed_solc_version=self.config.local_research.managed_solc_version,
            slither_binary=self.config.local_research.slither_binary,
            solc_binary=self.config.local_research.solc_binary,
            timeout_seconds=self.config.local_research.slither_timeout_seconds,
        )
        resolved_binary = runner.resolved_binary()
        resolved_solc_binary = runner.resolved_solc_binary()
        version = runner.analyzer_version() or t(self.language, "value.unavailable")
        details = [
            t(
                self.language,
                "doctor.detail.slither_enabled",
                value=self._bool_text(self.config.local_research.slither_enabled),
            ),
            t(
                self.language,
                "doctor.detail.managed_solc_dir",
                value=self.config.local_research.managed_solc_dir,
            ),
            t(
                self.language,
                "doctor.detail.managed_solc_version",
                value=self.config.local_research.managed_solc_version,
            ),
            t(self.language, "doctor.detail.slither_binary", value=self.config.local_research.slither_binary),
            t(
                self.language,
                "doctor.detail.slither_timeout",
                value=str(self.config.local_research.slither_timeout_seconds),
            ),
            t(
                self.language,
                "doctor.detail.resolved_analyzer_binary",
                value=resolved_binary or t(self.language, "value.unavailable"),
            ),
            t(self.language, "doctor.detail.analyzer_version", value=version),
            t(
                self.language,
                "doctor.detail.resolved_compiler_binary",
                value=resolved_solc_binary or t(self.language, "value.unavailable"),
            ),
        ]
        context = {
            "slither_enabled": str(self.config.local_research.slither_enabled).lower(),
            "slither_binary": self.config.local_research.slither_binary,
            "resolved_binary": resolved_binary or "",
            "resolved_solc_binary": resolved_solc_binary or "",
            "analyzer_version": version,
        }
        if not self.config.local_research.slither_enabled:
            return DoctorCheck(
                status="info",
                title=t(self.language, "doctor.check.slither.title"),
                summary=t(self.language, "doctor.check.slither.disabled"),
                details=details,
                context=context,
            )
        if runner.is_available():
            return DoctorCheck(
                status="ok",
                title=t(self.language, "doctor.check.slither.title"),
                summary=t(
                    self.language,
                    "doctor.check.slither.available",
                    binary=resolved_binary or self.config.local_research.slither_binary,
                ),
                details=details,
                context=context,
            )
        return DoctorCheck(
            status="warning",
            title=t(self.language, "doctor.check.slither.title"),
            summary=t(self.language, "doctor.check.slither.unavailable"),
            details=details,
            context=context,
        )

    def _check_foundry_adapter(self) -> DoctorCheck:
        runner = FoundryRunner(
            enabled=self.config.local_research.foundry_enabled,
            managed_solc_dir=self.config.local_research.managed_solc_dir,
            managed_solc_version=self.config.local_research.managed_solc_version,
            forge_binary=self.config.local_research.forge_binary,
            solc_binary=self.config.local_research.solc_binary,
            timeout_seconds=self.config.local_research.foundry_timeout_seconds,
        )
        resolved_binary = runner.resolved_binary()
        resolved_solc_binary = runner.resolved_solc_binary()
        version = runner.forge_version() or t(self.language, "value.unavailable")
        details = [
            t(
                self.language,
                "doctor.detail.foundry_enabled",
                value=self._bool_text(self.config.local_research.foundry_enabled),
            ),
            t(self.language, "doctor.detail.forge_binary", value=self.config.local_research.forge_binary),
            t(
                self.language,
                "doctor.detail.foundry_timeout",
                value=str(self.config.local_research.foundry_timeout_seconds),
            ),
            t(
                self.language,
                "doctor.detail.resolved_analyzer_binary",
                value=resolved_binary or t(self.language, "value.unavailable"),
            ),
            t(self.language, "doctor.detail.analyzer_version", value=version),
            t(
                self.language,
                "doctor.detail.resolved_compiler_binary",
                value=resolved_solc_binary or t(self.language, "value.unavailable"),
            ),
        ]
        context = {
            "foundry_enabled": str(self.config.local_research.foundry_enabled).lower(),
            "forge_binary": self.config.local_research.forge_binary,
            "resolved_binary": resolved_binary or "",
            "resolved_solc_binary": resolved_solc_binary or "",
            "forge_version": version,
        }
        if not self.config.local_research.foundry_enabled:
            return DoctorCheck(
                status="info",
                title=t(self.language, "doctor.check.foundry.title"),
                summary=t(self.language, "doctor.check.foundry.disabled"),
                details=details,
                context=context,
            )
        if runner.is_available():
            return DoctorCheck(
                status="ok",
                title=t(self.language, "doctor.check.foundry.title"),
                summary=t(
                    self.language,
                    "doctor.check.foundry.available",
                    binary=resolved_binary or self.config.local_research.forge_binary,
                ),
                details=details,
                context=context,
            )
        return DoctorCheck(
            status="warning",
            title=t(self.language, "doctor.check.foundry.title"),
            summary=t(self.language, "doctor.check.foundry.unavailable"),
            details=details,
            context=context,
        )

    def _check_echidna_adapter(self) -> DoctorCheck:
        runner = EchidnaRunner(
            enabled=self.config.local_research.echidna_enabled,
            managed_solc_dir=self.config.local_research.managed_solc_dir,
            managed_solc_version=self.config.local_research.managed_solc_version,
            echidna_binary=self.config.local_research.echidna_binary,
            solc_binary=self.config.local_research.solc_binary,
            timeout_seconds=self.config.local_research.echidna_timeout_seconds,
            test_limit=self.config.local_research.echidna_test_limit,
            seq_len=self.config.local_research.echidna_seq_len,
        )
        resolved_binary = runner.resolved_binary()
        resolved_solc_binary = runner.resolved_solc_binary()
        version = runner.analyzer_version() or t(self.language, "value.unavailable")
        details = [
            t(
                self.language,
                "doctor.detail.echidna_enabled",
                value=self._bool_text(self.config.local_research.echidna_enabled),
            ),
            t(self.language, "doctor.detail.echidna_binary", value=self.config.local_research.echidna_binary),
            t(
                self.language,
                "doctor.detail.echidna_timeout",
                value=str(self.config.local_research.echidna_timeout_seconds),
            ),
            t(
                self.language,
                "doctor.detail.echidna_test_limit",
                value=str(self.config.local_research.echidna_test_limit),
            ),
            t(
                self.language,
                "doctor.detail.echidna_seq_len",
                value=str(self.config.local_research.echidna_seq_len),
            ),
            t(
                self.language,
                "doctor.detail.resolved_analyzer_binary",
                value=resolved_binary or t(self.language, "value.unavailable"),
            ),
            t(self.language, "doctor.detail.analyzer_version", value=version),
            t(
                self.language,
                "doctor.detail.resolved_compiler_binary",
                value=resolved_solc_binary or t(self.language, "value.unavailable"),
            ),
        ]
        context = {
            "echidna_enabled": str(self.config.local_research.echidna_enabled).lower(),
            "echidna_binary": self.config.local_research.echidna_binary,
            "resolved_binary": resolved_binary or "",
            "resolved_solc_binary": resolved_solc_binary or "",
            "analyzer_version": version,
        }
        if not self.config.local_research.echidna_enabled:
            return DoctorCheck(
                status="info",
                title=t(self.language, "doctor.check.echidna.title"),
                summary=t(self.language, "doctor.check.echidna.disabled"),
                details=details,
                context=context,
            )
        if runner.is_available():
            return DoctorCheck(
                status="ok",
                title=t(self.language, "doctor.check.echidna.title"),
                summary=t(
                    self.language,
                    "doctor.check.echidna.available",
                    binary=resolved_binary or self.config.local_research.echidna_binary,
                ),
                details=details,
                context=context,
            )
        return DoctorCheck(
            status="warning",
            title=t(self.language, "doctor.check.echidna.title"),
            summary=t(self.language, "doctor.check.echidna.unavailable"),
            details=details,
            context=context,
        )

    def _probe_directory(self, directory: Path) -> tuple[bool, str]:
        try:
            directory.mkdir(parents=True, exist_ok=True)
            probe_path = directory / ".doctor_probe"
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink()
            return True, ""
        except OSError as exc:
            return False, str(exc)

    def _resolve_overall_status(self, checks: list[DoctorCheck]) -> str:
        statuses = {check.status for check in checks}
        if "error" in statuses:
            return "error"
        if "warning" in statuses:
            return "warning"
        if "ok" in statuses:
            return "ok"
        return "info"

    def _bool_text(self, value: bool) -> str:
        return t(self.language, "value.enabled") if value else t(self.language, "value.disabled")


def _normalize_language(language: str) -> str:
    from app.cli.i18n import normalize_language

    return normalize_language(language)


def t(language: str, key: str, **kwargs: object) -> str:
    from app.cli.i18n import t as translate

    return translate(language, key, **kwargs)
