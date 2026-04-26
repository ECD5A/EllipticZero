from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from app.config import AppConfig
from app.core.seed_parsing import (
    extract_contract_code,
    extract_contract_root,
    extract_contract_source_label,
    is_smart_contract_seed,
)
from app.llm.providers import HOSTED_PROVIDER_NAMES
from app.llm.router import ROUTED_AGENT_ROLES, ModelRouter


@dataclass(slots=True, frozen=True)
class ProviderContextPreview:
    payload: dict[str, Any]

    @property
    def hosted_route_count(self) -> int:
        return int(self.payload["routes"]["hosted_route_count"])

    @property
    def hosted_context_risk(self) -> str:
        return str(self.payload["risk"]["hosted_context_risk"])


def build_provider_context_preview(
    *,
    config: AppConfig,
    seed_text: str,
    selected_pack_name: str | None = None,
) -> ProviderContextPreview:
    router = ModelRouter(config)
    routes: list[dict[str, Any]] = []
    hosted_route_count = 0
    for agent_name in ROUTED_AGENT_ROLES:
        decision = router.select(agent_name)
        primary_hosted = decision.provider in HOSTED_PROVIDER_NAMES
        fallback_hosted = decision.fallback_provider in HOSTED_PROVIDER_NAMES
        if primary_hosted or fallback_hosted:
            hosted_route_count += 1
        routes.append(
            {
                "agent": agent_name,
                "provider": decision.provider,
                "model": decision.model,
                "primary_hosted": primary_hosted,
                "fallback_provider": decision.fallback_provider,
                "fallback_model": decision.fallback_model,
                "fallback_hosted": fallback_hosted,
                "context_sent_if_called": [
                    "agent system prompt",
                    "user seed / prepared run context",
                    "bounded agent guidance from earlier roles when applicable",
                ],
            }
        )

    contract_code = extract_contract_code(seed_text)
    source_label = extract_contract_source_label(seed_text)
    contract_root = extract_contract_root(seed_text)
    contains_contract_code = bool(contract_code)
    payload = {
        "summary_type": "provider_context_preview",
        "default_provider": config.llm.default_provider,
        "default_model": config.llm.default_model,
        "selected_pack_name": selected_pack_name,
        "context": {
            "seed_character_count": len(seed_text),
            "contains_smart_contract_context": is_smart_contract_seed(seed_text),
            "contains_contract_code": contains_contract_code,
            "contract_code_character_count": len(contract_code or ""),
            "contract_source_label": source_label,
            "contract_root": contract_root,
        },
        "routes": {
            "hosted_route_count": hosted_route_count,
            "rows": routes,
        },
        "risk": _risk_summary(
            hosted_route_count=hosted_route_count,
            contains_contract_code=contains_contract_code,
            source_label=source_label,
            contract_root=contract_root,
        ),
    }
    return ProviderContextPreview(payload=payload)


def render_provider_context_preview(
    *,
    preview: ProviderContextPreview,
    language: str,
    output_format: str = "text",
) -> str:
    if output_format == "json":
        return json.dumps(preview.payload, ensure_ascii=False, indent=2)
    if output_format != "text":
        raise ValueError(f"Unsupported provider context preview format: {output_format}")
    if language == "ru":
        return _render_ru(preview.payload)
    return _render_en(preview.payload)


def _risk_summary(
    *,
    hosted_route_count: int,
    contains_contract_code: bool,
    source_label: str | None,
    contract_root: str | None,
) -> dict[str, Any]:
    if hosted_route_count == 0:
        risk = "none"
        recommendation = "No hosted provider route is active for the agent layer."
    elif contains_contract_code:
        risk = "high"
        recommendation = (
            "Hosted agent routes may receive prepared contract code. Use mock for "
            "private code unless hosted sharing is explicitly acceptable."
        )
    else:
        risk = "medium"
        recommendation = (
            "Hosted agent routes may receive the user seed and bounded role context. "
            "Avoid sensitive private details unless hosted sharing is acceptable."
        )
    return {
        "hosted_context_risk": risk,
        "private_code_may_leave_local_machine": hosted_route_count > 0 and contains_contract_code,
        "source_path_may_be_referenced": hosted_route_count > 0 and bool(source_label),
        "contract_root_may_be_referenced": hosted_route_count > 0 and bool(contract_root),
        "recommendation": recommendation,
    }


