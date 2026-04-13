from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.seed_parsing import build_smart_contract_seed


class GoldenCaseError(ValueError):
    """Raised when a built-in golden case cannot be resolved or prepared."""


@dataclass(frozen=True)
class GoldenCaseRun:
    case_id: str
    domain: str
    seed_text: str
    experiment_pack_name: str
    synthetic_target_name: str | None
    input_path: Path
    contract_root: Path | None = None


def golden_cases_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "golden_cases"


def load_golden_manifest(root: Path | None = None) -> dict[str, Any]:
    manifest_path = (root or golden_cases_root()) / "golden_manifest.json"
    try:
        return json.loads(manifest_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GoldenCaseError(f"Golden case manifest not found: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise GoldenCaseError(f"Golden case manifest is invalid JSON: {manifest_path}") from exc


def list_golden_cases(root: Path | None = None) -> list[dict[str, Any]]:
    manifest = load_golden_manifest(root)
    cases = manifest.get("cases")
    if not isinstance(cases, list):
        raise GoldenCaseError("Golden case manifest must contain a 'cases' list.")
    return [case for case in cases if isinstance(case, dict)]


def resolve_golden_case(case_id: str, root: Path | None = None) -> dict[str, Any]:
    normalized = case_id.strip()
    if not normalized:
        raise GoldenCaseError("Golden case id cannot be empty.")
    for case in list_golden_cases(root):
        if str(case.get("case_id", "")).strip() == normalized:
            return case
    known = ", ".join(str(case.get("case_id", "")).strip() for case in list_golden_cases(root))
    raise GoldenCaseError(f"Unknown golden case '{case_id}'. Known cases: {known}")


def prepare_golden_case_run(case_id: str, root: Path | None = None) -> GoldenCaseRun:
    base_root = root or golden_cases_root()
    case = resolve_golden_case(case_id, base_root)
    domain = str(case.get("domain", "")).strip()
    input_file = str(case.get("input_file", "")).strip()
    experiment_pack_name = str(case.get("recommended_pack", "")).strip()
    if not domain or not input_file or not experiment_pack_name:
        raise GoldenCaseError(f"Golden case '{case_id}' is missing required metadata.")

    input_path = base_root / input_file
    if not input_path.is_file():
        raise GoldenCaseError(f"Golden case input file not found: {input_path}")

    if domain == "ecc_research":
        return GoldenCaseRun(
            case_id=str(case["case_id"]),
            domain=domain,
            seed_text=input_path.read_text(encoding="utf-8"),
            experiment_pack_name=experiment_pack_name,
            synthetic_target_name=_optional_text(case.get("synthetic_target")),
            input_path=input_path,
        )

    if domain == "smart_contract_audit":
        contract_root = _contract_root_for_case(base_root=base_root, case=case, input_path=input_path)
        contract_code = input_path.read_text(encoding="utf-8")
        seed_text = build_smart_contract_seed(
            idea_text=_case_idea_text(case),
            contract_code=contract_code,
            language=str(case.get("contract_language", "solidity") or "solidity"),
            source_label=str(input_path),
            contract_root=str(contract_root),
        )
        return GoldenCaseRun(
            case_id=str(case["case_id"]),
            domain=domain,
            seed_text=seed_text,
            experiment_pack_name=experiment_pack_name,
            synthetic_target_name=None,
            input_path=input_path,
            contract_root=contract_root,
        )

    raise GoldenCaseError(f"Golden case '{case_id}' has unsupported domain: {domain}")


def render_golden_cases(*, language: str = "en", root: Path | None = None) -> str:
    cases = list_golden_cases(root)
    if language == "ru":
        lines = [
            "Golden cases EllipticZero",
            "",
            "Безопасные синтетические кейсы для быстрой оценки маршрутизации, benchmark-пакетов и формы отчета.",
            "",
        ]
        for case in cases:
            lines.extend(
                [
                    f"- {case.get('case_id')}",
                    f"  Домен: {case.get('domain')}",
                    f"  Пакет: {case.get('recommended_pack')}",
                    f"  Вход: {case.get('input_file')}",
                ]
            )
        lines.extend(
            [
                "",
                "Запуск:",
                "python -m app.main --golden-case <case_id>",
            ]
        )
        return "\n".join(lines)

    lines = [
        "EllipticZero Golden Cases",
        "",
        "Safe synthetic evaluator cases for routing, benchmark packs, and report-shape checks.",
        "",
    ]
    for case in cases:
        lines.extend(
            [
                f"- {case.get('case_id')}",
                f"  Domain: {case.get('domain')}",
                f"  Pack: {case.get('recommended_pack')}",
                f"  Input: {case.get('input_file')}",
            ]
        )
    lines.extend(
        [
            "",
            "Run:",
            "python -m app.main --golden-case <case_id>",
        ]
    )
    return "\n".join(lines)


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _contract_root_for_case(*, base_root: Path, case: dict[str, Any], input_path: Path) -> Path:
    raw_root = _optional_text(case.get("contract_root"))
    contract_root = base_root / raw_root if raw_root else input_path.parent
    if not contract_root.is_dir():
        raise GoldenCaseError(f"Golden case contract root not found: {contract_root}")
    return contract_root


def _case_idea_text(case: dict[str, Any]) -> str:
    case_id = str(case.get("case_id", "unknown")).strip()
    shape = case.get("expected_report_shape")
    focus_items: list[str] = []
    if isinstance(shape, dict):
        must_include = shape.get("must_include")
        if isinstance(must_include, list):
            focus_items = [str(item).strip() for item in must_include[:4] if str(item).strip()]
    focus = ", ".join(focus_items) if focus_items else "bounded local evidence and report-shape expectations"
    return f"Run golden case {case_id}; focus on {focus}."
