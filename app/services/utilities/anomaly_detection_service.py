"""
Anomaly Detection Service
==========================
Detects anomalies in sensor readings using statistical methods.
"""

from __future__ import annotations

import contextlib
import logging
from collections import deque
from datetime import datetime
from typing import TYPE_CHECKING

from app.domain.anomaly import Anomaly
from app.enums import AnomalyType

if TYPE_CHECKING:
    from infrastructure.database.repositories.sensor_anomaly import SensorAnomalyRepository

logger = logging.getLogger(__name__)


class AnomalyDetectionService:
    """
    Service for detecting anomalies in sensor readings.

    Uses multiple detection methods:
    - Statistical outliers (z-score, IQR)
    - Rate of change detection
    - Stuck value detection
    - Range validation

    Optionally persists detected anomalies to the database when a
    ``SensorAnomalyRepository`` is provided.
    """

    def __init__(
        self,
        history_size: int = 100,
        anomaly_repo: SensorAnomalyRepository | None = None,
    ):
        """
        Initialize anomaly detection service.

        Args:
            history_size: Number of readings to keep in history
            anomaly_repo: Optional repository for persisting anomalies
        """
        self.history_size = history_size
        self._anomaly_repo = anomaly_repo
        self._sensor_history: dict[int, deque] = {}  # sensor_id -> deque of (timestamp, value)
        self._sensor_stats: dict[int, dict] = {}  # sensor_id -> statistics

    def detect_anomaly(
        self,
        sensor_id: int,
        value: float,
        field_name: str = "value",
        expected_range: tuple[float, float] | None = None,
    ) -> bool:
        """
        Detect if a value is anomalous (simplified API).

        Args:
            sensor_id: Sensor ID
            value: Reading value
            field_name: Name of the field being checked
            expected_range: Optional (min, max) expected range

        Returns:
            True if anomaly detected, False otherwise
        """
        anomaly = self.check_reading(sensor_id, value, field_name, expected_range)
        return anomaly is not None

    def check_reading(
        self,
        sensor_id: int,
        value: float,
        field_name: str = "value",
        expected_range: tuple[float, float] | None = None,
    ) -> Anomaly | None:
        """
        Check a single reading for anomalies.

        If an anomaly is detected **and** a ``SensorAnomalyRepository`` has
        been provided, the anomaly is automatically persisted to the database.

        Args:
            sensor_id: Sensor ID
            value: Reading value
            field_name: Name of the field being checked
            expected_range: Optional (min, max) expected range

        Returns:
            Anomaly if detected, None otherwise
        """
        timestamp = datetime.now()

        # Initialize history if needed
        if sensor_id not in self._sensor_history:
            self._sensor_history[sensor_id] = deque(maxlen=self.history_size)
            self._sensor_stats[sensor_id] = {}

        history = self._sensor_history[sensor_id]
        detected: Anomaly | None = None

        # Check range first
        if expected_range:
            min_val, max_val = expected_range
            if value < min_val or value > max_val:
                detected = Anomaly(
                    sensor_id=sensor_id,
                    timestamp=timestamp,
                    anomaly_type=AnomalyType.OUT_OF_RANGE,
                    value=value,
                    expected_range=expected_range,
                    severity=self._calculate_range_severity(value, expected_range),
                    description=f"{field_name} {value} is outside expected range [{min_val}, {max_val}]",
                )

        # Need at least 2 readings for other checks
        if detected is None and len(history) >= 2:
            # Check for stuck value
            detected = self._check_stuck_value(sensor_id, value, field_name, history)

            # Check rate of change
            if detected is None:
                detected = self._check_rate_of_change(sensor_id, value, field_name, timestamp, history)

            # Statistical outlier detection (need more history)
            if detected is None and len(history) >= 10:
                detected = self._check_statistical_outlier(sensor_id, value, field_name, history)

        # Always append to history
        history.append((timestamp, value))

        if detected is not None:
            logger.warning("Anomaly detected for sensor %s: %s", sensor_id, detected.description)
            self._persist_anomaly(detected)
            return detected

        # Update statistics (only when no anomaly)
        self._update_statistics(sensor_id)
        return None

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    def _persist_anomaly(self, anomaly: Anomaly) -> None:
        """Persist anomaly to the database if a repository is available."""
        if self._anomaly_repo is None:
            return
        with contextlib.suppress(Exception):
            exp_min = anomaly.expected_range[0] if anomaly.expected_range else None
            exp_max = anomaly.expected_range[1] if anomaly.expected_range else None
            self._anomaly_repo.insert(
                sensor_id=anomaly.sensor_id,
                anomaly_type=anomaly.anomaly_type.value,
                severity=anomaly.severity,
                value=anomaly.value,
                expected_min=exp_min,
                expected_max=exp_max,
                description=anomaly.description,
            )

    def _check_stuck_value(self, sensor_id: int, value: float, field_name: str, history: deque) -> Anomaly | None:
        """Check if value is stuck (not changing)"""

        # Check last N values
        check_count = min(5, len(history))
        recent_values = [v for _, v in list(history)[-check_count:]]

        # All values identical (with small tolerance for float comparison)
        if all(abs(v - value) < 0.001 for v in recent_values):
            return Anomaly(
                sensor_id=sensor_id,
                timestamp=datetime.now(),
                anomaly_type=AnomalyType.STUCK,
                value=value,
                expected_range=None,
                severity=0.6,
                description=f"{field_name} appears stuck at {value}",
            )

        return None

    def _check_rate_of_change(
        self, sensor_id: int, value: float, field_name: str, timestamp: datetime, history: deque
    ) -> Anomaly | None:
        """Check if value is changing too rapidly"""

        last_timestamp, last_value = history[-1]

        # Calculate rate of change
        time_diff = (timestamp - last_timestamp).total_seconds()
        if time_diff == 0:
            return None

        value_diff = abs(value - last_value)
        rate = value_diff / time_diff

        # Calculate typical rate from history
        if len(history) < 5:
            return None

        rates = []
        for i in range(len(history) - 1):
            t1, v1 = history[i]
            t2, v2 = history[i + 1]
            td = (t2 - t1).total_seconds()
            if td > 0:
                rates.append(abs(v2 - v1) / td)

        if not rates:
            return None

        avg_rate = sum(rates) / len(rates)

        # Spike if rate is 5x typical
        if rate > avg_rate * 5 and value_diff > 1.0:  # Also require significant absolute change
            anomaly_type = AnomalyType.SPIKE if value > last_value else AnomalyType.DROP

            return Anomaly(
                sensor_id=sensor_id,
                timestamp=timestamp,
                anomaly_type=anomaly_type,
                value=value,
                expected_range=None,
                severity=min(1.0, rate / (avg_rate * 10)),
                description=f"{field_name} changed rapidly: {last_value} -> {value} ({rate:.2f}/s)",
            )

        return None

    def _check_statistical_outlier(
        self, sensor_id: int, value: float, field_name: str, history: deque
    ) -> Anomaly | None:
        """Check if value is a statistical outlier using z-score"""

        # Get values from history
        values = [v for _, v in history]

        # Calculate mean and std
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance**0.5

        # Avoid division by zero
        if std < 0.001:
            return None

        # Calculate z-score
        z_score = abs((value - mean) / std)

        # Outlier if z-score > 3 (99.7% confidence)
        if z_score > 3:
            return Anomaly(
                sensor_id=sensor_id,
                timestamp=datetime.now(),
                anomaly_type=AnomalyType.STATISTICAL,
                value=value,
                expected_range=(mean - 3 * std, mean + 3 * std),
                severity=min(1.0, z_score / 5),
                description=f"{field_name} {value} is a statistical outlier (z-score: {z_score:.2f})",
            )

        return None

    def _calculate_range_severity(self, value: float, expected_range: tuple[float, float]) -> float:
        """Calculate severity for out-of-range value"""
        min_val, max_val = expected_range
        range_size = max_val - min_val

        if value < min_val:
            distance = min_val - value
        else:
            distance = value - max_val

        # Severity based on how far outside range
        severity = min(1.0, distance / range_size)
        return severity

    def _update_statistics(self, sensor_id: int):
        """Update running statistics for sensor"""
        history = self._sensor_history[sensor_id]
        values = [v for _, v in history]

        if len(values) < 2:
            return

        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / len(values)
        std = variance**0.5

        self._sensor_stats[sensor_id] = {
            "mean": mean,
            "std": std,
            "min": min(values),
            "max": max(values),
            "count": len(values),
        }

    def get_statistics(self, sensor_id: int) -> dict:
        """
        Get statistics for a sensor.

        Args:
            sensor_id: Sensor ID

        Returns:
            Statistics dict with mean, std_dev, min, max, count
        """
        stats = self._sensor_stats.get(sensor_id)
        if not stats:
            return {"mean": 0.0, "std_dev": 0.0, "min": 0.0, "max": 0.0, "count": 0}

        # Normalize key names (std -> std_dev for consistency)
        return {
            "mean": stats.get("mean", 0.0),
            "std_dev": stats.get("std", 0.0),
            "min": stats.get("min", 0.0),
            "max": stats.get("max", 0.0),
            "count": stats.get("count", 0),
        }

    def reset_sensor(self, sensor_id: int):
        """
        Reset history and statistics for a sensor.

        Args:
            sensor_id: Sensor ID
        """
        if sensor_id in self._sensor_history:
            del self._sensor_history[sensor_id]
        if sensor_id in self._sensor_stats:
            del self._sensor_stats[sensor_id]

        logger.info("Reset anomaly detection for sensor %s", sensor_id)