def _render_en(payload: dict[str, Any]) -> str:
    context = payload["context"]
    risk = payload["risk"]
    lines = [
        "EllipticZero Provider Context Preview",
        "",
        "Provider Risk:",
        f"- Default provider: {payload['default_provider']}",
        f"- Hosted agent routes: {payload['routes']['hosted_route_count']}",
        f"- Hosted context risk: {risk['hosted_context_risk']}",
        f"- Recommendation: {risk['recommendation']}",
        "",
        "Prepared Context:",
        f"- Seed characters: {context['seed_character_count']}",
        f"- Smart-contract context: {_yes_no(context['contains_smart_contract_context'])}",
        f"- Contract code embedded: {_yes_no(context['contains_contract_code'])}",
        f"- Contract code characters: {context['contract_code_character_count']}",
        f"- Contract source label: {context['contract_source_label'] or 'none'}",
        f"- Contract root: {context['contract_root'] or 'none'}",
        "",
        "Hosted Routes:",
    ]
    lines.extend(_route_lines(payload["routes"]["rows"]))
    lines.extend(
        [
            "",
            "Boundary:",
            "- This is a preview only; no provider call was made.",
            "- Hosted routes may send agent system prompts and prepared run context to the configured provider.",
            "- Model output is interpretation; local tools and saved artifacts carry the evidence trail.",
        ]
    )
    return "\n".join(lines)


def _render_ru(payload: dict[str, Any]) -> str:
    context = payload["context"]
    risk = payload["risk"]
    lines = [
        "Предпросмотр контекста провайдера EllipticZero",
        "",
        "Риск провайдера:",
        f"- Базовый провайдер: {payload['default_provider']}",
        f"- Hosted-маршруты агентов: {payload['routes']['hosted_route_count']}",
        f"- Уровень риска передачи контекста: {_ru_risk_label(risk['hosted_context_risk'])}",
        f"- Рекомендация: {_ru_recommendation(risk['hosted_context_risk'])}",
        "",
        "Подготовленный контекст:",
        f"- Символов в seed: {context['seed_character_count']}",
        f"- Контекст смарт-контракта: {_yes_no_ru(context['contains_smart_contract_context'])}",
        f"- Код контракта встроен: {_yes_no_ru(context['contains_contract_code'])}",
        f"- Символов в коде контракта: {context['contract_code_character_count']}",
        f"- Метка исходного файла: {context['contract_source_label'] or 'none'}",
        f"- Корень контрактов: {context['contract_root'] or 'none'}",
        "",
        "Hosted-маршруты провайдеров:",
    ]
    lines.extend(_route_lines(payload["routes"]["rows"], language="ru"))
    lines.extend(
        [
            "",
            "Граница:",
            "- Это только предварительный просмотр; вызов провайдера не выполнялся.",
            "- Hosted-маршруты могут отправить системные подсказки агентов и подготовленный контекст запуска настроенному провайдеру.",
            "- Вывод модели является интерпретацией; доказательную базу несут локальные инструменты и сохранённые артефакты.",
        ]
    )
    return "\n".join(lines)


def _route_lines(rows: list[dict[str, Any]], *, language: str = "en") -> list[str]:
    lines: list[str] = []
    for row in rows:
        hosted = (
            ("hosted" if row["primary_hosted"] else "local")
            if language == "en"
            else ("hosted" if row["primary_hosted"] else "локальный")
        )
        fallback = (
            f", fallback={row['fallback_provider']}"
            if row["fallback_provider"]
            else ""
        )
        lines.append(
            f"- {row['agent']}: {row['provider']} / {row['model']} ({hosted}{fallback})"
        )
    return lines


def _yes_no(value: bool) -> str:
    return "yes" if value else "no"


def _yes_no_ru(value: bool) -> str:
    return "да" if value else "нет"


def _ru_risk_label(risk: str) -> str:
    if risk == "none":
        return "нет"
    if risk == "high":
        return "высокий"
    if risk == "medium":
        return "средний"
    return risk


def _ru_recommendation(risk: str) -> str:
    if risk == "none":
        return "Для агентного слоя не активен ни один hosted-маршрут."
    if risk == "high":
        return (
            "Hosted-маршруты могут получить подготовленный код контракта. "
            "Для приватного кода используй mock, если передача провайдеру явно не одобрена."
        )
    return (
        "Hosted-маршруты могут получить seed пользователя и ограниченный контекст ролей. "
        "Не добавляй чувствительные детали, если передача провайдеру не одобрена."
    )
