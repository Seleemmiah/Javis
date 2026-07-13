"""Plugin / skill loader — discover drop-in .py skill files."""

from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from typing import Any, Callable, Optional

from jarvis_core.config import ROOT

PLUGIN_DIR = ROOT / "skills" / "plugins"


class Plugin:
    """A discovered plugin with metadata and execute function."""

    def __init__(
        self,
        name: str,
        description: str,
        triggers: list[str],
        execute_fn: Callable[..., str],
        source_file: str = "",
    ) -> None:
        self.name = name
        self.description = description
        self.triggers = triggers
        self._compiled = [re.compile(t, re.IGNORECASE) for t in triggers]
        self.execute_fn = execute_fn
        self.source_file = source_file

    def matches(self, text: str) -> Optional[re.Match]:
        """Check if user text matches any trigger pattern."""
        for pattern in self._compiled:
            m = pattern.search(text)
            if m:
                return m
        return None

    def execute(self, **kwargs: Any) -> str:
        try:
            return self.execute_fn(**kwargs)
        except Exception as exc:
            return f"Plugin '{self.name}' error: {exc}"


_plugins: list[Plugin] = []
_loaded = False


def discover_plugins(plugin_dir: Optional[Path] = None) -> list[Plugin]:
    """Scan plugin directory for .py files with the plugin interface."""
    global _plugins, _loaded
    if _loaded:
        return _plugins

    pdir = plugin_dir or PLUGIN_DIR
    if not pdir.is_dir():
        pdir.mkdir(parents=True, exist_ok=True)
        _loaded = True
        return _plugins

    for py_file in sorted(pdir.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        try:
            spec = importlib.util.spec_from_file_location(
                f"jarvis_plugin_{py_file.stem}", py_file
            )
            if spec is None or spec.loader is None:
                continue
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)

            name = getattr(mod, "PLUGIN_NAME", py_file.stem)
            desc = getattr(mod, "PLUGIN_DESCRIPTION", "")
            triggers = getattr(mod, "PLUGIN_TRIGGERS", [])
            execute_fn = getattr(mod, "plugin_execute", None)

            if execute_fn is None:
                print(f"[plugins] Skipping {py_file.name}: no plugin_execute function")
                continue

            plugin = Plugin(
                name=name,
                description=desc,
                triggers=triggers,
                execute_fn=execute_fn,
                source_file=str(py_file),
            )
            _plugins.append(plugin)
            print(f"[plugins] Loaded: {name} ({py_file.name})")
        except Exception as exc:
            print(f"[plugins] Failed to load {py_file.name}: {exc}")

    _loaded = True
    return _plugins


def get_plugins() -> list[Plugin]:
    """Return all discovered plugins (discovers on first call)."""
    if not _loaded:
        discover_plugins()
    return _plugins


def find_matching_plugin(text: str) -> Optional[tuple[Plugin, re.Match]]:
    """Find the first plugin whose trigger matches the text."""
    for plugin in get_plugins():
        m = plugin.matches(text)
        if m:
            return plugin, m
    return None


def reload_plugins() -> list[Plugin]:
    """Force re-scan of plugin directory."""
    global _plugins, _loaded
    _plugins = []
    _loaded = False
    return discover_plugins()


def plugin_action_schemas() -> list[dict]:
    """Generate action type schemas for discovered plugins (for brain prompt)."""
    schemas = []
    for p in get_plugins():
        schemas.append({
            "type": f"plugin_{p.name}",
            "description": p.description,
            "triggers": p.triggers,
        })
    return schemas
