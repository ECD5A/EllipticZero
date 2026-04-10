from __future__ import annotations

from pathlib import Path

from app.config import AppConfig
from app.main import build_orchestrator
from app.plugins.loader import PluginLoader
from app.tools.builtin import CurveMetadataTool
from app.tools.registry import ToolRegistry
from app.types import make_id


def _write_demo_plugin(plugin_dir: Path, *, plugin_name: str = "demo_plugin") -> None:
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.py").write_text(
        "\n".join(
            [
                "from __future__ import annotations",
                "",
                "from collections.abc import Mapping",
                "from typing import Any",
                "",
                "from pydantic import BaseModel, ConfigDict, field_validator",
                "",
                "from app.tools.base import BaseTool",
                "",
                f"plugin_name = '{plugin_name}'",
                "plugin_version = '0.1.0'",
                "plugin_description = 'Bounded local test plugin.'",
                "",
                "class NotePayload(BaseModel):",
                "    model_config = ConfigDict(extra='forbid')",
                "    text: str",
                "",
                "    @field_validator('text')",
                "    @classmethod",
                "    def validate_text(cls, value: str) -> str:",
                "        stripped = value.strip()",
                "        if not stripped:",
                "            raise ValueError('text cannot be empty.')",
                "        return stripped",
                "",
                "class ResearchNoteNormalizerTool(BaseTool):",
                "    name = 'plugin_note_normalizer_tool'",
                "    description = 'Normalize a short research note in a deterministic plugin-provided helper.'",
                "    version = '0.1.0'",
                "    category = 'plugin_research_helper'",
                "    input_schema_hint = 'text string'",
                "    output_schema_hint = 'normalized note summary'",
                "    payload_model = NotePayload",
                "",
                "    def run(self, payload: Mapping[str, Any]) -> dict[str, Any]:",
                "        text = str(payload['text']).strip()",
                "        normalized = ' '.join(text.lower().split())",
                "        return self.make_result(",
                "            status='ok',",
                "            conclusion='Plugin note normalization completed deterministically.',",
                "            notes=['Bounded test plugin executed through the registry.'],",
                "            result_data={'normalized_text': normalized, 'word_count': len(normalized.split())},",
                "        )",
                "",
                "def register(registry: Any) -> None:",
                "    registry.register(ResearchNoteNormalizerTool())",
            ]
        ),
        encoding="utf-8",
    )


def test_plugin_loader_discovers_and_registers_temp_plugin() -> None:
    run_root = Path(".test_runs") / make_id("plugintemp")
    plugin_root = run_root / "plugins"
    _write_demo_plugin(plugin_root / "demo_plugin", plugin_name="demo_plugin")

    registry = ToolRegistry()
    registry.register(CurveMetadataTool())
    loader = PluginLoader(directory=str(plugin_root), enabled=True, allow_local_plugins=True)

    discovered = loader.discover_plugin_paths()
    metadata = loader.load_into_registry(registry)

    assert any(path.name == "demo_plugin" for path in discovered)
    assert any(item.plugin_name == "demo_plugin" and item.load_status == "loaded" for item in metadata)
    assert "plugin_note_normalizer_tool" in registry.names()
    tool_metadata = registry.get("plugin_note_normalizer_tool").metadata
    assert tool_metadata.source_type == "plugin"
    assert tool_metadata.plugin_name == "demo_plugin"


def test_plugin_loader_handles_broken_plugin_gracefully() -> None:
    run_root = Path(".test_runs") / make_id("pluginfail")
    plugin_dir = run_root / "plugins" / "broken_plugin"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.py").write_text(
        "plugin_name = 'broken_plugin'\n"
        "plugin_version = '0.0.1'\n"
        "plugin_description = 'Broken plugin for tests'\n"
        "raise RuntimeError('boom')\n",
        encoding="utf-8",
    )

    registry = ToolRegistry()
    registry.register(CurveMetadataTool())
    loader = PluginLoader(directory=str(run_root / "plugins"), enabled=True, allow_local_plugins=True)

    metadata = loader.load_into_registry(registry)

    assert any(item.plugin_name == "broken_plugin" and item.load_status == "failed" for item in metadata)
    assert "curve_metadata_tool" in registry.names()
    assert "plugin_note_normalizer_tool" not in registry.names()


def test_plugin_loader_rejects_unsafe_plugin_directory_names() -> None:
    run_root = Path(".test_runs") / make_id("pluginunsafe")
    plugin_root = run_root / "plugins"
    _write_demo_plugin(plugin_root / "bad plugin", plugin_name="bad_plugin")

    registry = ToolRegistry()
    registry.register(CurveMetadataTool())
    loader = PluginLoader(directory=str(plugin_root), enabled=True, allow_local_plugins=True)

    discovered = loader.discover_plugin_paths()
    metadata = loader.load_into_registry(registry)

    assert all(path.name != "bad plugin" for path in discovered)
    assert any(item.plugin_name == "bad plugin" and item.load_status == "failed" for item in metadata)
    assert "plugin_note_normalizer_tool" not in registry.names()


def test_build_orchestrator_keeps_builtins_and_plugins() -> None:
    run_root = Path(".test_runs") / make_id("plugins")
    plugin_root = run_root / "plugins"
    _write_demo_plugin(plugin_root / "demo_plugin", plugin_name="demo_plugin")
    config = AppConfig.model_validate(
        {
            "llm": {
                "default_provider": "mock",
                "default_model": "mock-default",
                "timeout_seconds": 30,
                "max_request_tokens": 2048,
                "max_total_requests_per_session": 16,
            },
            "plugins": {
                "enabled": True,
                "directory": str(plugin_root),
                "allow_local_plugins": True,
            },
            "storage": {
                "artifacts_dir": str(run_root),
                "sessions_dir": str(run_root / "sessions"),
                "traces_dir": str(run_root / "traces"),
                "bundles_dir": str(run_root / "bundles"),
            },
            "log_level": "INFO",
            "max_hypotheses": 2,
            "tool_timeout_seconds": 15,
        }
    )

    orchestrator = build_orchestrator(config)

    assert "curve_metadata_tool" in orchestrator.executor.registry.names()
    assert "plugin_note_normalizer_tool" in orchestrator.executor.registry.names()
    assert any(item.plugin_name == "demo_plugin" for item in orchestrator.plugin_metadata)
