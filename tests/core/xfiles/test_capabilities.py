"""Tests for Capabilities helper methods."""

from rag2f.core.xfiles import (
    Capabilities,
    FilterCapability,
    NativeCapability,
)


class TestCapabilitiesHelperMethods:
    """Test Capabilities.supports_operator and supports_native_kind methods."""

    def test_supports_operator_returns_true_for_supported_ops(self):
        """supports_operator should return True for operators in filter.ops."""
        caps = Capabilities(
            filter=FilterCapability(supported=True, ops=("eq", "ne", "gt", "and", "or")),
        )
        assert caps.supports_operator("eq") is True
        assert caps.supports_operator("ne") is True
        assert caps.supports_operator("gt") is True
        assert caps.supports_operator("and") is True
        assert caps.supports_operator("or") is True

    def test_supports_operator_returns_false_for_unsupported_ops(self):
        """supports_operator should return False for operators not in filter.ops."""
        caps = Capabilities(
            filter=FilterCapability(supported=True, ops=("eq", "and")),
        )
        # These are not in ops
        assert caps.supports_operator("ne") is False
        assert caps.supports_operator("gt") is False
        assert caps.supports_operator("or") is False
        assert caps.supports_operator("foo") is False  # Unknown op

    def test_supports_operator_returns_false_when_filter_disabled(self):
        """supports_operator should return False when filter.supported=False."""
        caps = Capabilities(
            filter=FilterCapability(supported=False, ops=("eq", "ne")),
        )
        # Even though "eq" is in ops, filter is not supported
        assert caps.supports_operator("eq") is False
        assert caps.supports_operator("ne") is False

    def test_supports_native_kind_returns_true_for_supported_kinds(self):
        """supports_native_kind should return True for kinds in native.kinds."""
        caps = Capabilities(
            native=NativeCapability(supported=True, kinds=("primary", "session", "tx")),
        )
        assert caps.supports_native_kind("primary") is True
        assert caps.supports_native_kind("session") is True
        assert caps.supports_native_kind("tx") is True

    def test_supports_native_kind_returns_false_for_unsupported_kinds(self):
        """supports_native_kind should return False for kinds not in native.kinds."""
        caps = Capabilities(
            native=NativeCapability(supported=True, kinds=("primary", "session")),
        )
        assert caps.supports_native_kind("tx") is False
        assert caps.supports_native_kind("collection") is False
        assert caps.supports_native_kind("unknown") is False

    def test_supports_native_kind_returns_false_when_native_disabled(self):
        """supports_native_kind should return False when native.supported=False."""
        caps = Capabilities(
            native=NativeCapability(supported=False, kinds=("primary", "session")),
        )
        # Even though "primary" is in kinds, native is not supported
        assert caps.supports_native_kind("primary") is False
        assert caps.supports_native_kind("session") is False
