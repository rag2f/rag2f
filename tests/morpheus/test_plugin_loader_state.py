import json
import sys
from pathlib import Path

import pytest

from rag2f.core.morpheus.plugin import Plugin
from rag2f.core.morpheus.decorators.hook import hook


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write_text(path, json.dumps(payload))


def _make_plugin_dir(tmp_path: Path, name: str) -> Path:
    plugin_dir = tmp_path / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "plugin.json", json.dumps({"name": "X"}))
    return plugin_dir


# =====================================
# E) LOADER STATE / IMPORT BEHAVIOR
# =====================================

def test_dedup_module_loading_no_double_side_effects(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug_dedup")

    # module that increments a global count on import
    _write_text(
        plugin_dir / "src" / "hook_mod.py",
        """
IMPORT_COUNT = 0
IMPORT_COUNT += 1

from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def my_hook(phone, rag2f=None):
    return phone
""".lstrip(),
    )

    plugin = Plugin(str(plugin_dir))

    plugin._load_decorated_functions()
    module_name = f"plugins.{plugin.id}.src.hook_mod"
    assert module_name in sys.modules
    assert getattr(sys.modules[module_name], "IMPORT_COUNT") == 1
    assert len(plugin.hooks) == 1

    # Second load must reuse sys.modules without executing module code again
    plugin._load_decorated_functions()
    assert getattr(sys.modules[module_name], "IMPORT_COUNT") == 1
    assert len(plugin.hooks) == 1


def test_hook_plugin_id_not_overwritten_if_already_set(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug_id")

    _write_text(
        plugin_dir / "src" / "hook_mod.py",
        """
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def my_hook(phone, rag2f=None):
    return phone


# Force plugin_id at module import time
my_hook.plugin_id = 'already-set'
""".lstrip(),
    )

    plugin = Plugin(str(plugin_dir))
    plugin._load_decorated_functions()

    assert len(plugin.hooks) == 1
    assert plugin.hooks[0].plugin_id == "already-set"


def test_relative_imports_work_under_dummy_packages(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug_rel")

    _write_text(
        plugin_dir / "src" / "b.py",
        """
X = 1
""".lstrip(),
    )
    _write_text(
        plugin_dir / "src" / "a.py",
        """
from .b import X
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def my_hook(phone, rag2f=None):
    return phone
""".lstrip(),
    )

    plugin = Plugin(str(plugin_dir))
    plugin._load_decorated_functions()

    assert any(h.name == "morpheus_test_hook_message" for h in plugin.hooks)


def test_py_files_filter_excludes_tests_folder(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug_filter_tests")

    _write_text(
        plugin_dir / "src" / "main.py",
        """
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def ok(phone, rag2f=None):
    return phone
""".lstrip(),
    )
    _write_text(
        plugin_dir / "tests" / "side.py",
        """
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def should_not_load(phone, rag2f=None):
    return phone
""".lstrip(),
    )

    plugin = Plugin(str(plugin_dir))
    plugin._load_decorated_functions()

    assert len(plugin.hooks) == 1
    assert plugin.hooks[0].function.__name__ == "ok"


def test_py_files_filter_excludes_plugins_subfolder_when_not_in_plugins_path(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug_filter_plugins")

    _write_text(
        plugin_dir / "src" / "main.py",
        """
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def ok(phone, rag2f=None):
    return phone
""".lstrip(),
    )
    _write_text(
        plugin_dir / "plugins" / "subplugin" / "x.py",
        """
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def should_not_load(phone, rag2f=None):
    return phone
""".lstrip(),
    )

    plugin = Plugin(str(plugin_dir))
    plugin._load_decorated_functions()

    assert len(plugin.hooks) == 1
    assert plugin.hooks[0].function.__name__ == "ok"


# =====================================
# F) ERROR HANDLING
# =====================================

def test_invalid_plugin_json_raises_with_path(tmp_path: Path):
    plugin_dir = tmp_path / "plug"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "src" / "dummy.py", "x = 1\n")
    _write_text(plugin_dir / "plugin.json", "{ not: valid json")

    with pytest.raises(Exception) as e:
        Plugin(str(plugin_dir))

    msg = str(e.value)
    assert "Invalid JSON" in msg
    assert str(plugin_dir / "plugin.json") in msg


def test_invalid_pyproject_toml_raises_with_path(tmp_path: Path):
    plugin_dir = tmp_path / "plug"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "src" / "dummy.py", "x = 1\n")
    _write_text(plugin_dir / "plugin.json", json.dumps({"name": "X"}))
    _write_text(plugin_dir / "pyproject.toml", "[project\nname='x'\n")

    with pytest.raises(Exception) as e:
        Plugin(str(plugin_dir))

    msg = str(e.value)
    assert "Invalid TOML" in msg
    assert str(plugin_dir / "pyproject.toml") in msg


def test_plugin_with_no_python_files_errors(tmp_path: Path):
    plugin_dir = tmp_path / "plug"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "plugin.json", json.dumps({"name": "X"}))

    with pytest.raises(Exception) as e:
        Plugin(str(plugin_dir))

    assert "does not contain any python files" in str(e.value)
