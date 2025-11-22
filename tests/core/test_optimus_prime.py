"""Tests for OptimusPrime - Embedder Registry Manager."""

import pytest
from rag2f.core.optimus_prime.optimus_prime import OptimusPrime
from rag2f.core.protocols import Embedder


class MockEmbedder:
    """Mock embedder for testing."""
    
    @property
    def size(self) -> int:
        return 768
    
    def getEmbedding(self, text: str, *, normalize: bool = False) -> list[float]:
        return [0.1] * self.size


class TestOptimusPrime:
    """Test suite for OptimusPrime embedder registry manager."""

    def test_initialization(self):
        """Test OptimusPrime initialization."""
        optimus = OptimusPrime()

        assert len(optimus.list_keys()) == 0
        assert optimus.list_keys() == []

    def test_register_single_embedder(self):
        """Test registering a single embedder."""
        optimus = OptimusPrime()
        embedder = MockEmbedder()
        
        optimus.register("test_embedder", embedder)
        
        assert len(optimus.list_keys()) == 1
        assert optimus.has("test_embedder")
        assert optimus.get("test_embedder") is embedder

    def test_register_invalid_key(self):
        """Test registering with invalid key raises ValueError."""
        optimus = OptimusPrime()
        embedder = MockEmbedder()
        
        with pytest.raises(ValueError, match="Invalid embedder key"):
            optimus.register("", embedder)
        
        with pytest.raises(ValueError, match="Invalid embedder key"):
            optimus.register("   ", embedder)

    def test_register_invalid_embedder_type(self):
        """Test registering non-Embedder object raises TypeError."""
        optimus = OptimusPrime()
        
        with pytest.raises(TypeError, match="does not implement the Embedder protocol"):
            optimus.register("invalid", "not_an_embedder")

    def test_register_duplicate_key(self):
        """Test registering duplicate key raises ValueError."""
        optimus = OptimusPrime()
        embedder1 = MockEmbedder()
        embedder2 = MockEmbedder()
        
        optimus.register("test", embedder1)
        
        with pytest.raises(ValueError, match="Override not allowed"):
            optimus.register("test", embedder2)

    def test_register_batch(self):
        """Test batch registration of embedders."""
        optimus = OptimusPrime()
        embedders = {
            "embedder1": MockEmbedder(),
            "embedder2": MockEmbedder(),
            "embedder3": MockEmbedder(),
        }
        
        optimus.register_batch(embedders)
        
        assert len(optimus.list_keys()) == 3
        assert optimus.has("embedder1")
        assert optimus.has("embedder2")
        assert optimus.has("embedder3")

    def test_register_batch_with_none(self):
        """Test batch registration with None input."""
        optimus = OptimusPrime()
        
        optimus.register_batch(None)
        
        assert len(optimus.list_keys()) == 0

    def test_register_batch_invalid_type(self):
        """Test batch registration with non-dict raises TypeError."""
        optimus = OptimusPrime()
        
        with pytest.raises(TypeError, match="must be a mapping"):
            optimus.register_batch("not_a_dict")

    def test_register_batch_duplicate_key(self):
        """Test batch registration with duplicate key raises ValueError."""
        optimus = OptimusPrime()
        optimus.register("existing", MockEmbedder())
        
        embedders = {
            "existing": MockEmbedder(),
            "new": MockEmbedder(),
        }
        
        with pytest.raises(ValueError, match="Override not allowed"):
            optimus.register_batch(embedders)
        
        # Registry should remain unchanged
        assert len(optimus.list_keys()) == 1
        assert not optimus.has("new")

    def test_get_existing_embedder(self):
        """Test getting an existing embedder."""
        optimus = OptimusPrime()
        embedder = MockEmbedder()
        optimus.register("test", embedder)
        
        retrieved = optimus.get("test")
        
        assert retrieved is embedder

    def test_get_nonexistent_embedder(self):
        """Test getting non-existent embedder returns None."""
        optimus = OptimusPrime()
        
        result = optimus.get("nonexistent")
        
        assert result is None

    def test_has_embedder(self):
        """Test checking embedder existence."""
        optimus = OptimusPrime()
        optimus.register("test", MockEmbedder())
        
        assert optimus.has("test")
        assert not optimus.has("nonexistent")

    def test_list_keys(self):
        """Test listing all embedder keys."""
        optimus = OptimusPrime()
        optimus.register("embedder1", MockEmbedder())
        optimus.register("embedder2", MockEmbedder())
        optimus.register("embedder3", MockEmbedder())
        
        keys = optimus.list_keys()
        
        assert len(keys) == 3
        assert "embedder1" in keys
        assert "embedder2" in keys
        assert "embedder3" in keys

    def test_count(self):
        """Test counting embedders."""
        optimus = OptimusPrime()
        
        assert len(optimus.list_keys()) == 0
        
        optimus.register("e1", MockEmbedder())
        assert len(optimus.list_keys()) == 1
        
        optimus.register("e2", MockEmbedder())
        assert len(optimus.list_keys()) == 2



    def test_registry_property(self):
        """Test getting registry copy."""
        optimus = OptimusPrime()
        embedder1 = MockEmbedder()
        embedder2 = MockEmbedder()
        
        optimus.register("e1", embedder1)
        optimus.register("e2", embedder2)
        
        registry = optimus.registry
        
        assert len(registry) == 2
        assert registry["e1"] is embedder1
        assert registry["e2"] is embedder2
        
        # Verify it's a copy (modifications don't affect internal registry)
        registry["e3"] = MockEmbedder()
        assert not optimus.has("e3")

    def test_atomic_batch_registration(self):
        """Test that batch registration is atomic (all or nothing)."""
        optimus = OptimusPrime()
        optimus.register("existing", MockEmbedder())
        
        # Batch with one conflicting key
        embedders = {
            "new1": MockEmbedder(),
            "existing": MockEmbedder(),  # This will conflict
            "new2": MockEmbedder(),
        }
        
        with pytest.raises(ValueError):
            optimus.register_batch(embedders)
        
        # Verify no partial registration occurred
        assert len(optimus.list_keys()) == 1
        assert not optimus.has("new1")
        assert not optimus.has("new2")
