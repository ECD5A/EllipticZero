from __future__ import annotations

import json
import re
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.core.replay_loader import LoadedReplaySource
from app.core.seed_parsing import extract_contract_source_label
from app.models.report import ResearchReport

SARIF_VERSION = "2.1.0"
SARIF_SCHEMA = "https://json.schemastore.org/sarif-2.1.0.json"


RULE_DEFINITIONS: dict[str, dict[str, str]] = {
    "EZ-CONTRACT-FINDING": {
        "name": "Bounded smart-contract finding",
        "description": "A smart-contract finding or candidate issue from a bounded EllipticZero run.",
    },
    "EZ-CONTRACT-STATIC-SIGNAL": {
        "name": "Smart-contract static signal",
        "description": "A parser, compile, static, surface, or testbed signal that should be reviewed.",
    },
    "EZ-CONTRACT-KNOWN-CASE": {
        "name": "Smart-contract known-case profile match",
        "description": "A cached threat-intel profile matched local contract context or bounded signals.",
    },
    "EZ-CONTRACT-MANUAL-REVIEW": {
        "name": "Smart-contract manual review item",
        "description": "A manual-review lane or residual risk that the run did not fully prove.",
    },
    "EZ-REGRESSION-FLAG": {
        "name": "Regression or before-after flag",
        "description": "A cautious before/after or regression-oriented signal from a comparison run.",
    },
    "EZ-ECC-REVIEW": {
        "name": "ECC review item",
        "description": "A bounded ECC review queue, residual-risk, or validation item.",
    },
    "EZ-QUALITY-GATE": {
        "name": "Evidence quality gate",
        "description": "A quality, hardening, or evidence-boundary note from the run.",
    },
    "EZ-REPORT-SNAPSHOT": {
        "name": "Report snapshot",
        "description": "A compact saved-run snapshot exported when detailed report sections are unavailable.",
    },
}


def build_sarif_payload(*, loaded_source: LoadedReplaySource) -> dict[str, Any]:
    """Build a SARIF 2.1.0 payload from a saved EllipticZero run."""

    session = loaded_source.session
    report = session.report if session is not None else None
    seed_text = session.seed.raw_text if session is not None else ""
    source_uri = _source_uri(seed_text=seed_text, loaded_source=loaded_source)
    results = (
        _results_from_report(
            report=report,
            source_uri=source_uri,
            loaded_source=loaded_source,
        )
        if report is not None
        else _results_from_manifest(loaded_source=loaded_source, source_uri=source_uri)
    )
    if not results:
        results.append(
            _result(
                rule_id="EZ-REPORT-SNAPSHOT",
                level="note",
                message="No SARIF-exportable findings were recorded in this saved run.",
                source_uri=source_uri,
                section="empty_export",
                loaded_source=loaded_source,
            )
        )

    return {
        "$schema": SARIF_SCHEMA,
        "version": SARIF_VERSION,
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "EllipticZero",
                        "informationUri": "https://github.com/ECD5A/EllipticZero",
                        "rules": [_rule(rule_id) for rule_id in sorted(_used_rule_ids(results))],
                    }
                },
                "invocations": [
                    {
                        "executionSuccessful": True,
                        "properties": {
                            "sourceType": loaded_source.source_type,
                            "sourcePath": loaded_source.source_path,
                            "originalSessionId": loaded_source.original_session_id,
                            "researchMode": loaded_source.research_mode,
                            "selectedPackName": loaded_source.selected_pack_name,
                            "toolNames": list(loaded_source.tool_names),
                            "experimentTypes": list(loaded_source.experiment_types),
                        },
                    }
                ],
                "artifacts": _artifacts(source_uri=source_uri, loaded_source=loaded_source),
                "results": results,
                "properties": {
                    "summaryType": "ellipticzero_saved_run_sarif",
                    "evidenceBoundary": (
                        "Model output is interpretation; local tool outputs and saved artifacts "
                        "carry the evidence trail."
                    ),
                    "manualReviewBoundary": (
                        "SARIF results are review items unless independently validated by the local "
                        "tool evidence and a human reviewer."
                    ),
                },
            }
        ],
    }


def write_sarif_file(
    *,
    loaded_source: LoadedReplaySource,
    output_path: str | Path,
) -> tuple[Path, int]:
    payload = build_sarif_payload(loaded_source=loaded_source)
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return destination, len(payload["runs"][0]["results"])


