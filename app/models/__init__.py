"""Pydantic data models for EllipticZero."""

from app.models.agent_results import (
    CriticAgentResult,
    CryptographyAgentResult,
    HypothesisAgentResult,
    HypothesisBranch,
    MathAgentResult,
    ReportAgentResult,
    StrategyAgentResult,
)
from app.models.comparative_report import (
    BranchComparison,
    ComparativeReport,
    ComparativeReportSection,
    CrossSessionComparison,
    ToolComparison,
)
from app.models.doctor import DoctorCheck, DoctorReport
from app.models.ecc_domain import ECCDomainParameters
from app.models.ecc_point import ECCPointDescriptor
from app.models.evidence import Evidence
from app.models.experiment_pack import (
    ExperimentPack,
    ExperimentPackRecommendation,
    ExperimentPackStep,
)
from app.models.hypothesis import Hypothesis
from app.models.job import ComputeJob
from app.models.math_workspace import MathWorkspace
from app.models.planning import ExperimentSpec, ExperimentType, ToolPlan
from app.models.plugin_metadata import PluginMetadata
from app.models.replay_request import ReplayRequest
from app.models.replay_result import ReplayResult
from app.models.report import ResearchReport
from app.models.run_manifest import RunArtifactReference, RunManifest
from app.models.sandbox import (
    ExplorationProfile,
    ResearchMode,
    ResearchTarget,
    ResearchTargetProfile,
    SandboxExecutionRequest,
    SandboxExecutionResult,
    SandboxSpec,
    SyntheticResearchTarget,
)
from app.models.seed import ResearchSeed
from app.models.session import ResearchSession
from app.models.tool_metadata import ToolMetadata
from app.models.tool_payloads import (
    CurveMetadataPayload,
    DeterministicExperimentPayload,
    ECCConsistencyPayload,
    ECCCurvePayload,
    ECCPointPayload,
    ECCTestbedPayload,
    FiniteFieldCheckPayload,
    FormalConstraintPayload,
    FuzzMutationPayload,
    PointDescriptorPayload,
    PropertyInvariantPayload,
    SmartContractAuditPayload,
    SmartContractInventoryPayload,
    SmartContractTestbedPayload,
    SymbolicCheckPayload,
)

__all__ = [
    "BranchComparison",
    "ComparativeReport",
    "ComparativeReportSection",
    "CrossSessionComparison",
    "CriticAgentResult",
    "CryptographyAgentResult",
    "ComputeJob",
    "DoctorCheck",
    "DoctorReport",
    "CurveMetadataPayload",
    "DeterministicExperimentPayload",
    "ECCTestbedPayload",
    "ECCConsistencyPayload",
    "ECCCurvePayload",
    "ECCDomainParameters",
    "ECCPointDescriptor",
    "ECCPointPayload",
    "Evidence",
    "ExperimentPack",
    "ExperimentPackRecommendation",
    "ExperimentPackStep",
    "ExperimentSpec",
    "ExperimentType",
    "FiniteFieldCheckPayload",
    "FormalConstraintPayload",
    "FuzzMutationPayload",
    "Hypothesis",
    "HypothesisAgentResult",
    "HypothesisBranch",
    "MathWorkspace",
    "MathAgentResult",
    "PluginMetadata",
    "PointDescriptorPayload",
    "PropertyInvariantPayload",
    "ReportAgentResult",
    "SmartContractAuditPayload",
    "SmartContractInventoryPayload",
    "SmartContractTestbedPayload",
    "StrategyAgentResult",
    "ReplayRequest",
    "ReplayResult",
    "ExplorationProfile",
    "ResearchMode",
    "ResearchReport",
    "ResearchSeed",
    "ResearchTarget",
    "ResearchTargetProfile",
    "ResearchSession",
    "RunArtifactReference",
    "RunManifest",
    "SandboxExecutionRequest",
    "SandboxExecutionResult",
    "SandboxSpec",
    "SyntheticResearchTarget",
    "SymbolicCheckPayload",
    "ToolPlan",
    "ToolComparison",
    "ToolMetadata",
]
