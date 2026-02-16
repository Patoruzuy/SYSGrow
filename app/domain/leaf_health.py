"""
Leaf Health Domain Models
==========================
Domain models for leaf health monitoring and analysis.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class LeafHealthStatus(str, Enum):
    """Leaf health status levels"""

    HEALTHY = "healthy"
    MINOR_STRESS = "minor_stress"
    MODERATE_STRESS = "moderate_stress"
    SEVERE_STRESS = "severe_stress"
    CRITICAL = "critical"


class LeafIssueType(str, Enum):
    """Types of leaf health issues"""

    CHLOROSIS = "chlorosis"  # Yellowing
    NECROSIS = "necrosis"  # Browning/dead tissue
    WILTING = "wilting"
    SPOTS = "spots"
    DISCOLORATION = "discoloration"
    PEST_DAMAGE = "pest_damage"
    FUNGAL_INFECTION = "fungal_infection"
    NUTRIENT_DEFICIENCY = "nutrient_deficiency"
    SUNBURN = "sunburn"
    EDEMA = "edema"  # Water-soaked blisters


@dataclass
class ColorMetrics:
    """RGB/HSV color analysis of leaf"""

    # RGB values (0-255)
    red_mean: float
    green_mean: float
    blue_mean: float

    # HSV values
    hue_mean: float  # 0-180
    saturation_mean: float  # 0-255
    value_mean: float  # 0-255

    # Derived metrics
    green_ratio: float  # green / (red + blue)
    yellowness_index: float  # Indicator of chlorosis

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "rgb": {
                "red": round(self.red_mean, 1),
                "green": round(self.green_mean, 1),
                "blue": round(self.blue_mean, 1),
            },
            "hsv": {
                "hue": round(self.hue_mean, 1),
                "saturation": round(self.saturation_mean, 1),
                "value": round(self.value_mean, 1),
            },
            "indices": {"green_ratio": round(self.green_ratio, 3), "yellowness_index": round(self.yellowness_index, 3)},
        }


@dataclass
class LeafIssue:
    """Individual leaf health issue"""

    issue_type: LeafIssueType
    severity: float  # 0.0-1.0
    confidence: float  # 0.0-1.0
    affected_area_pct: float  # Percentage of leaf area
    description: str
    recommended_actions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "type": self.issue_type.value,
            "severity": round(self.severity, 2),
            "confidence": round(self.confidence, 2),
            "affected_area_pct": round(self.affected_area_pct, 1),
            "description": self.description,
            "recommended_actions": self.recommended_actions,
        }


@dataclass
class LeafHealthAnalysis:
    """Complete leaf health analysis result"""

    unit_id: int
    plant_id: int | None
    timestamp: datetime
    image_path: str

    # Overall health
    health_status: LeafHealthStatus
    health_score: float  # 0.0-1.0 (1.0 = perfect health)

    # Color analysis
    color_metrics: ColorMetrics

    # Detected issues
    issues: list[LeafIssue]

    # Environmental correlation
    temperature: float | None = None
    humidity: float | None = None
    vpd: float | None = None
    soil_moisture: float | None = None

    # NDVI data (if available)
    ndvi: float | None = None
    chlorophyll_index: float | None = None

    # Analysis metadata
    analysis_method: str = "rgb_camera"  # or "ndvi_sensor"
    processing_time_ms: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "unit_id": self.unit_id,
            "plant_id": self.plant_id,
            "timestamp": self.timestamp.isoformat(),
            "image_path": self.image_path,
            "health_status": self.health_status.value,
            "health_score": round(self.health_score, 2),
            "color_metrics": self.color_metrics.to_dict(),
            "issues": [issue.to_dict() for issue in self.issues],
            "environmental_context": {
                "temperature": self.temperature,
                "humidity": self.humidity,
                "vpd": self.vpd,
                "soil_moisture": self.soil_moisture,
            },
            "ndvi_data": {"ndvi": self.ndvi, "chlorophyll_index": self.chlorophyll_index}
            if self.ndvi is not None
            else None,
            "analysis_method": self.analysis_method,
            "processing_time_ms": self.processing_time_ms,
        }

    def get_summary(self) -> str:
        """Get human-readable summary"""
        if self.health_status == LeafHealthStatus.HEALTHY:
            return f"Leaves are healthy (score: {self.health_score:.0%})"

        issue_summary = ", ".join([i.issue_type.value for i in self.issues[:3]])
        return f"{self.health_status.value.replace('_', ' ').title()}: {issue_summary}"


@dataclass
class NDVIReading:
    """NDVI sensor reading for future use"""

    unit_id: int
    timestamp: datetime

    # Spectral bands
    red_reflectance: float
    nir_reflectance: float  # Near-infrared

    # Calculated indices
    ndvi: float  # (NIR - RED) / (NIR + RED), range -1 to 1
    chlorophyll_index: float

    # Health classification
    health_status: LeafHealthStatus

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        return {
            "unit_id": self.unit_id,
            "timestamp": self.timestamp.isoformat(),
            "spectral_bands": {"red": round(self.red_reflectance, 3), "nir": round(self.nir_reflectance, 3)},
            "indices": {"ndvi": round(self.ndvi, 3), "chlorophyll_index": round(self.chlorophyll_index, 3)},
            "health_status": self.health_status.value,
        }

    @classmethod
    def from_mqtt_payload(cls, unit_id: int, data: dict[str, Any]) -> "NDVIReading":
        """Create from MQTT sensor payload"""
        red = data.get("red", 0)
        nir = data.get("nir", 0)

        # Calculate NDVI
        if (nir + red) > 0:
            ndvi = (nir - red) / (nir + red)
        else:
            ndvi = 0.0

        # Classify health from NDVI
        # NDVI ranges: <0.2=unhealthy, 0.2-0.4=stressed, 0.4-0.6=moderate, >0.6=healthy
        if ndvi < 0.2:
            health = LeafHealthStatus.CRITICAL
        elif ndvi < 0.4:
            health = LeafHealthStatus.SEVERE_STRESS
        elif ndvi < 0.6:
            health = LeafHealthStatus.MODERATE_STRESS
        else:
            health = LeafHealthStatus.HEALTHY

        return cls(
            unit_id=unit_id,
            timestamp=datetime.now(),
            red_reflectance=red,
            nir_reflectance=nir,
            ndvi=ndvi,
            chlorophyll_index=data.get("chlorophyll_index", ndvi),
            health_status=health,
        )
