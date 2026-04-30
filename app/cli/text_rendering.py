from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.cli.i18n import normalize_language, t
from app.config import AppConfig
from app.core.orchestrator import ResearchOrchestrator
from app.core.replay_loader import LoadedReplaySource
from app.llm.router import build_route_overview, summarize_route_mode
from app.models.doctor import DoctorReport
from app.models.replay_result import ReplayResult
from app.models.report import ResearchReport
from app.models.run_manifest import RunManifest
from app.models.session import ResearchSession


def build_evaluation_summary_payload(
    *,
    golden_cases: list[dict[str, object]],
    pack_names: list[str],
    provider_names: list[str],
) -> dict[str, Any]:
    domain_counts: dict[str, int] = {}
    for case in golden_cases:
        domain = str(case.get("domain", "unknown") or "unknown")
        domain_counts[domain] = domain_counts.get(domain, 0) + 1
    return {
        "project": "EllipticZero",
        "summary_type": "evaluation_summary",
        "license": {
            "current": "FSL-1.1-ALv2",
            "future_license": "Apache-2.0",
            "future_license_trigger": "second anniversary of the date each published version was made available",
            "commercial_boundary": [
                "competing commercial use",
                "hosted or managed service use",
                "SaaS or platform deployment",
                "OEM distribution",
                "white-label usage",
                "resale",
            ],
        },
        "purpose": [
            "Source-available local lab for scoped smart-contract security review and ECC research.",
            "Main focus: reproducible evidence, cautious reporting, and explicit manual-review boundaries.",
        ],
        "domains": ["smart_contract_audit", "ecc_research"],
        "golden_cases": {
            "count": len(golden_cases),
            "domain_counts": dict(sorted(domain_counts.items())),
            "case_ids": [
                str(case.get("case_id", "")).strip()
                for case in golden_cases
                if str(case.get("case_id", "")).strip()
            ],
        },
        "experiment_packs": {
            "count": len(pack_names),
            "pack_names": list(pack_names),
        },
        "provider_paths": list(provider_names),
        "fast_no_key_checks": [
            "python -m app.main --doctor",
            "python -m app.main --list-golden-cases",
            "python -m app.main --golden-case ecc-secp256k1-point-format-edge",
            "python -m app.main --golden-case contract-repo-scale-lending-protocol",
            "python -m app.main --provider openrouter --provider-context-preview \"Review provider privacy before running live agents.\"",
        ],
        "saved_run_checks": [
            "python -m app.main --evaluation-summary --replay-bundle .\\artifacts\\bundles\\session_id",
            "python -m app.main --replay-bundle .\\artifacts\\bundles\\session_id --export-sarif .\\artifacts\\sarif\\session_id.sarif",
            "python -m app.main --replay-bundle .\\artifacts\\bundles\\session_id --export-report-md .\\artifacts\\reports\\session_id.md",
        ],
        "evaluation_focus": {
            "ecc": [
                "point formats",
                "curve metadata",
                "subgroup/cofactor",
                "twist hygiene",
                "family transitions",
                "domain completeness",
            ],
            "smart_contracts": [
                "parser",
                "compile",
                "inventory",
                "repo map",
                "casebook",
                "benchmark",
                "comparison",
                "manual-review lanes",
            ],
            "evidence_boundary": (
                "Model output is interpretation; local tool outputs and artifacts carry the evidence trail."
            ),
        },
        "docs": {
            "en": [
                "README.md",
                "EVALUATION.md",
                "SECURITY.md",
                "examples/SAMPLE_OUTPUTS.md",
                "COMMERCIAL_LICENSE.md",
            ],
            "ru": [
                "README.ru.md",
                "docs/ru/EVALUATION.ru.md",
                "docs/ru/SECURITY.ru.md",
                "examples/SAMPLE_OUTPUTS.ru.md",
                "docs/ru/COMMERCIAL_LICENSE.ru.md",
            ],
        },
    }


def build_run_evaluation_summary_payload(
    *,
    loaded_source: LoadedReplaySource,
) -> dict[str, Any]:
    session = loaded_source.session
    manifest = loaded_source.manifest
    report = session.report if session is not None else None

    report_snapshot_summary = _report_snapshot_summary(
        report=report,
        manifest=manifest,
    )
    focus_summary = _report_focus_summary(report=report, manifest=manifest)
    quality_gates = _quality_gates(report=report, manifest=manifest)
    hardening_summary = _hardening_summary(report=report, manifest=manifest)
    evidence_coverage = _evidence_coverage(report=report, manifest=manifest)
    artifact_paths = _artifact_paths(
        loaded_source=loaded_source,
        session=session,
        manifest=manifest,
    )
    review_status = _review_status(
        report_snapshot_summary=report_snapshot_summary,
        focus_summary=focus_summary,
        quality_gates=quality_gates,
        hardening_summary=hardening_summary,
        evidence_coverage=evidence_coverage,
        artifacts=artifact_paths,
    )

    return {
        "project": "EllipticZero",
        "summary_type": "run_evaluation_summary",
        "source": {
            "source_type": loaded_source.source_type,
            "source_path": loaded_source.source_path,
            "original_session_id": loaded_source.original_session_id,
            "recovered_session": session is not None,
            "recovered_manifest": manifest is not None,
        },
        "session": {
            "session_id": (
                session.session_id
                if session is not None
                else (manifest.session_id if manifest is not None else None)
            ),
            "research_mode": loaded_source.research_mode,
            "exploration_profile": loaded_source.exploration_profile,
            "selected_pack_name": loaded_source.selected_pack_name,
            "tool_names": list(loaded_source.tool_names),
            "experiment_types": list(loaded_source.experiment_types),
        },
        "review_status": review_status,
        "report": {
            "summary": _report_summary(report=report, manifest=manifest),
            "confidence": _report_confidence(report=report, manifest=manifest),
            "report_snapshot_summary": report_snapshot_summary,
            "report_snapshot_count": len(report_snapshot_summary),
            "focus_summary": focus_summary,
            "quality_gates": quality_gates,
            "hardening_summary": hardening_summary,
        },
        "evidence": {
            "coverage": evidence_coverage,
            "tool_count": len(loaded_source.tool_names),
            "experiment_type_count": len(loaded_source.experiment_types),
            "artifact_reference_count": len(loaded_source.artifact_paths),
        },
        "artifacts": artifact_paths,
        "notes": list(loaded_source.notes),
    }


