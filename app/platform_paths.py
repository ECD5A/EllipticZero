# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

from __future__ import annotations

import sys

MANAGED_SOLC_DIR_TEMPLATE = ".ellipticzero/tooling/solcx/{platform}"


def platform_cache_tag() -> str:
    if sys.platform == "win32":
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "linux"


def expand_platform_path(value: str) -> str:
    return value.replace("{platform}", platform_cache_tag())


def default_managed_solc_dir() -> str:
    return expand_platform_path(MANAGED_SOLC_DIR_TEMPLATE)
