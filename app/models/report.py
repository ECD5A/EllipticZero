from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.types import ConfidenceLevel


class ResearchReport(BaseModel):
    """Final bounded report for a research session."""

    model_config = ConfigDict(extra="forbid")

    session_id: str
    seed_text: str
    summary: str
    research_mode: str | None = None
    exploration_profile: str | None = None
    research_target: str | None = None
    selected_pack_name: str | None = None
    recommended_pack_names: list[str] = Field(default_factory=list)
    executed_pack_steps: list[str] = Field(default_factory=list)
    tested_hypotheses: list[str] = Field(default_factory=list)
    tool_usage_summary: list[str] = Field(default_factory=list)
    local_experiment_summary: list[str] = Field(default_factory=list)
    local_signal_summary: list[str] = Field(default_factory=list)
    evidence_profile: list[str] = Field(default_factory=list)
    evidence_coverage_summary: list[str] = Field(default_factory=list)
    validation_posture: list[str] = Field(default_factory=list)
    shared_follow_up: list[str] = Field(default_factory=list)
    calibration_blockers: list[str] = Field(default_factory=list)
    reproducibility_summary: list[str] = Field(default_factory=list)
    toolchain_fingerprint_summary: list[str] = Field(default_factory=list)
    secret_redaction_summary: list[str] = Field(default_factory=list)
    quality_gates: list[str] = Field(default_factory=list)
    hardening_summary: list[str] = Field(default_factory=list)
    ecc_triage_snapshot: list[str] = Field(default_factory=list)
    ecc_benchmark_summary: list[str] = Field(default_factory=list)
    ecc_benchmark_posture: list[str] = Field(default_factory=list)
    ecc_family_coverage: list[str] = Field(default_factory=list)
    ecc_coverage_matrix: list[str] = Field(default_factory=list)
    ecc_benchmark_case_summaries: list[str] = Field(default_factory=list)
    ecc_review_focus: list[str] = Field(default_factory=list)
    ecc_residual_risk: list[str] = Field(default_factory=list)
    ecc_signal_consensus: list[str] = Field(default_factory=list)
    ecc_validation_matrix: list[str] = Field(default_factory=list)
    ecc_comparison_focus: list[str] = Field(default_factory=list)
    ecc_benchmark_delta: list[str] = Field(default_factory=list)
    ecc_regression_summary: list[str] = Field(default_factory=list)
    ecc_review_queue: list[str] = Field(default_factory=list)
    ecc_exit_criteria: list[str] = Field(default_factory=list)
    contract_overview: list[str] = Field(default_factory=list)
    contract_inventory_summary: list[str] = Field(default_factory=list)
    contract_protocol_map: list[str] = Field(default_factory=list)
    contract_protocol_invariants: list[str] = Field(default_factory=list)
    contract_signal_consensus: list[str] = Field(default_factory=list)
    contract_validation_matrix: list[str] = Field(default_factory=list)
    contract_benchmark_posture: list[str] = Field(default_factory=list)
    contract_benchmark_pack_summary: list[str] = Field(default_factory=list)
    contract_benchmark_case_summaries: list[str] = Field(default_factory=list)
    contract_repo_priorities: list[str] = Field(default_factory=list)
    contract_repo_triage: list[str] = Field(default_factory=list)
    contract_casebook_coverage: list[str] = Field(default_factory=list)
    contract_casebook_coverage_matrix: list[str] = Field(default_factory=list)
    contract_casebook_case_studies: list[str] = Field(default_factory=list)
    contract_casebook_priority_cases: list[str] = Field(default_factory=list)
    contract_casebook_gaps: list[str] = Field(default_factory=list)
    contract_casebook_benchmark_support: list[str] = Field(default_factory=list)
    contract_casebook_triage: list[str] = Field(default_factory=list)
    contract_toolchain_alignment: list[str] = Field(default_factory=list)
    contract_review_queue: list[str] = Field(default_factory=list)
    contract_compile_summary: list[str] = Field(default_factory=list)
    contract_surface_summary: list[str] = Field(default_factory=list)
    contract_priority_findings: list[str] = Field(default_factory=list)
    contract_finding_cards: list[str] = Field(default_factory=list)
    contract_static_findings: list[str] = Field(default_factory=list)
    contract_testbed_findings: list[str] = Field(default_factory=list)
    contract_remediation_validation: list[str] = Field(default_factory=list)
    contract_review_focus: list[str] = Field(default_factory=list)
    contract_remediation_guidance: list[str] = Field(default_factory=list)
    contract_remediation_follow_up: list[str] = Field(default_factory=list)
    contract_residual_risk: list[str] = Field(default_factory=list)
    contract_exit_criteria: list[str] = Field(default_factory=list)
    contract_manual_review_items: list[str] = Field(default_factory=list)
    contract_triage_snapshot: list[str] = Field(default_factory=list)
    remediation_delta_summary: list[str] = Field(default_factory=list)
    before_after_comparison: list[str] = Field(default_factory=list)
    regression_flags: list[str] = Field(default_factory=list)
    agent_contributions: list[str] = Field(default_factory=list)
    comparative_findings: list[str] = Field(default_factory=list)
    exploratory_findings: list[str] = Field(default_factory=list)
    exploratory_rounds_executed: int = 0
    dead_end_summary: list[str] = Field(default_factory=list)
    next_defensive_leads: list[str] = Field(default_factory=list)
    anomalies: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    manual_review_items: list[str] = Field(default_factory=list)
    confidence_rationale: list[str] = Field(default_factory=list)
    confidence: ConfidenceLevel

    @field_validator("session_id", "seed_text", "summary")
    @classmethod
    def validate_text_fields(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Report text fields cannot be empty.")
        return stripped

    @field_validator("research_mode", "exploration_profile", "research_target", "selected_pack_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None
