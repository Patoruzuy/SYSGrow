"""
Repository-Level Caching Decorators
=====================================

Provides LRU caching for frequently accessed repository methods with:
- Cache metrics tracking
- Invalidation on writes
- Pi-friendly memory limits

Architecture:
    Repository Method -> @repository_cache -> LRU Cache -> Database

Author: Architecture Refactoring Team
Date: December 2025
"""

from __future__ import annotations

import functools
import logging
from threading import Lock
from typing import Any, Callable, TypeVar, cast

logger = logging.getLogger(__name__)

# Type variable for generic function signatures
F = TypeVar("F", bound=Callable[..., Any])


class RepositoryCacheStats:
    """
    Track cache statistics for a single repository method.

    Thread-safe metrics collection for monitoring cache performance.
    """

    def __init__(self, method_name: str, maxsize: int):
        """
        Initialize cache statistics.

        Args:
            method_name: Name of the cached method
            maxsize: Maximum cache size
        """
        self.method_name = method_name
        self.maxsize = maxsize
        self.hits = 0
        self.misses = 0
        self.invalidations = 0
        self._lock = Lock()

    def record_hit(self) -> None:
        """Record a cache hit."""
        with self._lock:
            self.hits += 1

    def record_miss(self) -> None:
        """Record a cache miss."""
        with self._lock:
            self.misses += 1

    def record_invalidation(self) -> None:
        """Record a cache invalidation."""
        with self._lock:
            self.invalidations += 1

    def get_stats(self) -> dict[str, Any]:
        """
        Get current statistics.

        Returns:
            Dictionary with hit rate, miss count, etc.
        """
        with self._lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100) if total > 0 else 0.0

            return {
                "method": self.method_name,
                "maxsize": self.maxsize,
                "hits": self.hits,
                "misses": self.misses,
                "hit_rate": round(hit_rate, 2),
                "invalidations": self.invalidations,
                "total_requests": total,
            }

    def reset(self) -> None:
        """Reset all statistics to zero."""
        with self._lock:
            self.hits = 0
            self.misses = 0
            self.invalidations = 0


# Global registry for repository cache statistics
_cache_stats_registry: dict[str, RepositoryCacheStats] = {}
_registry_lock = Lock()


def get_repository_cache_stats() -> dict[str, dict[str, Any]]:
    """
    Get statistics for all repository caches.

    Returns:
        Dictionary mapping method names to their statistics
    """
    with _registry_lock:
        return {name: stats.get_stats() for name, stats in _cache_stats_registry.items()}


def reset_repository_cache_stats() -> None:
    """Reset all repository cache statistics."""
    with _registry_lock:
        for stats in _cache_stats_registry.values():
            stats.reset()


def repository_cache(
    maxsize: int = 128, *, typed: bool = False, invalidate_on: list[str] | None = None
) -> Callable[[F], F]:
    """
    LRU cache decorator for repository methods with metrics tracking.

    Provides:
    - Efficient LRU caching via functools.lru_cache
    - Hit/miss/invalidation metrics
    - Cache invalidation triggers
    - Integration with monitoring

    Usage:
        class MyRepository:
            @repository_cache(maxsize=128)
            def get_item(self, item_id: int):
                return self._backend.fetch_item(item_id)

            @repository_cache(maxsize=256, invalidate_on=['create_item', 'delete_item'])
            def list_items(self):
                return self._backend.fetch_all_items()

    Args:
        maxsize: Maximum number of cached entries (Pi-friendly: 128-256)
        typed: If True, arguments of different types are cached separately
        invalidate_on: List of method names that should invalidate this cache

    Returns:
        Decorated function with caching and metrics
    """

    def decorator(func: F) -> F:
        # Get qualified method name for tracking
        method_name = f"{func.__module__}.{func.__qualname__}"

        # Create statistics tracker
        stats = RepositoryCacheStats(method_name, maxsize)
        with _registry_lock:
            _cache_stats_registry[method_name] = stats

        # Apply LRU cache
        cached_func = functools.lru_cache(maxsize=maxsize, typed=typed)(func)

        # Wrap to track hits/misses
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if result is in cache by inspecting cache_info
            cache_info_before = cached_func.cache_info()
            result = cached_func(*args, **kwargs)
            cache_info_after = cached_func.cache_info()

            # Detect hit vs miss by comparing hits count
            if cache_info_after.hits > cache_info_before.hits:
                stats.record_hit()
                logger.debug(f"Cache HIT: {method_name}")
            else:
                stats.record_miss()
                logger.debug(f"Cache MISS: {method_name}")

            return result

        # Add cache control methods
        def invalidate_cache() -> None:
            """Clear the cache for this method."""
            cached_func.cache_clear()
            stats.record_invalidation()
            logger.info(f"Cache invalidated: {method_name}")

        def get_cache_info() -> dict[str, Any]:
            """Get cache info including custom stats."""
            info = cached_func.cache_info()
            custom_stats = stats.get_stats()
            return {
                **custom_stats,
                "lru_hits": info.hits,
                "lru_misses": info.misses,
                "lru_currsize": info.currsize,
                "lru_maxsize": info.maxsize,
            }

        # Attach utility methods to wrapper
        wrapper.invalidate_cache = invalidate_cache  # type: ignore
        wrapper.get_cache_info = get_cache_info  # type: ignore
        wrapper._cache_stats = stats  # type: ignore
        wrapper._invalidate_on = invalidate_on or []  # type: ignore

        logger.debug(f"Repository cache enabled: {method_name} (maxsize={maxsize}, invalidate_on={invalidate_on})")

        return cast(F, wrapper)

    return decorator


def invalidate_related_caches(repository_instance: Any, method_name: str) -> None:
    """
    Invalidate caches that depend on a write operation.

    When a write method (create/update/delete) is called, this function
    finds all cached methods that registered this writer as an invalidation
    trigger and clears their caches.

    Usage:
        class MyRepository:
            def create_item(self, ...):
                result = self._backend.insert_item(...)
                invalidate_related_caches(self, 'create_item')
                return result

    Args:
        repository_instance: The repository object
        method_name: Name of the write method being called
    """
    invalidated_count = 0

    # Iterate through all methods on the repository instance
    for attr_name in dir(repository_instance):
        try:
            attr = getattr(repository_instance, attr_name)

            # Check if this method has cache invalidation triggers
            if hasattr(attr, "_invalidate_on"):
                invalidate_on = attr._invalidate_on

                # If this method should be invalidated by the current write
                if method_name in invalidate_on:
                    if hasattr(attr, "invalidate_cache"):
                        attr.invalidate_cache()
                        invalidated_count += 1
                        logger.debug(f"Invalidated {attr_name} due to {method_name}")
        except Exception as e:
            # Skip attributes that can't be accessed
            logger.debug(f"Could not check {attr_name} for invalidation: {e}")
            continue

    if invalidated_count > 0:
        logger.info(f"Write operation '{method_name}' invalidated {invalidated_count} cache(s)")


# Convenience decorator for write methods that trigger invalidations
def invalidates_caches(func: F) -> F:
    """
    Decorator for write methods that automatically invalidates related caches.

    Usage:
        class MyRepository:
            @invalidates_caches
            def create_item(self, ...):
                return self._backend.insert_item(...)

    This will automatically call invalidate_related_caches after the method executes.
    """

    @functools.wraps(func)
    def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
        result = func(self, *args, **kwargs)
        invalidate_related_caches(self, func.__name__)
        return result

    return cast(F, wrapper)
