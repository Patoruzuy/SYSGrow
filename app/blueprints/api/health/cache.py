"""
Cache Health Endpoints
======================

Health monitoring endpoints for cache metrics.
"""

from __future__ import annotations

import logging

from flask import Blueprint, Response

from app.blueprints.api._common import (
    success as _success,
)
from app.utils.http import safe_route
from app.utils.time import iso_now

logger = logging.getLogger("health_api")


def register_cache_routes(health_api: Blueprint):
    """Register cache health routes on the blueprint."""

    @health_api.get("/cache")
    @safe_route("Failed to get cache metrics")
    def get_cache_metrics() -> Response:
        """
        Get cache performance metrics for all registered caches.

        This endpoint provides monitoring for TTLCache instances across services,
        helping to identify memory usage patterns and optimize cache configuration
        for Raspberry Pi resource constraints.

        Returns:
            {
                "caches": {...},
                "summary": {...},
                "memory_estimate_kb": 20.5,
                "timestamp": "2025-12-25T..."
            }
        """
        from app.utils.cache import CacheRegistry

        registry = CacheRegistry.get_instance()

        all_stats = registry.get_all_stats()
        summary = registry.get_summary()

        # Rough memory estimate: ~128 bytes per entry (key + value + metadata)
        memory_estimate_bytes = summary["total_size"] * 128
        memory_estimate_kb = round(memory_estimate_bytes / 1024, 2)

        return _success(
            {
                "caches": all_stats,
                "summary": summary,
                "memory_estimate_kb": memory_estimate_kb,
                "timestamp": iso_now(),
            }
        )

    @health_api.get("/cache/repository")
    @safe_route("Failed to get repository cache metrics")
    def get_repository_cache_metrics() -> Response:
        """
        Get cache performance metrics for repository-level LRU caches.

        This endpoint provides monitoring for functools.lru_cache decorated
        repository methods, showing database query caching effectiveness.

        Returns:
            {
                "caches": {...},
                "summary": {...},
                "timestamp": "2025-12-25T..."
            }
        """
        from infrastructure.database.decorators import get_repository_cache_stats

        repo_stats = get_repository_cache_stats()

        # Calculate summary statistics
        total_requests = sum(stats["total_requests"] for stats in repo_stats.values())
        total_hits = sum(stats["hits"] for stats in repo_stats.values())
        total_misses = sum(stats["misses"] for stats in repo_stats.values())
        total_invalidations = sum(stats["invalidations"] for stats in repo_stats.values())

        overall_hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0.0

        summary = {
            "total_caches": len(repo_stats),
            "total_requests": total_requests,
            "total_hits": total_hits,
            "total_misses": total_misses,
            "overall_hit_rate": round(overall_hit_rate, 2),
            "total_invalidations": total_invalidations,
            "estimated_db_queries_saved": total_hits,  # Each hit = 1 saved DB query
        }

        return _success({"caches": repo_stats, "summary": summary, "timestamp": iso_now()})
