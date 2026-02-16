"""
Feature Engineering Module
===========================
Shared feature engineering utilities for ML models.

Ensures consistency between training and prediction by providing
a single source of truth for feature transformations.

Features include:
- VPD (Vapor Pressure Deficit): Measure of drying power of air
- DIF (Day-Night temperature difference): Affects stem elongation
- Rolling statistics: Moving averages, std dev, trends
- Anomaly detection: Outliers and sudden changes
- Thermal time: Growing degree days accumulation
- Risk indicators: Environmental stress detection

Key Principles:
- All feature engineering must be deterministic
- Same input -> same output (no random transformations)
- Version all feature engineering changes
- Document all feature definitions

Author: SYSGrow Team
Date: December 2025
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any

# ML libraries lazy loaded in methods for faster startup
# import pandas as pd
# import numpy as np

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.domain.plant_profile import PlantProfile
    from app.domain.unit_runtime import UnitSettings


@dataclass
class FeatureSet:
    """
    Definition of a feature set with metadata.

    Attributes:
        name: Feature set name (e.g., 'disease_prediction_v1')
        version: Feature set version
        features: List of feature names
        description: What these features represent
    """

    name: str
    version: str
    features: list[str]
    description: str


class FeatureEngineer:
    """
    Feature engineering utilities for ML models.

    Provides consistent feature transformations for:
    - Disease prediction
    - Climate optimization
    - Plant health monitoring
    """

    # Feature set versions for different models
    DISEASE_FEATURES_V1 = [
        "temp_current",
        "temp_mean_24h",
        "temp_std_24h",
        "temp_min_24h",
        "temp_max_24h",
        "humidity_current",
        "humidity_mean_24h",
        "humidity_std_24h",
        "humidity_max_24h",
        "soil_moisture_current",
        "soil_moisture_mean_24h",
        "soil_moisture_std_24h",
        "temp_humidity_interaction",
        "vapor_pressure_deficit",
        "growth_stage_vegetative",
        "growth_stage_flowering",
        "growth_stage_fruiting",
        "hour_of_day_sin",
        "hour_of_day_cos",
        "day_of_week_sin",
        "day_of_week_cos",
    ]

    CLIMATE_FEATURES_V1 = [
        "temp_mean_24h",
        "temp_std_24h",
        "humidity_mean_24h",
        "humidity_std_24h",
        "soil_moisture_mean_24h",
        "light_hours_24h",
        "growth_stage_vegetative",
        "growth_stage_flowering",
        "growth_stage_fruiting",
        "plant_age_days",
        "season_spring",
        "season_summer",
        "season_fall",
        "season_winter",
    ]

    # Irrigation features for ML prediction
    IRRIGATION_FEATURES_V1 = [
        # Current conditions
        "soil_moisture_current",
        "soil_moisture_threshold_ratio",  # current / threshold
        "temperature_current",
        "humidity_current",
        "vpd_current",
        # Historical
        "hours_since_last_irrigation",
        "moisture_depletion_rate_per_hour",
        "avg_irrigation_duration",
        # Temporal
        "hour_of_day_sin",
        "hour_of_day_cos",
        "day_of_week_sin",
        "day_of_week_cos",
        "is_weekend",
        # User behavior
        "user_approval_rate",
        "user_avg_response_time_minutes",
        "user_delay_frequency",
        "user_cancel_frequency",
        # Plant context
        "plant_stage_vegetative",
        "plant_stage_flowering",
        "plant_stage_fruiting",
        "plant_age_days",
    ]

    IRRIGATION_FEATURES_V2 = [
        # Current conditions
        "soil_moisture_current",
        "soil_moisture_threshold_ratio",
        "soil_moisture_threshold",
        "soil_moisture_to_threshold",
        "temperature_current",
        "humidity_current",
        "vpd_current",
        "lux_current",
        # Eligibility context
        "manual_mode",
        "cooldown_active",
        "pending_request",
        "stale_reading_minutes",
        # Historical execution
        "hours_since_last_irrigation",
        "execution_success_rate",
        "avg_actual_duration_s",
        "avg_planned_duration_s",
        "avg_estimated_volume_ml",
        "avg_delta_moisture",
        "avg_post_delay_s",
        "last_post_moisture",
        "last_delta_moisture",
        "trigger_gap_last",
        "trigger_gap_mean",
        # Temporal
        "hour_of_day_sin",
        "hour_of_day_cos",
        "day_of_week_sin",
        "day_of_week_cos",
        "is_weekend",
        # User behavior
        "user_approval_rate",
        "user_avg_response_time_minutes",
        "user_delay_frequency",
        "user_cancel_frequency",
        "user_auto_execution_rate",
        "feedback_too_much_rate",
        "feedback_too_little_rate",
        "feedback_just_right_rate",
        # Plant context
        "plant_stage_vegetative",
        "plant_stage_flowering",
        "plant_stage_fruiting",
        "plant_age_days",
        "drydown_rate_per_hour",
        "drydown_confidence",
    ]

    # Canonical per-model feature lists (single source of truth)
    IRRIGATION_MODEL_FEATURES = {
        "threshold_optimizer": [
            "temperature_at_detection",
            "humidity_at_detection",
            "soil_moisture_detected",
            "hours_since_last_irrigation",
            "plant_stage_vegetative",
            "plant_stage_flowering",
            "plant_stage_fruiting",
            "user_consistency_score",
            "current_threshold",
        ],
        "response_predictor": [
            "hour_of_day",
            "day_of_week",
            "is_weekend",
            "soil_moisture_detected",
            "temperature_at_detection",
            "humidity_at_detection",
            "hours_since_last_irrigation",
        ],
        "duration_optimizer": [
            "soil_moisture_detected",
            "target_moisture",
            "temperature_at_detection",
            "humidity_at_detection",
            "avg_previous_duration",
        ],
        "timing_predictor": [
            "hour_of_day",
            "day_of_week",
            "is_weekend",
            "soil_moisture_detected",
            "temperature_at_detection",
            "humidity_at_detection",
            "hours_since_last_irrigation",
        ],
    }

    # Plant health features for ML-driven health scoring
    # Used by PlantHealthScorer for ensemble prediction (regressor + classifier)
    PLANT_HEALTH_FEATURES_V1 = [
        # Current plant metrics
        "soil_moisture_current",
        "ph_current",
        "ec_current",
        # Current environmental metrics
        "temperature_current",
        "humidity_current",
        "vpd_current",
        # 24-hour statistics (from rolling window)
        "soil_moisture_mean_24h",
        "soil_moisture_std_24h",
        "temperature_mean_24h",
        "temperature_std_24h",
        "humidity_mean_24h",
        "humidity_std_24h",
        # Derived features - deviation from optimal
        "soil_moisture_deviation",
        "temperature_deviation",
        "humidity_deviation",
        "vpd_deviation",
        "ph_deviation",
        "ec_deviation",
        # Stress indicators
        "hours_below_moisture_threshold",
        "hours_above_temp_threshold",
        "consecutive_stress_hours",
        # Plant context
        "growth_stage_encoded",
        "days_in_stage",
        "plant_age_days",
        # Temporal (cyclical)
        "hour_of_day_sin",
        "hour_of_day_cos",
        "season_encoded",
    ]

    @staticmethod
    def create_disease_features(
        sensor_data,
        growth_stage: str,
        current_time: datetime | None = None,
    ):
        """
        Create features for disease prediction.

        Args:
            sensor_data: DataFrame with columns [timestamp, temperature, humidity, soil_moisture]
            growth_stage: Current growth stage ('Vegetative', 'Flowering', 'Fruiting')
            current_time: Current timestamp (defaults to now)

        Returns:
            DataFrame with engineered features
        """
        import numpy as np  # Lazy load
        import pandas as pd  # Lazy load

        if current_time is None:
            current_time = datetime.now()

        features = {}

        # Current values
        if not sensor_data.empty:
            latest = sensor_data.iloc[-1]
            features["temp_current"] = latest.get("temperature", 20.0)
            features["humidity_current"] = latest.get("humidity", 50.0)
            features["soil_moisture_current"] = latest.get("soil_moisture", 60.0)

            # 24-hour statistics
            features["temp_mean_24h"] = sensor_data["temperature"].mean()
            features["temp_std_24h"] = sensor_data["temperature"].std()
            features["temp_min_24h"] = sensor_data["temperature"].min()
            features["temp_max_24h"] = sensor_data["temperature"].max()

            features["humidity_mean_24h"] = sensor_data["humidity"].mean()
            features["humidity_std_24h"] = sensor_data["humidity"].std()
            features["humidity_max_24h"] = sensor_data["humidity"].max()

            features["soil_moisture_mean_24h"] = sensor_data["soil_moisture"].mean()
            features["soil_moisture_std_24h"] = sensor_data["soil_moisture"].std()

            # Interaction features
            features["temp_humidity_interaction"] = features["temp_mean_24h"] * features["humidity_mean_24h"]

            # Vapor Pressure Deficit (VPD) - important for disease risk
            from app.utils.psychrometrics import calculate_vpd_kpa

            vpd = calculate_vpd_kpa(features["temp_mean_24h"], features["humidity_mean_24h"])
            features["vapor_pressure_deficit"] = float(vpd) if vpd is not None else 1.0

        else:
            # Default values if no sensor data
            features["temp_current"] = 20.0
            features["humidity_current"] = 50.0
            features["soil_moisture_current"] = 60.0
            features["temp_mean_24h"] = 20.0
            features["temp_std_24h"] = 2.0
            features["temp_min_24h"] = 18.0
            features["temp_max_24h"] = 22.0
            features["humidity_mean_24h"] = 50.0
            features["humidity_std_24h"] = 10.0
            features["humidity_max_24h"] = 60.0
            features["soil_moisture_mean_24h"] = 60.0
            features["soil_moisture_std_24h"] = 5.0
            features["temp_humidity_interaction"] = 1000.0
            features["vapor_pressure_deficit"] = 1.0

        # Growth stage one-hot encoding
        features["growth_stage_vegetative"] = 1 if growth_stage == "Vegetative" else 0
        features["growth_stage_flowering"] = 1 if growth_stage == "Flowering" else 0
        features["growth_stage_fruiting"] = 1 if growth_stage == "Fruiting" else 0

        # Temporal features (cyclical encoding)
        hour = current_time.hour
        features["hour_of_day_sin"] = np.sin(2 * np.pi * hour / 24)
        features["hour_of_day_cos"] = np.cos(2 * np.pi * hour / 24)

        day_of_week = current_time.weekday()
        features["day_of_week_sin"] = np.sin(2 * np.pi * day_of_week / 7)
        features["day_of_week_cos"] = np.cos(2 * np.pi * day_of_week / 7)

        # Return as DataFrame with single row
        return pd.DataFrame([features])

    @staticmethod
    def create_climate_features(
        sensor_data,
        growth_stage: str,
        plant_age_days: int,
        current_time: datetime | None = None,
        *,
        light_schedule: dict[str, Any] | None = None,
        lux_threshold: float = 100.0,
    ):
        """
        Create features for climate optimization.

        Args:
            sensor_data: DataFrame with sensor readings
            growth_stage: Current growth stage
            plant_age_days: Age of plant in days
            current_time: Current timestamp

        Returns:
            DataFrame with engineered features
        """
        import pandas as pd  # Lazy load

        if current_time is None:
            current_time = datetime.now()

        features = {}

        # 24-hour statistics
        if not sensor_data.empty:
            features["temp_mean_24h"] = sensor_data["temperature"].mean()
            features["temp_std_24h"] = sensor_data["temperature"].std()
            features["humidity_mean_24h"] = sensor_data["humidity"].mean()
            features["humidity_std_24h"] = sensor_data["humidity"].std()
            features["soil_moisture_mean_24h"] = sensor_data["soil_moisture"].mean()

            # Light hours (prefer schedule if provided; otherwise infer from lux readings).
            light_start = None
            light_end = None
            light_enabled = True
            if light_schedule:
                if isinstance(light_schedule, dict):
                    light_start = light_schedule.get("start_time")
                    light_end = light_schedule.get("end_time")
                    light_enabled = bool(light_schedule.get("enabled", True))
                else:
                    light_start = getattr(light_schedule, "start_time", None)
                    light_end = getattr(light_schedule, "end_time", None)
                    light_enabled = bool(getattr(light_schedule, "enabled", True))

            if light_enabled and light_start and light_end:
                from app.domain.photoperiod import Photoperiod

                features["light_hours_24h"] = Photoperiod(
                    schedule_day_start=str(light_start),
                    schedule_day_end=str(light_end),
                ).schedule_duration_hours()
            elif "lux" in sensor_data.columns:
                import numpy as np  # Lazy load

                interval_hours = 1.0
                if isinstance(sensor_data.index, pd.DatetimeIndex) and len(sensor_data) > 1:
                    deltas = sensor_data.index.to_series().diff().dt.total_seconds() / 3600.0
                    interval_hours = float(deltas.dropna().median() or 1.0)

                light_values = sensor_data["lux"].fillna(0.0)
                is_day = light_values >= float(lux_threshold)
                features["light_hours_24h"] = float(np.sum(is_day) * interval_hours)
            else:
                features["light_hours_24h"] = 16.0  # Default

        else:
            # Default values
            features["temp_mean_24h"] = 22.0
            features["temp_std_24h"] = 2.0
            features["humidity_mean_24h"] = 60.0
            features["humidity_std_24h"] = 10.0
            features["soil_moisture_mean_24h"] = 65.0
            features["light_hours_24h"] = 16.0

        # Growth stage encoding
        features["growth_stage_vegetative"] = 1 if growth_stage == "Vegetative" else 0
        features["growth_stage_flowering"] = 1 if growth_stage == "Flowering" else 0
        features["growth_stage_fruiting"] = 1 if growth_stage == "Fruiting" else 0

        # Plant age
        features["plant_age_days"] = plant_age_days

        # Season encoding (northern hemisphere)
        month = current_time.month
        features["season_spring"] = 1 if month in [3, 4, 5] else 0
        features["season_summer"] = 1 if month in [6, 7, 8] else 0
        features["season_fall"] = 1 if month in [9, 10, 11] else 0
        features["season_winter"] = 1 if month in [12, 1, 2] else 0

        return pd.DataFrame([features])

    @staticmethod
    def create_irrigation_features(
        current_conditions: dict[str, float],
        irrigation_history: list[dict[str, Any]],
        user_preferences: dict[str, Any],
        plant_info: dict[str, Any],
        current_time: datetime | None = None,
    ):
        """
        Create features for irrigation prediction models.

        Args:
            current_conditions: Dict with soil_moisture, temperature, humidity, vpd, threshold
            irrigation_history: List of recent irrigation events with timestamps
            user_preferences: Dict with approval_rate, avg_response_time, etc.
            plant_info: Dict with growth_stage, plant_age_days
            current_time: Current timestamp (defaults to now)

        Returns:
            DataFrame with engineered features
        """
        import numpy as np  # Lazy load
        import pandas as pd  # Lazy load

        from app.utils.time import coerce_datetime, utc_now

        if current_time is None:
            current_time = utc_now()
        else:
            current_time = coerce_datetime(current_time) or utc_now()

        features = {}

        # Current conditions
        soil_moisture = current_conditions.get("soil_moisture", 50.0)
        threshold = current_conditions.get(
            "threshold",
            current_conditions.get("soil_moisture_threshold", 50.0),
        )
        features["soil_moisture_current"] = soil_moisture
        features["soil_moisture_threshold_ratio"] = soil_moisture / threshold if threshold > 0 else 1.0
        features["soil_moisture_threshold"] = threshold
        features["soil_moisture_to_threshold"] = (
            float(threshold) - float(soil_moisture) if threshold is not None else 0.0
        )
        features["temperature_current"] = current_conditions.get("temperature", 22.0)
        features["humidity_current"] = current_conditions.get("humidity", 60.0)
        features["vpd_current"] = current_conditions.get("vpd", 1.0)
        features["lux_current"] = current_conditions.get("lux", 0.0)

        features["manual_mode"] = 1 if current_conditions.get("manual_mode") else 0
        features["cooldown_active"] = 1 if current_conditions.get("cooldown_active") else 0
        features["pending_request"] = 1 if current_conditions.get("pending_request") else 0
        stale_seconds = current_conditions.get("stale_seconds")
        if stale_seconds is None:
            stale_seconds = current_conditions.get("stale_reading_seconds")
        features["stale_reading_minutes"] = float(stale_seconds) / 60.0 if stale_seconds is not None else 0.0

        # Historical features
        history = irrigation_history or []
        if history:

            def _parse_ts(record: dict[str, Any]) -> datetime | None:
                for key in ("executed_at_utc", "executed_at", "triggered_at_utc", "detected_at", "created_at_utc"):
                    raw = record.get(key)
                    if raw:
                        parsed = coerce_datetime(raw)
                        if parsed:
                            return parsed
                return None

            for record in history:
                record["_ts"] = _parse_ts(record)

            history = sorted(
                history,
                key=lambda r: r.get("_ts") or datetime.min.replace(tzinfo=current_time.tzinfo),
                reverse=True,
            )

            completed = [r for r in history if (r.get("execution_status") in (None, "completed"))]
            if not completed:
                completed = history

            # Hours since last irrigation
            try:
                last_irrigation = completed[0] if completed else history[0]
                last_time = last_irrigation.get("_ts")
                if last_time:
                    delta = current_time - last_time
                    features["hours_since_last_irrigation"] = delta.total_seconds() / 3600
                else:
                    features["hours_since_last_irrigation"] = 48.0  # Default
            except (ValueError, TypeError):
                features["hours_since_last_irrigation"] = 48.0

            # Average irrigation duration
            durations = [
                r.get("actual_duration_s") or r.get("execution_duration_seconds")
                for r in completed
                if r.get("actual_duration_s") or r.get("execution_duration_seconds")
            ]
            features["avg_irrigation_duration"] = sum(durations) / len(durations) if durations else 120.0
            features["avg_actual_duration_s"] = sum(durations) / len(durations) if durations else 0.0

            planned = [r.get("planned_duration_s") for r in completed if r.get("planned_duration_s") is not None]
            features["avg_planned_duration_s"] = sum(planned) / len(planned) if planned else 0.0

            estimated_volumes = [
                r.get("estimated_volume_ml") for r in completed if r.get("estimated_volume_ml") is not None
            ]
            features["avg_estimated_volume_ml"] = (
                sum(estimated_volumes) / len(estimated_volumes) if estimated_volumes else 0.0
            )

            depletion_rates = []
            for record in completed:
                delta = record.get("delta_moisture")
                delay_s = record.get("post_moisture_delay_s")
                if delta is None or delay_s is None:
                    continue
                try:
                    delay_hours = float(delay_s) / 3600.0
                    if delay_hours > 0:
                        depletion_rates.append(abs(float(delta)) / delay_hours)
                except (TypeError, ValueError):
                    continue
            if depletion_rates:
                features["moisture_depletion_rate_per_hour"] = sum(depletion_rates) / len(depletion_rates)
            else:
                fallback_rate = plant_info.get("drydown_rate_per_hour")
                if fallback_rate is not None:
                    features["moisture_depletion_rate_per_hour"] = abs(float(fallback_rate))
                else:
                    features["moisture_depletion_rate_per_hour"] = 0.5

            deltas = [r.get("delta_moisture") for r in completed if r.get("delta_moisture") is not None]
            features["avg_delta_moisture"] = sum(deltas) / len(deltas) if deltas else 0.0

            delays = [r.get("post_moisture_delay_s") for r in completed if r.get("post_moisture_delay_s") is not None]
            features["avg_post_delay_s"] = sum(delays) / len(delays) if delays else 0.0

            last_completed = completed[0] if completed else history[0]
            features["last_post_moisture"] = last_completed.get("post_moisture") or 0.0
            features["last_delta_moisture"] = last_completed.get("delta_moisture") or 0.0

            total = len(history)
            completed_count = len(completed)
            features["execution_success_rate"] = completed_count / total if total > 0 else 0.0

            trigger_gaps = []
            for record in completed:
                trig = record.get("trigger_moisture") or record.get("soil_moisture_detected")
                trig_threshold = record.get("threshold_at_trigger") or record.get("soil_moisture_threshold")
                if trig is None or trig_threshold is None:
                    continue
                try:
                    gap = float(trig_threshold) - float(trig)
                except (TypeError, ValueError):
                    continue
                trigger_gaps.append(gap)
            features["trigger_gap_mean"] = sum(trigger_gaps) / len(trigger_gaps) if trigger_gaps else 0.0
            features["trigger_gap_last"] = trigger_gaps[0] if trigger_gaps else 0.0
        else:
            features["hours_since_last_irrigation"] = 48.0
            features["moisture_depletion_rate_per_hour"] = 0.5
            features["avg_irrigation_duration"] = 120.0
            features["avg_actual_duration_s"] = 0.0
            features["avg_planned_duration_s"] = 0.0
            features["avg_estimated_volume_ml"] = 0.0
            features["avg_delta_moisture"] = 0.0
            features["avg_post_delay_s"] = 0.0
            features["last_post_moisture"] = 0.0
            features["last_delta_moisture"] = 0.0
            features["execution_success_rate"] = 0.0
            features["trigger_gap_mean"] = 0.0
            features["trigger_gap_last"] = 0.0

        # Temporal features (cyclical encoding)
        hour = current_time.hour
        features["hour_of_day_sin"] = np.sin(2 * np.pi * hour / 24)
        features["hour_of_day_cos"] = np.cos(2 * np.pi * hour / 24)

        day_of_week = current_time.weekday()
        features["day_of_week_sin"] = np.sin(2 * np.pi * day_of_week / 7)
        features["day_of_week_cos"] = np.cos(2 * np.pi * day_of_week / 7)
        features["is_weekend"] = 1 if day_of_week >= 5 else 0

        # User behavior features
        total_requests = user_preferences.get("total_requests")
        immediate = user_preferences.get("immediate_approvals", 0)
        delayed = user_preferences.get("delayed_approvals", 0)
        cancellations = user_preferences.get("cancellations", 0)
        auto_exec = user_preferences.get("auto_executions", 0)
        moisture_feedback_count = user_preferences.get("moisture_feedback_count", 0)
        too_much = user_preferences.get("too_much_feedback_count", 0)
        too_little = user_preferences.get("too_little_feedback_count", 0)
        just_right = user_preferences.get("just_right_feedback_count", 0)

        if total_requests:
            features["user_approval_rate"] = (immediate + delayed + auto_exec) / total_requests
            features["user_delay_frequency"] = delayed / total_requests
            features["user_cancel_frequency"] = cancellations / total_requests
            features["user_auto_execution_rate"] = auto_exec / total_requests
        else:
            features["user_approval_rate"] = user_preferences.get("approval_rate", 0.8)
            features["user_delay_frequency"] = user_preferences.get("delay_frequency", 0.1)
            features["user_cancel_frequency"] = user_preferences.get("cancel_frequency", 0.1)
            features["user_auto_execution_rate"] = user_preferences.get("auto_execution_rate", 0.0)

        avg_response_seconds = user_preferences.get("avg_response_time_seconds", 300)
        features["user_avg_response_time_minutes"] = float(avg_response_seconds) / 60.0

        if moisture_feedback_count:
            features["feedback_too_much_rate"] = too_much / moisture_feedback_count
            features["feedback_too_little_rate"] = too_little / moisture_feedback_count
            features["feedback_just_right_rate"] = just_right / moisture_feedback_count
        else:
            features["feedback_too_much_rate"] = 0.0
            features["feedback_too_little_rate"] = 0.0
            features["feedback_just_right_rate"] = 0.0

        # Plant context features
        growth_stage = plant_info.get("growth_stage", "Vegetative")
        features["plant_stage_vegetative"] = 1 if growth_stage == "Vegetative" else 0
        features["plant_stage_flowering"] = 1 if growth_stage == "Flowering" else 0
        features["plant_stage_fruiting"] = 1 if growth_stage == "Fruiting" else 0
        features["plant_age_days"] = plant_info.get("plant_age_days", 30)
        features["drydown_rate_per_hour"] = plant_info.get("drydown_rate_per_hour", 0.0)
        features["drydown_confidence"] = plant_info.get("drydown_confidence", 0.0)

        return pd.DataFrame([features])

    @staticmethod
    def validate_features(features, expected_features: list[str]) -> bool:
        """
        Validate that all expected features are present.

        Args:
            features: DataFrame with features
            expected_features: List of expected feature names

        Returns:
            True if all features present, False otherwise
        """
        feature_cols = set(features.columns)
        expected_cols = set(expected_features)

        missing = expected_cols - feature_cols
        if missing:
            logger.error(f"Missing features: {missing}")
            return False

        extra = feature_cols - expected_cols
        if extra:
            logger.warning(f"Extra features (will be ignored): {extra}")

        return True

    @staticmethod
    def get_feature_set(name: str, version: str = "v1") -> FeatureSet:
        """
        Get feature set definition.

        Args:
            name: Feature set name ('disease', 'climate')
            version: Version of feature set

        Returns:
            FeatureSet with metadata
        """
        if name == "disease" and version == "v1":
            return FeatureSet(
                name="disease_prediction",
                version="v1",
                features=FeatureEngineer.DISEASE_FEATURES_V1,
                description="Features for disease risk prediction including temporal and environmental factors",
            )

        elif name == "climate" and version == "v1":
            return FeatureSet(
                name="climate_optimization",
                version="v1",
                features=FeatureEngineer.CLIMATE_FEATURES_V1,
                description="Features for optimal climate condition prediction",
            )

        elif name == "irrigation" and version == "v1":
            return FeatureSet(
                name="irrigation_prediction",
                version="v1",
                features=FeatureEngineer.IRRIGATION_FEATURES_V1,
                description="Features for irrigation optimization including user behavior and temporal patterns",
            )
        elif name == "irrigation" and version == "v2":
            return FeatureSet(
                name="irrigation_prediction",
                version="v2",
                features=FeatureEngineer.IRRIGATION_FEATURES_V2,
                description="Features aligned to irrigation telemetry (execution logs, eligibility context, drydown model)",
            )

        else:
            raise ValueError(f"Unknown feature set: {name} version {version}")

    @staticmethod
    def get_irrigation_model_features(model_name: str) -> list[str]:
        """
        Get canonical feature list for an irrigation ML model.

        Args:
            model_name: One of threshold_optimizer, response_predictor,
                duration_optimizer, timing_predictor

        Returns:
            List of feature names
        """
        features = FeatureEngineer.IRRIGATION_MODEL_FEATURES.get(model_name)
        if not features:
            raise ValueError(f"Unknown irrigation model: {model_name}")
        return list(features)

    @staticmethod
    def align_features(features, expected_features: list[str]):
        """
        Ensure features match expected order and fill missing values.

        Args:
            features: DataFrame with features
            expected_features: List of expected feature names in order

        Returns:
            DataFrame with features in correct order
        """
        # Add missing features with default value 0
        for feature in expected_features:
            if feature not in features.columns:
                logger.warning(f"Missing feature {feature}, filling with 0")
                features[feature] = 0.0

        # Select only expected features in correct order
        return features[expected_features]


class EnvironmentalFeatureExtractor:
    """
    Advanced environmental feature extractor for sophisticated ML models.

    Extracts domain-specific agricultural features including:
    - VPD (Vapor Pressure Deficit): Critical for disease prediction
    - DIF (Day-Night temperature difference): Affects stem elongation
    - Rolling statistics: Temporal patterns and trends
    - Anomaly detection: Unusual environmental conditions
    - Thermal time (GDD): Plant development tracking
    - Risk indicators: Environmental stress detection
    """

    def __init__(self):
        """Initialize feature extractor with caching."""
        self.features_cache = {}

    def extract_all_features(
        self,
        sensor_df,
        plant_type: str | None = None,
        *,
        plant_profile: "PlantProfile" | None = None,
        unit_settings: "UnitSettings" | None = None,
        lux_threshold: float = 100.0,
        prefer_lux: bool = False,
    ) -> dict[str, float]:
        """
        Extract comprehensive environmental features from sensor data.

        Args:
            sensor_df: DataFrame with timestamp index and sensor columns
                      (temperature, humidity, soil_moisture, etc.)
            plant_type: Optional plant type for plant-specific features

        Returns:
            Dictionary of extracted features with descriptive names
        """
        import pandas as pd  # Lazy load

        features = {}

        if sensor_df.empty:
            logger.warning("Empty sensor data, returning default features")
            return self._get_default_features()

        try:
            schedule_start = "06:00"
            schedule_end = "18:00"
            schedule_enabled = False
            light_schedule = None
            if unit_settings and hasattr(unit_settings, "get_device_schedule_object"):
                light_schedule = unit_settings.get_device_schedule_object("light")

            if light_schedule:
                schedule_start = str(getattr(light_schedule, "start_time", schedule_start) or schedule_start)
                schedule_end = str(getattr(light_schedule, "end_time", schedule_end) or schedule_end)
                schedule_enabled = bool(getattr(light_schedule, "enabled", True))

            from app.domain.sensors.fields import SensorField

            lux_series = None
            # Prioritize standard 'lux' field, then common aliases
            for candidate in (SensorField.LUX.value, "light_lux", "illuminance", "light"):
                if candidate in sensor_df.columns:
                    lux_series = sensor_df[candidate]
                    break

            lux_values = None
            if lux_series is not None:
                lux_values = [None if pd.isna(value) else float(value) for value in lux_series.tolist()]

            # Basic statistics
            if "temperature" in sensor_df.columns:
                features["temp_mean"] = sensor_df["temperature"].mean()
                features["temp_std"] = sensor_df["temperature"].std()
                features["temp_min"] = sensor_df["temperature"].min()
                features["temp_max"] = sensor_df["temperature"].max()
                features["temp_range"] = features["temp_max"] - features["temp_min"]

            if "humidity" in sensor_df.columns:
                features["humidity_mean"] = sensor_df["humidity"].mean()
                features["humidity_std"] = sensor_df["humidity"].std()
                features["humidity_min"] = sensor_df["humidity"].min()
                features["humidity_max"] = sensor_df["humidity"].max()

            # VPD calculation (critical for disease risk)
            if "temperature" in sensor_df.columns and "humidity" in sensor_df.columns:
                vpd_series = self.calculate_vpd(sensor_df["temperature"], sensor_df["humidity"])
                features["vpd_mean"] = vpd_series.mean()
                features["vpd_std"] = vpd_series.std()
                features["vpd_max"] = vpd_series.max()
                features["vpd_stress_hours"] = (vpd_series > 1.5).sum()  # Hours above stress threshold

            # DIF calculation (affects plant morphology)
            if "temperature" in sensor_df.columns:
                from app.utils.psychrometrics import calculate_dif_c

                dif = calculate_dif_c(
                    sensor_df["temperature"],
                    day_start=schedule_start,
                    day_end=schedule_end,
                    lux_values=lux_values,
                    lux_threshold=lux_threshold,
                    prefer_sensor=prefer_lux,
                    schedule_enabled=schedule_enabled,
                )
                features["dif"] = dif
                features["dif_category"] = self._categorize_dif(dif)

            # Rolling window features (temporal patterns)
            rolling_features = self.extract_rolling_features(sensor_df)
            features.update(rolling_features)

            # Trend detection
            if "temperature" in sensor_df.columns:
                temp_trend = self.detect_trend(sensor_df["temperature"])
                features["temp_trend"] = temp_trend

            if "humidity" in sensor_df.columns:
                humidity_trend = self.detect_trend(sensor_df["humidity"])
                features["humidity_trend"] = humidity_trend

            # Anomaly detection
            anomalies = self.detect_anomalies(sensor_df)
            features["anomaly_count"] = len(anomalies)
            features["has_anomalies"] = 1.0 if len(anomalies) > 0 else 0.0

            # Thermal time (growing degree days)
            if "temperature" in sensor_df.columns:
                from app.domain.agronomics import calculate_gdd_degree_days, infer_gdd_base_temp_c

                base_temp_c = None
                if plant_profile is not None:
                    explicit_base = getattr(plant_profile, "gdd_base_temp_c", None)
                    if explicit_base is not None:
                        try:
                            base_temp_c = float(explicit_base)
                        except (TypeError, ValueError):
                            base_temp_c = None

                    growth_stages = getattr(plant_profile, "growth_stages", None) or []
                    stage_name = getattr(plant_profile, "current_stage", None) or ""
                    if base_temp_c is None:
                        base_temp_c = infer_gdd_base_temp_c(growth_stages, stage_name=str(stage_name), default=10.0)
                elif plant_type:
                    base_temp_c = float(self._legacy_gdd_base_temp_c(plant_type))

                if base_temp_c is not None:
                    features["growing_degree_days"] = calculate_gdd_degree_days(
                        sensor_df["temperature"],
                        base_temp_c=float(base_temp_c),
                    )
                    features["gdd_base_temp_c"] = float(base_temp_c)

            # Photoperiod / light hours (schedule, sensor, and correlation)
            stage_light_hours = None
            if plant_profile is not None:
                stage_lighting = getattr(plant_profile, "stage_lighting_hours", None) or {}
                stage_light_hours = stage_lighting.get(getattr(plant_profile, "current_stage", None))

            from app.domain.photoperiod import Photoperiod

            photoperiod = Photoperiod(
                schedule_day_start=schedule_start,
                schedule_day_end=schedule_end,
                schedule_enabled=schedule_enabled,
                sensor_threshold=float(lux_threshold),
                greenhouse_outside=bool(prefer_lux),
                sensor_enabled=lux_values is not None,
            )

            if lux_values is not None and isinstance(sensor_df.index, pd.DatetimeIndex):
                alignment = photoperiod.analyze_alignment(list(sensor_df.index), lux_values)
                schedule_hours = alignment.get("schedule_light_hours")
                sensor_hours = alignment.get("sensor_light_hours")

                if schedule_enabled and not prefer_lux:
                    features["light_hours_24h"] = float(schedule_hours or photoperiod.schedule_duration_hours())
                else:
                    features["light_hours_24h"] = float(
                        sensor_hours
                        if sensor_hours is not None
                        else (stage_light_hours or photoperiod.schedule_duration_hours())
                    )

                if schedule_hours is not None:
                    features["light_hours_schedule_24h"] = float(schedule_hours)
                if sensor_hours is not None:
                    features["light_hours_sensor_24h"] = float(sensor_hours)

                agreement_rate = alignment.get("agreement_rate")
                if agreement_rate is not None:
                    features["light_schedule_sensor_agreement"] = float(agreement_rate)

                start_offset = alignment.get("start_offset_minutes")
                if start_offset is not None:
                    features["light_start_offset_minutes"] = float(start_offset)

                end_offset = alignment.get("end_offset_minutes")
                if end_offset is not None:
                    features["light_end_offset_minutes"] = float(end_offset)
            else:
                if stage_light_hours is not None:
                    features["light_hours_24h"] = float(stage_light_hours)
                else:
                    features["light_hours_24h"] = float(photoperiod.schedule_duration_hours())

            # Stability metrics
            if "temperature" in sensor_df.columns:
                features["temp_stability"] = self._calculate_stability(sensor_df["temperature"])

            if "humidity" in sensor_df.columns:
                features["humidity_stability"] = self._calculate_stability(sensor_df["humidity"])

            # Risk indicators
            risk_indicators = self.calculate_risk_indicators(sensor_df)
            features.update(risk_indicators)

            return features

        except Exception as e:
            logger.error(f"Error extracting features: {e}", exc_info=True)
            return self._get_default_features()

    def calculate_vpd(self, temperature, relative_humidity):
        """
        Calculate Vapor Pressure Deficit (VPD) in kPa.

        VPD = SVP * (1 - RH/100)
        where SVP = Saturation Vapor Pressure (Magnus formula)

        VPD Categories (kPa):
        - < 0.4: Too low (mold/disease risk)
        - 0.4-0.8: Optimal for vegetative growth
        - 0.8-1.2: Optimal for flowering/fruiting
        - 1.2-1.6: Late flowering
        - > 1.6: Too high (stress, reduced transpiration)

        Args:
            temperature: Temperature in Celsius
            relative_humidity: Relative humidity (0-100)

        Returns:
            VPD in kPa
        """
        from app.utils.psychrometrics import calculate_vpd_kpa

        return calculate_vpd_kpa(temperature, relative_humidity)

    def calculate_dif(self, temperature, day_start_hour: int = 6, day_end_hour: int = 18) -> float:
        """
        Calculate DIF (Day-Night temperature difference).

        DIF = Average Day Temp - Average Night Temp

        Effects on plants:
        - Positive DIF (day warmer): Normal growth, more stem elongation
        - Negative DIF (night warmer): Reduces stem elongation, compact growth
        - Zero DIF: Constant temperature, moderate growth

        Args:
            temperature: Temperature series with datetime index
            day_start_hour: Hour when "day" starts (default 6am)
            day_end_hour: Hour when "day" ends (default 6pm)

        Returns:
            DIF value in degrees Celsius
        """
        from app.utils.psychrometrics import calculate_dif_c

        try:
            day_start = f"{int(day_start_hour):02d}:00"
            day_end = f"{int(day_end_hour):02d}:00"
        except Exception:
            day_start = "06:00"
            day_end = "18:00"

        return calculate_dif_c(temperature, day_start=day_start, day_end=day_end)

    @staticmethod
    def _legacy_gdd_base_temp_c(plant_type: str, default: float = 10.0) -> float:
        base_temps = {
            "tomato": 10.0,
            "tomatoes": 10.0,
            "lettuce": 4.0,
            "pepper": 15.0,
            "peppers": 15.0,
            "cucumber": 12.0,
            "cucumbers": 12.0,
            "basil": 10.0,
            "spinach": 4.0,
        }

        if not plant_type:
            return float(default)

        return float(base_temps.get(str(plant_type).lower(), default))

    def extract_rolling_features(self, sensor_df, windows: list[str] | None = None) -> dict[str, float]:
        """
        Extract rolling window statistics for temporal patterns.

        Args:
            sensor_df: Sensor data with datetime index
            windows: List of window sizes (e.g., ['6H', '24H', '7D'])

        Returns:
            Dictionary of rolling statistics
        """
        if windows is None:
            windows = ["6H", "24H"]

        features = {}

        try:
            for window in windows:
                window_label = window.replace("H", "h").replace("D", "d")

                if "temperature" in sensor_df.columns:
                    rolling = sensor_df["temperature"].rolling(window=window, min_periods=1)
                    features[f"temp_rolling_mean_{window_label}"] = rolling.mean().iloc[-1]
                    features[f"temp_rolling_std_{window_label}"] = rolling.std().iloc[-1]

                if "humidity" in sensor_df.columns:
                    rolling = sensor_df["humidity"].rolling(window=window, min_periods=1)
                    features[f"humidity_rolling_mean_{window_label}"] = rolling.mean().iloc[-1]
                    features[f"humidity_rolling_std_{window_label}"] = rolling.std().iloc[-1]

                if "soil_moisture" in sensor_df.columns:
                    rolling = sensor_df["soil_moisture"].rolling(window=window, min_periods=1)
                    features[f"moisture_rolling_mean_{window_label}"] = rolling.mean().iloc[-1]

            return features

        except Exception as e:
            logger.warning(f"Error extracting rolling features: {e}")
            return {}

    def detect_trend(self, series, window: int = 24) -> float:
        """
        Detect trend in time series using linear regression.

        Args:
            series: Time series data
            window: Number of periods to analyze

        Returns:
            Trend slope (positive = increasing, negative = decreasing, 0 = stable)
        """
        import numpy as np  # Lazy load

        try:
            if len(series) < window:
                window = len(series)

            recent = series.tail(window)
            x = np.arange(len(recent))
            y = recent.values

            # Linear regression: y = mx + b
            if len(x) > 1:
                slope, _ = np.polyfit(x, y, 1)
                return float(slope)
            else:
                return 0.0

        except Exception as e:
            logger.warning(f"Error detecting trend: {e}")
            return 0.0

    def detect_anomalies(self, sensor_df, std_threshold: float = 3.0) -> list[dict[str, Any]]:
        """
        Detect anomalies using Z-score method.

        Identifies data points that deviate significantly from the mean,
        which could indicate sensor errors or unusual environmental events.

        Args:
            sensor_df: Sensor data
            std_threshold: Number of standard deviations for anomaly (default 3.0)

        Returns:
            List of anomaly records with timestamps and deviations
        """
        import numpy as np  # Lazy load

        anomalies = []

        try:
            for column in ["temperature", "humidity", "soil_moisture"]:
                if column not in sensor_df.columns:
                    continue

                series = sensor_df[column]
                mean = series.mean()
                std = series.std()

                if std == 0:
                    continue

                # Calculate z-scores
                z_scores = np.abs((series - mean) / std)
                anomaly_mask = z_scores > std_threshold

                if anomaly_mask.any():
                    anomaly_indices = sensor_df[anomaly_mask].index
                    for idx in anomaly_indices:
                        anomalies.append(
                            {
                                "timestamp": idx,
                                "sensor": column,
                                "value": series[idx],
                                "z_score": float(z_scores[idx]),
                                "deviation": float(series[idx] - mean),
                            }
                        )

            return anomalies

        except Exception as e:
            logger.warning(f"Error detecting anomalies: {e}")
            return []

    def calculate_growing_degree_days(self, temperature, plant_type: str, base_temp: float | None = None) -> float:
        """
        Calculate Growing Degree Days (GDD) / Thermal Time.

        GDD = Σ (Daily Avg Temp - Base Temp) for temps above base

        Base temperatures by plant type:
        - Tomato: 10°C
        - Lettuce: 4°C
        - Pepper: 15°C
        - Cucumber: 12°C
        - Basil: 10°C
        - Spinach: 4°C

        Args:
            temperature: Temperature series
            plant_type: Plant type (case-insensitive)
            base_temp: Optional base temperature override

        Returns:
            Accumulated GDD in degree-days
        """
        if base_temp is None:
            base_temp = self._legacy_gdd_base_temp_c(plant_type)

        from app.domain.agronomics import calculate_gdd_degree_days

        interval_hours = None
        try:
            import pandas as pd  # Lazy load

            if not (hasattr(temperature, "index") and isinstance(temperature.index, pd.DatetimeIndex)):
                interval_hours = 1.0
        except Exception:
            interval_hours = 1.0

        return calculate_gdd_degree_days(
            temperature,
            base_temp_c=float(base_temp),
            interval_hours=interval_hours,
        )

    def calculate_risk_indicators(
        self,
        sensor_df,
    ) -> dict[str, float]:
        """
        Calculate environmental risk indicators.

        Identifies conditions that increase disease, pest, or stress risk.

        Returns:
            Dictionary with risk indicator features
        """
        risks = {}

        try:
            # High humidity risk (fungal diseases)
            if "humidity" in sensor_df.columns:
                high_humidity_hours = (sensor_df["humidity"] > 85).sum()
                risks["high_humidity_hours"] = float(high_humidity_hours)
                risks["fungal_risk_score"] = min(high_humidity_hours / 24.0, 1.0)

            # Temperature extremes
            if "temperature" in sensor_df.columns:
                cold_stress_hours = (sensor_df["temperature"] < 10).sum()
                heat_stress_hours = (sensor_df["temperature"] > 35).sum()
                risks["cold_stress_hours"] = float(cold_stress_hours)
                risks["heat_stress_hours"] = float(heat_stress_hours)

            # Moisture extremes
            if "soil_moisture" in sensor_df.columns:
                dry_stress_hours = (sensor_df["soil_moisture"] < 30).sum()
                wet_stress_hours = (sensor_df["soil_moisture"] > 90).sum()
                risks["dry_stress_hours"] = float(dry_stress_hours)
                risks["wet_stress_hours"] = float(wet_stress_hours)

            # Combined stress score
            total_stress = sum(
                [
                    risks.get("cold_stress_hours", 0),
                    risks.get("heat_stress_hours", 0),
                    risks.get("dry_stress_hours", 0),
                    risks.get("wet_stress_hours", 0),
                    risks.get("high_humidity_hours", 0),
                ]
            )
            risks["total_stress_score"] = min(total_stress / 48.0, 1.0)

            return risks

        except Exception as e:
            logger.warning(f"Error calculating risk indicators: {e}")
            return {}

    def _calculate_stability(self, series) -> float:
        """
        Calculate stability score (inverse of coefficient of variation).

        Higher score = more stable conditions
        Lower score = more variable conditions
        """
        try:
            mean = series.mean()
            std = series.std()

            if mean == 0:
                return 0.0

            cv = std / mean  # Coefficient of variation
            stability = 1.0 / (1.0 + cv)  # Normalize to 0-1

            return float(stability)

        except Exception as e:
            logger.warning(f"Error calculating stability: {e}")
            return 0.5

    def _categorize_dif(self, dif: float) -> float:
        """
        Categorize DIF into numeric categories.

        Returns:
            -1.0 for negative DIF, 0.0 for zero DIF, 1.0 for positive DIF
        """
        if dif < -1.0:
            return -1.0
        elif dif > 1.0:
            return 1.0
        else:
            return 0.0

    def _get_default_features(self) -> dict[str, float]:
        """Return default feature values when data is unavailable."""
        return {
            "temp_mean": 20.0,
            "temp_std": 2.0,
            "temp_min": 18.0,
            "temp_max": 22.0,
            "temp_range": 4.0,
            "humidity_mean": 60.0,
            "humidity_std": 10.0,
            "vpd_mean": 1.0,
            "vpd_std": 0.2,
            "dif": 2.0,
            "growing_degree_days": 0.0,
            "gdd_base_temp_c": 10.0,
            "light_hours_24h": 16.0,
            "temp_trend": 0.0,
            "humidity_trend": 0.0,
            "anomaly_count": 0.0,
            "has_anomalies": 0.0,
            "temp_stability": 0.8,
            "humidity_stability": 0.7,
        }


class PlantHealthFeatureExtractor:
    """
    Feature extractor for plant health ML models.

    Extracts features from plant metrics, environmental data, and historical
    readings for use in PlantHealthScorer's ML-driven prediction system.

    Features are aligned with PLANT_HEALTH_FEATURES_V1 for consistency
    between training and prediction.
    """

    # Growth stage encoding (ordinal)
    GROWTH_STAGE_ENCODING = {
        "germination": 0,
        "seedling": 1,
        "vegetative": 2,
        "flowering": 3,
        "fruiting": 4,
        "harvest": 5,
    }

    # Season encoding (ordinal based on northern hemisphere growing)
    SEASON_ENCODING = {
        "spring": 0,
        "summer": 1,
        "fall": 2,
        "autumn": 2,
        "winter": 3,
    }

    def __init__(self):
        """Initialize feature extractor."""
        pass

    def extract_features(
        self,
        plant_metrics: dict[str, float],
        env_metrics: dict[str, float],
        historical_data: Any | None = None,
        plant_profile: Any | None = None,
        thresholds: dict[str, Any] | None = None,
    ) -> dict[str, float]:
        """
        Extract features for a single prediction.

        Args:
            plant_metrics: Dict with soil_moisture, ph, ec from plant sensors
            env_metrics: Dict with temperature, humidity, vpd from environment
            historical_data: Optional DataFrame with 24h sensor history
            plant_profile: Optional plant profile with growth stage info
            thresholds: Optional dict with optimal thresholds for deviation calc

        Returns:
            Dictionary of feature values aligned with PLANT_HEALTH_FEATURES_V1
        """

        features = {}

        # Current plant metrics
        features["soil_moisture_current"] = plant_metrics.get("soil_moisture", 60.0)
        features["ph_current"] = plant_metrics.get("ph", 6.5)
        features["ec_current"] = plant_metrics.get("ec", 1.5)

        # Current environmental metrics
        features["temperature_current"] = env_metrics.get("temperature", 22.0)
        features["humidity_current"] = env_metrics.get("humidity", 60.0)
        features["vpd_current"] = env_metrics.get("vpd", 1.0)

        # 24-hour statistics
        if historical_data is not None and not historical_data.empty:
            features.update(self._extract_24h_statistics(historical_data))
        else:
            # Defaults based on current values
            features["soil_moisture_mean_24h"] = features["soil_moisture_current"]
            features["soil_moisture_std_24h"] = 5.0
            features["temperature_mean_24h"] = features["temperature_current"]
            features["temperature_std_24h"] = 2.0
            features["humidity_mean_24h"] = features["humidity_current"]
            features["humidity_std_24h"] = 5.0

        # Deviation features (|current - optimal|)
        features.update(self._calculate_deviations(plant_metrics, env_metrics, thresholds))

        # Stress indicators
        if historical_data is not None and not historical_data.empty:
            features.update(self._calculate_stress_indicators(historical_data, thresholds))
        else:
            features["hours_below_moisture_threshold"] = 0.0
            features["hours_above_temp_threshold"] = 0.0
            features["consecutive_stress_hours"] = 0.0

        # Plant context
        features.update(self._extract_plant_context(plant_profile))

        # Temporal features
        features.update(self._extract_temporal_features())

        return features

    def extract_training_features(
        self,
        training_samples: list[dict[str, Any]],
    ) -> Any:
        """
        Extract features for training dataset.

        Args:
            training_samples: List of training sample dicts with:
                - plant_metrics: Dict with soil_moisture, ph, ec
                - env_metrics: Dict with temperature, humidity, vpd
                - historical_data: Optional 24h history
                - plant_profile: Plant info
                - thresholds: Optimal thresholds
                - observation_date: When observation was made

        Returns:
            DataFrame with features for all samples
        """
        import pandas as pd  # Lazy load

        all_features = []

        for sample in training_samples:
            plant_metrics = sample.get("plant_metrics", {})
            env_metrics = sample.get("env_metrics", {})
            historical_data = sample.get("historical_data")
            plant_profile = sample.get("plant_profile")
            thresholds = sample.get("thresholds")
            observation_date = sample.get("observation_date")

            # Convert historical_data to DataFrame if it's a list
            if historical_data and isinstance(historical_data, list):
                historical_data = pd.DataFrame(historical_data)
                if "timestamp" in historical_data.columns:
                    historical_data["timestamp"] = pd.to_datetime(historical_data["timestamp"])
                    historical_data = historical_data.set_index("timestamp")

            # Extract features for this sample
            features = self.extract_features(
                plant_metrics=plant_metrics,
                env_metrics=env_metrics,
                historical_data=historical_data,
                plant_profile=plant_profile,
                thresholds=thresholds,
            )

            # Override temporal features with observation date if provided
            if observation_date:
                features.update(self._extract_temporal_features(observation_date))

            all_features.append(features)

        # Convert to DataFrame, aligned to PLANT_HEALTH_FEATURES_V1
        df = pd.DataFrame(all_features)

        # Ensure all expected columns exist
        for feature in FeatureEngineer.PLANT_HEALTH_FEATURES_V1:
            if feature not in df.columns:
                logger.warning(f"Missing feature {feature}, filling with 0")
                df[feature] = 0.0

        # Select only expected features in correct order
        return df[FeatureEngineer.PLANT_HEALTH_FEATURES_V1]

    def _extract_24h_statistics(
        self,
        historical_data: Any,
    ) -> dict[str, float]:
        """Extract 24-hour rolling statistics from historical data."""
        stats = {}

        try:
            if "soil_moisture" in historical_data.columns:
                stats["soil_moisture_mean_24h"] = historical_data["soil_moisture"].mean()
                stats["soil_moisture_std_24h"] = historical_data["soil_moisture"].std()
            else:
                stats["soil_moisture_mean_24h"] = 60.0
                stats["soil_moisture_std_24h"] = 5.0

            if "temperature" in historical_data.columns:
                stats["temperature_mean_24h"] = historical_data["temperature"].mean()
                stats["temperature_std_24h"] = historical_data["temperature"].std()
            else:
                stats["temperature_mean_24h"] = 22.0
                stats["temperature_std_24h"] = 2.0

            if "humidity" in historical_data.columns:
                stats["humidity_mean_24h"] = historical_data["humidity"].mean()
                stats["humidity_std_24h"] = historical_data["humidity"].std()
            else:
                stats["humidity_mean_24h"] = 60.0
                stats["humidity_std_24h"] = 5.0

        except Exception as e:
            logger.warning(f"Error extracting 24h statistics: {e}")
            stats = {
                "soil_moisture_mean_24h": 60.0,
                "soil_moisture_std_24h": 5.0,
                "temperature_mean_24h": 22.0,
                "temperature_std_24h": 2.0,
                "humidity_mean_24h": 60.0,
                "humidity_std_24h": 5.0,
            }

        return stats

    def _calculate_deviations(
        self,
        plant_metrics: dict[str, float],
        env_metrics: dict[str, float],
        thresholds: dict[str, Any] | None,
    ) -> dict[str, float]:
        """Calculate deviation from optimal values."""
        deviations = {}

        # Default optimal ranges
        optimal = {
            "soil_moisture": {"min": 50.0, "max": 70.0, "optimal": 60.0},
            "temperature": {"min": 18.0, "max": 28.0, "optimal": 24.0},
            "humidity": {"min": 50.0, "max": 70.0, "optimal": 60.0},
            "vpd": {"min": 0.8, "max": 1.2, "optimal": 1.0},
            "ph": {"min": 5.5, "max": 7.0, "optimal": 6.5},
            "ec": {"min": 1.0, "max": 2.5, "optimal": 1.5},
        }

        # Override with provided thresholds
        if thresholds:
            for key in optimal:
                if key in thresholds:
                    if isinstance(thresholds[key], dict):
                        optimal[key].update(thresholds[key])
                    else:
                        # Scalar value treated as optimal
                        optimal[key]["optimal"] = thresholds[key]

        # Calculate deviations
        soil_moisture = plant_metrics.get("soil_moisture", 60.0)
        deviations["soil_moisture_deviation"] = abs(soil_moisture - optimal["soil_moisture"]["optimal"])

        temperature = env_metrics.get("temperature", 24.0)
        deviations["temperature_deviation"] = abs(temperature - optimal["temperature"]["optimal"])

        humidity = env_metrics.get("humidity", 60.0)
        deviations["humidity_deviation"] = abs(humidity - optimal["humidity"]["optimal"])

        vpd = env_metrics.get("vpd", 1.0)
        deviations["vpd_deviation"] = abs(vpd - optimal["vpd"]["optimal"])

        ph = plant_metrics.get("ph", 6.5)
        deviations["ph_deviation"] = abs(ph - optimal["ph"]["optimal"])

        ec = plant_metrics.get("ec", 1.5)
        deviations["ec_deviation"] = abs(ec - optimal["ec"]["optimal"])

        return deviations

    def _calculate_stress_indicators(
        self,
        historical_data: Any,
        thresholds: dict[str, Any] | None,
    ) -> dict[str, float]:
        """Calculate stress indicator features from historical data."""
        indicators = {
            "hours_below_moisture_threshold": 0.0,
            "hours_above_temp_threshold": 0.0,
            "consecutive_stress_hours": 0.0,
        }

        try:
            # Get thresholds
            moisture_threshold = 40.0  # Below this is dry stress
            temp_threshold = 32.0  # Above this is heat stress

            if thresholds:
                if "soil_moisture" in thresholds:
                    if isinstance(thresholds["soil_moisture"], dict):
                        moisture_threshold = thresholds["soil_moisture"].get("min", 40.0)
                    else:
                        moisture_threshold = thresholds["soil_moisture"] * 0.7
                if "temperature" in thresholds:
                    if isinstance(thresholds["temperature"], dict):
                        temp_threshold = thresholds["temperature"].get("max", 32.0)
                    else:
                        temp_threshold = thresholds["temperature"] * 1.3

            # Calculate hours below moisture threshold
            if "soil_moisture" in historical_data.columns:
                below_threshold = historical_data["soil_moisture"] < moisture_threshold
                indicators["hours_below_moisture_threshold"] = float(below_threshold.sum())

            # Calculate hours above temperature threshold
            if "temperature" in historical_data.columns:
                above_threshold = historical_data["temperature"] > temp_threshold
                indicators["hours_above_temp_threshold"] = float(above_threshold.sum())

            # Calculate consecutive stress hours
            # Count max consecutive hours where either stress condition is true
            if "soil_moisture" in historical_data.columns or "temperature" in historical_data.columns:
                stress_mask = None
                if "soil_moisture" in historical_data.columns:
                    stress_mask = historical_data["soil_moisture"] < moisture_threshold
                if "temperature" in historical_data.columns:
                    temp_stress = historical_data["temperature"] > temp_threshold
                    if stress_mask is not None:
                        stress_mask = stress_mask | temp_stress
                    else:
                        stress_mask = temp_stress

                if stress_mask is not None:
                    # Count max consecutive True values
                    max_consecutive = 0
                    current_consecutive = 0
                    for is_stressed in stress_mask:
                        if is_stressed:
                            current_consecutive += 1
                            max_consecutive = max(max_consecutive, current_consecutive)
                        else:
                            current_consecutive = 0
                    indicators["consecutive_stress_hours"] = float(max_consecutive)

        except Exception as e:
            logger.warning(f"Error calculating stress indicators: {e}")

        return indicators

    def _extract_plant_context(
        self,
        plant_profile: Any | None,
    ) -> dict[str, float]:
        """Extract plant context features."""
        context = {
            "growth_stage_encoded": 2.0,  # Default: vegetative
            "days_in_stage": 14.0,
            "plant_age_days": 30.0,
        }

        if plant_profile is None:
            return context

        try:
            # Handle both dict and object
            if isinstance(plant_profile, dict):
                growth_stage = plant_profile.get("growth_stage", "vegetative")
                days_in_stage = plant_profile.get("days_in_stage", 14)
                plant_age = plant_profile.get("plant_age_days", 30)
            else:
                growth_stage = getattr(plant_profile, "growth_stage", "vegetative")
                growth_stage = growth_stage or getattr(plant_profile, "current_stage", "vegetative")
                days_in_stage = getattr(plant_profile, "days_in_stage", 14)
                plant_age = getattr(plant_profile, "plant_age_days", 30)
                if plant_age is None:
                    plant_age = getattr(plant_profile, "age_days", 30)

            # Encode growth stage
            if growth_stage:
                stage_lower = str(growth_stage).lower()
                context["growth_stage_encoded"] = float(self.GROWTH_STAGE_ENCODING.get(stage_lower, 2))

            context["days_in_stage"] = float(days_in_stage or 14)
            context["plant_age_days"] = float(plant_age or 30)

        except Exception as e:
            logger.warning(f"Error extracting plant context: {e}")

        return context

    def _extract_temporal_features(
        self,
        observation_date: datetime | None = None,
    ) -> dict[str, float]:
        """Extract temporal features with cyclical encoding."""
        import numpy as np  # Lazy load

        if observation_date is None:
            observation_date = datetime.now()
        elif isinstance(observation_date, str):
            try:
                observation_date = datetime.fromisoformat(observation_date.replace("Z", "+00:00"))
            except ValueError:
                observation_date = datetime.now()

        features = {}

        # Hour of day (cyclical)
        hour = observation_date.hour
        features["hour_of_day_sin"] = float(np.sin(2 * np.pi * hour / 24))
        features["hour_of_day_cos"] = float(np.cos(2 * np.pi * hour / 24))

        # Season encoding
        month = observation_date.month
        if month in [3, 4, 5]:
            season = "spring"
        elif month in [6, 7, 8]:
            season = "summer"
        elif month in [9, 10, 11]:
            season = "fall"
        else:
            season = "winter"

        features["season_encoded"] = float(self.SEASON_ENCODING.get(season, 0))

        return features

    def get_feature_names(self) -> list[str]:
        """Return list of feature names in order."""
        return FeatureEngineer.PLANT_HEALTH_FEATURES_V1.copy()


# Module-level alias for convenient imports
PLANT_HEALTH_FEATURES_V1 = FeatureEngineer.PLANT_HEALTH_FEATURES_V1