def render_evaluation_summary(
    *,
    language: str,
    golden_cases: list[dict[str, object]],
    pack_names: list[str],
    provider_names: list[str],
    output_format: str = "text",
) -> str:
    lang = normalize_language(language)
    payload = build_evaluation_summary_payload(
        golden_cases=golden_cases,
        pack_names=pack_names,
        provider_names=provider_names,
    )
    if output_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if output_format != "text":
        raise ValueError(f"Unsupported evaluation summary format: {output_format}")

    domain_summary = ", ".join(
        f"{domain}={count}"
        for domain, count in payload["golden_cases"]["domain_counts"].items()
    )
    providers = ", ".join(payload["provider_paths"])

    if lang == "ru":
        return "\n".join(
            [
                "Сводка оценки EllipticZero",
                "",
                "Назначение:",
                "- Source-available локальная лаборатория для контролируемого аудита смарт-контрактов и ECC-исследований.",
                "- Основной фокус: воспроизводимая доказательная база, осторожные отчёты и явные границы ручной проверки.",
                "",
                "Покрытие:",
                "- Домены: аудит смарт-контрактов; ECC / защитная криптография.",
                f"- Golden cases: {len(golden_cases)} безопасных синтетических кейсов ({domain_summary}).",
                f"- Experiment packs: {len(pack_names)} встроенных benchmark/review-пакетов.",
                f"- Пути провайдеров: {providers}.",
                "",
                "Быстрая проверка без ключей:",
                "- python -m app.main --doctor",
                "- python -m app.main --list-golden-cases",
                "- python -m app.main --golden-case contract-repo-scale-lending-protocol",
                "- python -m app.main --golden-case ecc-secp256k1-point-format-edge",
                "",
                "Что оценивать:",
                "- Смарт-контракты: parser, compile, inventory, repo map, casebook, benchmark, comparison и manual-review lanes.",
                "- ECC: форматы точек, метаданные кривых, subgroup/cofactor, twist hygiene, family transitions, domain completeness.",
                "- Граница доказательств: вывод модели является интерпретацией; локальные tool outputs и artifacts несут доказательную базу.",
                "",
                "Документы:",
                "- README.ru.md",
                "- docs/ru/EVALUATION.ru.md",
                "- docs/ru/SECURITY.ru.md",
                "- examples/SAMPLE_OUTPUTS.ru.md",
                "- docs/ru/COMMERCIAL_LICENSE.ru.md",
                "",
                "Коммерческая граница:",
                "- Оценка, исследование, внутренний review и локальное тестирование доступны по условиям публичной лицензии.",
                "- Продукт, hosted-сервис, OEM, white-label, resale или похожие коммерческие сценарии лучше согласовать заранее.",
            ]
        )

    return "\n".join(
        [
            "EllipticZero Evaluation Summary",
            "",
            "Purpose:",
            "- Source-available local lab for scoped smart-contract security review and ECC research.",
            "- Main focus: reproducible evidence, cautious reporting, and explicit manual-review boundaries.",
            "",
            "Coverage:",
            "- Domains: smart-contract audit; ECC / defensive cryptography research.",
            f"- Golden cases: {len(golden_cases)} safe synthetic cases ({domain_summary}).",
            f"- Experiment packs: {len(pack_names)} built-in benchmark/review packs.",
            f"- Provider paths: {providers}.",
            "",
            "Fast no-key checks:",
            "- python -m app.main --doctor",
            "- python -m app.main --list-golden-cases",
            "- python -m app.main --golden-case contract-repo-scale-lending-protocol",
            "- python -m app.main --golden-case ecc-secp256k1-point-format-edge",
            "",
            "What to evaluate:",
            "- Smart contracts: parser, compile, inventory, repo map, casebook, benchmark, comparison, manual-review lanes.",
            "- ECC: point formats, curve metadata, subgroup/cofactor, twist hygiene, family transitions, domain completeness.",
            "- Evidence boundary: model output is interpretation; local tool outputs and artifacts carry the evidence trail.",
            "",
            "Docs:",
            "- README.md",
            "- EVALUATION.md",
            "- SECURITY.md",
            "- examples/SAMPLE_OUTPUTS.md",
            "- COMMERCIAL_LICENSE.md",
            "",
            "Commercial boundary:",
            "- Evaluation, research, internal review, and local testing are available under the public license terms.",
            "- Product, hosted service, OEM, white-label, resale, or similar commercial paths should be discussed before deployment.",
        ]
    )


