# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True, frozen=True)
class BudgetPolicy:
    """Lightweight budget envelope for future routing and guardrails."""

    max_request_tokens: int
    max_total_requests_per_session: int
    timeout_seconds: int
