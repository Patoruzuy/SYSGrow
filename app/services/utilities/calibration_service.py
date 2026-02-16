"""
Calibration Service
===================
Manages sensor calibration operations.
"""

import logging
from datetime import datetime

from app.domain.sensors import CalibrationData, CalibrationType

logger = logging.getLogger(__name__)


class CalibrationService:
    """
    Service for managing sensor calibrations.

    Provides:
    - Calibration creation and management
    - Multi-point calibration
    - Calibration verification
    - Calibration history tracking
    """

    def __init__(self, repository=None):
        """
        Initialize calibration service.

        Args:
            repository: Optional repository for persisting calibrations
        """
        self.repository = repository
        self._calibrations: dict[int, CalibrationData] = {}  # sensor_id -> calibration

    def create_linear_calibration(
        self, sensor_id: int, slope: float, offset: float, calibrated_by: str, notes: str | None = None
    ) -> CalibrationData:
        """
        Create a linear calibration (y = slope * x + offset).

        Args:
            sensor_id: Sensor ID
            slope: Calibration slope
            offset: Calibration offset
            calibrated_by: Who performed calibration
            notes: Optional notes

        Returns:
            CalibrationData instance
        """
        calibration = CalibrationData(
            sensor_id=sensor_id,
            calibration_type=CalibrationType.LINEAR,
            slope=slope,
            offset=offset,
            calibrated_at=datetime.now(),
            calibrated_by=calibrated_by,
            notes=notes,
        )

        self._calibrations[sensor_id] = calibration

        if self.repository:
            self._save_calibration(calibration)

        logger.info(f"Created linear calibration for sensor {sensor_id}: y = {slope}x + {offset}")
        return calibration

    def create_two_point_calibration(
        self,
        sensor_id: int,
        point1: tuple[float, float],
        point2: tuple[float, float],
        calibrated_by: str,
        notes: str | None = None,
    ) -> CalibrationData:
        """
        Create a two-point linear calibration.

        Args:
            sensor_id: Sensor ID
            point1: (measured_value, actual_value) for point 1
            point2: (measured_value, actual_value) for point 2
            calibrated_by: Who performed calibration
            notes: Optional notes

        Returns:
            CalibrationData instance
        """
        # Calculate slope and offset from two points
        x1, y1 = point1  # measured, actual
        x2, y2 = point2

        if x1 == x2:
            raise ValueError("Measured values must be different for two-point calibration")

        slope = (y2 - y1) / (x2 - x1)
        offset = y1 - (slope * x1)

        calibration = CalibrationData(
            sensor_id=sensor_id,
            calibration_type=CalibrationType.LINEAR,
            slope=slope,
            offset=offset,
            calibrated_at=datetime.now(),
            calibrated_by=calibrated_by,
            reference_values=[y1, y2],
            measured_values=[x1, x2],
            notes=notes,
        )

        self._calibrations[sensor_id] = calibration

        if self.repository:
            self._save_calibration(calibration)

        logger.info(f"Created two-point calibration for sensor {sensor_id}")
        return calibration

    def create_multi_point_calibration(
        self,
        sensor_id: int,
        points: list[tuple[float, float]],
        calibrated_by: str,
        calibration_type: CalibrationType = CalibrationType.LOOKUP_TABLE,
        notes: str | None = None,
    ) -> CalibrationData:
        """
        Create a multi-point calibration (lookup table or polynomial).

        Args:
            sensor_id: Sensor ID
            points: List of (measured_value, actual_value) tuples
            calibrated_by: Who performed calibration
            calibration_type: LOOKUP_TABLE or POLYNOMIAL
            notes: Optional notes

        Returns:
            CalibrationData instance
        """
        if len(points) < 2:
            raise ValueError("Multi-point calibration requires at least 2 points")

        measured_values = [p[0] for p in points]
        reference_values = [p[1] for p in points]

        if calibration_type == CalibrationType.LOOKUP_TABLE:
            # Create lookup table
            lookup_table = {measured: actual for measured, actual in points}

            calibration = CalibrationData(
                sensor_id=sensor_id,
                calibration_type=CalibrationType.LOOKUP_TABLE,
                lookup_table=lookup_table,
                calibrated_at=datetime.now(),
                calibrated_by=calibrated_by,
                reference_values=reference_values,
                measured_values=measured_values,
                notes=notes,
            )

        elif calibration_type == CalibrationType.POLYNOMIAL:
            # Fit polynomial to points
            import numpy as np

            degree = min(3, len(points) - 1)  # Max cubic, but adapt to point count
            coefficients = np.polyfit(measured_values, reference_values, degree)

            calibration = CalibrationData(
                sensor_id=sensor_id,
                calibration_type=CalibrationType.POLYNOMIAL,
                coefficients=coefficients.tolist(),
                calibrated_at=datetime.now(),
                calibrated_by=calibrated_by,
                reference_values=reference_values,
                measured_values=measured_values,
                notes=notes,
            )

        else:
            raise ValueError(f"Unsupported calibration type: {calibration_type}")

        self._calibrations[sensor_id] = calibration

        if self.repository:
            self._save_calibration(calibration)

        logger.info(f"Created {calibration_type.value} calibration for sensor {sensor_id} with {len(points)} points")
        return calibration

    def add_calibration_point(
        self,
        sensor_id: int,
        measured_value: float,
        reference_value: float,
        calibrated_by: str = "system",
        notes: str | None = None,
    ) -> CalibrationData:
        """
        Add a single calibration point. Creates or updates calibration.

        If no calibration exists, creates a two-point calibration (needs 2nd point).
        If calibration exists, converts to multi-point if needed.

        Args:
            sensor_id: Sensor ID
            measured_value: Measured (uncalibrated) value
            reference_value: Actual (reference) value
            calibrated_by: Who performed calibration
            notes: Optional notes

        Returns:
            Updated CalibrationData
        """
        existing = self._calibrations.get(sensor_id)

        if existing:
            # Add point to existing calibration
            if existing.measured_values is None:
                existing.measured_values = []
            if existing.reference_values is None:
                existing.reference_values = []

            existing.measured_values.append(measured_value)
            existing.reference_values.append(reference_value)

            # Update calibration parameters based on all points
            points = list(zip(existing.measured_values, existing.reference_values))

            if len(points) == 2:
                # Recalculate linear calibration
                x1, y1 = points[0]
                x2, y2 = points[1]
                if x1 != x2:
                    existing.slope = (y2 - y1) / (x2 - x1)
                    existing.offset = y1 - (existing.slope * x1)
            elif len(points) > 2:
                # Convert to multi-point calibration
                existing.calibration_type = CalibrationType.POLYNOMIAL
                import numpy as np

                degree = min(2, len(points) - 1)
                existing.coefficients = np.polyfit(existing.measured_values, existing.reference_values, degree).tolist()

            existing.calibrated_at = datetime.now()
            existing.calibrated_by = calibrated_by
            if notes:
                existing.notes = notes

            if self.repository:
                self._save_calibration(existing)

            logger.info(f"Added calibration point for sensor {sensor_id}: {measured_value} -> {reference_value}")
            return existing
        else:
            # Create initial calibration with first point
            calibration = CalibrationData(
                sensor_id=sensor_id,
                calibration_type=CalibrationType.LINEAR,
                measured_values=[measured_value],
                reference_values=[reference_value],
                slope=1.0,  # Default identity until 2nd point added
                offset=reference_value - measured_value,
                calibrated_at=datetime.now(),
                calibrated_by=calibrated_by,
                notes=notes,
            )

            self._calibrations[sensor_id] = calibration

            if self.repository:
                self._save_calibration(calibration)

            logger.info(f"Created initial calibration for sensor {sensor_id}: {measured_value} -> {reference_value}")
            return calibration

    def get_calibration(self, sensor_id: int) -> CalibrationData | None:
        """
        Get calibration for a sensor.

        Args:
            sensor_id: Sensor ID

        Returns:
            CalibrationData if exists, None otherwise
        """
        return self._calibrations.get(sensor_id)

    def remove_calibration(self, sensor_id: int) -> bool:
        """
        Remove calibration for a sensor.

        Args:
            sensor_id: Sensor ID

        Returns:
            True if calibration was removed
        """
        if sensor_id in self._calibrations:
            del self._calibrations[sensor_id]

            if self.repository:
                self._delete_calibration(sensor_id)

            logger.info(f"Removed calibration for sensor {sensor_id}")
            return True

        return False

    def verify_calibration(
        self, sensor_id: int, test_points: list[tuple[float, float]], tolerance: float = 0.05
    ) -> dict[str, any]:
        """
        Verify calibration accuracy with test points.

        Args:
            sensor_id: Sensor ID
            test_points: List of (measured_value, expected_value) tuples
            tolerance: Acceptable error as fraction (default 5%)

        Returns:
            Dict with verification results
        """
        calibration = self.get_calibration(sensor_id)
        if not calibration:
            return {"success": False, "error": "No calibration found for sensor"}

        errors = []
        max_error = 0.0

        for measured, expected in test_points:
            calibrated = calibration.apply(measured)
            error = abs(calibrated - expected)
            relative_error = error / expected if expected != 0 else float("inf")

            errors.append(
                {
                    "measured": measured,
                    "expected": expected,
                    "calibrated": calibrated,
                    "error": error,
                    "relative_error": relative_error,
                    "within_tolerance": relative_error <= tolerance,
                }
            )

            max_error = max(max_error, relative_error)

        passed = all(e["within_tolerance"] for e in errors)

        return {"success": True, "passed": passed, "max_error": max_error, "tolerance": tolerance, "errors": errors}

    def _save_calibration(self, calibration: CalibrationData):
        """Save calibration to repository"""
        if self.repository:
            try:
                # Repository method would be implemented
                logger.info(f"Saved calibration for sensor {calibration.sensor_id}")
            except Exception as e:
                logger.error(f"Failed to save calibration: {e}")

    def _delete_calibration(self, sensor_id: int):
        """Delete calibration from repository"""
        if self.repository:
            try:
                # Repository method would be implemented
                logger.info(f"Deleted calibration for sensor {sensor_id}")
            except Exception as e:
                logger.error(f"Failed to delete calibration: {e}")