def render_run_evaluation_summary(
    *,
    language: str,
    loaded_source: LoadedReplaySource,
    output_format: str = "text",
) -> str:
    lang = normalize_language(language)
    payload = build_run_evaluation_summary_payload(loaded_source=loaded_source)
    if output_format == "json":
        return json.dumps(payload, ensure_ascii=False, indent=2)
    if output_format != "text":
        raise ValueError(f"Unsupported run evaluation summary format: {output_format}")

    if lang == "ru":
        return "\n".join(
            [
                "Сводка сохраненного запуска EllipticZero",
                "",
                "Источник:",
                f"- Тип: {payload['source']['source_type']}",
                f"- Путь: {payload['source']['source_path']}",
                f"- Session ID: {payload['session']['session_id'] or 'недоступно'}",
                f"- Confidence: {payload['report']['confidence'] or 'недоступно'}",
                f"- Pack: {payload['session']['selected_pack_name'] or 'none'}",
                "",
                "Review Status:",
                *_render_review_status(payload["review_status"], language=lang),
                "",
                "Report Snapshot:",
                *_render_list(payload["report"]["report_snapshot_summary"], "snapshot недоступен"),
                "",
                "Focus Summary:",
                *_render_list(payload["report"]["focus_summary"], "focus summary недоступен"),
                "",
                "Evidence Coverage:",
                *_render_evidence_lines(payload["evidence"], language=lang),
                "",
                "Quality Gates:",
                *_render_list(payload["report"]["quality_gates"], "quality gates не записаны"),
                "",
                "Hardening Summary:",
                *_render_list(payload["report"]["hardening_summary"], "hardening summary не записан"),
                "",
                "Artifacts:",
                *_render_artifact_lines(payload["artifacts"]),
            ]
        )

    return "\n".join(
        [
            "EllipticZero Run Evaluation Summary",
            "",
            "Source:",
            f"- Type: {payload['source']['source_type']}",
            f"- Path: {payload['source']['source_path']}",
            f"- Session ID: {payload['session']['session_id'] or 'unavailable'}",
            f"- Confidence: {payload['report']['confidence'] or 'unavailable'}",
            f"- Pack: {payload['session']['selected_pack_name'] or 'none'}",
            "",
            "Review Status:",
            *_render_review_status(payload["review_status"], language=lang),
            "",
            "Report Snapshot:",
            *_render_list(payload["report"]["report_snapshot_summary"], "snapshot unavailable"),
            "",
            "Focus Summary:",
            *_render_list(payload["report"]["focus_summary"], "focus summary unavailable"),
            "",
            "Evidence Coverage:",
            *_render_evidence_lines(payload["evidence"], language=lang),
            "",
            "Quality Gates:",
            *_render_list(payload["report"]["quality_gates"], "no quality gates recorded"),
            "",
            "Hardening Summary:",
            *_render_list(payload["report"]["hardening_summary"], "no hardening summary recorded"),
            "",
            "Artifacts:",
            *_render_artifact_lines(payload["artifacts"]),
        ]
    )


def _report_summary(
    *,
    report: ResearchReport | None,
    manifest: RunManifest | None,
) -> str | None:
    if report is not None:
        return report.summary
    if manifest is not None:
        return manifest.report_summary
    return None


def _report_confidence(
    *,
    report: ResearchReport | None,
    manifest: RunManifest | None,
) -> str | None:
    if report is not None:
        return report.confidence.value
    if manifest is not None:
        return manifest.confidence
    return None


def _report_snapshot_summary(
    *,
    report: ResearchReport | None,
    manifest: RunManifest | None,
) -> list[str]:
    if manifest is not None and manifest.report_snapshot_summary:
        return list(manifest.report_snapshot_summary)
    if report is None:
        return []
    items: list[str] = []
    items.extend(report.contract_triage_snapshot[:4])
    items.extend(report.ecc_triage_snapshot[:4])
    items.extend(report.remediation_delta_summary[:2])
    items.extend(report.before_after_comparison[:1])
    items.extend(report.quality_gates[:1])
    return _ordered_nonempty(items)[:6]


def _report_focus_summary(
    *,
    report: ResearchReport | None,
    manifest: RunManifest | None,
) -> list[str]:
    if manifest is not None and manifest.report_focus_summary:
        return list(manifest.report_focus_summary)
    if report is None:
        return []
    items: list[str] = []
    items.extend(report.contract_repo_triage[:2])
    items.extend(report.contract_review_focus[:1])
    items.extend(report.ecc_benchmark_posture[:1])
    items.extend(report.ecc_coverage_matrix[:1])
    items.extend(report.ecc_validation_matrix[:1])
    items.extend(report.ecc_review_queue[:1])
    items.extend(report.validation_posture[:1])
    items.extend(report.shared_follow_up[:1])
    items.extend(report.recommendations[:1])
    return _ordered_nonempty(items)[:4]


def _quality_gates(
    *,
    report: ResearchReport | None,
    manifest: RunManifest | None,
) -> list[str]:
    if manifest is not None and manifest.quality_gate_summary:
        return list(manifest.quality_gate_summary)
    if report is not None:
        return list(report.quality_gates)
    return []


def _hardening_summary(
    *,
    report: ResearchReport | None,
    manifest: RunManifest | None,
) -> list[str]:
    if manifest is not None and manifest.hardening_summary:
        return list(manifest.hardening_summary)
    if report is not None:
        return list(report.hardening_summary)
    return []


def _evidence_coverage(
    *,
    report: ResearchReport | None,
    manifest: RunManifest | None,
) -> dict[str, Any] | list[str]:
    if manifest is not None and manifest.evidence_coverage_summary:
        return dict(manifest.evidence_coverage_summary)
    if report is not None:
        return list(report.evidence_coverage_summary)
    return {}


def _artifact_paths(
    *,
    loaded_source: LoadedReplaySource,
    session: ResearchSession | None,
    manifest: RunManifest | None,
) -> dict[str, str | None]:
    bundle_dir = loaded_source.bundle_dir or (session.bundle_dir if session is not None else None)
    if loaded_source.source_type == "bundle" and bundle_dir is None:
        bundle_dir = loaded_source.source_path

    manifest_path = session.manifest_file_path if session is not None else None
    if manifest_path is None and loaded_source.source_type == "manifest":
        manifest_path = loaded_source.source_path
    if manifest_path is None and bundle_dir:
        bundle_manifest_path = Path(bundle_dir) / "manifest.json"
        manifest_path = str(bundle_manifest_path) if bundle_manifest_path.exists() else None

    session_path = session.session_file_path if session is not None else None
    if session_path is None and manifest is not None:
        session_path = manifest.session_file_path
    if session_path is None and loaded_source.source_type == "session":
        session_path = loaded_source.source_path

    return {
        "source": loaded_source.source_path,
        "session_json": session_path,
        "trace_jsonl": loaded_source.trace_file_path,
        "manifest_json": manifest_path,
        "bundle_dir": bundle_dir,
        "comparative_report_json": (
            session.comparative_report_file_path
            if session is not None
            else (manifest.comparative_report_path if manifest is not None else None)
        ),
    }