def render_sarif_export_result(*, output_path: Path, result_count: int, language: str) -> str:
    if language == "ru":
        return "\n".join(
            [
                "SARIF export complete",
                f"- Файл: {output_path}",
                f"- Results: {result_count}",
                "- Назначение: saved-run review items for GitHub Code Scanning or CI review.",
                "- Граница: SARIF не превращает bounded signals в подтвержденные уязвимости без ручной проверки.",
            ]
        )
    return "\n".join(
        [
            "SARIF export complete",
            f"- File: {output_path}",
            f"- Results: {result_count}",
            "- Purpose: saved-run review items for GitHub Code Scanning or CI review.",
            "- Boundary: SARIF does not turn bounded signals into confirmed vulnerabilities without review.",
        ]
    )


def _results_from_report(
    *,
    report: ResearchReport,
    source_uri: str,
    loaded_source: LoadedReplaySource,
) -> list[dict[str, Any]]:
    sections: tuple[tuple[str, str, str], ...] = (
        ("contract_finding_cards", "EZ-CONTRACT-FINDING", "warning"),
        ("contract_known_case_matches", "EZ-CONTRACT-KNOWN-CASE", "note"),
        ("contract_priority_findings", "EZ-CONTRACT-FINDING", "warning"),
        ("contract_static_findings", "EZ-CONTRACT-STATIC-SIGNAL", "warning"),
        ("contract_testbed_findings", "EZ-CONTRACT-STATIC-SIGNAL", "warning"),
        ("contract_compile_summary", "EZ-CONTRACT-STATIC-SIGNAL", "note"),
        ("contract_surface_summary", "EZ-CONTRACT-STATIC-SIGNAL", "note"),
        ("contract_manual_review_items", "EZ-CONTRACT-MANUAL-REVIEW", "note"),
        ("contract_review_queue", "EZ-CONTRACT-MANUAL-REVIEW", "note"),
        ("contract_residual_risk", "EZ-CONTRACT-MANUAL-REVIEW", "note"),
        ("regression_flags", "EZ-REGRESSION-FLAG", "warning"),
        ("before_after_comparison", "EZ-REGRESSION-FLAG", "note"),
        ("ecc_review_queue", "EZ-ECC-REVIEW", "note"),
        ("ecc_residual_risk", "EZ-ECC-REVIEW", "note"),
        ("ecc_validation_matrix", "EZ-ECC-REVIEW", "note"),
        ("quality_gates", "EZ-QUALITY-GATE", "note"),
        ("hardening_summary", "EZ-QUALITY-GATE", "note"),
    )
    results: list[dict[str, Any]] = []
    for section_name, rule_id, level in sections:
        for item in _string_items(getattr(report, section_name)):
            results.append(
                _result(
                    rule_id=rule_id,
                    level=level,
                    message=item,
                    source_uri=source_uri,
                    section=section_name,
                    loaded_source=loaded_source,
                    confidence=report.confidence.value,
                )
            )
    return results


def _results_from_manifest(
    *,
    loaded_source: LoadedReplaySource,
    source_uri: str,
) -> list[dict[str, Any]]:
    manifest = loaded_source.manifest
    if manifest is None:
        return []
    sections: tuple[tuple[str, list[str], str], ...] = (
        ("report_snapshot_summary", list(manifest.report_snapshot_summary), "EZ-REPORT-SNAPSHOT"),
        ("report_focus_summary", list(manifest.report_focus_summary), "EZ-REPORT-SNAPSHOT"),
        ("quality_gate_summary", list(manifest.quality_gate_summary), "EZ-QUALITY-GATE"),
        ("hardening_summary", list(manifest.hardening_summary), "EZ-QUALITY-GATE"),
    )
    results: list[dict[str, Any]] = []
    for section_name, items, rule_id in sections:
        for item in _string_items(items):
            results.append(
                _result(
                    rule_id=rule_id,
                    level="note",
                    message=item,
                    source_uri=source_uri,
                    section=section_name,
                    loaded_source=loaded_source,
                    confidence=manifest.confidence,
                )
            )
    return results


