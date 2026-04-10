from __future__ import annotations

import importlib.util
import logging
import re
from pathlib import Path
from types import ModuleType

from app.models.plugin_metadata import PluginMetadata
from app.plugins.base import PluginDefinition, PluginRegistryAdapter
from app.tools.registry import ToolRegistry


class PluginLoader:
    """Discover and load local plugins through an explicit bounded contract."""

    _SAFE_PLUGIN_DIR_RE = re.compile(r"^[A-Za-z0-9_-]+$")

    def __init__(
        self,
        *,
        directory: str,
        enabled: bool = True,
        allow_local_plugins: bool = True,
    ) -> None:
        self.directory = Path(directory)
        self.enabled = enabled
        self.allow_local_plugins = allow_local_plugins
        self.logger = logging.getLogger(self.__class__.__name__)

    def discover_plugin_paths(self) -> list[Path]:
        if not self.enabled or not self.allow_local_plugins or not self.directory.exists():
            return []
        return sorted(
            path
            for path in self._candidate_plugin_dirs()
            if self._is_safe_plugin_dir(path)
        )

    def load_into_registry(self, registry: ToolRegistry) -> list[PluginMetadata]:
        if not self.enabled or not self.allow_local_plugins:
            return []

        metadata: list[PluginMetadata] = []
        for plugin_dir in self._candidate_plugin_dirs():
            if not self._is_safe_plugin_dir(plugin_dir):
                metadata.append(
                    PluginMetadata(
                        plugin_name=plugin_dir.name,
                        plugin_version="unknown",
                        plugin_description="Plugin failed safety checks.",
                        registered_tools=[],
                        source_path=str(plugin_dir),
                        load_status="failed",
                        notes=["Plugin path or file layout failed bounded local safety checks."],
                    )
                )
                continue
            metadata.append(self._load_one(plugin_dir=plugin_dir, registry=registry))
        return metadata

    def _candidate_plugin_dirs(self) -> list[Path]:
        if not self.enabled or not self.allow_local_plugins or not self.directory.exists():
            return []
        return sorted(
            path
            for path in self.directory.iterdir()
            if path.is_dir() and (path / "plugin.py").exists()
        )

    def _is_safe_plugin_dir(self, plugin_dir: Path) -> bool:
        plugin_file = plugin_dir / "plugin.py"
        if plugin_dir.is_symlink() or plugin_file.is_symlink():
            return False
        if not self._SAFE_PLUGIN_DIR_RE.fullmatch(plugin_dir.name):
            return False
        base_dir = self._safe_resolve(self.directory)
        plugin_dir_resolved = self._safe_resolve(plugin_dir)
        plugin_file_resolved = self._safe_resolve(plugin_file)
        if base_dir is None or plugin_dir_resolved is None or plugin_file_resolved is None:
            return False
        return self._is_relative_to(plugin_dir_resolved, base_dir) and self._is_relative_to(plugin_file_resolved, base_dir)

    def _load_one(self, *, plugin_dir: Path, registry: ToolRegistry) -> PluginMetadata:
        plugin_file = plugin_dir / "plugin.py"
        try:
            module = self._import_module(plugin_dir.name, plugin_file)
            definition = self._extract_definition(module=module, plugin_file=plugin_file)
            before_names = set(registry.names())
            try:
                definition.register_hook(
                    PluginRegistryAdapter(registry=registry, plugin_name=definition.plugin_name)
                )
            except Exception as exc:
                registry.remove_where_plugin(definition.plugin_name)
                raise RuntimeError(f"Plugin register hook failed: {exc}") from exc

            registered_tools = sorted(set(registry.names()) - before_names)
            return PluginMetadata(
                plugin_name=definition.plugin_name,
                plugin_version=definition.plugin_version,
                plugin_description=definition.plugin_description,
                registered_tools=registered_tools,
                source_path=definition.source_path,
                load_status="loaded",
                notes=["Plugin loaded through the bounded local registry adapter."],
            )
        except Exception as exc:
            self.logger.warning("Failed to load plugin from %s: %s", plugin_file, exc)
            return PluginMetadata(
                plugin_name=plugin_dir.name,
                plugin_version="unknown",
                plugin_description="Plugin failed to load.",
                registered_tools=[],
                source_path=str(plugin_dir),
                load_status="failed",
                notes=[str(exc)],
            )

    def _import_module(self, plugin_name: str, plugin_file: Path) -> ModuleType:
        module_name = f"ellipticzero_local_plugins.{plugin_name}"
        spec = importlib.util.spec_from_file_location(module_name, plugin_file)
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not create an import spec for the plugin.")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _extract_definition(self, *, module: ModuleType, plugin_file: Path) -> PluginDefinition:
        plugin_name = getattr(module, "plugin_name", None)
        plugin_version = getattr(module, "plugin_version", None)
        plugin_description = getattr(module, "plugin_description", None)
        register_hook = getattr(module, "register", None)

        if not isinstance(plugin_name, str) or not plugin_name.strip():
            raise RuntimeError("Plugin contract requires a non-empty plugin_name string.")
        if not isinstance(plugin_version, str) or not plugin_version.strip():
            raise RuntimeError("Plugin contract requires a non-empty plugin_version string.")
        if not isinstance(plugin_description, str) or not plugin_description.strip():
            raise RuntimeError("Plugin contract requires a non-empty plugin_description string.")
        if not callable(register_hook):
            raise RuntimeError("Plugin contract requires a callable register hook.")

        return PluginDefinition(
            plugin_name=plugin_name.strip(),
            plugin_version=plugin_version.strip(),
            plugin_description=plugin_description.strip(),
            source_path=str(plugin_file.parent),
            register_hook=register_hook,
        )

    def _safe_resolve(self, path: Path) -> Path | None:
        try:
            return path.resolve(strict=False)
        except OSError:
            return None

    def _is_relative_to(self, path: Path, root: Path) -> bool:
        try:
            path.relative_to(root)
            return True
        except ValueError:
            return False
