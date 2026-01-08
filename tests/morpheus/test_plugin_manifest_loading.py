import json
from pathlib import Path

import pytest

from rag2f.core.morpheus.plugin import Plugin


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, payload: dict) -> None:
    _write_text(path, json.dumps(payload))


def _make_plugin_dir(tmp_path: Path, name: str) -> Path:
    plugin_dir = tmp_path / name
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "src" / "dummy.py", "x = 1\n")
    return plugin_dir


def _manifest_snapshot(m):
    return {
        "name": m.name,
        "version": m.version,
        "description": m.description,
        "keywords": m.keywords,
        "author_name": m.author_name,
        "license": m.license,
        "min_rag2f_version": m.min_rag2f_version,
        "max_rag2f_version": m.max_rag2f_version,
    }


# =====================================
# A) DISCOVERY ROOT-FIRST
# =====================================


def test_root_first_plugin_json_base(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug")

    _write_json(plugin_dir / "plugin.json", {"name": "Root", "version": "0.1.0"})
    _write_json(plugin_dir / "sub" / "plugin.json", {"name": "Nested", "version": "9.9.9"})

    plugin = Plugin(str(plugin_dir))
    assert plugin.manifest.name == "Root"


def test_fallback_nested_plugin_json_when_root_missing(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug")

    _write_json(plugin_dir / "sub" / "plugin.json", {"name": "Nested"})

    plugin = Plugin(str(plugin_dir))
    assert plugin.manifest.name == "Nested"


def test_root_first_pyproject_override(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug")

    _write_json(plugin_dir / "plugin.json", {"name": "Base", "description": "from-json"})

    _write_text(
        plugin_dir / "pyproject.toml",
        """
[project]
name = "Override"
description = "from-root"
""".lstrip(),
    )
    _write_text(
        plugin_dir / "nested" / "pyproject.toml",
        """
[project]
name = "OverrideNested"
description = "from-nested"
""".lstrip(),
    )

    plugin = Plugin(str(plugin_dir))
    assert plugin.manifest.name == "Override"
    assert plugin.manifest.description == "from-root"


# =====================================
# B) MERGE POLICY
# =====================================


@pytest.mark.parametrize(
    "py_desc_toml,expected",
    [
        ("description = \"from-pyproject\"\n", "from-pyproject"),
        ("description = \"\"\n", "from-json"),
        ("description = \"   \"\n", "from-json"),
        ("", "from-json"),
    ],
)
def test_override_only_if_non_empty(tmp_path: Path, py_desc_toml: str, expected: str):
    plugin_dir = _make_plugin_dir(tmp_path, "plug")

    _write_json(plugin_dir / "plugin.json", {"name": "Base", "description": "from-json"})

    _write_text(
        plugin_dir / "pyproject.toml",
        (
            "[project]\n"
            "name = \"Override\"\n"
            + py_desc_toml
        ),
    )

    plugin = Plugin(str(plugin_dir))
    assert plugin.manifest.name == "Override"
    assert plugin.manifest.description == expected


def test_keywords_normalization_is_robust(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug")

    _write_json(
        plugin_dir / "plugin.json",
        {"name": "X", "keywords": ["a", 1, " ", None, "b"]},
    )

    plugin = Plugin(str(plugin_dir))
    assert plugin.manifest.keywords == "a, 1, b"


def test_bounds_json_has_priority_over_dependency(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "plug")

    _write_json(
        plugin_dir / "plugin.json",
        {"name": "X", "min_rag2f_version": "1.0", "max_rag2f_version": "2.0"},
    )
    _write_text(
        plugin_dir / "pyproject.toml",
        """
[project]
name = "X"
dependencies = ["rag2f>=9.0,<10.0"]
min_rag2f_version = "9"
max_rag2f_version = "10"
""".lstrip(),
    )

    plugin = Plugin(str(plugin_dir))
    assert plugin.manifest.min_rag2f_version == "1.0"
    assert plugin.manifest.max_rag2f_version == "2.0"


# =====================================
# C) RAG2F BOUNDS PARSING
# =====================================


@pytest.mark.parametrize(
    "deps,expected_min,expected_max",
    [
        (["rag2f>=1.2,<2.0; python_version>'3.11'"], "1.2", "2.0"),
        (["rag2f[foo]>=1.0,<2.0"], "1.0", "2.0"),
        (["rag2f"], "Unknown", "Unknown"),
        (["rag2f~=1.2"], "Unknown", "Unknown"),
        (["RAG2F>=1,<2"], "1", "2"),
        (["rag2f>=1.0", "rag2f>=1.5,<2.0"], "1.5", "2.0"),
        (["rag2f==1.5.0"], "Unknown", "1.5.0"),
    ],
)
def test_bounds_from_dependencies_matrix(tmp_path: Path, deps, expected_min, expected_max):
    plugin_dir = _make_plugin_dir(tmp_path, "plug")

    deps_list = ", ".join([f"\"{d}\"" for d in deps])
    _write_text(
        plugin_dir / "pyproject.toml",
        (
            "[project]\n"
            "name = \"X\"\n"
            f"dependencies = [{deps_list}]\n"
        ),
    )

    plugin = Plugin(str(plugin_dir))
    assert plugin.manifest.min_rag2f_version == expected_min
    assert plugin.manifest.max_rag2f_version == expected_max


# =====================================
# D) FALLBACK METADATA (pip-like)
# =====================================


class _FakeMetadata(dict):
    def get_all(self, key):
        v = self.get(key)
        if v is None:
            return None
        if isinstance(v, list):
            return v
        return [v]


class _FakeDist:
    def __init__(self, *, version="3.3.3", requires=None, metadata=None, files=None, locate_map=None):
        self._version = version
        self.requires = requires or []
        self.metadata = _FakeMetadata(metadata or {"Name": "FakePkg", "Version": version, "Summary": "sum"})
        self.files = files or []
        self._locate_map = locate_map or {}

    @property
    def version(self):
        return self._version

    def locate_file(self, f):
        return self._locate_map[str(f)]


def test_metadata_fallback_fills_only_defaultish(tmp_path: Path, monkeypatch):
    plugin_dir = tmp_path / "site-packages" / "fake_pkg"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "src" / "dummy.py", "x = 1\n")

    _write_json(plugin_dir / "plugin.json", {"name": "BaseName", "license": "MIT"})

    fake_dist = _FakeDist(
        version="9.9.9",
        requires=["rag2f>=1.2,<2.0"],
        metadata={
            "Name": "MetaName",
            "Version": "9.9.9",
            "Summary": "From metadata",
            "Author": "Bob",
            "License": "Apache",
            "Home-page": "https://example.com",
        },
        files=[],
    )

    monkeypatch.setattr("importlib.metadata.distribution", lambda _name: fake_dist)

    plugin = Plugin(str(plugin_dir))

    snap = _manifest_snapshot(plugin.manifest)
    assert snap["license"] == "MIT"
    assert snap["author_name"] == "Bob"
    assert snap["min_rag2f_version"] == "1.2"
    assert snap["max_rag2f_version"] == "2.0"


def test_missing_name_everywhere_falls_back_to_humanized_id(tmp_path: Path):
    plugin_dir = _make_plugin_dir(tmp_path, "my_plugin")

    plugin = Plugin(str(plugin_dir))
    assert plugin.manifest.name == "My plugin"


def test_pip_like_uses_dist_plugin_json_when_fs_missing(tmp_path: Path, monkeypatch):
    plugin_dir = tmp_path / "site-packages" / "fake_pkg"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    _write_text(plugin_dir / "src" / "dummy.py", "x = 1\n")

    dist_plugin_json_path = tmp_path / "dist_plugin.json"
    _write_json(dist_plugin_json_path, {"name": "FromDist", "version": "1.2.3"})

    fake_dist = _FakeDist(
        version="0.0.0",
        metadata={"Name": "fake_pkg", "Version": "0.0.0"},
        files=["pkg/plugin.json"],
        locate_map={"pkg/plugin.json": dist_plugin_json_path},
    )

    monkeypatch.setattr("importlib.metadata.distribution", lambda _name: fake_dist)

    plugin = Plugin(str(plugin_dir))
    assert plugin.manifest.name == "FromDist"
    assert plugin.manifest.version == "1.2.3"
