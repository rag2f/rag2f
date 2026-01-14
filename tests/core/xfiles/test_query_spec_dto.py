"""Tests for QuerySpec DTO to_dict/from_dict methods."""

from rag2f.core.xfiles.types import QuerySpec


class TestQuerySpecToDict:
    """Test QuerySpec.to_dict method."""

    def test_base_query_spec_to_dict_includes_offset(self):
        """QuerySpec() base -> to_dict produces at least {"offset": 0}."""
        spec = QuerySpec()

        result = spec.to_dict()

        assert "offset" in result
        assert result["offset"] == 0

    def test_to_dict_excludes_none_values(self):
        """to_dict should not include None values except offset."""
        spec = QuerySpec()

        result = spec.to_dict()

        assert result == {"offset": 0}
        assert "select" not in result
        assert "where" not in result
        assert "order_by" not in result
        assert "limit" not in result


class TestQuerySpecFromDict:
    """Test QuerySpec.from_dict method."""

    def test_from_dict_offset_defaults_to_zero(self):
        """QuerySpec.from_dict({"limit": 10}) -> offset == 0."""
        data = {"limit": 10}

        spec = QuerySpec.from_dict(data)

        assert spec.offset == 0
        assert spec.limit == 10


class TestQuerySpecRoundTrip:
    """Test QuerySpec to_dict/from_dict round-trip."""

    def test_round_trip_preserves_all_fields(self):
        """QuerySpec with all fields -> round-trip preserves values."""
        original = QuerySpec(
            select=["id", "name", "email"],
            where=("eq", "status", "active"),
            order_by=["-created_at", "name"],
            limit=50,
            offset=100,
        )

        dict_repr = original.to_dict()
        restored = QuerySpec.from_dict(dict_repr)

        assert restored.select == original.select
        assert restored.where == original.where
        assert restored.order_by == original.order_by
        assert restored.limit == original.limit
        assert restored.offset == original.offset

    def test_round_trip_base_query_spec(self):
        """QuerySpec() base -> round-trip preserves default offset."""
        original = QuerySpec()

        dict_repr = original.to_dict()
        restored = QuerySpec.from_dict(dict_repr)

        assert restored.offset == 0
        assert restored.select is None
        assert restored.where is None
        assert restored.order_by is None
        assert restored.limit is None