def _review_status(
    *,
    report_snapshot_summary: list[str],
    focus_summary: list[str],
    quality_gates: list[str],
    hardening_summary: list[str],
    evidence_coverage: dict[str, Any] | list[str],
    artifacts: dict[str, str | None],
) -> dict[str, Any]:
    evidence_count = _coverage_int(evidence_coverage, "evidence_count")
    tool_backed_count = _coverage_int(evidence_coverage, "tool_backed_evidence_count")
    unique_tool_count = _coverage_int(evidence_coverage, "unique_tool_count")
    experiment_type_count = _coverage_int(evidence_coverage, "experiment_type_count")
    comparison_ready = _coverage_bool(evidence_coverage, "before_after_ready")
    missing_artifacts = [
        key
        for key in ("session_json", "manifest_json")
        if not artifacts.get(key)
    ]

    if evidence_count <= 0 or tool_backed_count <= 0:
        evidence_depth = "missing"
    elif evidence_count == 1 or unique_tool_count <= 1:
        evidence_depth = "thin"
    elif evidence_count >= 3 and unique_tool_count >= 2 and experiment_type_count >= 2:
        evidence_depth = "strong"
    else:
        evidence_depth = "usable"

    blockers: list[str] = []
    if not report_snapshot_summary:
        blockers.append("missing report snapshot summary")
    if not focus_summary:
        blockers.append("missing focus summary")
    if evidence_depth == "missing":
        blockers.append("no tool-backed evidence coverage recorded")
    elif evidence_depth == "thin":
        blockers.append("thin evidence depth; repeat with additional bounded tool paths")
    if missing_artifacts:
        blockers.append("missing required reviewer artifacts: " + ", ".join(missing_artifacts))
    if not quality_gates:
        blockers.append("quality gates not recorded")
    if not hardening_summary:
        blockers.append("hardening summary not recorded")

    ready_for_review = (
        bool(report_snapshot_summary)
        and bool(focus_summary)
        and evidence_depth != "missing"
        and not missing_artifacts
    )
    if not ready_for_review:
        verdict = "needs_artifacts_or_evidence"
    elif blockers:
        verdict = "reviewable_with_manual_caution"
    else:
        verdict = "ready_for_review"

    return {
        "verdict": verdict,
        "ready_for_review": ready_for_review,
        "needs_manual_review": True,
        "evidence_depth": evidence_depth,
        "comparison_ready": comparison_ready,
        "missing_artifacts": missing_artifacts,
        "blockers": blockers,
    }


def _coverage_int(coverage: dict[str, Any] | list[str], key: str) -> int:
    if isinstance(coverage, dict):
        value = coverage.get(key)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return 0


def _coverage_bool(coverage: dict[str, Any] | list[str], key: str) -> bool:
    if not isinstance(coverage, dict):
        return False
    value = coverage.get(key)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "ready"}
    return bool(value)


def _render_list(items: object, empty_message: str) -> list[str]:
    if not isinstance(items, list) or not items:
        return [f"- {empty_message}"]
    return [f"- {item}" for item in items]


def _render_review_status(status: object, *, language: str) -> list[str]:
    if not isinstance(status, dict):
        return ["- review status unavailable"]
    yes = "да" if language == "ru" else "yes"
    no = "нет" if language == "ru" else "no"
    manual_review = "требуется" if language == "ru" else "required"
    missing = status.get("missing_artifacts")
    blockers = status.get("blockers")
    lines = [
        f"- verdict: {status.get('verdict', 'unavailable')}",
        f"- ready_for_review: {yes if status.get('ready_for_review') else no}",
        f"- evidence_depth: {status.get('evidence_depth', 'unavailable')}",
        f"- comparison_ready: {yes if status.get('comparison_ready') else no}",
        f"- manual_review: {manual_review}",
    ]
    if isinstance(missing, list) and missing:
        lines.append("- missing_artifacts: " + ", ".join(str(item) for item in missing))
    else:
        lines.append("- missing_artifacts: none")
    if isinstance(blockers, list) and blockers:
        lines.append("- blockers: " + "; ".join(str(item) for item in blockers))
    else:
        lines.append("- blockers: none")
    return lines


def _render_evidence_lines(evidence: object, *, language: str) -> list[str]:
    if not isinstance(evidence, dict):
        return ["- evidence coverage unavailable"]
    coverage = evidence.get("coverage")
    lines: list[str] = []
    if isinstance(coverage, dict):
        for key in (
            "evidence_count",
            "tool_backed_evidence_count",
            "unique_tool_count",
            "experiment_type_count",
            "artifact_reference_count",
            "filtered_artifact_reference_count",
            "finding_card_count",
            "manual_review_item_count",
            "quality_gate_count",
            "before_after_ready",
        ):
            if key in coverage:
                lines.append(f"- {key}: {coverage[key]}")
        experiment_types = coverage.get("experiment_types")
        if isinstance(experiment_types, list) and experiment_types:
            lines.append("- experiment_types: " + ", ".join(str(item) for item in experiment_types))
    elif isinstance(coverage, list) and coverage:
        lines.extend(
            [
                f"- tool_count: {evidence.get('tool_count', 0)}",
                f"- experiment_type_count: {evidence.get('experiment_type_count', 0)}",
                f"- artifact_reference_count: {evidence.get('artifact_reference_count', 0)}",
            ]
        )
        lines.extend(f"- {item}" for item in coverage)
    else:
        lines.extend(
            [
                f"- tool_count: {evidence.get('tool_count', 0)}",
                f"- experiment_type_count: {evidence.get('experiment_type_count', 0)}",
                f"- artifact_reference_count: {evidence.get('artifact_reference_count', 0)}",
            ]
        )
        if language == "ru":
            lines.append("- подробная сводка покрытия недоступна")
        else:
            lines.append("- detailed coverage summary unavailable")
    return lines


def _render_artifact_lines(artifacts: object) -> list[str]:
    if not isinstance(artifacts, dict):
        return ["- artifacts unavailable"]
    lines: list[str] = []
    for key in (
        "source",
        "session_json",
        "trace_jsonl",
        "manifest_json",
        "bundle_dir",
        "comparative_report_json",
    ):
        value = artifacts.get(key)
        lines.append(f"- {key}: {value or 'unavailable'}")
    return lines


def _ordered_nonempty(values: list[str]) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def render_live_smoke_result(
    *,
    language: str,
    provider: str,
    model: str,
    timeout_seconds: int,
    max_request_tokens: int,
    output: str,
) -> str:
    lang = normalize_language(language)
    return "\n".join(
        [
            t(lang, "live_smoke.title"),
            f"{t(lang, 'live_smoke.provider')}: {provider}",
            f"{t(lang, 'live_smoke.model')}: {model}",
            f"{t(lang, 'live_smoke.timeout')}: {timeout_seconds}",
            f"{t(lang, 'live_smoke.max_request_tokens')}: {max_request_tokens}",
            "",
            f"{t(lang, 'live_smoke.result')}:",
            output,
        ]
    )


