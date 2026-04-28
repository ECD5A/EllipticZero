from __future__ import annotations

import textwrap
from collections.abc import Callable
from dataclasses import dataclass

from app.cli.ui import AMBER, CYAN, GRAY, GREEN, RED, WHITE, LocalConsoleUI
from app.core.orchestrator import ResearchOrchestrator
from app.core.report_markdown import build_review_snapshot_items
from app.models.replay_result import ReplayResult
from app.models.session import ResearchSession
from app.tools.curve_registry import CURVE_REGISTRY, CurveRegistryEntry


@dataclass(frozen=True)
class CurveHelperChoice:
    label: str
    curve_name: str | None
    description: str


def curve_helper_choices(
    *,
    language: str,
    translate: Callable[..., str],
) -> list[CurveHelperChoice]:
    return [
        CurveHelperChoice(
            label=translate("curve_helper.auto.label"),
            curve_name=None,
            description=translate("curve_helper.auto.desc"),
        ),
        CurveHelperChoice(
            label=translate("curve_helper.secp256k1.label"),
            curve_name="secp256k1",
            description=translate("curve_helper.secp256k1.desc"),
        ),
        CurveHelperChoice(
            label=translate("curve_helper.secp256r1.label"),
            curve_name="secp256r1",
            description=translate("curve_helper.secp256r1.desc"),
        ),
        CurveHelperChoice(
            label=translate("curve_helper.ed25519.label"),
            curve_name="ed25519",
            description=translate("curve_helper.ed25519.desc"),
        ),
        CurveHelperChoice(
            label=translate("curve_helper.x25519.label"),
            curve_name="x25519",
            description=translate("curve_helper.x25519.desc"),
        ),
    ]


def tool_summary_lines(orchestrator: ResearchOrchestrator) -> list[str]:
    lines: list[str] = []
    for metadata in orchestrator.executor.registry.list_metadata():
        source = metadata.source_type
        if metadata.plugin_name:
            source = f"{source}:{metadata.plugin_name}"
        deterministic = "deterministic" if metadata.deterministic else "bounded"
        lines.append(
            f"{metadata.name} | {metadata.category} | {deterministic} | {source} | {metadata.description}"
        )
    return lines


def curve_summary_lines() -> list[str]:
    lines: list[str] = []
    for entry in CURVE_REGISTRY.list_entries():
        usage = ", ".join(entry.usage_category) or "general"
        lines.append(
            f"{entry.canonical_name} | {entry.family} | {entry.field_type} | {usage} | {entry.short_description}"
        )
    return lines


