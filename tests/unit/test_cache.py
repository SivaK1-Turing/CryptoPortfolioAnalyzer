"""Tests for cache manager."""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta

from crypto_portfolio_analyzer.data.cache import (
    CacheManager,
    CacheConfig,
    cache_key_for_price,
    cache_key_for_historical
)


@pytest.fixture
def cache_config():
    """Create a test cache configuration."""
    return CacheConfig(
        default_ttl=60,  # 1 minute
        max_size=100,
        cleanup_interval=10,  # 10 seconds
        enable_persistence=False  # Disable for testing
    )


@pytest.fixture
async def cache_manager(cache_config):
    """Create a cache manager for testing."""
    manager = CacheManager(cache_config)
    await manager.start()
    
    yield manager
    
    await manager.stop()


class TestCacheConfig:
    """Test CacheConfig class."""
    
    def test_cache_config_defaults(self):
        """Test default cache configuration values."""
        config = CacheConfig()
        
        assert config.default_ttl == 300
        assert config.max_size == 1000
        assert config.cleanup_interval == 600
        assert config.enable_persistence is True
        assert config.enable_compression is False
    
    def test_cache_config_custom(self):
        """Test custom cache configuration values."""
        config = CacheConfig(
            default_ttl=120,
            max_size=500,
            cleanup_interval=300,
            enable_persistence=False,
            enable_compression=True
        )
        
        assert config.default_ttl == 120
        assert config.max_size == 500
        assert config.cleanup_interval == 300
        assert config.enable_persistence is False
        assert config.enable_compression is True


