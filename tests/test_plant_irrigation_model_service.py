from datetime import UTC, datetime, timedelta
from unittest.mock import Mock

from app.services.application.plant_irrigation_model_service import PlantIrrigationModelService


def test_update_drydown_model_computes_median_slope():
    now = datetime.now(UTC)
    readings = [
        {"soil_moisture": 60.0, "timestamp": (now - timedelta(hours=4)).isoformat()},
        {"soil_moisture": 56.0, "timestamp": (now - timedelta(hours=2)).isoformat()},
        {"soil_moisture": 52.0, "timestamp": now.isoformat()},
    ]

    irrigation_repo = Mock()
    irrigation_repo.get_manual_logs_for_plant.return_value = []
    irrigation_repo.get_execution_logs_for_plant.return_value = []
    irrigation_repo.upsert_plant_irrigation_model.return_value = True

    analytics_repo = Mock()
    analytics_repo.get_plant_moisture_readings_in_window.return_value = readings

    service = PlantIrrigationModelService(
        irrigation_repo=irrigation_repo,
        analytics_repo=analytics_repo,
    )
    service._min_samples = 2

    result = service.update_drydown_model(plant_id=5)
    assert result["ok"] is True
    assert result["sample_count"] == 2
    assert result["drydown_rate_per_hour"] == -2.0

    call_kwargs = irrigation_repo.upsert_plant_irrigation_model.call_args.kwargs
    assert call_kwargs["drydown_rate_per_hour"] == -2.0
