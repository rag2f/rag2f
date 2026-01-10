import logging

import pytest

from rag2f.core.xfiles import BaseRepository, XFiles, minimal_crud_capabilities


class DummyRepository(BaseRepository):
    def __init__(self, name: str = "dummy") -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    def capabilities(self):
        return minimal_crud_capabilities()

    def get(self, id, select=None):  # pragma: no cover
        raise NotImplementedError

    def insert(self, id, item):  # pragma: no cover
        raise NotImplementedError

    def update(self, id, patch):  # pragma: no cover
        raise NotImplementedError

    def delete(self, id):  # pragma: no cover
        raise NotImplementedError

    def _get_native_handle(self, kind: str):  # pragma: no cover
        raise NotImplementedError


class TestXFilesManager:
    @pytest.mark.parametrize("bad_id", [None, 123, "", "   "])
    def test_register_rejects_invalid_id(self, bad_id):
        xfiles = XFiles()
        repo = DummyRepository()
        with pytest.raises(ValueError, match="Invalid repository ID"):
            xfiles.register(bad_id, repo)  # type: ignore[arg-type]

    def test_register_rejects_non_repository(self):
        xfiles = XFiles()
        with pytest.raises(TypeError, match="does not implement the BaseRepository protocol"):
            xfiles.register("not_a_repo", object())  # type: ignore[arg-type]

    def test_register_success_and_meta_copy(self):
        xfiles = XFiles()
        repo = DummyRepository()

        xfiles.register("repo1", repo)

        assert xfiles.get("repo1") is repo
        assert xfiles.has("repo1") is True

        meta1 = xfiles.get_meta("repo1")
        assert meta1 == {}

        # get_meta() must return a copy (mutating it must not affect registry)
        meta1["purpose"] = "mutated"
        assert xfiles.get_meta("repo1") == {}

    def test_register_duplicate_same_instance_warns_and_does_not_override_meta(self, caplog):
        xfiles = XFiles()
        repo = DummyRepository()

        xfiles.register("repo1", repo, meta={"domain": "users"})

        caplog.set_level(logging.WARNING, logger="rag2f.core.xfiles.xfiles")
        xfiles.register("repo1", repo, meta={"domain": "orders"})

        # Should keep original registration (no override)
        assert len(xfiles) == 1
        assert xfiles.get("repo1") is repo
        assert xfiles.get_meta("repo1") == {"domain": "users"}

        assert any(
            "already registered with the same instance" in rec.getMessage()
            for rec in caplog.records
        )

    def test_register_duplicate_different_instance_raises(self):
        xfiles = XFiles()
        repo1 = DummyRepository(name="r1")
        repo2 = DummyRepository(name="r2")

        xfiles.register("repo1", repo1)
        with pytest.raises(ValueError, match="Override not allowed"):
            xfiles.register("repo1", repo2)

        assert xfiles.get("repo1") is repo1

    def test_unregister_removes_and_returns_expected_flags(self):
        xfiles = XFiles()

        assert xfiles.unregister("missing") is False

        repo = DummyRepository()
        xfiles.register("repo1", repo)

        assert xfiles.unregister("repo1") is True
        assert xfiles.has("repo1") is False
        assert xfiles.get("repo1") is None

        # Second removal should be false
        assert xfiles.unregister("repo1") is False

    def test_register_same_instance_is_idempotent(self):
        """Registering the same instance twice should be a no-op."""

        xfiles = XFiles()
        repo = DummyRepository()

        xfiles.register("repo", repo)
        xfiles.register("repo", repo)

        assert len(xfiles.list_ids()) == 1
        assert xfiles.get("repo") is repo

