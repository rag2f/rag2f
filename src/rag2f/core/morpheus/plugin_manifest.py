from __future__ import annotations

from typing import Any, ClassVar, Dict, Iterable, Mapping

from pydantic import BaseModel

#TODO: pyproject or plugin compile have same info, remove?
# The properties accepted in the [project] section of pyproject.toml are defined by the PEP 621 standard. The main ones are:
# name
# version (o dynamic)
# description
# readme
# requires-python
# license
# authors
# maintainers
# keywords
# classifiers
# urls (can be a dictionary of urls, e.g.: {"Homepage" = "...", "Repository" = "..."})
# dependencies
# optional-dependencies
# You can find the official and detailed description of all properties here:
# https://peps.python.org/pep-0621/



class PluginManifest(BaseModel):
    #id: str id plugin set and defined from Morpheus Plugin class
    name: str
    version: str = "0.0.0"
    keywords: str = "Unknown"
    description: str = (
        "Description not found for this plugin."
        "Please create a plugin.json manifest"
        " in the plugin folder."
    )
    author_name: str = "Unknown"
    author_email: str = "Unknown"
    urls: str = "Unknown"
    license: str = "Unknown"
    min_rag2f_version: str = "Unknown"
    max_rag2f_version: str = "Unknown"

    _DEFAULTS: ClassVar[Dict[str, str]] = {
        "version": "0.0.0",
        "keywords": "Unknown",
        "description": (
            "Description not found for this plugin."
            "Please create a plugin.json manifest"
            " in the plugin folder."
        ),
        "author_name": "Unknown",
        "author_email": "Unknown",
        "urls": "Unknown",
        "license": "Unknown",
        "min_rag2f_version": "Unknown",
        "max_rag2f_version": "Unknown",
    }

    @classmethod
    def apply_fallback_defaults(cls, merged: dict, fallback: dict) -> dict:
        """Fill missing/default-ish fields from fallback metadata.

        A field is considered eligible if it's missing, empty, or still equal to
        the model default (e.g., "Unknown", default description, default version).
        """
        out = dict(merged)
        for field_name, default_value in cls._DEFAULTS.items():
            current = out.get(field_name)
            current_s = cls.normalize_str(current)
            needs_fallback = current is None or current_s is None or current_s == default_value
            if not needs_fallback:
                continue
            fallback_s = cls.normalize_str(fallback.get(field_name))
            if fallback_s is not None:
                out[field_name] = fallback_s
        return out

    @staticmethod
    def normalize_str(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            s = value.strip()
            return s if s else None
        s = str(value).strip()
        return s if s else None

    @staticmethod
    def join_keywords(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, list) or isinstance(value, tuple):
            parts: list[str] = []
            for item in value:
                s = PluginManifest.normalize_str(item)
                if s:
                    parts.append(s)
            return ", ".join(parts) if parts else None
        return PluginManifest.normalize_str(value)

    @staticmethod
    def serialize_urls(value: Any) -> str | None:
        if value is None:
            return None
        if isinstance(value, str):
            return PluginManifest.normalize_str(value)
        if isinstance(value, list) or isinstance(value, tuple):
            parts: list[str] = []
            for item in value:
                s = PluginManifest.normalize_str(item)
                if s:
                    parts.append(s)
            return ", ".join(parts) if parts else None
        if isinstance(value, Mapping):
            # Deterministic serialization with priority keys.
            priority = ["Homepage", "Repository", "Documentation"]
            items: list[tuple[str, str]] = []

            def add_key(k: str):
                if k in value:
                    v = PluginManifest.normalize_str(value.get(k))
                    if v:
                        items.append((k, v))

            for k in priority:
                add_key(k)

            other_keys = sorted([k for k in value.keys() if k not in set(priority)])
            for k in other_keys:
                add_key(str(k))

            return ", ".join([f"{k}={v}" for k, v in items]) if items else None

        # Unknown type: best-effort string
        return PluginManifest.normalize_str(value)

    @staticmethod
    def override_if_non_empty(base: dict, override: dict, *, exclude: Iterable[str] = ()) -> dict:
        """Return merged dict where override wins only if non-empty string.

        exclude: keys not eligible for this policy.
        """
        excluded = set(exclude)
        merged = dict(base)
        for key, value in override.items():
            if key in excluded:
                continue
            s = PluginManifest.normalize_str(value)
            if s is not None:
                merged[key] = s
        return merged