def render_report(
    *,
    language: str,
    research_mode: str,
    selected_pack_name: str | None,
    recommended_pack_names: list[str],
    executed_pack_steps: list[str],
    session_path: str,
    trace_path: str | None,
    bundle_path: str | None,
    comparative_report_path: str | None,
    comparative_generated: bool,
    plugin_summary: str | None,
    session_id: str,
    report_summary: str,
    evidence_profile: list[str],
    evidence_coverage_summary: list[str],
    validation_posture: list[str],
    shared_follow_up: list[str],
    calibration_blockers: list[str],
    reproducibility_summary: list[str],
    toolchain_fingerprint_summary: list[str],
    secret_redaction_summary: list[str],
    quality_gates: list[str],
    hardening_summary: list[str],
    ecc_triage_snapshot: list[str],
    ecc_benchmark_summary: list[str],
    ecc_benchmark_posture: list[str],
    ecc_family_coverage: list[str],
    ecc_coverage_matrix: list[str],
    ecc_benchmark_case_summaries: list[str],
    ecc_review_focus: list[str],
    ecc_residual_risk: list[str],
    ecc_signal_consensus: list[str],
    ecc_validation_matrix: list[str],
    ecc_comparison_focus: list[str],
    ecc_benchmark_delta: list[str],
    ecc_regression_summary: list[str],
    ecc_review_queue: list[str],
    ecc_exit_criteria: list[str],
    contract_overview: list[str],
    contract_inventory_summary: list[str],
    contract_protocol_map: list[str],
    contract_protocol_invariants: list[str],
    contract_signal_consensus: list[str],
    contract_validation_matrix: list[str],
    contract_benchmark_posture: list[str],
    contract_benchmark_pack_summary: list[str],
    contract_benchmark_case_summaries: list[str],
    contract_repo_priorities: list[str],
    contract_repo_triage: list[str],
    contract_casebook_coverage: list[str],
    contract_casebook_coverage_matrix: list[str],
    contract_casebook_case_studies: list[str],
    contract_casebook_priority_cases: list[str],
    contract_casebook_gaps: list[str],
    contract_casebook_benchmark_support: list[str],
    contract_casebook_triage: list[str],
    contract_toolchain_alignment: list[str],
    contract_review_queue: list[str],
    contract_compile_summary: list[str],
    contract_surface_summary: list[str],
    contract_priority_findings: list[str],
    contract_finding_cards: list[str],
    contract_known_case_matches: list[str],
    contract_static_findings: list[str],
    contract_testbed_findings: list[str],
    contract_remediation_validation: list[str],
    contract_review_focus: list[str],
    contract_remediation_guidance: list[str],
    contract_remediation_follow_up: list[str],
    contract_residual_risk: list[str],
    contract_exit_criteria: list[str],
    contract_manual_review_items: list[str],
    contract_triage_snapshot: list[str],
    remediation_delta_summary: list[str],
    before_after_comparison: list[str],
    regression_flags: list[str],
    tested_hypotheses: list[str],
    tool_usage_summary: list[str],
    comparative_findings: list[str],
    anomalies: list[str],
    recommendations: list[str],
    manual_review_items: list[str],
    confidence_rationale: list[str],
    confidence: str,
) -> str:
    lang = normalize_language(language)
    lines = [
        f"{t(lang, 'report.session_id')}: {session_id}",
        f"{t(lang, 'report.research_mode')}: {research_mode}",
    ]
    if selected_pack_name:
        lines.append(f"{t(lang, 'report.experiment_pack')}: {selected_pack_name}")
    if recommended_pack_names:
        lines.append(f"{t(lang, 'report.recommended_packs')}: {', '.join(recommended_pack_names)}")
    if executed_pack_steps:
        lines.append(f"{t(lang, 'report.executed_pack_steps')}: {', '.join(executed_pack_steps)}")
    lines.extend(
        [
            f"{t(lang, 'report.stored_session')}: {session_path}",
            f"{t(lang, 'report.stored_trace')}: {trace_path or t(lang, 'value.unavailable')}",
            f"{t(lang, 'report.bundle')}: {bundle_path or t(lang, 'value.unavailable')}",
            *(
                [
                    f"{t(lang, 'report.saved_run_evaluation')}: "
                    f"{_saved_run_evaluation_command(bundle_path)}"
                ]
                if bundle_path
                else []
            ),
            (
                f"{t(lang, 'report.comparative_analysis')}: "
                f"{t(lang, 'report.comparative_generated') if comparative_generated else t(lang, 'report.comparative_limited')}"
            ),
            f"{t(lang, 'report.comparative_report')}: {comparative_report_path or t(lang, 'value.unavailable')}",
        ]
    )
    if plugin_summary:
        lines.append(f"{t(lang, 'report.plugins')}: {plugin_summary}")
    lines.extend(
        [
            "",
            f"{t(lang, 'report.summary')}:",
            report_summary,
            "",
            f"{t(lang, 'report.confidence')}: {confidence}",
        ]
    )
    if contract_triage_snapshot:
        lines.extend(["", f"{t(lang, 'report.contract_triage_snapshot')}:"])
        lines.extend(f"- {item}" for item in contract_triage_snapshot)
    if remediation_delta_summary:
        lines.extend(["", f"{t(lang, 'report.remediation_delta_summary')}:"])
        lines.extend(f"- {item}" for item in remediation_delta_summary)
    if ecc_triage_snapshot:
        lines.extend(["", f"{t(lang, 'report.ecc_triage_snapshot')}:"])
        lines.extend(f"- {item}" for item in ecc_triage_snapshot)
    if confidence_rationale:
        lines.extend(["", f"{t(lang, 'report.confidence_rationale')}:"])
        lines.extend(f"- {item}" for item in confidence_rationale)
    if contract_overview:
        lines.extend(["", f"{t(lang, 'report.contract_overview')}:"])
        lines.extend(f"- {item}" for item in contract_overview)
    if contract_finding_cards:
        lines.extend(["", f"{t(lang, 'report.contract_finding_cards')}:"])
        lines.extend(f"- {item}" for item in contract_finding_cards)
    if contract_known_case_matches:
        lines.extend(["", f"{t(lang, 'report.contract_known_case_matches')}:"])
        lines.extend(f"- {item}" for item in contract_known_case_matches)
    if ecc_benchmark_summary:
        lines.extend(["", f"{t(lang, 'report.ecc_benchmark_summary')}:"])
        lines.extend(f"- {item}" for item in ecc_benchmark_summary)
    if evidence_profile:
        lines.extend(["", f"{t(lang, 'report.evidence_profile')}:"])
        lines.extend(f"- {item}" for item in evidence_profile)
    if evidence_coverage_summary:
        lines.extend(["", f"{t(lang, 'report.evidence_coverage_summary')}:"])
        lines.extend(f"- {item}" for item in evidence_coverage_summary)
    if validation_posture:
        lines.extend(["", f"{t(lang, 'report.validation_posture')}:"])
        lines.extend(f"- {item}" for item in validation_posture)
    if shared_follow_up:
        lines.extend(["", f"{t(lang, 'report.shared_follow_up')}:"])
        lines.extend(f"- {item}" for item in shared_follow_up)
    if calibration_blockers:
        lines.extend(["", f"{t(lang, 'report.calibration_blockers')}:"])
        lines.extend(f"- {item}" for item in calibration_blockers)
    if reproducibility_summary:
        lines.extend(["", f"{t(lang, 'report.reproducibility_summary')}:"])
        lines.extend(f"- {item}" for item in reproducibility_summary)
    if quality_gates:
        lines.extend(["", f"{t(lang, 'report.quality_gates')}:"])
        lines.extend(f"- {item}" for item in quality_gates)
    if hardening_summary:
        lines.extend(["", f"{t(lang, 'report.hardening_summary')}:"])
        lines.extend(f"- {item}" for item in hardening_summary)
    if toolchain_fingerprint_summary:
        lines.extend(["", f"{t(lang, 'report.toolchain_fingerprint')}:"])
        lines.extend(f"- {item}" for item in toolchain_fingerprint_summary)
    if secret_redaction_summary:
        lines.extend(["", f"{t(lang, 'report.secret_redaction_summary')}:"])
        lines.extend(f"- {item}" for item in secret_redaction_summary)
    if ecc_benchmark_posture:
        lines.extend(["", f"{t(lang, 'report.ecc_benchmark_posture')}:"])
        lines.extend(f"- {item}" for item in ecc_benchmark_posture)
    if ecc_family_coverage:
        lines.extend(["", f"{t(lang, 'report.ecc_family_coverage')}:"])
        lines.extend(f"- {item}" for item in ecc_family_coverage)
    if ecc_coverage_matrix:
        lines.extend(["", f"{t(lang, 'report.ecc_coverage_matrix')}:"])
        lines.extend(f"- {item}" for item in ecc_coverage_matrix)
    if ecc_benchmark_case_summaries:
        lines.extend(["", f"{t(lang, 'report.ecc_benchmark_case_summaries')}:"])
        lines.extend(f"- {item}" for item in ecc_benchmark_case_summaries)
    if ecc_review_focus:
        lines.extend(["", f"{t(lang, 'report.ecc_review_focus')}:"])
        lines.extend(f"- {item}" for item in ecc_review_focus)
    if ecc_residual_risk:
        lines.extend(["", f"{t(lang, 'report.ecc_residual_risk')}:"])
        lines.extend(f"- {item}" for item in ecc_residual_risk)
    if ecc_signal_consensus:
        lines.extend(["", f"{t(lang, 'report.ecc_signal_consensus')}:"])
        lines.extend(f"- {item}" for item in ecc_signal_consensus)
    if ecc_validation_matrix:
        lines.extend(["", f"{t(lang, 'report.ecc_validation_matrix')}:"])
        lines.extend(f"- {item}" for item in ecc_validation_matrix)
    if ecc_comparison_focus:
        lines.extend(["", f"{t(lang, 'report.ecc_comparison_focus')}:"])
        lines.extend(f"- {item}" for item in ecc_comparison_focus)
    if ecc_benchmark_delta:
        lines.extend(["", f"{t(lang, 'report.ecc_benchmark_delta')}:"])
        lines.extend(f"- {item}" for item in ecc_benchmark_delta)
    if ecc_regression_summary:
        lines.extend(["", f"{t(lang, 'report.ecc_regression_summary')}:"])
        lines.extend(f"- {item}" for item in ecc_regression_summary)
    if ecc_review_queue:
        lines.extend(["", f"{t(lang, 'report.ecc_review_queue')}:"])
        lines.extend(f"- {item}" for item in ecc_review_queue)
    if ecc_exit_criteria:
        lines.extend(["", f"{t(lang, 'report.ecc_exit_criteria')}:"])
        lines.extend(f"- {item}" for item in ecc_exit_criteria)
    if contract_inventory_summary:
        lines.extend(["", f"{t(lang, 'report.contract_inventory')}:"])
        lines.extend(f"- {item}" for item in contract_inventory_summary)
    if contract_protocol_map:
        lines.extend(["", f"{t(lang, 'report.contract_protocol_map')}:"])
        lines.extend(f"- {item}" for item in contract_protocol_map)
    if contract_protocol_invariants:
        lines.extend(["", f"{t(lang, 'report.contract_protocol_invariants')}:"])
        lines.extend(f"- {item}" for item in contract_protocol_invariants)
    if contract_signal_consensus:
        lines.extend(["", f"{t(lang, 'report.contract_signal_consensus')}:"])
        lines.extend(f"- {item}" for item in contract_signal_consensus)
    if contract_validation_matrix:
        lines.extend(["", f"{t(lang, 'report.contract_validation_matrix')}:"])
        lines.extend(f"- {item}" for item in contract_validation_matrix)
    if contract_benchmark_posture:
        lines.extend(["", f"{t(lang, 'report.contract_benchmark_posture')}:"])
        lines.extend(f"- {item}" for item in contract_benchmark_posture)
    if contract_benchmark_pack_summary:
        lines.extend(["", f"{t(lang, 'report.contract_benchmark_pack_summary')}:"])
        lines.extend(f"- {item}" for item in contract_benchmark_pack_summary)
    if contract_benchmark_case_summaries:
        lines.extend(["", f"{t(lang, 'report.contract_benchmark_case_summaries')}:"])
        lines.extend(f"- {item}" for item in contract_benchmark_case_summaries)
    if contract_repo_priorities:
        lines.extend(["", f"{t(lang, 'report.contract_repo_priorities')}:"])
        lines.extend(f"- {item}" for item in contract_repo_priorities)
    if contract_repo_triage:
        lines.extend(["", f"{t(lang, 'report.contract_repo_triage')}:"])
        lines.extend(f"- {item}" for item in contract_repo_triage)
    if contract_casebook_coverage:
        lines.extend(["", f"{t(lang, 'report.contract_casebook_coverage')}:"])
        lines.extend(f"- {item}" for item in contract_casebook_coverage)
    if contract_casebook_coverage_matrix:
        lines.extend(["", f"{t(lang, 'report.contract_casebook_coverage_matrix')}:"])
        lines.extend(f"- {item}" for item in contract_casebook_coverage_matrix)
    if contract_casebook_case_studies:
        lines.extend(["", f"{t(lang, 'report.contract_casebook_case_studies')}:"])
        lines.extend(f"- {item}" for item in contract_casebook_case_studies)
    if contract_casebook_priority_cases:
        lines.extend(["", f"{t(lang, 'report.contract_casebook_priority_cases')}:"])
        lines.extend(f"- {item}" for item in contract_casebook_priority_cases)
    if contract_casebook_gaps:
        lines.extend(["", f"{t(lang, 'report.contract_casebook_gaps')}:"])
        lines.extend(f"- {item}" for item in contract_casebook_gaps)
    if contract_casebook_benchmark_support:
        lines.extend(["", f"{t(lang, 'report.contract_casebook_benchmark_support')}:"])
        lines.extend(f"- {item}" for item in contract_casebook_benchmark_support)
    if contract_casebook_triage:
        lines.extend(["", f"{t(lang, 'report.contract_casebook_triage')}:"])
        lines.extend(f"- {item}" for item in contract_casebook_triage)
    if contract_toolchain_alignment:
        lines.extend(["", f"{t(lang, 'report.contract_toolchain_alignment')}:"])
        lines.extend(f"- {item}" for item in contract_toolchain_alignment)
    if contract_review_queue:
        lines.extend(["", f"{t(lang, 'report.contract_review_queue')}:"])
        lines.extend(f"- {item}" for item in contract_review_queue)
    if contract_compile_summary:
        lines.extend(["", f"{t(lang, 'report.contract_compile')}:"])
        lines.extend(f"- {item}" for item in contract_compile_summary)
    if contract_surface_summary:
        lines.extend(["", f"{t(lang, 'report.contract_surface')}:"])
        lines.extend(f"- {item}" for item in contract_surface_summary)
    if contract_priority_findings:
        lines.extend(["", f"{t(lang, 'report.contract_priority_findings')}:"])
        lines.extend(f"- {item}" for item in contract_priority_findings)
    if contract_static_findings:
        lines.extend(["", f"{t(lang, 'report.contract_static_findings')}:"])
        lines.extend(f"- {item}" for item in contract_static_findings)
    if contract_testbed_findings:
        lines.extend(["", f"{t(lang, 'report.contract_testbeds')}:"])
        lines.extend(f"- {item}" for item in contract_testbed_findings)
    if contract_remediation_validation:
        lines.extend(["", f"{t(lang, 'report.contract_remediation_validation')}:"])
        lines.extend(f"- {item}" for item in contract_remediation_validation)
    if contract_review_focus:
        lines.extend(["", f"{t(lang, 'report.contract_review_focus')}:"])
        lines.extend(f"- {item}" for item in contract_review_focus)
    if contract_remediation_guidance:
        lines.extend(["", f"{t(lang, 'report.contract_remediation_guidance')}:"])
        lines.extend(f"- {item}" for item in contract_remediation_guidance)
    if contract_remediation_follow_up:
        lines.extend(["", f"{t(lang, 'report.contract_remediation_follow_up')}:"])
        lines.extend(f"- {item}" for item in contract_remediation_follow_up)
    if contract_residual_risk:
        lines.extend(["", f"{t(lang, 'report.contract_residual_risk')}:"])
        lines.extend(f"- {item}" for item in contract_residual_risk)
    if contract_exit_criteria:
        lines.extend(["", f"{t(lang, 'report.contract_exit_criteria')}:"])
        lines.extend(f"- {item}" for item in contract_exit_criteria)
    if contract_manual_review_items:
        lines.extend(["", f"{t(lang, 'report.contract_manual_review')}:"])
        lines.extend(f"- {item}" for item in contract_manual_review_items)
    if before_after_comparison:
        lines.extend(["", f"{t(lang, 'report.before_after_comparison')}:"])
        lines.extend(f"- {item}" for item in before_after_comparison)
    if regression_flags:
        lines.extend(["", f"{t(lang, 'report.regression_flags')}:"])
        lines.extend(f"- {item}" for item in regression_flags)
    if tested_hypotheses:
        lines.extend(["", f"{t(lang, 'report.tested_hypotheses')}:"])
        lines.extend(f"- {item}" for item in tested_hypotheses)
    if tool_usage_summary:
        lines.extend(["", f"{t(lang, 'report.tool_usage')}:"])
        lines.extend(f"- {item}" for item in tool_usage_summary)
    if comparative_findings:
        lines.extend(["", f"{t(lang, 'report.comparative_findings')}:"])
        lines.extend(f"- {item}" for item in comparative_findings)
    if anomalies:
        lines.extend(["", f"{t(lang, 'report.anomalies')}:"])
        lines.extend(f"- {item}" for item in anomalies)
    if recommendations:
        lines.extend(["", f"{t(lang, 'report.recommendations')}:"])
        lines.extend(f"- {item}" for item in recommendations)
    if manual_review_items:
        lines.extend(["", f"{t(lang, 'report.manual_review_items')}:"])
        lines.extend(f"- {item}" for item in manual_review_items)
    return "\n".join(lines)


