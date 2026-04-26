from __future__ import annotations

import json

from app.config import AppConfig
from app.core.provider_privacy import (
    build_provider_context_preview,
    render_provider_context_preview,
)
from app.core.seed_parsing import build_smart_contract_seed
from app.main import build_parser


def _config(provider: str) -> AppConfig:
    return AppConfig.model_validate(
        {
            "llm": {
                "default_provider": provider,
                "default_model": "provider-default",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            }
        }
    )


def test_provider_context_preview_flags_hosted_contract_code_risk() -> None:
    seed_text = build_smart_contract_seed(
        idea_text="Review private vault permissions.",
        contract_code="pragma solidity ^0.8.20; contract Vault {}",
        source_label="contracts/Vault.sol",
        contract_root="contracts",
    )
    preview = build_provider_context_preview(
        config=_config("openrouter"),
        seed_text=seed_text,
        selected_pack_name="vault_permission_benchmark_pack",
    )
    rendered = render_provider_context_preview(preview=preview, language="en")
    rendered_json = render_provider_context_preview(
        preview=preview,
        language="en",
        output_format="json",
    )
    payload = json.loads(rendered_json)

    assert preview.hosted_route_count == 6
    assert preview.hosted_context_risk == "high"
    assert payload["risk"]["private_code_may_leave_local_machine"] is True
    assert payload["context"]["contract_code_character_count"] > 0
    assert "This is a preview only; no provider call was made." in rendered


def test_provider_context_preview_stays_low_for_mock_routes() -> None:
    preview = build_provider_context_preview(
        config=_config("mock"),
        seed_text="Inspect secp256k1 metadata labels.",
    )

    assert preview.hosted_route_count == 0
    assert preview.hosted_context_risk == "none"
    assert preview.payload["risk"]["private_code_may_leave_local_machine"] is False


def test_parser_supports_provider_context_preview_flags() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--provider",
            "openrouter",
            "--provider-context-preview",
            "--provider-context-preview-format",
            "json",
            "Review routing privacy.",
        ]
    )

    assert args.provider == "openrouter"
    assert args.provider_context_preview is True
    assert args.provider_context_preview_format == "json"
