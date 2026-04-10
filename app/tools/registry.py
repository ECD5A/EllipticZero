from __future__ import annotations

from app.models.tool_metadata import ToolMetadata
from app.tools.base import BaseTool


class ToolRegistry:
    """Registry that controls access to approved local tools."""

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}
        self._metadata: dict[str, ToolMetadata] = {}

    def register(
        self,
        tool: BaseTool,
        *,
        source_type: str | None = None,
        plugin_name: str | None = None,
    ) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool already registered: {tool.name}")
        if source_type is not None:
            tool.source_type = source_type
        if plugin_name is not None:
            tool.plugin_name = plugin_name
        self._tools[tool.name] = tool
        self._metadata[tool.name] = tool.metadata

    def remove(self, tool_name: str) -> None:
        self._tools.pop(tool_name, None)
        self._metadata.pop(tool_name, None)

    def remove_where_plugin(self, plugin_name: str) -> None:
        for tool_name in [
            name
            for name, metadata in self._metadata.items()
            if metadata.plugin_name == plugin_name
        ]:
            self.remove(tool_name)

    def get(self, tool_name: str) -> BaseTool:
        try:
            return self._tools[tool_name]
        except KeyError as exc:
            raise KeyError(f"Tool not registered: {tool_name}") from exc

    def names(self) -> list[str]:
        return sorted(self._tools)

    def list_tools(self) -> list[BaseTool]:
        return [self._tools[name] for name in self.names()]

    def list_metadata(self) -> list[ToolMetadata]:
        return [self._metadata[name] for name in self.names()]
