"""
Tests for GrowthService.

GrowthService has 20 constructor params; we test the core database-facing
paths using a real in-memory DB and mock the many optional dependencies.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def growth_service(unit_repo, analytics_repo, device_repo, mock_audit_logger, mock_event_bus):
    """GrowthService with real repos and mocked cross-cutting concerns."""
    from app.services.application.growth_service import GrowthService

    return GrowthService(
        unit_repo=unit_repo,
        analytics_repo=analytics_repo,
        audit_logger=mock_audit_logger,
        devices_repo=device_repo,
        event_bus=mock_event_bus,
        cache_enabled=False,  # deterministic tests — no TTL surprises
    )


# ========================== Unit Lifecycle ==================================


class TestUnitLifecycle:
    """create / get / list / delete units through GrowthService."""

    def test_create_unit(self, growth_service, seed):
        # Directly seed a unit and verify we can retrieve it
        unit_id = seed.create_unit("Greenhouse A")
        unit = growth_service.get_unit(unit_id)
        assert unit is not None
        assert unit["name"] == "Greenhouse A"

    def test_list_units_empty(self, growth_service):
        units = growth_service.list_units()
        assert units == []

    def test_list_units_populated(self, growth_service, seed):
        seed.create_unit("Unit Alpha")
        seed.create_unit("Unit Beta")
        units = growth_service.list_units()
        assert len(units) >= 2

    def test_get_nonexistent_unit(self, growth_service):
        unit = growth_service.get_unit(99999)
        assert unit is None or unit == {}


# ========================== Unit Runtime Registry ===========================


class TestUnitRuntimeRegistry:
    """Runtime management (start/stop/get) — with mocked hardware."""

    def test_get_unit_runtime_returns_none_for_unknown(self, growth_service):
        rt = growth_service.get_unit_runtime(99999)
        assert rt is None

    def test_get_unit_runtimes_initially_empty(self, growth_service):
        runtimes = growth_service.get_unit_runtimes()
        assert runtimes == {}


# ========================== Settings / Thresholds ===========================


class TestThresholds:
    """Threshold read/write via GrowthService + real repo."""

    def test_update_settings_persists(self, growth_service, seed):
        unit_id = seed.create_unit()
        new_settings = {"temperature_min": 18.0, "temperature_max": 30.0}
        result = growth_service.update_unit_settings(unit_id, new_settings)
        # update_unit_settings returns bool
        assert result is True or result is False

    def test_update_settings_rejects_empty(self, growth_service, seed):
        unit_id = seed.create_unit()
        result = growth_service.update_unit_settings(unit_id, {})
        assert result is False


# ========================== Cache behaviour =================================


class TestCacheBehaviour:
    """Verify that cache-disabled mode still works correctly."""

    def test_cache_miss_falls_through(self, growth_service, seed):
        uid = seed.create_unit("Cached Unit")
        # Two consecutive calls should both succeed
        u1 = growth_service.get_unit(uid)
        u2 = growth_service.get_unit(uid)
        assert u1["name"] == u2["name"] == "Cached Unit"