def _saved_run_evaluation_command(bundle_path: str) -> str:
    escaped_path = bundle_path.replace('"', '\\"')
    return f'python -m app.main --evaluation-summary --replay-bundle "{escaped_path}"'


def render_replay_result(result: ReplayResult, *, language: str) -> str:
    lang = normalize_language(language)
    yes_value = "yes" if lang == "en" else "да"
    no_value = "no" if lang == "en" else "нет"
    def _bool_text(value: bool) -> str:
        return yes_value if value else no_value

    lines = [
        f"{t(lang, 'replay.replay_id')}: {result.replay_id}",
        f"{t(lang, 'replay.replay_source')}: {result.source_type}",
        f"{t(lang, 'replay.replay_path')}: {result.source_path}",
        f"{t(lang, 'replay.replay_session')}: {result.session_id or t(lang, 'value.unavailable')}",
        f"{t(lang, 'label.dry_run')}: {_bool_text(result.dry_run)}",
        f"{t(lang, 'label.reexecuted')}: {_bool_text(result.reexecuted)}",
        f"{t(lang, 'label.success')}: {_bool_text(result.success)}",
        "",
        f"{t(lang, 'report.summary')}:",
        result.summary,
    ]
    if result.generated_session_path:
        lines.append(f"{t(lang, 'replay.generated_session')}: {result.generated_session_path}")
    if result.generated_trace_path:
        lines.append(f"{t(lang, 'replay.generated_trace')}: {result.generated_trace_path}")
    if result.generated_bundle_path:
        lines.append(f"{t(lang, 'replay.generated_bundle')}: {result.generated_bundle_path}")
    if result.notes:
        lines.extend(["", f"{t(lang, 'replay.notes')}:"])
        lines.extend(f"- {item}" for item in result.notes)
    return "\n".join(lines)


