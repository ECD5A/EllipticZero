# EllipticZero: https://github.com/ECD5A/EllipticZero
# Copyright (c) 2026 ECD5A
# SPDX-License-Identifier: LicenseRef-FSL-1.1-ALv2
# License terms: see LICENSE in the project root.

"""Plugin contract and loader helpers for local EllipticZero extensions."""

from app.plugins.base import PluginDefinition, PluginRegistryAdapter
from app.plugins.loader import PluginLoader

__all__ = ["PluginDefinition", "PluginLoader", "PluginRegistryAdapter"]
