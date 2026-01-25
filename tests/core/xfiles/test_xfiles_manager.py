"""Tests for the XFiles repository registry manager."""

import logging

import pytest

from rag2f.core.dto.result_dto import StatusCode
from rag2f.core.xfiles import BaseRepository, XFiles, minimal_crud_capabilities


class DummyRepository(BaseRepository):
    """Minimal BaseRepository implementation for registry tests."""

    def __init__(self, name: str = "dummy") -> None:
        """Create a dummy repository with the given name."""
        self._name = name

    @property
    def name(self) -> str:
        """Return the repository name."""
        return self._name

    def capabilities(self):
        """Return minimal CRUD capabilities for this dummy repo."""
        return minimal_crud_capabilities()

    def get(self, id, select=None):  # pragma: no cover
        """Not implemented for this dummy repository."""
        raise NotImplementedError

    def insert(self, id, item):  # pragma: no cover
        """Not implemented for this dummy repository."""
        raise NotImplementedError

    def update(self, id, patch):  # pragma: no cover
        """Not implemented for this dummy repository."""
        raise NotImplementedError

    def delete(self, id):  # pragma: no cover
        """Not implemented for this dummy repository."""
        raise NotImplementedError

    def _get_native_handle(self, kind: str):  # pragma: no cover
        """Not implemented for this dummy repository."""
        raise NotImplementedError


class TestXFilesManager:
    """Tests for the XFiles registry manager behavior."""

    @pytest.mark.parametrize("bad_id", [None, 123, "", "   "])
    def test_register_rejects_invalid_id(self, bad_id):
        """Register should return error result for invalid repository ids."""
        xfiles = XFiles()
        repo = DummyRepository()
        result = xfiles.execute_register(bad_id, repo)  # type: ignore[arg-type]
        assert result.is_error()
        assert result.detail.code == StatusCode.INVALID
        assert "Invalid repository ID" in result.detail.message

    def test_register_rejects_non_repository(self):
        """Register should return error result for non-BaseRepository objects."""
        xfiles = XFiles()
        result = xfiles.execute_register("not_a_repo", object())  # type: ignore[arg-type]
        assert result.is_error()
        assert result.detail.code == StatusCode.INVALID
        assert "does not implement the BaseRepository protocol" in result.detail.message

    def test_register_success_and_meta_copy(self):
        """Register should store repositories and meta should be copied on read."""
        xfiles = XFiles()
        repo = DummyRepository()

        result = xfiles.execute_register("repo1", repo)

        assert result.is_ok()
        assert result.created is True
        get_result = xfiles.execute_get("repo1")
        assert get_result.is_ok()
        assert get_result.repository is repo
        assert xfiles.has("repo1") is True

        meta1 = xfiles.get_meta("repo1")
        assert meta1 == {}

        # get_meta() must return a copy (mutating it must not affect registry)
        meta1["purpose"] = "mutated"
        assert xfiles.get_meta("repo1") == {}

    def test_register_duplicate_same_instance_warns_and_does_not_override_meta(self, caplog):
        """Re-registering the same instance should return success with duplicate detail."""
        xfiles = XFiles()
        repo = DummyRepository()

        result1 = xfiles.execute_register("repo1", repo, meta={"domain": "users"})
        assert result1.is_ok()
        assert result1.created is True

        caplog.set_level(logging.WARNING, logger="rag2f.core.xfiles.xfiles")
        result2 = xfiles.execute_register("repo1", repo, meta={"domain": "orders"})

        # Should return success but created=False with DUPLICATE detail
        assert result2.is_ok()
        assert result2.created is False
        assert result2.detail is not None
        assert result2.detail.code == StatusCode.DUPLICATE

        # Should keep original registration (no override)
        assert len(xfiles) == 1
        get_result = xfiles.execute_get("repo1")
        assert get_result.is_ok()
        assert get_result.repository is repo
        assert xfiles.get_meta("repo1") == {"domain": "users"}

        assert any(
            "already registered with the same instance" in rec.getMessage()
            for rec in caplog.records
        )

    def test_register_duplicate_different_instance_returns_error(self):
        """Register should return error when overriding an id with a different instance."""
        xfiles = XFiles()
        repo1 = DummyRepository(name="r1")
        repo2 = DummyRepository(name="r2")

        result1 = xfiles.execute_register("repo1", repo1)
        assert result1.is_ok()
        assert result1.created is True

        result2 = xfiles.execute_register("repo1", repo2)
        assert result2.is_error()
        assert result2.detail.code == StatusCode.ALREADY_EXISTS
        assert "Override not allowed" in result2.detail.message

        get_result = xfiles.execute_get("repo1")
        assert get_result.is_ok()
        assert get_result.repository is repo1

    def test_unregister_removes_and_returns_expected_flags(self):
        """Unregister should return a boolean indicating removal."""
        xfiles = XFiles()

        assert xfiles.unregister("missing") is False

        repo = DummyRepository()
        result = xfiles.execute_register("repo1", repo)
        assert result.is_ok()

        assert xfiles.unregister("repo1") is True
        assert xfiles.has("repo1") is False
        get_result = xfiles.execute_get("repo1")
        # Not found is an expected state, returns success with NOT_FOUND detail
        assert get_result.is_ok()
        assert get_result.repository is None
        assert get_result.detail is not None
        assert get_result.detail.code == StatusCode.NOT_FOUND

        # Second removal should be false
        assert xfiles.unregister("repo1") is False

    def test_register_same_instance_is_idempotent(self):
        """Registering the same instance twice should be handled gracefully."""
        xfiles = XFiles()
        repo = DummyRepository()

        result1 = xfiles.execute_register("repo", repo)
        assert result1.is_ok()
        assert result1.created is True

        result2 = xfiles.execute_register("repo", repo)
        assert result2.is_ok()
        assert result2.created is False

        assert len(xfiles.list_ids()) == 1
        get_result = xfiles.execute_get("repo")
        assert get_result.is_ok()
        assert get_result.repository is repo
