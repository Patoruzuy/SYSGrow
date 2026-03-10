# app/utils/cache.py
"""Tiny per-process TTL cache with explicit invalidation and metrics."""

from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Any, Callable


class TTLCache:
    """Tiny per-process TTL cache with explicit invalidation."""

    def __init__(self, *, enabled: bool = True, ttl_seconds: int = 30, maxsize: int = 128) -> None:
        """Initialize the TTL cache.
        Args:
            enabled: Whether the cache is enabled
            ttl_seconds: Time-to-live for cache entries in seconds
            maxsize: Maximum number of entries in the cache
        """
        self.enabled = enabled and ttl_seconds > 0 and maxsize > 0
        self.ttl = max(1, ttl_seconds) if self.enabled else 0
        self.maxsize = max(1, maxsize) if self.enabled else 0
        self._store: OrderedDict[Any, tuple[float, Any]] = OrderedDict()
        self._lock = Lock()

        # Metrics tracking
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def get(self, key: Any, loader: Callable[[], Any] | None = None) -> Any:
        """Get a cache entry by key, loading it if missing or expired."""
        if not self.enabled:
            if loader:
                self._misses += 1
                return loader()
            return None

        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry:
                expires_at, value = entry
                if expires_at > now:
                    self._hits += 1
                    self._store.move_to_end(key)
                    return value
                self._store.pop(key, None)

        # Cache miss
        self._misses += 1

        if loader is None:
            return None

        value = loader()
        self.set(key, value)
        return value

    def set(self, key: Any, value: Any) -> None:
        """Set a cache entry with the given key and value."""
        if not self.enabled:
            return
        with self._lock:
            if value is None:
                self._store.pop(key, None)
                return
            expires_at = time.monotonic() + self.ttl
            self._store[key] = (expires_at, value)
            self._store.move_to_end(key)
            if len(self._store) > self.maxsize:
                self._store.popitem(last=False)
                self._evictions += 1

    def invalidate(self, key: Any) -> None:
        """Invalidate a specific cache entry by key."""
        if not self.enabled:
            return
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        """Clear the entire cache."""
        if not self.enabled:
            return
        with self._lock:
            self._store.clear()

    def get_stats(self) -> dict[str, Any]:
        """
        Get cache statistics for monitoring.

        Returns:
            Dictionary with cache metrics including:
            - enabled: Whether cache is enabled
            - size: Current number of entries
            - maxsize: Maximum capacity
            - ttl_seconds: Time-to-live for entries
            - hits: Number of cache hits
            - misses: Number of cache misses
            - hit_rate: Cache hit rate percentage (0-100)
            - evictions: Number of evictions due to size limit
            - utilization: Cache utilization percentage (0-100)
        """
        with self._lock:
            size = len(self._store)
            hits = self._hits
            misses = self._misses
            evictions = self._evictions

        total_requests = hits + misses
        hit_rate = (hits / total_requests * 100) if total_requests > 0 else 0.0
        utilization = (size / self.maxsize * 100) if self.maxsize > 0 else 0.0

        return {
            "enabled": self.enabled,
            "size": size,
            "maxsize": self.maxsize,
            "ttl_seconds": self.ttl,
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hit_rate, 2),
            "evictions": evictions,
            "utilization": round(utilization, 2),
        }


class CacheRegistry:
    """
    Global registry for tracking TTLCache instances across services.

    Provides centralized monitoring of all caches in the application.
    """

    _instance: "CacheRegistry" | None = None
    _lock = Lock()

    def __init__(self) -> None:
        """Initialize the cache registry."""
        self._caches: dict[str, TTLCache] = {}
        self._registry_lock = Lock()

    @classmethod
    def get_instance(cls) -> "CacheRegistry":
        """Get the singleton instance of CacheRegistry."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = CacheRegistry()
        return cls._instance

    def register(self, name: str, cache: TTLCache) -> None:
        """
        Register a cache for monitoring.

        Args:
            name: Unique identifier for the cache (e.g., "growth_service.units")
            cache: TTLCache instance to register
        """
        with self._registry_lock:
            if name in self._caches:
                raise ValueError(f"Cache '{name}' is already registered")
            self._caches[name] = cache

    def unregister(self, name: str) -> None:
        """
        Unregister a cache from monitoring.

        Args:
            name: Cache identifier to remove
        """
        with self._registry_lock:
            self._caches.pop(name, None)

    def get_all_stats(self) -> dict[str, dict[str, Any]]:
        """
        Get statistics for all registered caches.

        Returns:
            Dictionary mapping cache names to their statistics
        """
        with self._registry_lock:
            return {name: cache.get_stats() for name, cache in self._caches.items()}

    def get_summary(self) -> dict[str, Any]:
        """
        Get summary statistics across all caches.

        Returns:
            Aggregated cache metrics including:
            - total_caches: Number of registered caches
            - total_size: Combined size of all caches
            - total_maxsize: Combined capacity of all caches
            - total_hits: Total cache hits across all caches
            - total_misses: Total cache misses
            - overall_hit_rate: Weighted hit rate percentage
            - total_evictions: Total evictions
            - enabled_caches: Number of enabled caches
        """
        all_stats = self.get_all_stats()

        if not all_stats:
            return {
                "total_caches": 0,
                "total_size": 0,
                "total_maxsize": 0,
                "total_hits": 0,
                "total_misses": 0,
                "overall_hit_rate": 0.0,
                "total_evictions": 0,
                "enabled_caches": 0,
            }

        total_size = sum(stats["size"] for stats in all_stats.values())
        total_maxsize = sum(stats["maxsize"] for stats in all_stats.values())
        total_hits = sum(stats["hits"] for stats in all_stats.values())
        total_misses = sum(stats["misses"] for stats in all_stats.values())
        total_evictions = sum(stats["evictions"] for stats in all_stats.values())
        enabled_caches = sum(1 for stats in all_stats.values() if stats["enabled"])

        total_requests = total_hits + total_misses
        overall_hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0.0

        return {
            "total_caches": len(all_stats),
            "total_size": total_size,
            "total_maxsize": total_maxsize,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "overall_hit_rate": round(overall_hit_rate, 2),
            "total_evictions": total_evictions,
            "enabled_caches": enabled_caches,
        }


# Global cache registry instance
_cache_registry = CacheRegistry.get_instance()
