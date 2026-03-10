import math
import tempfile
from pathlib import Path
from unittest.mock import Mock

from app.enums.common import ConditionProfileMode, ConditionProfileVisibility
from app.services.ai.personalized_learning import PersonalizedLearningService


def test_condition_profile_upsert_and_rating_updates():
    with tempfile.TemporaryDirectory() as tmp_dir:
        service = PersonalizedLearningService(
            model_registry=Mock(),
            training_data_repo=Mock(),
            profiles_dir=Path(tmp_dir),
        )
        profile = service.upsert_condition_profile(
            user_id=1,
            plant_type="Tomato",
            growth_stage="Vegetative",
            environment_thresholds={"temperature_threshold": 25.0, "humidity_threshold": 60.0},
            soil_moisture_threshold=45.0,
            rating=4,
        )
        assert profile.rating_count == 1
        assert profile.rating_avg == 4.0
        assert profile.environment_thresholds["temperature_threshold"] == 25.0

        fetched = service.get_condition_profile(
            user_id=1,
            plant_type="Tomato",
            growth_stage="Vegetative",
        )
        assert fetched is not None
        assert fetched.soil_moisture_threshold == 45.0

        updated = service.upsert_condition_profile(
            user_id=1,
            plant_type="Tomato",
            growth_stage="Vegetative",
            environment_thresholds={"temperature_threshold": 27.0},
            rating=2,
        )
        assert updated.rating_count == 2
        assert math.isclose(updated.rating_avg, 3.0)
        assert updated.environment_thresholds["temperature_threshold"] == 27.0


def test_condition_profile_clone_and_template_lock():
    with tempfile.TemporaryDirectory() as tmp_dir:
        service = PersonalizedLearningService(
            model_registry=Mock(),
            training_data_repo=Mock(),
            profiles_dir=Path(tmp_dir),
        )
        template = service.upsert_condition_profile(
            user_id=1,
            plant_type="Lettuce",
            growth_stage="Vegetative",
            environment_thresholds={"temperature_threshold": 22.0},
            soil_moisture_threshold=40.0,
            image_url="static/img/profile-lettuce.png",
            mode=ConditionProfileMode.TEMPLATE,
            name="Lettuce Template",
            visibility=ConditionProfileVisibility.PRIVATE,
        )
        # Template updates should be ignored unless explicitly allowed
        unchanged = service.upsert_condition_profile(
            user_id=1,
            profile_id=template.profile_id,
            plant_type="Lettuce",
            growth_stage="Vegetative",
            environment_thresholds={"temperature_threshold": 26.0},
        )
        assert unchanged.environment_thresholds["temperature_threshold"] == 22.0

        cloned = service.clone_condition_profile(
            user_id=1,
            source_profile_id=template.profile_id,
            name="Lettuce Active",
            mode=ConditionProfileMode.ACTIVE,
        )
        assert cloned is not None
        assert cloned.profile_id != template.profile_id
        assert cloned.source_profile_id == template.profile_id
        assert cloned.mode == ConditionProfileMode.ACTIVE
        assert cloned.image_url == "static/img/profile-lettuce.png"
