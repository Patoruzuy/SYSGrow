"""
Environmental Thresholds Value Object
======================================
Immutable value object representing environmental control thresholds.

Following Domain-Driven Design (DDD), this is a value object:
- Immutable (frozen dataclass)
- No identity (defined by its attributes)
- Can be freely shared and passed around
- Validates its own invariants
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class EnvironmentalThresholds:
    """
    Immutable environmental threshold values for climate control.

    This value object encapsulates all threshold-related data and validation,
    preventing invalid states and providing a clear contract for threshold operations.

    Attributes:
        temperature: Temperature threshold in °C (default: 24.0)
        humidity: Humidity threshold in % (default: 50.0)
        soil_moisture: Soil moisture threshold in % (default: 40.0)
        co2: CO2 threshold in ppm (default: 1000.0)
        voc: VOC threshold in ppb (default: 1000.0)
        lux: Light intensity threshold in lux (default: 1000.0)
        air_quality: Air Quality Index threshold (default: 100.0)
    """

    temperature: float = 24.0
    humidity: float = 50.0
    soil_moisture: float = 40.0
    co2: float = 1000.0
    voc: float = 1000.0
    lux: float = 1000.0
    air_quality: float = 100.0

    def __post_init__(self):
        """Validate threshold values after initialization."""
        # Validate ranges (frozen dataclass requires object.__setattr__)
        if not (-50 <= self.temperature <= 100):
            raise ValueError(f"Temperature must be between -50 and 100°C, got {self.temperature}")
        if not (0 <= self.humidity <= 100):
            raise ValueError(f"Humidity must be between 0 and 100%, got {self.humidity}")
        if not (0 <= self.soil_moisture <= 100):
            raise ValueError(f"Soil moisture must be between 0 and 100%, got {self.soil_moisture}")
        if not (0 <= self.co2 <= 5000):
            raise ValueError(f"CO2 must be between 0 and 5000 ppm, got {self.co2}")
        if not (0 <= self.voc <= 10000):
            raise ValueError(f"VOC must be between 0 and 10000 ppb, got {self.voc}")
        if not (0 <= self.lux <= 100000):
            raise ValueError(f"Light intensity must be between 0 and 100000 lux, got {self.lux}")
        if not (0 <= self.air_quality <= 500):
            raise ValueError(f"Air quality must be between 0 and 500, got {self.air_quality}")

    def to_dict(self) -> dict[str, float]:
        """
        Convert to dictionary format.

        Returns:
            Dictionary with threshold field names as keys
        """
        return asdict(self)

    def to_settings_dict(self) -> dict[str, float]:
        """
        Convert to settings format (with _threshold suffix).

        Used for compatibility with existing UnitSettings format.

        Returns:
            Dictionary with _threshold suffix on keys
        """
        return {
            "temperature_threshold": self.temperature,
            "humidity_threshold": self.humidity,
            "soil_moisture_threshold": self.soil_moisture,
            "co2_threshold": self.co2,
            "voc_threshold": self.voc,
            "lux_threshold": self.lux,
            "air_quality_threshold": self.air_quality,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> EnvironmentalThresholds:
        """
        Create from dictionary.

        Handles both suffixed (_threshold) and non-suffixed formats.

        Args:
            data: Dictionary with threshold values

        Returns:
            EnvironmentalThresholds instance

        Examples:
            >>> thresholds = EnvironmentalThresholds.from_dict({"temperature_threshold": 25.0, "humidity": 60.0})
        """
        # Handle both suffixed and non-suffixed keys
        return EnvironmentalThresholds(
            temperature=data.get("temperature_threshold", data.get("temperature", 24.0)),
            humidity=data.get("humidity_threshold", data.get("humidity", 50.0)),
            soil_moisture=data.get("soil_moisture_threshold", data.get("soil_moisture", 40.0)),
            co2=data.get("co2_threshold", data.get("co2", 1000.0)),
            voc=data.get("voc_threshold", data.get("voc", 1000.0)),
            lux=data.get("lux_threshold", data.get("lux", 1000.0)),
            air_quality=data.get(
                "air_quality_threshold", data.get("air_quality", data.get("aqi_threshold", data.get("aqi", 100.0)))
            ),
        )

    def with_temperature(self, temperature: float) -> EnvironmentalThresholds:
        """
        Create new instance with updated temperature.

        Since value objects are immutable, this creates a new instance.

        Args:
            temperature: New temperature threshold

        Returns:
            New EnvironmentalThresholds instance
        """
        return EnvironmentalThresholds(
            temperature=temperature,
            humidity=self.humidity,
            soil_moisture=self.soil_moisture,
            co2=self.co2,
            voc=self.voc,
            lux=self.lux,
            air_quality=self.air_quality,
        )

    def with_humidity(self, humidity: float) -> EnvironmentalThresholds:
        """Create new instance with updated humidity."""
        return EnvironmentalThresholds(
            temperature=self.temperature,
            humidity=humidity,
            soil_moisture=self.soil_moisture,
            co2=self.co2,
            voc=self.voc,
            lux=self.lux,
            air_quality=self.air_quality,
        )

    def merge(self, other: dict[str, float]) -> EnvironmentalThresholds:
        """
        Create new instance by merging with partial updates.

        Args:
            other: Dictionary with threshold updates

        Returns:
            New EnvironmentalThresholds instance with merged values
        """
        current = self.to_dict()
        current.update(other)
        return EnvironmentalThresholds.from_dict(current)
