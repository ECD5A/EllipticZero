from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.sandbox import ExplorationProfile, ResearchMode


class LLMSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_provider: str = "mock"
    default_model: str = "mock-default"
    fallback_provider: str | None = None
    fallback_model: str | None = None
    timeout_seconds: int = 60
    max_request_tokens: int = 2048
    max_total_requests_per_session: int = 16


class ProviderAuthSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api_key_env: str | None = None


class ProviderSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    openai: ProviderAuthSettings = Field(
        default_factory=lambda: ProviderAuthSettings(api_key_env="OPENAI_API_KEY")
    )
    openrouter: ProviderAuthSettings = Field(
        default_factory=lambda: ProviderAuthSettings(api_key_env="OPENROUTER_API_KEY")
    )
    gemini: ProviderAuthSettings = Field(
        default_factory=lambda: ProviderAuthSettings(api_key_env="GEMINI_API_KEY")
    )
    anthropic: ProviderAuthSettings = Field(
        default_factory=lambda: ProviderAuthSettings(api_key_env="ANTHROPIC_API_KEY")
    )


class AgentRouteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str | None = None
    model: str | None = None


class AgentRoutingSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    math_agent: AgentRouteConfig = Field(default_factory=AgentRouteConfig)
    cryptography_agent: AgentRouteConfig = Field(default_factory=AgentRouteConfig)
    strategy_agent: AgentRouteConfig = Field(default_factory=AgentRouteConfig)
    hypothesis_agent: AgentRouteConfig = Field(default_factory=AgentRouteConfig)
    critic_agent: AgentRouteConfig = Field(default_factory=AgentRouteConfig)
    report_agent: AgentRouteConfig = Field(default_factory=AgentRouteConfig)

    def get_for_agent(self, agent_name: str) -> AgentRouteConfig:
        return getattr(self, agent_name, AgentRouteConfig())


class StorageSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifacts_dir: str = "artifacts"
    sessions_dir: str = "artifacts/sessions"
    traces_dir: str = "artifacts/traces"
    math_artifacts_dir: str = "artifacts/math"
    bundles_dir: str = "artifacts/bundles"


class SageSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    binary: str = "sage"
    timeout_seconds: int = 30


class PluginSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool = True
    directory: str = "plugins"
    allow_local_plugins: bool = True


class ResearchSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_mode: ResearchMode = ResearchMode.STANDARD
    default_exploration_profile: ExplorationProfile = ExplorationProfile.CAUTIOUS
    max_exploratory_branches: int = 2
    max_exploratory_rounds: int = 2
    max_jobs_per_session: int = 2
    aggressive_max_exploratory_branches: int = 3
    aggressive_max_exploratory_rounds: int = 3
    aggressive_max_jobs_per_session: int = 4
    require_manual_review_for_exploratory: bool = True

    @field_validator(
        "max_exploratory_branches",
        "max_exploratory_rounds",
        "max_jobs_per_session",
        "aggressive_max_exploratory_branches",
        "aggressive_max_exploratory_rounds",
        "aggressive_max_jobs_per_session",
    )
    @classmethod
    def validate_positive_limits(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Research limits must be >= 1.")
        return value


class LocalResearchSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sympy_enabled: bool = True
    smart_contract_compile_enabled: bool = True
    managed_solc_dir: str = ".ellipticzero/tooling/solcx"
    managed_solc_version: str = "0.8.20"
    solc_binary: str = "solc"
    solcjs_binary: str = "solcjs"
    smart_contract_compile_timeout_seconds: int = 12
    slither_enabled: bool = True
    slither_binary: str = "slither"
    slither_timeout_seconds: int = 45
    echidna_enabled: bool = True
    echidna_binary: str = "echidna"
    echidna_timeout_seconds: int = 45
    echidna_test_limit: int = 128
    echidna_seq_len: int = 16
    foundry_enabled: bool = True
    forge_binary: str = "forge"
    foundry_timeout_seconds: int = 45
    property_enabled: bool = True
    property_max_examples: int = 24
    fuzz_enabled: bool = True
    fuzz_max_mutations: int = 12
    fuzz_seed: int = 1337
    formal_enabled: bool = True
    formal_backend: str = "z3"
    formal_timeout_seconds: int = 5
    ecc_testbeds_enabled: bool = True
    smart_contract_testbeds_enabled: bool = True

    @field_validator(
        "property_max_examples",
        "fuzz_max_mutations",
        "fuzz_seed",
        "formal_timeout_seconds",
        "smart_contract_compile_timeout_seconds",
        "slither_timeout_seconds",
        "echidna_timeout_seconds",
        "echidna_test_limit",
        "echidna_seq_len",
        "foundry_timeout_seconds",
    )
    @classmethod
    def validate_positive_values(cls, value: int) -> int:
        if value < 1:
            raise ValueError("Local research settings must be >= 1 where integer-bounded.")
        return value

    @field_validator("formal_backend")
    @classmethod
    def normalize_formal_backend(cls, value: str) -> str:
        stripped = value.strip().lower()
        if stripped not in {"z3"}:
            raise ValueError("formal_backend must be z3.")
        return stripped

    @field_validator("managed_solc_dir", "managed_solc_version")
    @classmethod
    def validate_non_empty_strings(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Managed smart-contract toolchain settings must not be empty.")
        return stripped


class AppConfig(BaseModel):
    """Typed application configuration loaded from YAML, env, and defaults."""

    model_config = ConfigDict(extra="forbid")

    llm: LLMSettings = Field(default_factory=LLMSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)
    agents: AgentRoutingSettings = Field(default_factory=AgentRoutingSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    sage: SageSettings = Field(default_factory=SageSettings)
    plugins: PluginSettings = Field(default_factory=PluginSettings)
    research: ResearchSettings = Field(default_factory=ResearchSettings)
    local_research: LocalResearchSettings = Field(default_factory=LocalResearchSettings)
    log_level: str = "WARNING"
    ui_language: str = "en"
    max_hypotheses: int = 2
    tool_timeout_seconds: int = 30
    advanced_math_enabled: bool = True

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("ui_language")
    @classmethod
    def normalize_ui_language(cls, value: str) -> str:
        normalized = value.strip().lower().replace("_", "-")
        if normalized.startswith("ru"):
            return "ru"
        return "en"

    @classmethod
    def load(cls, config_path: str | None = None) -> "AppConfig":
        load_dotenv()
        resolved_path = Path(
            config_path
            or os.getenv("ELLIPTICZERO_CONFIG_PATH", "configs/settings.yaml")
        )
        payload: dict[str, Any] = {}
        if resolved_path.exists():
            payload = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}

        merged = cls._deep_merge(payload, cls._env_overrides())
        return cls.model_validate(merged)

    @classmethod
    def from_env(cls) -> "AppConfig":
        """Backward-compatible convenience loader."""

        return cls.load()

    def provider_api_key(self, provider_name: str) -> str | None:
        provider_settings = getattr(self.providers, provider_name, None)
        if provider_settings is None or provider_settings.api_key_env is None:
            return None
        return os.getenv(provider_settings.api_key_env)

    @classmethod
    def _env_overrides(cls) -> dict[str, Any]:
        overrides: dict[str, Any] = {}

        cls._set_if_present(
            overrides,
            ("llm", "default_provider"),
            os.getenv("ELLIPTICZERO_LLM_DEFAULT_PROVIDER")
            or os.getenv("ELLIPTICZERO_LLM_PROVIDER"),
            transform=lambda value: value.strip().lower(),
        )
        cls._set_if_present(
            overrides,
            ("llm", "default_model"),
            os.getenv("ELLIPTICZERO_LLM_DEFAULT_MODEL")
            or os.getenv("ELLIPTICZERO_OPENAI_MODEL"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("llm", "fallback_provider"),
            os.getenv("ELLIPTICZERO_LLM_FALLBACK_PROVIDER"),
            transform=lambda value: value.strip().lower(),
        )
        cls._set_if_present(
            overrides,
            ("llm", "fallback_model"),
            os.getenv("ELLIPTICZERO_LLM_FALLBACK_MODEL"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("llm", "timeout_seconds"),
            os.getenv("ELLIPTICZERO_LLM_TIMEOUT_SECONDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("llm", "max_request_tokens"),
            os.getenv("ELLIPTICZERO_LLM_MAX_REQUEST_TOKENS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("llm", "max_total_requests_per_session"),
            os.getenv("ELLIPTICZERO_LLM_MAX_TOTAL_REQUESTS_PER_SESSION"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("storage", "sessions_dir"),
            os.getenv("ELLIPTICZERO_STORAGE_SESSIONS_DIR")
            or os.getenv("ELLIPTICZERO_SESSION_STORE_DIR"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("storage", "traces_dir"),
            os.getenv("ELLIPTICZERO_STORAGE_TRACES_DIR")
            or os.getenv("ELLIPTICZERO_TRACE_DIR"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("storage", "math_artifacts_dir"),
            os.getenv("ELLIPTICZERO_STORAGE_MATH_ARTIFACTS_DIR"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("storage", "bundles_dir"),
            os.getenv("ELLIPTICZERO_STORAGE_BUNDLES_DIR"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("sage", "enabled"),
            os.getenv("ELLIPTICZERO_SAGE_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("sage", "binary"),
            os.getenv("ELLIPTICZERO_SAGE_BINARY"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("sage", "timeout_seconds"),
            os.getenv("ELLIPTICZERO_SAGE_TIMEOUT_SECONDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("plugins", "enabled"),
            os.getenv("ELLIPTICZERO_PLUGINS_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("plugins", "directory"),
            os.getenv("ELLIPTICZERO_PLUGINS_DIRECTORY"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("plugins", "allow_local_plugins"),
            os.getenv("ELLIPTICZERO_ALLOW_LOCAL_PLUGINS"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("research", "default_mode"),
            os.getenv("ELLIPTICZERO_RESEARCH_MODE"),
            transform=lambda value: ResearchMode(value.strip().lower()),
        )
        cls._set_if_present(
            overrides,
            ("research", "default_exploration_profile"),
            os.getenv("ELLIPTICZERO_DEFAULT_EXPLORATION_PROFILE"),
            transform=lambda value: ExplorationProfile(value.strip().lower()),
        )
        cls._set_if_present(
            overrides,
            ("research", "max_exploratory_branches"),
            os.getenv("ELLIPTICZERO_MAX_EXPLORATORY_BRANCHES"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("research", "max_exploratory_rounds"),
            os.getenv("ELLIPTICZERO_MAX_EXPLORATORY_ROUNDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("research", "max_jobs_per_session"),
            os.getenv("ELLIPTICZERO_MAX_JOBS_PER_SESSION"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("research", "aggressive_max_exploratory_branches"),
            os.getenv("ELLIPTICZERO_AGGRESSIVE_MAX_EXPLORATORY_BRANCHES"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("research", "aggressive_max_exploratory_rounds"),
            os.getenv("ELLIPTICZERO_AGGRESSIVE_MAX_EXPLORATORY_ROUNDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("research", "aggressive_max_jobs_per_session"),
            os.getenv("ELLIPTICZERO_AGGRESSIVE_MAX_JOBS_PER_SESSION"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("research", "require_manual_review_for_exploratory"),
            os.getenv("ELLIPTICZERO_REQUIRE_MANUAL_REVIEW_FOR_EXPLORATORY"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "smart_contract_compile_enabled"),
            os.getenv("ELLIPTICZERO_SMART_CONTRACT_COMPILE_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "managed_solc_dir"),
            os.getenv("ELLIPTICZERO_MANAGED_SOLC_DIR"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("local_research", "managed_solc_version"),
            os.getenv("ELLIPTICZERO_MANAGED_SOLC_VERSION"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("local_research", "solc_binary"),
            os.getenv("ELLIPTICZERO_SOLC_BINARY"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("local_research", "solcjs_binary"),
            os.getenv("ELLIPTICZERO_SOLCJS_BINARY"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("local_research", "smart_contract_compile_timeout_seconds"),
            os.getenv("ELLIPTICZERO_SMART_CONTRACT_COMPILE_TIMEOUT_SECONDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "slither_enabled"),
            os.getenv("ELLIPTICZERO_SLITHER_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "slither_binary"),
            os.getenv("ELLIPTICZERO_SLITHER_BINARY"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("local_research", "slither_timeout_seconds"),
            os.getenv("ELLIPTICZERO_SLITHER_TIMEOUT_SECONDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "echidna_enabled"),
            os.getenv("ELLIPTICZERO_ECHIDNA_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "echidna_binary"),
            os.getenv("ELLIPTICZERO_ECHIDNA_BINARY"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("local_research", "echidna_timeout_seconds"),
            os.getenv("ELLIPTICZERO_ECHIDNA_TIMEOUT_SECONDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "echidna_test_limit"),
            os.getenv("ELLIPTICZERO_ECHIDNA_TEST_LIMIT"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "echidna_seq_len"),
            os.getenv("ELLIPTICZERO_ECHIDNA_SEQ_LEN"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "foundry_enabled"),
            os.getenv("ELLIPTICZERO_FOUNDRY_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "forge_binary"),
            os.getenv("ELLIPTICZERO_FORGE_BINARY"),
            transform=lambda value: value.strip(),
        )
        cls._set_if_present(
            overrides,
            ("local_research", "foundry_timeout_seconds"),
            os.getenv("ELLIPTICZERO_FOUNDRY_TIMEOUT_SECONDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "sympy_enabled"),
            os.getenv("ELLIPTICZERO_SYMPY_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "property_enabled"),
            os.getenv("ELLIPTICZERO_PROPERTY_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "property_max_examples"),
            os.getenv("ELLIPTICZERO_PROPERTY_MAX_EXAMPLES"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "fuzz_enabled"),
            os.getenv("ELLIPTICZERO_FUZZ_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "fuzz_max_mutations"),
            os.getenv("ELLIPTICZERO_FUZZ_MAX_MUTATIONS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "fuzz_seed"),
            os.getenv("ELLIPTICZERO_FUZZ_SEED"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "formal_enabled"),
            os.getenv("ELLIPTICZERO_FORMAL_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "formal_backend"),
            os.getenv("ELLIPTICZERO_FORMAL_BACKEND"),
            transform=lambda value: value.strip().lower(),
        )
        cls._set_if_present(
            overrides,
            ("local_research", "formal_timeout_seconds"),
            os.getenv("ELLIPTICZERO_FORMAL_TIMEOUT_SECONDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("local_research", "ecc_testbeds_enabled"),
            os.getenv("ELLIPTICZERO_ECC_TESTBEDS_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("local_research", "smart_contract_testbeds_enabled"),
            os.getenv("ELLIPTICZERO_SMART_CONTRACT_TESTBEDS_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )
        cls._set_if_present(
            overrides,
            ("log_level",),
            os.getenv("ELLIPTICZERO_LOG_LEVEL"),
            transform=lambda value: value.strip().upper(),
        )
        cls._set_if_present(
            overrides,
            ("ui_language",),
            os.getenv("ELLIPTICZERO_UI_LANGUAGE"),
            transform=lambda value: "ru" if value.strip().lower().replace("_", "-").startswith("ru") else "en",
        )
        cls._set_if_present(
            overrides,
            ("max_hypotheses",),
            os.getenv("ELLIPTICZERO_MAX_HYPOTHESES"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("tool_timeout_seconds",),
            os.getenv("ELLIPTICZERO_TOOL_TIMEOUT_SECONDS"),
            transform=int,
        )
        cls._set_if_present(
            overrides,
            ("advanced_math_enabled",),
            os.getenv("ELLIPTICZERO_ADVANCED_MATH_ENABLED"),
            transform=lambda value: value.strip().lower() in {"1", "true", "yes", "on"},
        )

        for agent_name in (
            "math_agent",
            "cryptography_agent",
            "strategy_agent",
            "hypothesis_agent",
            "critic_agent",
            "report_agent",
        ):
            env_name = agent_name.upper()
            cls._set_if_present(
                overrides,
                ("agents", agent_name, "provider"),
                os.getenv(f"ELLIPTICZERO_AGENT_{env_name}_PROVIDER"),
                transform=lambda value: value.strip().lower(),
            )
            cls._set_if_present(
                overrides,
                ("agents", agent_name, "model"),
                os.getenv(f"ELLIPTICZERO_AGENT_{env_name}_MODEL"),
                transform=lambda value: value.strip(),
            )

        return overrides

    @classmethod
    def _set_if_present(
        cls,
        target: dict[str, Any],
        path: tuple[str, ...],
        value: str | None,
        *,
        transform,
    ) -> None:
        if value is None or value == "":
            return
        cursor = target
        for key in path[:-1]:
            cursor = cursor.setdefault(key, {})
        cursor[path[-1]] = transform(value)

    @classmethod
    def _deep_merge(cls, base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
        result = dict(base)
        for key, value in updates.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = cls._deep_merge(result[key], value)
            else:
                result[key] = value
        return result