def render_doctor_report(report: DoctorReport, *, language: str) -> str:
    lang = normalize_language(language)
    lines = [
        f"{t(lang, 'doctor.report_id')}: {report.report_id}",
        f"{t(lang, 'doctor.overall_status')}: {t(lang, f'doctor.status.{report.overall_status}')}",
        "",
        f"{t(lang, 'doctor.summary_label')}:",
        report.summary,
    ]
    for check in report.checks:
        lines.extend(
            [
                "",
                f"[{t(lang, f'doctor.status.{check.status}').upper()}] {check.title}",
                check.summary,
            ]
        )
        lines.extend(f"- {item}" for item in check.details)
    return "\n".join(lines)


def render_routing_summary(config: AppConfig, *, language: str) -> str:
    lang = normalize_language(language)
    header = "LLM Routing" if lang == "en" else "Маршрутизация LLM"
    shared_provider_label = "Shared Provider" if lang == "en" else "Общий провайдер"
    shared_model_label = "Shared Model" if lang == "en" else "Общая модель"
    routing_mode_label = "Routing Mode" if lang == "en" else "Режим маршрутизации"
    fallback_label = "Fallback Provider" if lang == "en" else "Резервный провайдер"
    agent_label = "Agent" if lang == "en" else "Агент"
    provider_label = "Provider" if lang == "en" else "Провайдер"
    model_label = "Model" if lang == "en" else "Модель"
    mode_label = "Mode" if lang == "en" else "Режим"
    shared_value = "shared" if lang == "en" else "общий"
    override_value = "override" if lang == "en" else "переопределение"

    mode_summary = summarize_route_mode(config)
    if lang == "ru":
        mode_summary = (
            "общий по умолчанию"
            if mode_summary == "shared-default"
            else mode_summary.replace("mixed", "смешанный")
            .replace("overrides", "переопределения")
            .replace("override", "переопределение")
        )

    lines = [
        header,
        f"{shared_provider_label}: {config.llm.default_provider}",
        f"{shared_model_label}: {config.llm.default_model}",
        f"{routing_mode_label}: {mode_summary}",
        f"{fallback_label}: {config.llm.fallback_provider or t(lang, 'value.none')}",
        "",
    ]
    rows = build_route_overview(config)
    widths = (20, 12, 24, 14)
    header_row = (
        f"{agent_label:<{widths[0]}}"
        f" {provider_label:<{widths[1]}}"
        f" {model_label:<{widths[2]}}"
        f" {mode_label:<{widths[3]}}"
    )
    lines.append(header_row)
    lines.append("-" * len(header_row))
    for row in rows:
        mode = shared_value if row.mode == "shared" else override_value
        lines.append(
            f"{row.agent_name:<{widths[0]}}"
            f" {row.provider:<{widths[1]}}"
            f" {row.model:<{widths[2]}}"
            f" {mode:<{widths[3]}}"
        )
    return "\n".join(lines)


def render_synthetic_targets(orchestrator: ResearchOrchestrator, *, language: str) -> str:
    lang = normalize_language(language)
    header = t(lang, "list.synthetic_targets.title")
    lines = [header]
    for item in orchestrator.target_registry.list_synthetic_targets():
        target = item.research_target
        profile = orchestrator.target_registry.resolve_profile(target).profile_name
        lines.extend(
            [
                "",
                f"- {item.target_name}",
                f"  {item.description}",
                f"  kind={target.target_kind}; reference={target.target_reference}; profile={profile}",
            ]
        )
    return "\n".join(lines)


def render_experiment_packs(orchestrator: ResearchOrchestrator, *, language: str) -> str:
    lang = normalize_language(language)
    header = t(lang, "list.experiment_packs.title")
    lines = [header]
    for pack in orchestrator.experiment_pack_registry.list_packs():
        lines.extend(
            [
                "",
                f"- {pack.pack_name}",
                f"  {pack.description}",
                "  target_kinds="
                + ", ".join(pack.target_kinds)
                + "; tools="
                + ", ".join(pack.supported_tools)
                + f"; steps={len(pack.steps)}",
            ]
        )
    return "\n".join(lines)
