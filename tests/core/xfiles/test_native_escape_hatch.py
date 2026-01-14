"""Tests for native escape hatch methods."""

from typing import Protocol

import pytest

from rag2f.core.xfiles import (
    Capabilities,
    NativeCapability,
    NotSupported,
)
from rag2f.core.xfiles.repository import RepositoryNativeMixin

# =============================================================================
# HELPER CLASSES
# =============================================================================


class DummyClient:
    """A dummy client class for testing as_native type checks."""

    def execute(self, query: str) -> str:
        """Execute a dummy query and return a deterministic result."""
        return f"executed: {query}"


class OtherClient:
    """Another client class, incompatible with DummyClient."""

    def run(self, cmd: str) -> str:
        """Run a dummy command and return a deterministic result."""
        return f"ran: {cmd}"


class DummyClientWithPing(DummyClient):
    """A dummy client with a ping method."""

    def ping(self) -> bool:
        """Return True to simulate a successful ping."""
        return True


class _DummyRepositoryBase(RepositoryNativeMixin):
    """Base dummy repository for testing native methods.

    Concrete tests must override:
    - capabilities() to return appropriate Capabilities
    - _get_native_handle() to return desired handle
    """

    def capabilities(self) -> Capabilities:
        raise NotImplementedError("Override in test fixture")

    def _get_native_handle(self, kind: str) -> object:
        raise NotImplementedError("Override in test fixture")


# =============================================================================
# TESTS
# =============================================================================