def _result(
    *,
    rule_id: str,
    level: str,
    message: str,
    source_uri: str,
    section: str,
    loaded_source: LoadedReplaySource,
    confidence: str | None = None,
) -> dict[str, Any]:
    severity = _severity(rule_id=rule_id, level=level, message=message)
    line_hint = _line_hint(message)
    physical_location: dict[str, Any] = {
        "artifactLocation": {
            "uri": source_uri,
        }
    }
    if line_hint is not None:
        physical_location["region"] = {"startLine": line_hint}
    return {
        "ruleId": rule_id,
        "level": level,
        "message": {"text": message},
        "locations": [
            {
                "physicalLocation": physical_location
            }
        ],
        "partialFingerprints": {
            "ellipticzero/v1": _fingerprint(rule_id=rule_id, source_uri=source_uri, message=message)
        },
        "properties": {
            "ellipticzeroSection": section,
            "ellipticzeroSeverity": severity,
            "tags": _tags(rule_id),
            "sourceType": loaded_source.source_type,
            "sourcePath": loaded_source.source_path,
            "originalSessionId": loaded_source.original_session_id,
            "confidence": confidence,
            "reviewRequired": True,
        },
    }


def _rule(rule_id: str) -> dict[str, Any]:
    definition = RULE_DEFINITIONS[rule_id]
    tags = _tags(rule_id)
    return {
        "id": rule_id,
        "name": definition["name"],
        "shortDescription": {"text": definition["name"]},
        "fullDescription": {"text": definition["description"]},
        "defaultConfiguration": {"level": "warning" if "FINDING" in rule_id else "note"},
        "help": {
            "text": (
                "Review the original EllipticZero session, trace, manifest, bundle, and local "
                "tool outputs before treating this result as a confirmed issue."
            )
        },
        "properties": {
            "tags": tags,
            "precision": "medium" if rule_id == "EZ-CONTRACT-FINDING" else "low",
        },
    }


def _source_uri(*, seed_text: str, loaded_source: LoadedReplaySource) -> str:
    source_label = extract_contract_source_label(seed_text)
    if source_label:
        return _uri(source_label)
    for artifact in loaded_source.artifact_paths:
        if artifact.endswith((".sol", ".vy")):
            return _uri(artifact)
    if loaded_source.source_type == "bundle":
        return _uri(str(Path(loaded_source.source_path) / "session.json"))
    return _uri(loaded_source.source_path)


def _artifacts(*, source_uri: str, loaded_source: LoadedReplaySource) -> list[dict[str, Any]]:
    uris = [source_uri]
    for artifact in loaded_source.artifact_paths[:32]:
        uri = _uri(artifact)
        if uri not in uris:
            uris.append(uri)
    return [{"location": {"uri": uri}} for uri in uris]


def _used_rule_ids(results: list[dict[str, Any]]) -> set[str]:
    return {str(result["ruleId"]) for result in results}


def _string_items(items: list[str]) -> list[str]:
    return [item.strip() for item in items if item.strip()]


def _uri(value: str) -> str:
    return value.replace("\\", "/")


def _severity(*, rule_id: str, level: str, message: str) -> str:
    lowered = message.lower()
    if rule_id == "EZ-CONTRACT-FINDING":
        if any(token in lowered for token in ("critical", "loss", "drain", "takeover")):
            return "high"
        if any(token in lowered for token in ("value-flow", "permission", "admin", "external")):
            return "medium"
        return "review"
    if rule_id == "EZ-REGRESSION-FLAG":
        return "medium"
    if level == "warning":
        return "review"
    return "informational"


def _line_hint(message: str) -> int | None:
    match = re.search(r"\bLine hint:\s*(\d+)\b", message)
    if match is None:
        return None
    line = int(match.group(1))
    return line if line > 0 else None


def _tags(rule_id: str) -> list[str]:
    base = ["ellipticzero", "manual-review"]
    if rule_id.startswith("EZ-CONTRACT"):
        return [*base, "smart-contracts", "security"]
    if rule_id.startswith("EZ-ECC"):
        return [*base, "ecc", "cryptography"]
    if rule_id == "EZ-REGRESSION-FLAG":
        return [*base, "regression", "comparison"]
    if rule_id == "EZ-QUALITY-GATE":
        return [*base, "quality-gate", "evidence"]
    return [*base, "evidence"]


def _fingerprint(*, rule_id: str, source_uri: str, message: str) -> str:
    value = "\n".join([rule_id, source_uri, " ".join(message.split())])
    return sha256(value.encode("utf-8")).hexdigest()[:32]
