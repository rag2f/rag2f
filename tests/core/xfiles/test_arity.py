"""Tests for arity helpers and constants."""

from rag2f.core.xfiles import (
    ALL_KNOWN_OPS,
    ARITY_2_UNARY,
    ARITY_3_COMPARISON,
    ARITY_3_LOGICAL,
    get_expected_arity,
)


class TestArityHelpers:
    """Test arity constant sets and get_expected_arity function."""

    def test_arity_3_comparison_operators(self):
        """Comparison operators should have arity 3."""
        for op in ("eq", "ne", "gt", "gte", "lt", "lte", "in"):
            assert op in ARITY_3_COMPARISON
            assert get_expected_arity(op) == 3

    def test_arity_2_unary_operators(self):
        """Unary operators should have arity 2."""
        for op in ("exists", "not"):
            assert op in ARITY_2_UNARY
            assert get_expected_arity(op) == 2

    def test_arity_3_logical_operators(self):
        """Binary logical operators should have arity 3."""
        for op in ("and", "or"):
            assert op in ARITY_3_LOGICAL
            assert get_expected_arity(op) == 3

    def test_unknown_operator_arity(self):
        """Unknown operators should return arity 0."""
        assert get_expected_arity("unknown_op") == 0
        assert get_expected_arity("foobar") == 0

    def test_all_known_ops_is_union(self):
        """ALL_KNOWN_OPS should be union of all arity sets."""
        expected = ARITY_2_UNARY | ARITY_3_COMPARISON | ARITY_3_LOGICAL
        assert expected == ALL_KNOWN_OPS
