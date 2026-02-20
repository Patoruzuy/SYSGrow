from __future__ import annotations

from app.control_loops import PlantSensorController
from app.enums import IrrigationEligibilityDecision, IrrigationSkipReason
from app.utils.event_bus import EventBus


class StubAnalyticsRepo:
    def __init__(self) -> None:
        self.readings = []
        self.snapshots = []

    def insert_sensor_reading(self, sensor_id: int, reading_data: dict, timestamp: str) -> None:
        self.readings.append({"sensor_id": sensor_id, "reading_data": reading_data, "timestamp": timestamp})

    def save_plant_reading(self, **kwargs):
        self.snapshots.append(kwargs)
        return None

    def get_latest_sensor_readings(self, unit_id: int):
        return {"temperature": 24.0, "humidity": 55.0, "lux": 250}


class StubIrrigationWorkflowService:
    def __init__(self) -> None:
        self.detect_calls = []
        self.trace_calls = []

    def detect_irrigation_need(self, **kwargs):
        self.detect_calls.append(kwargs)
        return 123

    def record_eligibility_trace(self, **kwargs):
        self.trace_calls.append(kwargs)


def test_soil_moisture_below_threshold_triggers_irrigation():
    workflow = StubIrrigationWorkflowService()
    analytics = StubAnalyticsRepo()

    def resolver(*, unit_id: int, sensor_id: int):
        return {
            "plant_id": 10,
            "plant_name": "Basil",
            "plant_type": "basil",
            "growth_stage": "vegetative",
            "user_id": 7,
            "target_moisture": 40.0,
            "actuator_id": 5,
            "plant_pump_assigned": True,
        }

    bus = EventBus()
    bus.subscribers.clear()
    controller = PlantSensorController(
        unit_id=1,
        analytics_repo=analytics,
        irrigation_workflow_service=workflow,
        plant_context_resolver=resolver,
        threshold_service=None,
        event_bus=bus,
    )

    controller.on_soil_moisture_update(
        {"unit_id": 1, "sensor_id": 3, "soil_moisture": 35.0, "timestamp": "2026-01-01T00:00:00Z"}
    )

    assert len(workflow.detect_calls) == 1
    call = workflow.detect_calls[0]
    assert call["unit_id"] == 1
    assert call["soil_moisture"] == 35.0
    assert call["threshold"] == 40.0
    assert call["user_id"] == 7
    assert call["plant_id"] == 10
    assert call["actuator_id"] == 5
    assert call["sensor_id"] == 3


def test_soil_moisture_above_threshold_records_skip():
    workflow = StubIrrigationWorkflowService()
    analytics = StubAnalyticsRepo()

    def resolver(*, unit_id: int, sensor_id: int):
        return {
            "plant_id": 10,
            "plant_name": "Basil",
            "user_id": 7,
            "target_moisture": 40.0,
            "actuator_id": 5,
        }

    bus = EventBus()
    bus.subscribers.clear()
    controller = PlantSensorController(
        unit_id=1,
        analytics_repo=analytics,
        irrigation_workflow_service=workflow,
        plant_context_resolver=resolver,
        threshold_service=None,
        event_bus=bus,
    )

    controller.on_soil_moisture_update(
        {"unit_id": 1, "sensor_id": 3, "soil_moisture": 45.0, "timestamp": "2026-01-01T00:00:00Z"}
    )

    assert len(workflow.detect_calls) == 0
    assert len(workflow.trace_calls) == 1
    trace = workflow.trace_calls[0]
    assert trace["decision"] == IrrigationEligibilityDecision.SKIP
    assert trace["skip_reason"] == IrrigationSkipReason.HYSTERESIS_NOT_MET