class TestNativeEscapeHatch:
    """Test native() and as_native() methods from RepositoryNativeMixin."""

    # =========================================================================
    # TEST 15: native() not supported
    # =========================================================================

    def test_native_not_supported_raises_not_supported(self):
        """NATIVE: native() when capabilities().native.supported=False.

        Setup: repo with capabilities().native.supported=False
        Expected: repo.native() -> NotSupported("native") with sensible details
        """

        class RepoWithNativeDisabled(_DummyRepositoryBase):
            def capabilities(self) -> Capabilities:
                return Capabilities(
                    native=NativeCapability(supported=False, kinds=()),
                )

            def _get_native_handle(self, kind: str) -> object:
                # Should never be called
                raise AssertionError("_get_native_handle should not be called")

        repo = RepoWithNativeDisabled()

        with pytest.raises(NotSupported) as exc_info:
            repo.native()

        error = exc_info.value
        assert error.feature == "native"
        assert error.details is not None
        assert "not supported" in error.details.lower()

    # =========================================================================
    # TEST 16: native() kind not available
    # =========================================================================

    def test_native_kind_not_available_raises_not_supported(self):
        """NATIVE: native() with kind not in capabilities().native.kinds.

        Setup: caps.native.supported=True, caps.native.kinds=("primary",)
        Expected: repo.native("session") -> NotSupported("native:session")
                  with list of available kinds
        """

        class RepoWithLimitedKinds(_DummyRepositoryBase):
            def capabilities(self) -> Capabilities:
                return Capabilities(
                    native=NativeCapability(supported=True, kinds=("primary",)),
                )

            def _get_native_handle(self, kind: str) -> object:
                if kind == "primary":
                    return DummyClient()
                raise NotSupported(f"native:{kind}")

        repo = RepoWithLimitedKinds()

        with pytest.raises(NotSupported) as exc_info:
            repo.native("session")  # Not in kinds

        error = exc_info.value
        assert error.feature == "native:session"
        assert error.details is not None
        # Details should mention available kinds
        assert "primary" in error.details
        assert "session" in error.details or "not available" in error.details.lower()

    # =========================================================================
    # TEST 17: as_native() with compatible type
    # =========================================================================

    def test_as_native_with_compatible_type_returns_handle(self):
        """NATIVE: as_native() with type that matches handle.

        Setup: handle is instance of DummyClient
        Expected: repo.as_native(DummyClient) -> returns handle
        """
        handle = DummyClient()

        class RepoWithDummyClient(_DummyRepositoryBase):
            def capabilities(self) -> Capabilities:
                return Capabilities(
                    native=NativeCapability(supported=True, kinds=("primary",)),
                )

            def _get_native_handle(self, kind: str) -> object:
                return handle

        repo = RepoWithDummyClient()

        result = repo.as_native(DummyClient)

        assert result is handle
        assert isinstance(result, DummyClient)

    # =========================================================================
    # TEST 18: as_native() with incompatible type
    # =========================================================================

    def test_as_native_with_incompatible_type_raises_not_supported(self):
        """NATIVE: as_native() with type that doesn't match handle.

        Setup: handle is DummyClient
        Expected: repo.as_native(OtherClient) -> NotSupported with details
                  showing actual type vs expected type
        """

        class RepoWithDummyClient(_DummyRepositoryBase):
            def capabilities(self) -> Capabilities:
                return Capabilities(
                    native=NativeCapability(supported=True, kinds=("primary",)),
                )

            def _get_native_handle(self, kind: str) -> object:
                return DummyClient()

        repo = RepoWithDummyClient()

        with pytest.raises(NotSupported) as exc_info:
            repo.as_native(OtherClient)

        error = exc_info.value
        assert error.feature == "native:primary"
        assert error.details is not None
        # Details should mention both actual and expected types
        assert "DummyClient" in error.details
        assert "OtherClient" in error.details

    # =========================================================================
    # TEST 19: as_native() with callable checker
    # =========================================================================

    def test_as_native_with_callable_checker_failure(self):
        """NATIVE: as_native() with callable that returns False.

        Setup: handle without 'ping' method
        Expected: repo.as_native(lambda o: hasattr(o, "ping")) -> NotSupported
        """

        class RepoWithNoPingClient(_DummyRepositoryBase):
            def capabilities(self) -> Capabilities:
                return Capabilities(
                    native=NativeCapability(supported=True, kinds=("primary",)),
                )

            def _get_native_handle(self, kind: str) -> object:
                return DummyClient()  # Has no ping() method

        repo = RepoWithNoPingClient()

        # Callable checker that requires ping method
        def has_ping(o):
            return hasattr(o, "ping")

        with pytest.raises(NotSupported) as exc_info:
            repo.as_native(has_ping)

        error = exc_info.value
        assert error.feature == "native:primary"
        assert error.details is not None
        assert "compatibility check" in error.details.lower() or "failed" in error.details.lower()

    def test_as_native_with_callable_checker_success(self):
        """NATIVE: as_native() with callable that returns True.

        Setup: handle with 'ping' method
        Expected: repo.as_native(lambda o: hasattr(o, "ping")) -> returns handle
        """
        handle = DummyClientWithPing()

        class RepoWithPingClient(_DummyRepositoryBase):
            def capabilities(self) -> Capabilities:
                return Capabilities(
                    native=NativeCapability(supported=True, kinds=("primary",)),
                )

            def _get_native_handle(self, kind: str) -> object:
                return handle

        repo = RepoWithPingClient()

        def has_ping(o):
            return hasattr(o, "ping")

        result = repo.as_native(has_ping)

        assert result is handle

    # =========================================================================
    # TEST 20: as_native() with non-runtime_checkable Protocol
    # =========================================================================

    def test_as_native_with_non_runtime_checkable_protocol_raises_not_supported(self):
        """NATIVE: as_native() with Protocol that lacks @runtime_checkable.

        Setup: Protocol without @runtime_checkable decorator
        Expected: repo.as_native(MyProtocol) -> NotSupported with hint to use
                  @runtime_checkable
        """

        # Define a Protocol WITHOUT @runtime_checkable
        class NonRuntimeCheckableProtocol(Protocol):
            def some_method(self) -> str: ...

        class RepoWithDummyClient(_DummyRepositoryBase):
            def capabilities(self) -> Capabilities:
                return Capabilities(
                    native=NativeCapability(supported=True, kinds=("primary",)),
                )

            def _get_native_handle(self, kind: str) -> object:
                return DummyClient()

        repo = RepoWithDummyClient()

        with pytest.raises(NotSupported) as exc_info:
            repo.as_native(NonRuntimeCheckableProtocol)

        error = exc_info.value
        assert error.feature == "native:primary"
        assert error.details is not None
        # Details should hint at using runtime_checkable
        assert "runtime_checkable" in error.details.lower() or "runtime" in error.details.lower()
