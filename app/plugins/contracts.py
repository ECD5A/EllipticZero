from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable


@runtime_checkable
class PluginRegistryProtocol(Protocol):
    def register(self, tool: object) -> None:
        """Register one tool through the bounded plugin registry adapter."""


PluginRegisterHook = Callable[[PluginRegistryProtocol], None]


@runtime_checkable
class PluginModuleContract(Protocol):
    plugin_name: str
    plugin_version: str
    plugin_description: str
    register: PluginRegisterHook