class InteractiveRenderer:
    def __init__(
        self,
        *,
        ui: LocalConsoleUI,
        translate: Callable[..., str],
        get_language: Callable[[], str],
        get_provider: Callable[[], str],
    ) -> None:
        self.ui = ui
        self.t = translate
        self.get_language = get_language
        self.get_provider = get_provider

    def home_header_lines(self) -> list[str]:
        lines = list(self.ui.hero_banner())
        lines.append(self.ui.subtitle(self.t("brand.subtitle")))
        lines.append("")
        lines.append(self.runtime_status_line())
        return lines

    def runtime_status_line(self) -> str:
        return self.ui.center_text(
            self.ui.status_chip(
                self.t("status.language", value=self.get_language().upper()),
                AMBER,
            )
            + "  "
            + self.ui.status_chip(self.get_provider(), CYAN)
            + "  "
            + self.ui.status_chip(self.t("status.local_lab"), GREEN)
        )

    def screen_header_lines(self, title: str, subtitle: str) -> list[str]:
        lines = list(self.home_header_lines())
        lines.append("")
        lines.append(self.ui.center_text(title, color=WHITE, bold=True))
        lines.append(self.ui.center_text(subtitle, color=GRAY, dim=True))
        lines.append(self.ui.separator())
        lines.append(
            self.ui.center_text(
                self.ui.status_chip(self.t("status.traces_on"), GREEN)
                + "  "
                + self.ui.status_chip(self.t("status.bundles_on"), GREEN)
                + "  "
                + self.ui.status_chip(self.t("status.reports_structured"), CYAN)
            )
        )
        return lines

    def print_panel_block(self, title: str, rows: list[str], *, title_color: str = WHITE) -> None:
        print(self.ui.center_text(title, color=title_color, bold=True))
        for line in self.ui.panel(rows):
            print(line)

    def print_list_block(self, title: str, items: list[str], *, color: str = CYAN) -> None:
        if not items:
            return
        self.print_panel_block(title, [f"- {item}" for item in items], title_color=color)

    def summary_row(self, label: str, value: str) -> str:
        return f"{label:<28} | {value}"

    def wrapped_panel_rows(self, text: str, *, width: int = 76) -> list[str]:
        stripped = text.strip()
        if not stripped:
            return []
        return textwrap.wrap(stripped, width=width) or [stripped]

    def localized_summary(self, summary: str) -> str:
        if self.get_language() != "ru":
            return summary

        normalized = " ".join(summary.split())
        known_mock_summaries = {
            self.t("summary.mock.ecc"): self.t("summary.mock.ecc"),
            self.t("summary.mock.contract"): self.t("summary.mock.contract"),
            (
                "The session preserved the original seed, produced bounded hypotheses, ran a registry-controlled "
                "local compute job, and recorded preliminary evidence without claiming a validated mathematical or "
                "cryptographic result."
            ): self.t("summary.mock.ecc"),
            (
                "The session preserved the original smart-contract audit seed, ran bounded local static analysis, "
                "and recorded review-oriented evidence without claiming a validated exploit path."
            ): self.t("summary.mock.contract"),
            (
                "The session preserved the original seed, ran a neutral bounded local classification pass, "
                "and avoided forcing the idea into a known ECC or smart-contract pattern."
            ): self.t("summary.mock.generic"),
        }
        return known_mock_summaries.get(normalized, summary)

    def doctor_status_color(self, status: str) -> str:
        if status == "error":
            return RED
        if status == "warning":
            return AMBER
        if status == "ok":
            return GREEN
        return CYAN

    def print_curve_helper(self, entry: CurveRegistryEntry) -> None:
        usage = ", ".join(entry.usage_category) or "general"
        alias_text = ", ".join(entry.aliases) if entry.aliases else self.t("value.none")
        self.print_panel_block(
            self.t("block.helper_curve_context"),
            [
                self.summary_row(self.t("label.canonical_name"), entry.canonical_name),
                self.summary_row(self.t("label.aliases"), alias_text),
                self.summary_row(self.t("label.family_usage"), f"{entry.family} | {usage}"),
                self.summary_row(self.t("label.description"), entry.short_description),
            ],
            title_color=AMBER,
        )

    def print_session_result(self, *, session: ResearchSession, helper_curve: str | None) -> None:
        assert session.report is not None
        summary_rows = [
            self.summary_row(self.t("label.session_id"), session.session_id),
            self.summary_row(self.t("label.confidence"), session.report.confidence.value),
            self.summary_row(
                self.t("label.hypotheses_evidence"),
                f"{len(session.hypotheses)} / {len(session.evidence)}",
            ),
        ]
        if session.research_target is not None and session.research_target.target_kind == "smart_contract":
            summary_rows.insert(
                1,
                self.summary_row(
                    self.t("label.description"),
                    session.research_target.target_reference,
                ),
            )
        else:
            summary_rows.insert(
                1,
                self.summary_row(self.t("label.helper_curve"), helper_curve or self.t("value.auto")),
            )
        if session.plugin_metadata:
            plugin_summary = ", ".join(
                f"{item.plugin_name}:{item.load_status}" for item in session.plugin_metadata
            )
            summary_rows.append(self.summary_row(self.t("label.plugins"), plugin_summary))
        self.ui.clear()
        for line in self.screen_header_lines(
            self.t("screen.session_complete.title"),
            self.t("screen.session_complete.subtitle"),
        ):
            print(line)
        self.print_panel_block(
            self.t("block.run_summary"),
            summary_rows,
            title_color=GREEN,
        )
        snapshot_rows = [
            self.summary_row(self.t(f"label.{key}"), value)
            for key, value in build_review_snapshot_items(session.report)
        ]
        if snapshot_rows:
            self.print_panel_block(
                self.t("block.review_snapshot"),
                snapshot_rows,
                title_color=AMBER,
            )
        self.print_panel_block(
            self.t("block.local_outputs"),
            [
                self.summary_row(self.t("label.session_json"), session.session_file_path or self.t("value.unavailable")),
                self.summary_row(self.t("label.trace_jsonl"), session.trace_file_path or self.t("value.unavailable")),
                self.summary_row(self.t("label.bundle_directory"), session.bundle_dir or self.t("value.unavailable")),
                self.summary_row(
                    self.t("label.comparative_report"),
                    session.comparative_report_file_path or self.t("value.unavailable"),
                ),
            ],
        )
        summary_text = self.localized_summary(session.report.summary)
        summary_rows = self.wrapped_panel_rows(summary_text)
        if summary_rows:
            self.print_panel_block(self.t("block.summary"), summary_rows)
        self.print_list_block(self.t("block.confidence_rationale"), session.report.confidence_rationale, color=GREEN)
        self.print_list_block(self.t("block.contract_overview"), session.report.contract_overview, color=CYAN)
        self.print_list_block(self.t("block.contract_finding_cards"), session.report.contract_finding_cards, color=AMBER)
        self.print_list_block(self.t("block.ecc_benchmark_summary"), session.report.ecc_benchmark_summary, color=CYAN)
        self.print_list_block(self.t("block.evidence_profile"), session.report.evidence_profile, color=CYAN)
        self.print_list_block(
            self.t("block.evidence_coverage_summary"),
            session.report.evidence_coverage_summary,
            color=CYAN,
        )
        self.print_list_block(self.t("block.validation_posture"), session.report.validation_posture, color=GREEN)
        self.print_list_block(self.t("block.shared_follow_up"), session.report.shared_follow_up, color=CYAN)
        self.print_list_block(self.t("block.calibration_blockers"), session.report.calibration_blockers, color=AMBER)
        self.print_list_block(self.t("block.reproducibility_summary"), session.report.reproducibility_summary, color=CYAN)
        self.print_list_block(self.t("block.quality_gates"), session.report.quality_gates, color=GREEN)
        self.print_list_block(self.t("block.hardening_summary"), session.report.hardening_summary, color=AMBER)
        self.print_list_block(
            self.t("block.toolchain_fingerprint"),
            session.report.toolchain_fingerprint_summary,
            color=CYAN,
        )
        self.print_list_block(
            self.t("block.secret_redaction_summary"),
            session.report.secret_redaction_summary,
            color=AMBER,
        )
        self.print_list_block(self.t("block.ecc_benchmark_posture"), session.report.ecc_benchmark_posture, color=GREEN)
        self.print_list_block(self.t("block.ecc_family_coverage"), session.report.ecc_family_coverage, color=CYAN)
        self.print_list_block(self.t("block.ecc_coverage_matrix"), session.report.ecc_coverage_matrix, color=CYAN)
        self.print_list_block(self.t("block.ecc_benchmark_case_summaries"), session.report.ecc_benchmark_case_summaries, color=CYAN)
        self.print_list_block(self.t("block.ecc_review_focus"), session.report.ecc_review_focus, color=CYAN)
        self.print_list_block(self.t("block.ecc_residual_risk"), session.report.ecc_residual_risk, color=AMBER)
        self.print_list_block(self.t("block.ecc_signal_consensus"), session.report.ecc_signal_consensus, color=GREEN)
        self.print_list_block(self.t("block.ecc_validation_matrix"), session.report.ecc_validation_matrix, color=GREEN)
        self.print_list_block(self.t("block.ecc_comparison_focus"), session.report.ecc_comparison_focus, color=CYAN)
        self.print_list_block(self.t("block.ecc_benchmark_delta"), session.report.ecc_benchmark_delta, color=CYAN)
        self.print_list_block(self.t("block.ecc_regression_summary"), session.report.ecc_regression_summary, color=AMBER)
        self.print_list_block(self.t("block.ecc_review_queue"), session.report.ecc_review_queue, color=GREEN)
        self.print_list_block(self.t("block.ecc_exit_criteria"), session.report.ecc_exit_criteria, color=GREEN)
        self.print_list_block(self.t("block.contract_inventory"), session.report.contract_inventory_summary, color=CYAN)
        self.print_list_block(self.t("block.contract_protocol_map"), session.report.contract_protocol_map, color=CYAN)
        self.print_list_block(self.t("block.contract_protocol_invariants"), session.report.contract_protocol_invariants, color=CYAN)
        self.print_list_block(self.t("block.contract_signal_consensus"), session.report.contract_signal_consensus, color=GREEN)
        self.print_list_block(self.t("block.contract_validation_matrix"), session.report.contract_validation_matrix, color=GREEN)
        self.print_list_block(self.t("block.contract_benchmark_posture"), session.report.contract_benchmark_posture, color=CYAN)
        self.print_list_block(self.t("block.contract_benchmark_pack_summary"), session.report.contract_benchmark_pack_summary, color=CYAN)
        self.print_list_block(self.t("block.contract_benchmark_case_summaries"), session.report.contract_benchmark_case_summaries, color=CYAN)
        self.print_list_block(self.t("block.contract_repo_priorities"), session.report.contract_repo_priorities, color=AMBER)
        self.print_list_block(self.t("block.contract_repo_triage"), session.report.contract_repo_triage, color=AMBER)
        self.print_list_block(self.t("block.contract_casebook_coverage"), session.report.contract_casebook_coverage, color=AMBER)
        self.print_list_block(self.t("block.contract_casebook_coverage_matrix"), session.report.contract_casebook_coverage_matrix, color=CYAN)
        self.print_list_block(self.t("block.contract_casebook_case_studies"), session.report.contract_casebook_case_studies, color=CYAN)
        self.print_list_block(self.t("block.contract_casebook_priority_cases"), session.report.contract_casebook_priority_cases, color=CYAN)
        self.print_list_block(self.t("block.contract_casebook_gaps"), session.report.contract_casebook_gaps, color=AMBER)
        self.print_list_block(self.t("block.contract_casebook_benchmark_support"), session.report.contract_casebook_benchmark_support, color=CYAN)
        self.print_list_block(self.t("block.contract_casebook_triage"), session.report.contract_casebook_triage, color=GREEN)
        self.print_list_block(self.t("block.contract_toolchain_alignment"), session.report.contract_toolchain_alignment, color=GREEN)
        self.print_list_block(self.t("block.contract_review_queue"), session.report.contract_review_queue, color=GREEN)
        self.print_list_block(self.t("block.contract_compile"), session.report.contract_compile_summary, color=CYAN)
        self.print_list_block(self.t("block.contract_surface"), session.report.contract_surface_summary, color=CYAN)
        self.print_list_block(self.t("block.contract_priority_findings"), session.report.contract_priority_findings, color=AMBER)
        self.print_list_block(self.t("block.contract_static_findings"), session.report.contract_static_findings, color=AMBER)
        self.print_list_block(self.t("block.contract_testbeds"), session.report.contract_testbed_findings, color=CYAN)
        self.print_list_block(self.t("block.contract_remediation_validation"), session.report.contract_remediation_validation, color=GREEN)
        self.print_list_block(self.t("block.contract_review_focus"), session.report.contract_review_focus, color=CYAN)
        self.print_list_block(self.t("block.contract_remediation_guidance"), session.report.contract_remediation_guidance, color=CYAN)
        self.print_list_block(self.t("block.contract_remediation_follow_up"), session.report.contract_remediation_follow_up, color=GREEN)
        self.print_list_block(self.t("block.contract_residual_risk"), session.report.contract_residual_risk, color=AMBER)
        self.print_list_block(self.t("block.contract_exit_criteria"), session.report.contract_exit_criteria, color=GREEN)
        self.print_list_block(self.t("block.contract_manual_review"), session.report.contract_manual_review_items, color=RED)
        self.print_list_block(self.t("block.before_after_comparison"), session.report.before_after_comparison, color=CYAN)
        self.print_list_block(self.t("block.regression_flags"), session.report.regression_flags, color=AMBER)
        self.print_list_block(self.t("block.agent_contributions"), session.report.agent_contributions, color=CYAN)
        self.print_list_block(self.t("block.local_experiments"), session.report.local_experiment_summary, color=CYAN)
        self.print_list_block(self.t("block.local_signals"), session.report.local_signal_summary, color=GREEN)
        self.print_list_block(self.t("block.dead_ends"), session.report.dead_end_summary, color=AMBER)
        self.print_list_block(self.t("block.next_defensive_leads"), session.report.next_defensive_leads, color=CYAN)
        self.print_list_block(self.t("block.tested_hypotheses"), session.report.tested_hypotheses, color=CYAN)
        self.print_list_block(self.t("block.tool_usage"), session.report.tool_usage_summary, color=CYAN)
        self.print_list_block(self.t("block.comparative_findings"), session.report.comparative_findings, color=CYAN)
        self.print_list_block(self.t("block.anomalies"), session.report.anomalies, color=AMBER)
        self.print_list_block(self.t("block.recommendations"), session.report.recommendations, color=CYAN)
        self.print_list_block(self.t("block.manual_review_items"), session.report.manual_review_items, color=RED)

    def print_replay_result(self, result: ReplayResult) -> None:
        self.ui.clear()
        for line in self.screen_header_lines(
            self.t("screen.replay_result.title"),
            self.t("screen.replay_result.subtitle"),
        ):
            print(line)
        header_color = GREEN if result.success else RED
        self.print_panel_block(
            self.t("block.replay_summary"),
            [
                self.summary_row(self.t("label.source_type"), result.source_type),
                self.summary_row(self.t("label.source_path"), result.source_path),
                self.summary_row(self.t("label.dry_run"), str(result.dry_run).lower()),
                self.summary_row(self.t("label.reexecuted"), str(result.reexecuted).lower()),
                self.summary_row(self.t("label.success"), str(result.success).lower()),
            ],
            title_color=header_color,
        )
        print(self.ui.center_text(result.summary, color=WHITE))
        output_rows: list[str] = []
        if result.generated_session_path:
            output_rows.append(self.summary_row(self.t("label.generated_session"), result.generated_session_path))
        if result.generated_trace_path:
            output_rows.append(self.summary_row(self.t("label.generated_trace"), result.generated_trace_path))
        if result.generated_bundle_path:
            output_rows.append(self.summary_row(self.t("label.generated_bundle"), result.generated_bundle_path))
        if output_rows:
            self.print_panel_block(self.t("block.replay_outputs"), output_rows, title_color=CYAN)
        self.print_list_block(self.t("block.replay_notes"), result.notes, color=CYAN)
