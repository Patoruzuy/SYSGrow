from pathlib import Path
from types import SimpleNamespace

from app.domain.actuators import ActuatorState
from app.services.application.irrigation_workflow_service import IrrigationWorkflowService
from app.utils.time import iso_now
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler


class StubRepo:
    def __init__(self) -> None:
        self.execution_logs = []

    def acquire_unit_lock(self, unit_id, lock_seconds, current_time=None):
        return True

    def release_unit_lock(self, unit_id):
        return True

    def mark_execution_started(self, request_id, started_at_utc, planned_duration_seconds):
        return True

    def create_execution_log(self, **kwargs):
        self.execution_logs.append(kwargs)
        return len(self.execution_logs)

    def update_execution_log_status(self, request_id, **kwargs):
        return True

    def record_execution(self, request_id, success, **kwargs):
        return True

    def get_user_preference(self, user_id, unit_id=None):
        return None

    def update_preference_on_response(self, *args, **kwargs):
        return True

    def mark_ml_collected(self, *args, **kwargs):
        return True


class StubActuatorManager:
    def __init__(self, valve_id: int, pump_id: int) -> None:
        self.valve_id = valve_id
        self.pump_id = pump_id
        self.pump_called = False

    def turn_on(self, actuator_id, duration_seconds=None):
        if actuator_id == self.valve_id:
            return SimpleNamespace(
                state=ActuatorState.ERROR,
                error_message="Valve open failed",
                runtime_seconds=None,
            )
        if actuator_id == self.pump_id:
            self.pump_called = True
            return SimpleNamespace(
                state=ActuatorState.ON,
                error_message=None,
                runtime_seconds=None,
            )
        return SimpleNamespace(
            state=ActuatorState.UNAVAILABLE,
            error_message="unknown actuator",
            runtime_seconds=None,
        )

    def turn_off(self, actuator_id):
        return SimpleNamespace(
            state=ActuatorState.OFF,
            error_message=None,
            runtime_seconds=0,
        )


class StubPlantService:
    def __init__(self, valve_id: int) -> None:
        self._valve_id = valve_id

    def get_plant_valve_actuator_id(self, plant_id: int):
        return self._valve_id


def _make_db() -> SQLiteDatabaseHandler:
    db = SQLiteDatabaseHandler(":memory:")
    db.create_tables()
    return db


def test_claim_due_requests_is_atomic():
    db = _make_db()
    now = iso_now()
    request_id = db.create_pending_irrigation_request(
        unit_id=1,
        soil_moisture_detected=10.0,
        soil_moisture_threshold=30.0,
        user_id=1,
        scheduled_time=now,
        expires_at=None,
    )

    first = db.claim_due_requests(now)
    second = db.claim_due_requests(now)

    assert any(row["request_id"] == request_id for row in first)
    assert second == []


def test_unit_lock_prevents_parallel_execution():
    db = _make_db()
    now = iso_now()
    assert db.acquire_unit_lock(1, 60, now) is True
    assert db.acquire_unit_lock(1, 60, now) is False
    assert db.release_unit_lock(1) is True
    assert db.acquire_unit_lock(1, 60, iso_now()) is True


def test_attribution_adjust_duration():
    service = IrrigationWorkflowService(workflow_repo=SimpleNamespace())
    result = service._execution._classify_attribution(
        trigger_moisture=10.0,
        threshold_at_trigger=30.0,
        post_moisture=40.0,
    )
    assert result == "adjust_duration"


def test_attribution_adjust_threshold():
    service = IrrigationWorkflowService(workflow_repo=SimpleNamespace())
    result = service._execution._classify_attribution(
        trigger_moisture=30.0,
        threshold_at_trigger=30.0,
        post_moisture=31.0,
    )
    assert result == "adjust_threshold"


def test_valve_failure_prevents_pump_start():
    repo = StubRepo()
    actuator_manager = StubActuatorManager(valve_id=42, pump_id=10)
    plant_service = StubPlantService(valve_id=42)

    service = IrrigationWorkflowService(
        workflow_repo=repo,
        actuator_service=actuator_manager,
        plant_service=plant_service,
    )

    request = {
        "request_id": 1,
        "unit_id": 1,
        "user_id": 1,
        "actuator_id": 10,
        "plant_id": 99,
        "sensor_id": 7,
        "soil_moisture_detected": 10.0,
        "soil_moisture_threshold": 30.0,
        "detected_at": iso_now(),
        "user_response": "approve",
    }

    result = service._execution._execute_irrigation(request)

    assert result["success"] is False
    assert actuator_manager.pump_called is False


def test_irrigation_workflow_has_no_sleep_calls():
    base = Path("app/services/application")
    files = [
        "irrigation_workflow_service.py",
        "irrigation_detection_service.py",
        "irrigation_execution_service.py",
        "irrigation_feedback_service.py",
    ]
    for fname in files:
        source = (base / fname).read_text(encoding="utf-8")
        assert "sleep(" not in source, f"sleep() found in {fname}"
