# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

from __future__ import annotations

RECOMMENDED_LIVE_SMOKE_MODELS: dict[str, str] = {
    "openrouter": "openrouter/auto",
}


def resolve_live_smoke_model(
    *,
    provider_name: str,
    configured_default_model: str,
    explicit_model: str | None = None,
) -> str:
    """Pick a bounded smoke-test model without surprising the main runtime route."""

    if explicit_model:
        return explicit_model
    provider = provider_name.strip().lower()
    return RECOMMENDED_LIVE_SMOKE_MODELS.get(provider, configured_default_model)
