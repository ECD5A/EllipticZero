from __future__ import annotations

from dataclasses import dataclass

from app.plugins.contracts import PluginRegisterHook
from app.tools.base import BaseTool
from app.tools.registry import ToolRegistry


@dataclass(frozen=True)
class PluginDefinition:
    plugin_name: str
    plugin_version: str
    plugin_description: str
    source_path: str
    register_hook: PluginRegisterHook


class PluginRegistryAdapter:
    """Bounded adapter that lets plugins register tools but not bypass the registry."""

    def __init__(self, *, registry: ToolRegistry, plugin_name: str) -> None:
        self._registry = registry
        self._plugin_name = plugin_name

    def register(self, tool: BaseTool) -> None:
        self._registry.register(tool, source_type="plugin", plugin_name=self._plugin_name)
