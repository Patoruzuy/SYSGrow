"""
Tests for ClimateController analytics storage.

Since primary sensor filtering is now done by CompositeProcessor._build_controller_events()
before events reach ClimateController, these tests verify that ClimateController
correctly stores all metrics from pre-filtered events.
"""

from unittest.mock import MagicMock

import pytest

from app.controllers import ClimateController


class MockAnalyticsRepo:
    """Mock analytics repository for tracking insert calls."""

    def __init__(self):
        self.readings = []

    def insert_sensor_reading(self, sensor_id: int, reading_data: dict, timestamp: str):
        self.readings.append(
            {
                "sensor_id": sensor_id,
                "reading_data": reading_data,
                "timestamp": timestamp,
            }
        )

    def save_plant_reading(self, **_kwargs):
        return None


@pytest.fixture
def mock_control_logic():
    logic = MagicMock()
    logic.control_temperature.return_value = True
    logic.control_humidity.return_value = True
    return logic


@pytest.fixture
def mock_analytics_repo():
    return MockAnalyticsRepo()


@pytest.fixture
def mock_polling_service():
    return MagicMock()


def test_stores_all_metrics_from_event(mock_control_logic, mock_analytics_repo, mock_polling_service):
    """
    Test that ClimateController stores all metrics from an event.

    Primary sensor filtering is done by CompositeProcessor before events
    reach ClimateController, so all metrics in the event should be stored.
    """
    controller = ClimateController(
        unit_id=1,
        control_logic=mock_control_logic,
        polling_service=mock_polling_service,
        analytics_repo=mock_analytics_repo,
    )

    # Event from sensor 2 (already filtered by CompositeProcessor)
    controller._log_analytics_data(
        {
            "sensor_id": 2,
            "temperature": 24.0,
            "humidity": 60.0,
        },
        {"temperature", "humidity"},
    )

    assert len(mock_analytics_repo.readings) == 1
    stored = mock_analytics_repo.readings[0]
    assert stored["sensor_id"] == 2
    assert stored["reading_data"]["temperature"] == 24.0
    assert stored["reading_data"]["humidity"] == 60.0


def test_stores_multiple_events_from_different_sensors(mock_control_logic, mock_analytics_repo, mock_polling_service):
    """
    Test that ClimateController stores events from different sensors.

    Since filtering is done at source, if events arrive from different sensors
    for different metrics, both should be stored.
    """
    controller = ClimateController(
        unit_id=1,
        control_logic=mock_control_logic,
        polling_service=mock_polling_service,
        analytics_repo=mock_analytics_repo,
    )

    # Event from environment sensor with temp/humidity
    controller._log_analytics_data(
        {
            "sensor_id": 2,
            "temperature": 24.0,
            "humidity": 60.0,
        },
        {"temperature", "humidity"},
    )

    # Event from soil sensor with soil_moisture only
    controller._log_analytics_data(
        {
            "sensor_id": 1,
            "soil_moisture": 45.0,
        },
        {"soil_moisture"},
    )

    # Both readings should be stored
    assert len(mock_analytics_repo.readings) == 2

    # Check first reading (temp/humidity from sensor 2)
    assert mock_analytics_repo.readings[0]["sensor_id"] == 2
    assert mock_analytics_repo.readings[0]["reading_data"]["temperature"] == 24.0

    # Check second reading (soil_moisture from sensor 1)
    assert mock_analytics_repo.readings[1]["sensor_id"] == 1
    assert mock_analytics_repo.readings[1]["reading_data"]["soil_moisture"] == 45.0


def test_co2_voc_storage(mock_control_logic, mock_analytics_repo, mock_polling_service):
    """Test that CO2/VOC readings are stored correctly."""
    controller = ClimateController(
        unit_id=1,
        control_logic=mock_control_logic,
        polling_service=mock_polling_service,
        analytics_repo=mock_analytics_repo,
    )

    # Air quality sensor event (already filtered by CompositeProcessor)
    controller._log_analytics_data(
        {
            "sensor_id": 10,
            "co2": 900,
            "voc": 150,
        },
        {"co2", "voc"},
    )

    assert len(mock_analytics_repo.readings) == 1
    stored = mock_analytics_repo.readings[0]
    assert stored["sensor_id"] == 10
    assert stored["reading_data"]["co2"] == 900
    assert stored["reading_data"]["voc"] == 150


def test_excludes_metadata_keys(mock_control_logic, mock_analytics_repo, mock_polling_service):
    """Test that unit_id, sensor_id, and timestamp are excluded from reading_data."""
    controller = ClimateController(
        unit_id=1,
        control_logic=mock_control_logic,
        polling_service=mock_polling_service,
        analytics_repo=mock_analytics_repo,
    )

    controller._log_analytics_data(
        {
            "sensor_id": 2,
            "unit_id": 1,
            "timestamp": "2025-01-18T12:00:00Z",
            "temperature": 24.0,
        },
        {"temperature", "humidity"},
    )

    assert len(mock_analytics_repo.readings) == 1
    stored = mock_analytics_repo.readings[0]
    # Only temperature should be in reading_data
    assert stored["reading_data"] == {"temperature": 24.0}
    assert "unit_id" not in stored["reading_data"]
    assert "sensor_id" not in stored["reading_data"]
    assert "timestamp" not in stored["reading_data"]


def test_skips_empty_metrics(mock_control_logic, mock_analytics_repo, mock_polling_service):
    """Test that events with no savable metrics are skipped."""
    controller = ClimateController(
        unit_id=1,
        control_logic=mock_control_logic,
        polling_service=mock_polling_service,
        analytics_repo=mock_analytics_repo,
    )

    # Event with only metadata, no actual metrics
    controller._log_analytics_data(
        {
            "sensor_id": 2,
            "unit_id": 1,
            "timestamp": "2025-01-18T12:00:00Z",
        },
        {"temperature", "humidity"},
    )

    # Should not store anything
    assert len(mock_analytics_repo.readings) == 0
