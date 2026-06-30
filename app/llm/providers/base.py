# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any


class BaseLLMProvider(ABC):
    """Abstract LLM provider interface."""

    provider_name: str = "base"

    @abstractmethod
    def generate(
        self,
        *,
        model: str,
        timeout_seconds: int,
        max_request_tokens: int,
        system_prompt: str,
        user_prompt: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        """Generate a bounded text response for an agent."""
