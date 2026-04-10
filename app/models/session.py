from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models.agent_results import (
    CriticAgentResult,
    CryptographyAgentResult,
    HypothesisAgentResult,
    MathAgentResult,
    ReportAgentResult,
    StrategyAgentResult,
)
from app.models.comparative_report import ComparativeReport
from app.models.evidence import Evidence
from app.models.experiment_pack import ExperimentPackRecommendation
from app.models.hypothesis import Hypothesis
from app.models.job import ComputeJob
from app.models.math_workspace import MathWorkspace
from app.models.plugin_metadata import PluginMetadata
from app.models.report import ResearchReport
from app.models.sandbox import ResearchMode, ResearchTarget, SandboxSpec
from app.models.seed import ResearchSeed
from app.types import make_id


class ResearchSession(BaseModel):
    """Top-level container for one EllipticZero investigation."""

    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(default_factory=lambda: make_id("session"))
    seed: ResearchSeed
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    math_workspaces: list[MathWorkspace] = Field(default_factory=list)
    plugin_metadata: list[PluginMetadata] = Field(default_factory=list)
    report: ResearchReport | None = None
    jobs: list[ComputeJob] = Field(default_factory=list)
    math_result: MathAgentResult | None = None
    cryptography_result: CryptographyAgentResult | None = None
    strategy_result: StrategyAgentResult | None = None
    hypothesis_result: HypothesisAgentResult | None = None
    critic_result: CriticAgentResult | None = None
    report_result: ReportAgentResult | None = None
    comparative_report: ComparativeReport | None = None
    research_mode: ResearchMode = ResearchMode.STANDARD
    sandbox_spec: SandboxSpec | None = None
    research_target: ResearchTarget | None = None
    selected_pack_name: str | None = None
    recommended_pack_names: list[str] = Field(default_factory=list)
    executed_pack_steps: list[str] = Field(default_factory=list)
    pack_recommendations: list[ExperimentPackRecommendation] = Field(default_factory=list)
    explored_hypothesis_ids: list[str] = Field(default_factory=list)
    exploratory_rounds_executed: int = 0
    exploratory_round_summaries: list[str] = Field(default_factory=list)
    trace_file_path: str | None = None
    session_file_path: str | None = None
    manifest_file_path: str | None = None
    bundle_dir: str | None = None
    comparative_report_file_path: str | None = None
    is_replay: bool = False
    replay_source_type: str | None = None
    replay_source_path: str | None = None
    original_session_id: str | None = None
    replay_mode: str | None = None
    replay_notes: list[str] = Field(default_factory=list)
    comparison_baseline_session_id: str | None = None
    comparison_baseline_source_type: str | None = None
    comparison_baseline_source_path: str | None = None
