"""Tests covering plugin loader state and module import behavior."""

import json
import sys
from pathlib import Path

import pytest

from rag2f.core.morpheus.plugin import Plugin


def _write_text(path: Path, content: str) -> None:
    """Write text to a file, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    """Write JSON payload to a file."""
    _write_text(path, json.dumps(payload))


def _make_plugin_dir(tmp_path: Path, name: str) -> Path:
    """Create a minimal plugin directory with a manifest."""
    plugin_dir = tmp_path / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "plugin.json", json.dumps({"name": "X"}))
    return plugin_dir


# =====================================
# E) LOADER STATE / IMPORT BEHAVIOR
# =====================================


def test_dedup_module_loading_no_double_side_effects(tmp_path: Path, rag2f):
    """Loading hooks twice should not re-execute module side effects."""
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

    plugin = Plugin(rag2f, str(plugin_dir))

    plugin._load_decorated_functions()
    module_name = f"plugins.{plugin.id}.src.hook_mod"
    assert module_name in sys.modules
    assert sys.modules[module_name].IMPORT_COUNT == 1
    assert len(plugin.hooks) == 1

    # Second load must reuse sys.modules without executing module code again
    plugin._load_decorated_functions()
    assert sys.modules[module_name].IMPORT_COUNT == 1
    assert len(plugin.hooks) == 1


def test_hook_plugin_id_not_overwritten_if_already_set(tmp_path: Path, rag2f):
    """Existing hook.plugin_id should not be overwritten by the loader."""
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

    plugin = Plugin(rag2f, str(plugin_dir))
    plugin._load_decorated_functions()

    assert len(plugin.hooks) == 1
    assert plugin.hooks[0].plugin_id == "already-set"


def test_relative_imports_work_under_dummy_packages(tmp_path: Path, rag2f):
    """Relative imports inside plugin files should resolve under dummy packages."""
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

    plugin = Plugin(rag2f, str(plugin_dir))
    plugin._load_decorated_functions()

    assert any(h.name == "morpheus_test_hook_message" for h in plugin.hooks)


def test_py_files_filter_excludes_tests_folder(tmp_path: Path, rag2f):
    """The loader should ignore files under a plugin's tests/ folder."""
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

    plugin = Plugin(rag2f, str(plugin_dir))
    plugin._load_decorated_functions()

    assert len(plugin.hooks) == 1
    assert plugin.hooks[0].function.__name__ == "ok"


def test_py_files_filter_excludes_plugins_subfolder_when_not_in_plugins_path(
    tmp_path: Path, rag2f
):
    """The loader should ignore nested plugins/ when plugin is not under plugins/."""
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

    plugin = Plugin(rag2f, str(plugin_dir))
    plugin._load_decorated_functions()

    assert len(plugin.hooks) == 1
    assert plugin.hooks[0].function.__name__ == "ok"


def test_unload_removes_plugin_modules_from_sys_modules(tmp_path: Path, rag2f):
    """Deactivate should unload plugin modules and clear hook/override lists."""
    plugin_dir = _make_plugin_dir(tmp_path, "plug_unload")

    _write_text(
        plugin_dir / "src" / "hook_mod.py",
        """
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def my_hook(phone, rag2f=None):
    return phone
""".lstrip(),
    )

    plugin = Plugin(rag2f, str(plugin_dir))
    plugin._load_decorated_functions()

    module_name = f"plugins.{plugin.id}.src.hook_mod"
    assert module_name in sys.modules
    assert len(plugin.hooks) == 1

    plugin.deactivate()

    assert module_name not in sys.modules
    assert plugin.hooks == []
    assert plugin.overrides == {}


def test_unload_does_not_remove_other_plugins_modules(tmp_path: Path, rag2f):
    """Unloading one plugin should not remove another plugin's modules."""
    plugin_a_dir = _make_plugin_dir(tmp_path, "plug_a")
    plugin_b_dir = _make_plugin_dir(tmp_path, "plug_b")

    _write_text(
        plugin_a_dir / "src" / "a.py",
        """
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def hook_a(phone, rag2f=None):
    return phone
""".lstrip(),
    )
    _write_text(
        plugin_b_dir / "src" / "b.py",
        """
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def hook_b(phone, rag2f=None):
    return phone
""".lstrip(),
    )

    plugin_a = Plugin(rag2f, str(plugin_a_dir))
    plugin_b = Plugin(rag2f, str(plugin_b_dir))

    plugin_a._load_decorated_functions()
    plugin_b._load_decorated_functions()

    mod_a = f"plugins.{plugin_a.id}.src.a"
    mod_b = f"plugins.{plugin_b.id}.src.b"
    assert mod_a in sys.modules
    assert mod_b in sys.modules

    plugin_a.deactivate()

    assert mod_a not in sys.modules
    assert mod_b in sys.modules


def test_unload_removes_relative_import_submodules(tmp_path: Path, rag2f):
    """Deactivate should remove submodules created via relative imports."""
    plugin_dir = _make_plugin_dir(tmp_path, "plug_rel_unload")

    _write_text(
        plugin_dir / "src" / "b.py",
        """
VALUE = 123
""".lstrip(),
    )
    _write_text(
        plugin_dir / "src" / "a.py",
        """
from .b import VALUE
from rag2f.core.morpheus.decorators.hook import hook


@hook('morpheus_test_hook_message')
def my_hook(phone, rag2f=None):
    return phone
""".lstrip(),
    )

    plugin = Plugin(rag2f, str(plugin_dir))
    plugin._load_decorated_functions()

    mod_a = f"plugins.{plugin.id}.src.a"
    mod_b = f"plugins.{plugin.id}.src.b"
    assert mod_a in sys.modules
    assert mod_b in sys.modules

    plugin.deactivate()

    assert mod_a not in sys.modules
    assert mod_b not in sys.modules


# =====================================
# F) ERROR HANDLING
# =====================================


def test_invalid_plugin_json_raises_with_path(tmp_path: Path, rag2f):
    """Invalid plugin.json should raise an error containing the file path."""
    plugin_dir = tmp_path / "plug"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "src" / "dummy.py", "x = 1\n")
    _write_text(plugin_dir / "plugin.json", "{ not: valid json")

    with pytest.raises(Exception) as e:
        Plugin(rag2f, str(plugin_dir))

    msg = str(e.value)
    assert "Invalid JSON" in msg
    assert str(plugin_dir / "plugin.json") in msg


def test_invalid_pyproject_toml_raises_with_path(tmp_path: Path, rag2f):
    """Invalid pyproject.toml should raise an error containing the file path."""
    plugin_dir = tmp_path / "plug"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "src" / "dummy.py", "x = 1\n")
    _write_text(plugin_dir / "plugin.json", json.dumps({"name": "X"}))
    _write_text(plugin_dir / "pyproject.toml", "[project\nname='x'\n")

    with pytest.raises(Exception) as e:
        Plugin(rag2f, str(plugin_dir))

    msg = str(e.value)
    assert "Invalid TOML" in msg
    assert str(plugin_dir / "pyproject.toml") in msg


def test_plugin_with_no_python_files_errors(tmp_path: Path, rag2f):
    """Plugins with no Python files should be rejected."""
    plugin_dir = tmp_path / "plug"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "plugin.json", json.dumps({"name": "X"}))

    with pytest.raises(Exception) as e:
        Plugin(rag2f, str(plugin_dir))

    assert "does not contain any python files" in str(e.value)
