"""
Shared test fixtures for the SYSGrow backend test suite.

Provides:
- In-memory SQLite database with all tables created
- Repository instances wired to the test database
- Mock services for optional dependencies
- Service factories for top-level application services
- Helper utilities for seeding test data

Usage:
    def test_example(db_handler, device_repo):
        sensor_id = device_repo.create_sensor(...)
        assert sensor_id is not None
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import MagicMock

import pytest

from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.growth import GrowthRepository
from infrastructure.database.repositories.irrigation_workflow import (
    IrrigationWorkflowRepository,
)
from infrastructure.database.repositories.plants import PlantRepository
from infrastructure.database.repositories.units import UnitRepository

# ---------------------------------------------------------------------------
# Database & Repositories
# ---------------------------------------------------------------------------
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

# ---------------------------------------------------------------------------
# Logging — keep test output clean
# ---------------------------------------------------------------------------
logging.getLogger("infrastructure").setLevel(logging.WARNING)
logging.getLogger("app").setLevel(logging.WARNING)


# ========================== Database Fixtures ==============================


@pytest.fixture()
def db_handler():
    """In-memory SQLite database with all tables created.

    Each test gets a fresh database — no cross-test contamination.
    """
    handler = SQLiteDatabaseHandler(":memory:")
    handler.create_tables()
    yield handler


@pytest.fixture()
def db_connection(db_handler):
    """Raw sqlite3 connection for direct SQL in tests."""
    with db_handler.connection() as conn:
        yield conn


# ========================== Repository Fixtures ============================


@pytest.fixture()
def analytics_repo(db_handler):
    """AnalyticsRepository backed by the in-memory DB."""
    return AnalyticsRepository(db_handler)


@pytest.fixture()
def device_repo(db_handler):
    """DeviceRepository backed by the in-memory DB."""
    return DeviceRepository(db_handler)


@pytest.fixture()
def growth_repo(db_handler):
    """GrowthRepository (deprecated compatibility facade)."""
    return GrowthRepository(db_handler)


@pytest.fixture()
def plant_repo(db_handler):
    """PlantRepository backed by the in-memory DB."""
    return PlantRepository(db_handler)


@pytest.fixture()
def unit_repo(db_handler):
    """UnitRepository backed by the in-memory DB."""
    return UnitRepository(db_handler)


@pytest.fixture()
def irrigation_workflow_repo(db_handler):
    """IrrigationWorkflowRepository backed by the in-memory DB."""
    return IrrigationWorkflowRepository(db_handler)


# ========================== Mock Service Fixtures ==========================


@pytest.fixture()
def mock_event_bus():
    """Mock EventBus that records publish calls."""
    bus = MagicMock()
    bus.publish = MagicMock()
    bus.subscribe = MagicMock()
    return bus


@pytest.fixture()
def mock_audit_logger():
    """Mock AuditLogger."""
    logger = MagicMock()
    logger.log = MagicMock()
    return logger


@pytest.fixture()
def mock_activity_logger():
    """Mock ActivityLogger that accepts any log_activity call."""
    logger = MagicMock()
    logger.log_activity = MagicMock()
    logger.SYSTEM_STARTUP = "system_startup"
    logger.INFO = "info"
    logger.WARNING = "warning"
    logger.HARVEST_RECORDED = "harvest_recorded"
    return logger


@pytest.fixture()
def mock_notifications_service():
    """Mock NotificationsService."""
    svc = MagicMock()
    svc.send_notification = MagicMock()
    svc.register_action_handler = MagicMock()
    return svc


@pytest.fixture()
def mock_emitter():
    """Mock EmitterService for SocketIO emission."""
    emitter = MagicMock()
    emitter.emit_sensor_reading = MagicMock()
    emitter.emit_actuator_state = MagicMock()
    return emitter


@pytest.fixture()
def mock_processor():
    """Mock IDataProcessor pipeline."""
    processor = MagicMock()
    processor.process = MagicMock(side_effect=lambda data: data)
    return processor


# ========================== Service Factory Fixtures =======================


@pytest.fixture()
def analytics_service(analytics_repo, device_repo, growth_repo):
    """AnalyticsService with real repos and no optional deps."""
    from app.services.application.analytics_service import AnalyticsService

    return AnalyticsService(
        repository=analytics_repo,
        device_repository=device_repo,
        growth_repository=growth_repo,
    )


@pytest.fixture()
def harvest_service(analytics_repo, plant_repo, device_repo):
    """PlantHarvestService with real repos."""
    from app.services.application.harvest_service import PlantHarvestService

    return PlantHarvestService(
        analytics_repo=analytics_repo,
        plant_repo=plant_repo,
        device_repo=device_repo,
    )


@pytest.fixture()
def irrigation_workflow_service(irrigation_workflow_repo):
    """IrrigationWorkflowService with real repo, no optional deps."""
    from app.services.application.irrigation_workflow_service import (
        IrrigationWorkflowService,
    )

    return IrrigationWorkflowService(workflow_repo=irrigation_workflow_repo)


@pytest.fixture()
def sensor_management_service(device_repo, mock_emitter, mock_processor):
    """SensorManagementService with real repo, mocked emitter/processor."""
    from app.services.hardware.sensor_management_service import (
        SensorManagementService,
    )

    return SensorManagementService(
        repository=device_repo,
        emitter=mock_emitter,
        processor=mock_processor,
    )


@pytest.fixture()
def actuator_management_service(device_repo):
    """ActuatorManagementService with real repo, no optional deps."""
    from app.services.hardware.actuator_management_service import (
        ActuatorManagementService,
    )

    return ActuatorManagementService(repository=device_repo)


# ========================== Seed Data Helpers ==============================


class SeedData:
    """Helper to create commonly needed test data.

    Usage in tests::

        def test_something(db_handler, seed):
            unit_id = seed.create_unit("Test Unit")
            plant_id = seed.create_plant("Tomato", unit_id=unit_id)
            sensor_id = seed.create_sensor(unit_id=unit_id, sensor_type="temperature")
            seed.insert_reading(sensor_id, temperature=22.5, humidity=65.0)
    """

    def __init__(self, db_handler: SQLiteDatabaseHandler):
        self._db = db_handler

    def create_unit(
        self,
        name: str = "Test Unit",
        location: str = "Indoor",
    ) -> int:
        """Create a growth unit and return its ID."""
        with self._db.connection() as conn:
            cur = conn.execute(
                "INSERT INTO GrowthUnits (name, location) VALUES (?, ?)",
                (name, location),
            )
            return cur.lastrowid

    def create_plant(
        self,
        name: str = "Test Tomato",
        plant_type: str = "Cherry Tomato",
        unit_id: int | None = None,
        stage: str = "vegetative",
        days_in_stage: int = 10,
    ) -> int:
        """Create a plant and optionally link it to a unit."""
        planted_date = (datetime.now() - timedelta(days=days_in_stage + 14)).strftime("%Y-%m-%d %H:%M:%S")
        with self._db.connection() as conn:
            cur = conn.execute(
                """INSERT INTO Plants (name, plant_type, current_stage,
                   days_in_stage, planted_date)
                   VALUES (?, ?, ?, ?, ?)""",
                (name, plant_type, stage, days_in_stage, planted_date),
            )
            plant_id = cur.lastrowid

            if unit_id is not None:
                conn.execute(
                    "INSERT INTO GrowthUnitPlants (unit_id, plant_id) VALUES (?, ?)",
                    (unit_id, plant_id),
                )
            return plant_id

    def create_sensor(
        self,
        unit_id: int = 1,
        name: str = "Test Sensor",
        sensor_type: str = "temperature",
        protocol: str = "i2c",
        model: str = "BME280",
    ) -> int:
        """Create a sensor and return its ID."""
        with self._db.connection() as conn:
            cur = conn.execute(
                """INSERT INTO Sensor (unit_id, name, sensor_type, protocol, model)
                   VALUES (?, ?, ?, ?, ?)""",
                (unit_id, name, sensor_type, protocol, model),
            )
            return cur.lastrowid

    def create_actuator(
        self,
        unit_id: int = 1,
        name: str = "Test Pump",
        actuator_type: str = "water_pump",
        protocol: str = "gpio",
        model: str = "Generic",
    ) -> int:
        """Create an actuator and return its ID."""
        with self._db.connection() as conn:
            cur = conn.execute(
                """INSERT INTO Actuator (unit_id, name, actuator_type, protocol, model)
                   VALUES (?, ?, ?, ?, ?)""",
                (unit_id, name, actuator_type, protocol, model),
            )
            return cur.lastrowid

    def insert_reading(
        self,
        sensor_id: int,
        *,
        temperature: float | None = None,
        humidity: float | None = None,
        soil_moisture: float | None = None,
        timestamp: str | None = None,
        quality_score: float = 1.0,
    ) -> int:
        """Insert a sensor reading and return its ID."""
        data: dict[str, Any] = {}
        if temperature is not None:
            data["temperature"] = temperature
        if humidity is not None:
            data["humidity"] = humidity
        if soil_moisture is not None:
            data["soil_moisture"] = soil_moisture

        ts = timestamp or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._db.connection() as conn:
            cur = conn.execute(
                """INSERT INTO SensorReading (sensor_id, reading_data,
                   quality_score, timestamp)
                   VALUES (?, ?, ?, ?)""",
                (sensor_id, json.dumps(data), quality_score, ts),
            )
            return cur.lastrowid

    def insert_energy_reading(
        self,
        device_id: int,
        unit_id: int,
        *,
        power_watts: float = 100.0,
        energy_kwh: float = 2.4,
        plant_id: int | None = None,
        growth_stage: str = "vegetative",
    ) -> int:
        """Insert an energy reading and return its ID."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._db.connection() as conn:
            cur = conn.execute(
                """INSERT INTO EnergyReadings
                   (device_id, unit_id, plant_id, growth_stage, timestamp,
                    power_watts, energy_kwh, source_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'test')""",
                (device_id, unit_id, plant_id, growth_stage, ts, power_watts, energy_kwh),
            )
            return cur.lastrowid


@pytest.fixture()
def seed(db_handler):
    """SeedData helper for quickly populating the test database."""
    return SeedData(db_handler)