class TestCacheManager:
    """Test CacheManager functionality."""
    
    @pytest.mark.asyncio
    async def test_cache_manager_lifecycle(self, cache_config):
        """Test cache manager start and stop."""
        manager = CacheManager(cache_config)
        
        # Initially not running
        assert not manager._running
        
        # Start manager
        await manager.start()
        assert manager._running
        
        # Stop manager
        await manager.stop()
        assert not manager._running
        
        # Should be able to start/stop multiple times
        await manager.start()
        await manager.stop()
    
    @pytest.mark.asyncio
    async def test_cache_set_and_get(self, cache_manager):
        """Test basic cache set and get operations."""
        # Set a value
        success = await cache_manager.set("test_key", "test_value")
        assert success
        
        # Get the value
        value = await cache_manager.get("test_key")
        assert value == "test_value"
        
        # Get non-existent key
        value = await cache_manager.get("non_existent", "default")
        assert value == "default"
    
    @pytest.mark.asyncio
    async def test_cache_set_with_ttl(self, cache_manager):
        """Test cache set with custom TTL."""
        # Set value with short TTL
        await cache_manager.set("short_ttl", "value", ttl=1)
        
        # Should be available immediately
        value = await cache_manager.get("short_ttl")
        assert value == "value"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        value = await cache_manager.get("short_ttl", "expired")
        assert value == "expired"
    
    @pytest.mark.asyncio
    async def test_cache_delete(self, cache_manager):
        """Test cache delete operation."""
        # Set a value
        await cache_manager.set("delete_test", "value")
        
        # Verify it exists
        assert await cache_manager.exists("delete_test")
        
        # Delete it
        deleted = await cache_manager.delete("delete_test")
        assert deleted
        
        # Verify it's gone
        assert not await cache_manager.exists("delete_test")
        
        # Delete non-existent key
        deleted = await cache_manager.delete("non_existent")
        assert not deleted
    
    @pytest.mark.asyncio
    async def test_cache_clear(self, cache_manager):
        """Test cache clear operation."""
        # Set multiple values
        await cache_manager.set("key1", "value1")
        await cache_manager.set("key2", "value2")
        await cache_manager.set("key3", "value3")
        
        # Clear all
        cleared_count = await cache_manager.clear()
        assert cleared_count == 3
        
        # Verify all are gone
        assert not await cache_manager.exists("key1")
        assert not await cache_manager.exists("key2")
        assert not await cache_manager.exists("key3")
    
    @pytest.mark.asyncio
    async def test_cache_exists(self, cache_manager):
        """Test cache exists operation."""
        # Non-existent key
        assert not await cache_manager.exists("non_existent")
        
        # Set a key
        await cache_manager.set("exists_test", "value")
        assert await cache_manager.exists("exists_test")
        
        # Expired key should not exist
        await cache_manager.set("expired_test", "value", ttl=1)
        await asyncio.sleep(1.1)
        assert not await cache_manager.exists("expired_test")
    
    @pytest.mark.asyncio
    async def test_cache_get_or_set(self, cache_manager):
        """Test cache get_or_set operation."""
        call_count = 0
        
        def factory():
            nonlocal call_count
            call_count += 1
            return f"generated_value_{call_count}"
        
        # First call should generate value
        value1 = await cache_manager.get_or_set("factory_test", factory)
        assert value1 == "generated_value_1"
        assert call_count == 1
        
        # Second call should use cached value
        value2 = await cache_manager.get_or_set("factory_test", factory)
        assert value2 == "generated_value_1"
        assert call_count == 1  # Factory not called again
    
    @pytest.mark.asyncio
    async def test_cache_get_or_set_async_factory(self, cache_manager):
        """Test cache get_or_set with async factory."""
        async def async_factory():
            await asyncio.sleep(0.1)
            return "async_value"
        
        value = await cache_manager.get_or_set("async_test", async_factory)
        assert value == "async_value"
    
    @pytest.mark.asyncio
    async def test_cache_lru_eviction(self, cache_config):
        """Test LRU eviction when cache is full."""
        # Use small cache size for testing
        cache_config.max_size = 3
        
        manager = CacheManager(cache_config)
        await manager.start()
        
        try:
            # Fill cache to capacity
            await manager.set("key1", "value1")
            await manager.set("key2", "value2")
            await manager.set("key3", "value3")
            
            # All should exist
            assert await manager.exists("key1")
            assert await manager.exists("key2")
            assert await manager.exists("key3")
            
            # Add one more to trigger eviction
            await manager.set("key4", "value4")
            
            # key1 should be evicted (least recently used)
            assert not await manager.exists("key1")
            assert await manager.exists("key2")
            assert await manager.exists("key3")
            assert await manager.exists("key4")
            
            # Access key2 to make it recently used
            await manager.get("key2")
            
            # Add another key
            await manager.set("key5", "value5")
            
            # key3 should be evicted now (key2 was accessed)
            assert not await manager.exists("key3")
            assert await manager.exists("key2")
            assert await manager.exists("key4")
            assert await manager.exists("key5")
            
        finally:
            await manager.stop()
    
    @pytest.mark.asyncio
    async def test_cache_stats(self, cache_manager):
        """Test cache statistics."""
        # Initial stats
        stats = await cache_manager.get_stats()
        assert stats['hits'] == 0
        assert stats['misses'] == 0
        assert stats['size'] == 0
        
        # Set some values
        await cache_manager.set("key1", "value1")
        await cache_manager.set("key2", "value2")
        
        # Cache hits
        await cache_manager.get("key1")
        await cache_manager.get("key2")
        
        # Cache misses
        await cache_manager.get("non_existent1")
        await cache_manager.get("non_existent2")
        
        # Check stats
        stats = await cache_manager.get_stats()
        assert stats['hits'] == 2
        assert stats['misses'] == 2
        assert stats['hit_rate'] == 50.0
        assert stats['size'] == 2
    
    @pytest.mark.asyncio
    async def test_cache_invalidate_pattern(self, cache_manager):
        """Test pattern-based cache invalidation."""
        # Set values with different patterns
        await cache_manager.set("user:123:profile", "profile_data")
        await cache_manager.set("user:123:settings", "settings_data")
        await cache_manager.set("user:456:profile", "other_profile")
        await cache_manager.set("product:789", "product_data")
        
        # Invalidate all user:123 entries
        invalidated = await cache_manager.invalidate_pattern("user:123:*")
        assert invalidated == 2
        
        # Check what remains
        assert not await cache_manager.exists("user:123:profile")
        assert not await cache_manager.exists("user:123:settings")
        assert await cache_manager.exists("user:456:profile")
        assert await cache_manager.exists("product:789")
    
    @pytest.mark.asyncio
    async def test_cache_key_normalization(self, cache_manager):
        """Test cache key normalization."""
        # Test case insensitive keys
        await cache_manager.set("TEST_KEY", "value")
        
        value = await cache_manager.get("test_key")
        assert value == "value"
        
        # Test very long key hashing
        long_key = "x" * 300
        await cache_manager.set(long_key, "long_value")
        
        value = await cache_manager.get(long_key)
        assert value == "long_value"
    
    @pytest.mark.asyncio
    async def test_cache_cleanup_expired(self, cache_config):
        """Test automatic cleanup of expired entries."""
        # Use short cleanup interval for testing
        cache_config.cleanup_interval = 1
        
        manager = CacheManager(cache_config)
        await manager.start()
        
        try:
            # Set values with short TTL
            await manager.set("expire1", "value1", ttl=1)
            await manager.set("expire2", "value2", ttl=1)
            await manager.set("persist", "value3")  # No TTL
            
            # Wait for expiration and cleanup
            await asyncio.sleep(2)
            
            # Expired entries should be cleaned up
            assert not await manager.exists("expire1")
            assert not await manager.exists("expire2")
            assert await manager.exists("persist")
            
        finally:
            await manager.stop()


class TestCacheHelpers:
    """Test cache helper functions."""
    
    @pytest.mark.asyncio
    async def test_cache_key_for_price(self):
        """Test price cache key generation."""
        key = await cache_key_for_price("BTC", "usd")
        assert key == "price:BTC:usd"
        
        # Test case normalization
        key = await cache_key_for_price("btc", "USD")
        assert key == "price:BTC:usd"
    
    @pytest.mark.asyncio
    async def test_cache_key_for_historical(self):
        """Test historical data cache key generation."""
        start_date = datetime(2024, 1, 1)
        end_date = datetime(2024, 1, 31)
        
        key = await cache_key_for_historical("ETH", start_date, end_date, "usd")
        assert key == "historical:ETH:20240101:20240131:usd"
        
        # Test case normalization
        key = await cache_key_for_historical("eth", start_date, end_date, "EUR")
        assert key == "historical:ETH:20240101:20240131:eur"
