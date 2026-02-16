from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

from app.services.application.manual_irrigation_service import ManualIrrigationService


def test_log_watering_event_includes_pre_moisture():
    repo = Mock()
    repo.create_manual_irrigation_log.return_value = 42
    analytics = Mock()
    analytics.get_latest_plant_moisture_in_window.return_value = {
        "soil_moisture": 41.5,
        "timestamp": "2025-01-01T00:00:00+00:00",
    }

    service = ManualIrrigationService(
        irrigation_repo=repo,
        analytics_repo=analytics,
    )

    result = service.log_watering_event(
        user_id=1,
        unit_id=2,
        plant_id=3,
        watered_at_utc="2025-01-01T00:10:00+00:00",
        amount_ml=150.0,
    )

    assert result["ok"] is True
    call_kwargs = repo.create_manual_irrigation_log.call_args.kwargs
    assert call_kwargs["pre_moisture"] == 41.5
    assert call_kwargs["pre_moisture_at_utc"] == "2025-01-01T00:00:00+00:00"


def test_capture_manual_outcomes_updates_post_moisture():
    now = datetime.now(UTC)
    watered_at = (now - timedelta(minutes=30)).isoformat()

    repo = Mock()
    repo.get_manual_logs_pending_post_capture.return_value = [
        {
            "id": 7,
            "plant_id": 10,
            "unit_id": 2,
            "watered_at_utc": watered_at,
            "settle_delay_min": 10,
            "pre_moisture": 40.0,
        }
    ]
    repo.update_manual_log_post_moisture.return_value = True

    analytics = Mock()
    plant_service = Mock()
    plant_service.get_plant.return_value = SimpleNamespace(moisture_level=47.0)

    service = ManualIrrigationService(
        irrigation_repo=repo,
        analytics_repo=analytics,
        plant_service=plant_service,
    )

    updated = service.capture_manual_outcomes()
    assert updated == [7]

    call_kwargs = repo.update_manual_log_post_moisture.call_args.kwargs
    assert call_kwargs["post_moisture"] == 47.0
    assert call_kwargs["delta_moisture"] == 7.0
