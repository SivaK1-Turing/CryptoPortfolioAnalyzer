"""Intelligent caching system for cryptocurrency data."""

import asyncio
import json
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, Dict, List, Callable, Union
from dataclasses import dataclass, field
from collections import OrderedDict
import logging

from .models import CacheEntry

logger = logging.getLogger(__name__)


@dataclass
class CacheConfig:
    """Configuration for cache behavior."""
    
    default_ttl: int = 300  # 5 minutes default TTL
    max_size: int = 1000    # Maximum number of cache entries
    cleanup_interval: int = 600  # Cleanup every 10 minutes
    enable_persistence: bool = True  # Save cache to database
    enable_compression: bool = False  # Compress large cache values


class CacheManager:
    """Multi-layer caching system with TTL, LRU eviction, and persistence."""
    
    def __init__(self, config: Optional[CacheConfig] = None, db_manager=None):
        """Initialize cache manager.
        
        Args:
            config: Cache configuration
            db_manager: Database manager for persistence
        """
        self.config = config or CacheConfig()
        self.db_manager = db_manager
        
        # In-memory cache with LRU ordering
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._cache_lock = asyncio.Lock()
        
        # Cache statistics
        self._stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0,
            'size': 0
        }
        
        # Background cleanup task
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
    
    async def start(self):
        """Start cache manager and background tasks."""
        if self._running:
            return
        
        self._running = True
        
        # Load cache from database if persistence is enabled
        if self.config.enable_persistence and self.db_manager:
            await self._load_from_database()
        
        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Cache manager started")
    
    async def stop(self):
        """Stop cache manager and save state."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel cleanup task
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        # Save cache to database if persistence is enabled
        if self.config.enable_persistence and self.db_manager:
            await self._save_to_database()
        
        logger.info("Cache manager stopped")
    
    async def get(self, key: str, default: Any = None) -> Any:
        """Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if key not found
            
        Returns:
            Cached value or default
        """
        async with self._cache_lock:
            cache_key = self._normalize_key(key)
            
            if cache_key in self._memory_cache:
                entry = self._memory_cache[cache_key]
                
                # Check if entry has expired
                if entry.is_expired:
                    del self._memory_cache[cache_key]
                    self._stats['misses'] += 1
                    return default
                
                # Move to end (most recently used)
                self._memory_cache.move_to_end(cache_key)
                entry.access()
                self._stats['hits'] += 1
                
                return entry.value
            
            self._stats['misses'] += 1
            return default
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (uses default if None)
            
        Returns:
            True if set successfully
        """
        async with self._cache_lock:
            cache_key = self._normalize_key(key)
            
            # Calculate expiration time
            ttl = ttl or self.config.default_ttl
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl) if ttl > 0 else None
            
            # Create cache entry
            entry = CacheEntry(
                key=cache_key,
                value=value,
                expires_at=expires_at
            )
            
            # Add to memory cache
            self._memory_cache[cache_key] = entry
            
            # Move to end (most recently used)
            self._memory_cache.move_to_end(cache_key)
            
            # Evict if cache is too large
            await self._evict_if_needed()
            
            self._stats['size'] = len(self._memory_cache)
            
            return True
    
    async def delete(self, key: str) -> bool:
        """Delete value from cache.
        
        Args:
            key: Cache key to delete
            
        Returns:
            True if key existed and was deleted
        """
        async with self._cache_lock:
            cache_key = self._normalize_key(key)
            
            if cache_key in self._memory_cache:
                del self._memory_cache[cache_key]
                self._stats['size'] = len(self._memory_cache)
                return True
            
            return False
    
    async def clear(self) -> int:
        """Clear all cache entries.
        
        Returns:
            Number of entries cleared
        """
        async with self._cache_lock:
            count = len(self._memory_cache)
            self._memory_cache.clear()
            self._stats['size'] = 0
            return count
    
    async def exists(self, key: str) -> bool:
        """Check if key exists in cache.
        
        Args:
            key: Cache key to check
            
        Returns:
            True if key exists and is not expired
        """
        value = await self.get(key, None)
        return value is not None
    
    async def get_or_set(self, key: str, factory: Callable, ttl: Optional[int] = None) -> Any:
        """Get value from cache or set it using factory function.
        
        Args:
            key: Cache key
            factory: Function to generate value if not in cache
            ttl: Time to live in seconds
            
        Returns:
            Cached or newly generated value
        """
        value = await self.get(key)
        
        if value is None:
            # Generate new value
            if asyncio.iscoroutinefunction(factory):
                value = await factory()
            else:
                value = factory()
            
            # Cache the new value
            await self.set(key, value, ttl)
        
        return value
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        async with self._cache_lock:
            total_requests = self._stats['hits'] + self._stats['misses']
            hit_rate = (self._stats['hits'] / total_requests * 100) if total_requests > 0 else 0
            
            return {
                'hits': self._stats['hits'],
                'misses': self._stats['misses'],
                'hit_rate': round(hit_rate, 2),
                'evictions': self._stats['evictions'],
                'size': len(self._memory_cache),
                'max_size': self.config.max_size
            }
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate cache entries matching a pattern.
        
        Args:
            pattern: Pattern to match (supports * wildcard)
            
        Returns:
            Number of entries invalidated
        """
        async with self._cache_lock:
            import fnmatch
            
            keys_to_delete = []
            for key in self._memory_cache.keys():
                if fnmatch.fnmatch(key, pattern):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self._memory_cache[key]
            
            self._stats['size'] = len(self._memory_cache)
            return len(keys_to_delete)
    
    def _normalize_key(self, key: str) -> str:
        """Normalize cache key for consistency.
        
        Args:
            key: Original cache key
            
        Returns:
            Normalized cache key
        """
        # Create hash for very long keys
        if len(key) > 250:
            return hashlib.sha256(key.encode()).hexdigest()
        
        return key.lower().strip()
    
    async def _evict_if_needed(self):
        """Evict least recently used entries if cache is full."""
        while len(self._memory_cache) > self.config.max_size:
            # Remove least recently used (first item)
            oldest_key = next(iter(self._memory_cache))
            del self._memory_cache[oldest_key]
            self._stats['evictions'] += 1
    
    async def _cleanup_expired(self) -> int:
        """Remove expired entries from cache.
        
        Returns:
            Number of expired entries removed
        """
        async with self._cache_lock:
            expired_keys = []
            
            for key, entry in self._memory_cache.items():
                if entry.is_expired:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self._memory_cache[key]
            
            self._stats['size'] = len(self._memory_cache)
            return len(expired_keys)
    
    async def _cleanup_loop(self):
        """Background task to clean up expired entries."""
        while self._running:
            try:
                await asyncio.sleep(self.config.cleanup_interval)
                
                if self._running:
                    expired_count = await self._cleanup_expired()
                    if expired_count > 0:
                        logger.debug(f"Cleaned up {expired_count} expired cache entries")
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cache cleanup loop: {e}")
    
    async def _load_from_database(self):
        """Load cache entries from database."""
        if not self.db_manager:
            return
        
        try:
            # This would load from the cache_entries table
            # Implementation depends on database manager interface
            logger.debug("Loading cache from database")
        except Exception as e:
            logger.error(f"Failed to load cache from database: {e}")
    
    async def _save_to_database(self):
        """Save cache entries to database."""
        if not self.db_manager:
            return
        
        try:
            # This would save to the cache_entries table
            # Implementation depends on database manager interface
            logger.debug("Saving cache to database")
        except Exception as e:
            logger.error(f"Failed to save cache to database: {e}")


# Global cache instance
_global_cache: Optional[CacheManager] = None


async def get_cache() -> CacheManager:
    """Get global cache instance."""
    global _global_cache
    
    if _global_cache is None:
        _global_cache = CacheManager()
        await _global_cache.start()
    
    return _global_cache


async def cache_key_for_price(symbol: str, currency: str = "usd") -> str:
    """Generate cache key for price data."""
    return f"price:{symbol.upper()}:{currency.lower()}"


async def cache_key_for_historical(symbol: str, start_date: datetime, 
                                 end_date: datetime, currency: str = "usd") -> str:
    """Generate cache key for historical data."""
    start_str = start_date.strftime("%Y%m%d")
    end_str = end_date.strftime("%Y%m%d")
    return f"historical:{symbol.upper()}:{start_str}:{end_str}:{currency.lower()}"
