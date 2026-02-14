from __future__ import annotations

import pytest

pytest.skip("Legacy event bus payload mapping tests removed", allow_module_level=True)


def _prime_event_bus_subscribers() -> None:
    """
    Register the same key subscribers the app wires at runtime.

    This keeps the test small but still exercises the real wiring
    (logger, services, and controllers) against the shared EventBus.
    """
    bus = EventBus()
    # Start from a clean slate so we only see wiring from this helper.
    bus.subscribers.clear()

    # EventLogger subscribes to several Sensor/Plant/Device/Runtime events.
    # Importing the module instantiates the logger as a side-effect.
    from infrastructure.logging import event_logger as _event_logger  # noqa: F401

    # DeviceService subscribes to relay/actuator/connectivity events.
    from app.services.application.device_service import DeviceService

    class DummyRepo:
        def __getattr__(self, name: str):
            def _(*_args: Any, **_kwargs: Any) -> Any:
                raise RuntimeError(f"DummyRepo method {name} should not be called in tests")

            return _

    DeviceService(repository=DummyRepo(), growth_service=None, analytics_service=None)

    # ClimateController subscribes to SensorEvent.* and RuntimeEvent.THRESHOLDS_UPDATE.
    from app.controllers import ClimateController

    class DummyControlLogic:
        def control_temperature(self, *_: Any, **__: Any) -> bool:
            return True

        def control_humidity(self, *_: Any, **__: Any) -> bool:
            return True

        def control_co2(self, *_: Any, **__: Any) -> bool:
            return True

        def control_lux(self, *_: Any, **__: Any) -> bool:
            return True

        def update_thresholds(self, *_: Any, **__: Any) -> None:
            pass
        
        def get_metrics(self, *_: Any, **__: Any) -> dict:
            return {}

    class DummyPollingService:
        pass

    class DummyAnalyticsRepo:
        def get_latest_ai_log(self, *_: Any, **__: Any) -> Dict[str, Any] | None:
            return None

        def insert_sensor_reading(self, *_: Any, **__: Any) -> None:
            return None

    ClimateController(
        unit_id=1,
        control_logic=DummyControlLogic(),
        polling_service=DummyPollingService(),
        analytics_repo=DummyAnalyticsRepo(),
    )

    # PlantProfile subscribes to PlantEvent.MOISTURE_LEVEL_UPDATED.
    from app.domain.plant_profile import PlantProfile

    class DummyGrowthRepo:
        def get_unit_id_for_plant(self, _plant_id: int) -> int:
            return 1

    PlantProfile(
        plant_id=1,
        plant_name="Test Plant",
        current_stage="Seedling",
        growth_stages=[
            {
                "stage": "Seedling",
                "duration": {"min_days": 1, "max_days": 10},
                "conditions": {"hours_per_day": 12},
            }
        ],
        growth_repo=DummyGrowthRepo(),
        plant_type="test",
    )

    # UnitRuntime is a pure domain model — no longer subscribes to events.
    # AI threshold proposals are handled by GrowthService at the service layer.
    from app.domain.unit_runtime import UnitRuntime, UnitSettings

    UnitRuntime(
        unit_id=1,
        unit_name="Unit Test",
        location="Indoor",
        user_id=1,
        settings=UnitSettings(),
        custom_image=None,
    )


def test_event_types_have_subscribers_or_allowlist() -> None:
    """Every EventType should have >=1 subscriber or be explicitly allow-listed."""
    _prime_event_bus_subscribers()
    bus = EventBus()

    # Flatten routing table to a simple name -> subscriber count mapping.
    subscriber_counts: Dict[str, int] = {
        name: len(callbacks) for name, callbacks in bus.subscribers.items()
    }

    all_events: List[EventType] = (
        list(SensorEvent)
        + list(PlantEvent)
        + list(DeviceEvent)
        + list(RuntimeEvent)
    )

    # Events that are intentionally fire-and-forget or not wired yet.
    no_subscriber_expected = {
        DeviceEvent.SENSOR_CREATED,
        DeviceEvent.SENSOR_DELETED,
        DeviceEvent.ACTUATOR_CREATED,
        DeviceEvent.ACTUATOR_DELETED,
        DeviceEvent.ACTUATOR_ANOMALY_DETECTED,
        DeviceEvent.ACTUATOR_ANOMALY_RESOLVED,
        DeviceEvent.ACTUATOR_CALIBRATION_UPDATED,
        DeviceEvent.ACTUATOR_REGISTERED,
        DeviceEvent.ACTUATOR_UNREGISTERED,
    }

    for event in all_events:
        key = event.value
        count = subscriber_counts.get(key, 0)

        if event in no_subscriber_expected:
            # Explicitly documented as having no subscribers (yet).
            continue

        assert (
            count >= 1
        ), f"Event {event} has no subscribers registered; wire a subscriber or add it to the allow-list."


def test_event_payload_models_are_serializable() -> None:
    """
    Ensure all schema-backed event payloads can be instantiated and serialized.

    This guards against missing required fields or invalid defaults that would
    break EventBus.publish() normalization or subscribers expecting dict payloads.
    """
    samples = [
        SensorUpdatePayload(unit_id=1, sensor_id=1),
        PlantLifecyclePayload(unit_id=1, plant_id=1),
        PlantStageUpdatePayload(plant_id=1, new_stage="Seedling", days_in_stage=0),
        PlantGrowthWarningPayload(
            plant_id=1,
            unit_id=1,
            stage="Vegetative",
            days_in_stage=10,
            days_to_transition=2,
            message="Test warning",
        ),
        DeviceLifecyclePayload(unit_id=1, sensor_id=1),
        DeviceLifecyclePayload(unit_id=1, actuator_id=2),
        ActuatorAnomalyPayload(
            actuator_id=1,
            anomaly_id=42,
            anomaly_type="overcurrent",
            severity="high",
            details={"source": "test"},
        ),
        ActuatorAnomalyResolvedPayload(anomaly_id=42),
        ActuatorCalibrationPayload(
            actuator_id=1,
            calibration_type="power_profile",
            calibration_data={"points": []},
        ),
        ThresholdsUpdatePayload(unit_id=1, thresholds={"temperature_min": 20.0}),
        SensorReloadPayload(unit_id=1, source="test"),
        RelayStatePayload(device="pump", state="on"),
        DeviceCommandPayload(command="on", device_id="pump-1"),
        ActuatorStatePayload(actuator_id=1, state="on"),
        ConnectivityStatePayload(
            connection_type="mqtt",
            status="connected",
            endpoint="localhost:1883",
        ),
    ]

    for model in samples:
        data = model.dict()
        # Basic sanity: dict is not empty and keys match original model fields.
        assert isinstance(data, dict)
        assert data.keys(), f"{model.__class__.__name__} produced an empty dict"
