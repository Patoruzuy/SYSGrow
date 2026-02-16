import tempfile
from pathlib import Path
from unittest.mock import Mock

from app.services.ai.personalized_learning import PersonalizedLearningService
from app.services.application.threshold_service import ThresholdService


class StubPlantHandler:
    def search_plants(self, common_name=None):
        return [
            {
                "growth_stages": [
                    {
                        "stage": "Vegetative",
                        "conditions": {
                            "temperature_C": {"min": 20.0, "max": 22.0},
                            "humidity_percent": {"min": 50.0, "max": 60.0},
                        },
                        "sensor_targets": {"soil_moisture": 35.0},
                    }
                ],
                "sensor_requirements": {"co2_requirements": {"min": 900.0, "max": 1100.0}},
            }
        ]


def test_threshold_service_prefers_profile_over_defaults():
    with tempfile.TemporaryDirectory() as tmp_dir:
        personalized = PersonalizedLearningService(
            model_registry=Mock(),
            training_data_repo=Mock(),
            profiles_dir=Path(tmp_dir),
        )
        personalized.upsert_condition_profile(
            user_id=1,
            plant_type="Tomato",
            growth_stage="Vegetative",
            environment_thresholds={"temperature_threshold": 27.0, "humidity_threshold": 65.0},
            soil_moisture_threshold=45.0,
        )
        service = ThresholdService(
            plant_handler=StubPlantHandler(),
            climate_optimizer=None,
            growth_repo=None,
            notifications_service=None,
            event_bus=None,
            personalized_learning=personalized,
        )
        thresholds = service.get_thresholds(
            "Tomato",
            "Vegetative",
            user_id=1,
        )
        assert thresholds.temperature == 27.0
        assert thresholds.humidity == 65.0
        assert thresholds.soil_moisture == 45.0


def test_threshold_service_falls_back_when_no_profile_for_stage():
    with tempfile.TemporaryDirectory() as tmp_dir:
        personalized = PersonalizedLearningService(
            model_registry=Mock(),
            training_data_repo=Mock(),
            profiles_dir=Path(tmp_dir),
        )
        personalized.upsert_condition_profile(
            user_id=1,
            plant_type="Tomato",
            growth_stage="Flowering",
            environment_thresholds={"temperature_threshold": 30.0},
        )
        service = ThresholdService(
            plant_handler=StubPlantHandler(),
            climate_optimizer=None,
            growth_repo=None,
            notifications_service=None,
            event_bus=None,
            personalized_learning=personalized,
        )
        thresholds = service.get_thresholds(
            "Tomato",
            "Vegetative",
            user_id=1,
        )
        assert thresholds.temperature == 21.0
