"""
Tests for SensorManagementService and ActuatorManagementService.

Covers the DB-facing query paths (list, get) using a real in-memory
database. Hardware control paths are not tested because they require
physical adapters; focus is on data-layer correctness.
"""

from __future__ import annotations

import pytest

# ========================== Sensor Management ===============================


class TestSensorListAndGet:
    """SensorManagementService query methods with real DB."""

    def test_list_sensors_empty(self, sensor_management_service):
        result = sensor_management_service.list_sensors()
        assert result == []

    def test_list_sensors_with_data(self, sensor_management_service, seed):
        uid = seed.create_unit()
        seed.create_sensor(unit_id=uid, name="Temp A", sensor_type="temperature")
        seed.create_sensor(unit_id=uid, name="Hum B", sensor_type="humidity")

        sensors = sensor_management_service.list_sensors(unit_id=uid)
        assert len(sensors) >= 2

    def test_list_sensors_filtered_by_unit(self, sensor_management_service, seed):
        u1 = seed.create_unit("Unit 1")
        u2 = seed.create_unit("Unit 2")
        seed.create_sensor(unit_id=u1, name="S1")
        seed.create_sensor(unit_id=u2, name="S2")

        result = sensor_management_service.list_sensors(unit_id=u1)
        assert all(s.get("unit_id") == u1 for s in result)

    def test_get_sensor_not_found(self, sensor_management_service):
        result = sensor_management_service.get_sensor(99999)
        assert result is None

    def test_get_sensor_found(self, sensor_management_service, seed):
        uid = seed.create_unit()
        sid = seed.create_sensor(unit_id=uid, name="Test Sensor")

        result = sensor_management_service.get_sensor(sid)
        assert result is not None
        assert result.get("name") == "Test Sensor" or result.get("sensor_id") == sid


class TestSensorRegisteredIds:
    """Runtime registration tracking."""

    def test_initially_empty(self, sensor_management_service):
        assert sensor_management_service.get_registered_sensor_ids() == []


# ========================== Actuator Management =============================


class TestActuatorListAndGet:
    """ActuatorManagementService query methods with real DB."""

    def test_list_actuators_empty(self, actuator_management_service):
        result = actuator_management_service.list_actuators()
        assert result == []

    def test_list_actuators_with_data(self, actuator_management_service, seed):
        uid = seed.create_unit()
        seed.create_actuator(unit_id=uid, name="Pump 1", actuator_type="water_pump")
        seed.create_actuator(unit_id=uid, name="Fan 1", actuator_type="fan")

        actuators = actuator_management_service.list_actuators(unit_id=uid)
        assert len(actuators) >= 2

    def test_list_actuators_filtered_by_unit(self, actuator_management_service, seed):
        u1 = seed.create_unit("Unit A")
        u2 = seed.create_unit("Unit B")
        seed.create_actuator(unit_id=u1, name="P1")
        seed.create_actuator(unit_id=u2, name="P2")

        result = actuator_management_service.list_actuators(unit_id=u1)
        assert all(a.get("unit_id") == u1 for a in result)

    def test_get_actuator_not_found(self, actuator_management_service):
        result = actuator_management_service.get_actuator(99999)
        assert result is None

    def test_get_actuator_found(self, actuator_management_service, seed):
        uid = seed.create_unit()
        aid = seed.create_actuator(unit_id=uid, name="Test Pump")

        result = actuator_management_service.get_actuator(aid)
        assert result is not None
        assert result.get("name") == "Test Pump" or result.get("actuator_id") == aid


class TestActuatorRegisteredIds:
    """Runtime registration tracking."""

    def test_initially_empty(self, actuator_management_service):
        assert actuator_management_service.get_registered_actuator_ids() == []


class TestActuatorStateValidation:
    """set_actuator_state validation."""

    def test_invalid_id_raises(self, actuator_management_service):
        with pytest.raises(ValueError, match="Invalid actuator_id"):
            actuator_management_service.set_actuator_state(actuator_id=0, state=True)

    def test_negative_id_raises(self, actuator_management_service):
        with pytest.raises(ValueError, match="Invalid actuator_id"):
            actuator_management_service.set_actuator_state(actuator_id=-1, state=False)
