# Enterprise Irrigation Optimization Plan

## Objective

Remove all hardcoded defaults and leverage real plant data (pot size, growth stage, pump specs, growing medium) to create data-driven, precision irrigation with adaptive ML learning and per-plant actuator support.

---

## Architecture Decisions

### Data Access Pattern
- **DO NOT** access `plants_info.json` directly
- **USE** `PlantViewService` as the single source of truth for plant information
- `PlantViewService` internally uses `PlantJsonHandler` for JSON data access so you can use its methods to get plant-type-specific watering data get_plant_watering_schedule(plant_type) or get_plant_info(plant_type)
- All irrigation services get plant data via `PlantViewService.get_plant()` or `get_active_plant()`

### UI Location
- **MOVE** irrigation configuration from `devices.html` to `settings.html` under **Automation** tab
- Consolidate all irrigation settings (pump duration, mist duration, thresholds, calibration) in one place

### Calibration Strategy
- **Single measurement** for initial calibration with "Recalibrate" option
- **ML feedback loop** via existing `too_little/just_right/too_much` feedback continuously refines duration calculations
- User can trigger manual recalibration anytime from Automation settings

### Threshold Proposal UX
- Notification shows **old vs. new threshold comparison**
- Three action buttons: **"Apply"** / **"Keep Current"** / **"Customize"**
- "Customize" opens a modal with slider for manual adjustment

### Shared Pump Strategy
- **Prompt user selection per irrigation** when unit has multiple plants but single pump
- Notification lists all plants needing water with checkboxes
- User selects which plants to irrigate in this cycle
- Prevents overwatering plants that don't need it

---

## Implementation Steps

### Step 1: Create `IrrigationCalculator` Domain Service

**File:** `app/domain/irrigation_calculator.py`

```python
"""
Irrigation Calculator
=====================
Computes water volume and duration from plant/pump specifications.
Replaces all hardcoded irrigation defaults with data-driven calculations.
"""
from dataclasses import dataclass
from typing import Optional, Dict, Any
from app.constants import GrowingMediumConfig

@dataclass
class IrrigationCalculation:
    """Result of irrigation calculation."""
    water_volume_ml: float
    duration_seconds: int
    flow_rate_ml_per_second: float
    confidence: float  # 0-1, based on calibration data availability
    reasoning: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "water_volume_ml": round(self.water_volume_ml, 1),
            "duration_seconds": self.duration_seconds,
            "flow_rate_ml_per_second": round(self.flow_rate_ml_per_second, 2),
            "confidence": round(self.confidence, 2),
            "reasoning": self.reasoning,
        }


class IrrigationCalculator:
    """
    Calculates optimal irrigation parameters from plant and pump data.
    
    Water Volume Formula:
        base_ml = plant_type.amount_ml_per_plant (from PlantViewService)
        pot_factor = pot_size_liters / reference_pot_size (default 5L)
        medium_factor = GrowingMediumConfig.retention_coefficient[growing_medium]
        stage_factor = growth_stage_multipliers[current_stage]
        
        volume_ml = base_ml * pot_factor * medium_factor * stage_factor
    
    Duration Formula:
        duration_seconds = volume_ml / flow_rate_ml_per_second
    """
    
    def __init__(self, plant_service: "PlantViewService"):
        self._plant_service = plant_service
    
    def compute_water_volume(
        self,
        plant_id: int,
        pot_size_liters: float,
        growing_medium: str,
        growth_stage: str,
        plant_type: str,
    ) -> float:
        """
        Compute required water volume in ml.
        
        Uses PlantViewService to get plant-type-specific watering data.
        """
        # Get base amount from plant type via PlantViewService
        watering_schedule = self._plant_service.plant_json_handler.get_watering_schedule(plant_type)
        base_ml = watering_schedule.get("amount_ml_per_plant", 100.0)  # Default 100ml
        
        # Pot size scaling (reference: 5L pot)
        pot_factor = pot_size_liters / 5.0 if pot_size_liters > 0 else 1.0
        
        # Growing medium retention
        medium_config = GrowingMediumConfig.get(growing_medium)
        medium_factor = medium_config.retention_coefficient
        
        # Growth stage multiplier
        stage_multipliers = {
            "germination": 0.5,
            "seedling": 0.7,
            "vegetative": 1.0,
            "flowering": 1.2,
            "fruiting": 1.3,
            "harvest": 0.8,
        }
        stage_factor = stage_multipliers.get(growth_stage.lower(), 1.0)
        
        return base_ml * pot_factor * medium_factor * stage_factor
    
    def compute_duration(
        self,
        volume_ml: float,
        flow_rate_ml_per_second: float,
        min_duration: int = 5,
        max_duration: int = 600,
    ) -> int:
        """
        Compute irrigation duration in seconds.
        
        Args:
            volume_ml: Required water volume
            flow_rate_ml_per_second: Pump flow rate (from calibration)
            min_duration: Safety minimum
            max_duration: Safety maximum
        """
        if flow_rate_ml_per_second <= 0:
            return 30  # Fallback if not calibrated
        
        duration = int(volume_ml / flow_rate_ml_per_second)
        return max(min_duration, min(duration, max_duration))
    
    def calculate(
        self,
        plant_id: int,
        pump_flow_rate: Optional[float] = None,
    ) -> IrrigationCalculation:
        """
        Full irrigation calculation for a plant.
        
        Fetches plant data via PlantViewService and computes volume + duration.
        """
        plant = self._plant_service.get_plant(plant_id)
        if not plant:
            return IrrigationCalculation(
                water_volume_ml=100.0,
                duration_seconds=30,
                flow_rate_ml_per_second=3.33,
                confidence=0.1,
                reasoning="Plant not found, using defaults",
            )
        
        volume_ml = self.compute_water_volume(
            plant_id=plant_id,
            pot_size_liters=plant.pot_size_liters,
            growing_medium=plant.growing_medium,
            growth_stage=plant.current_stage,
            plant_type=plant.plant_type or "default",
        )
        
        # Use calibrated flow rate or estimate
        flow_rate = pump_flow_rate or 3.33  # Default ~200ml/min
        confidence = 0.9 if pump_flow_rate else 0.3
        
        duration = self.compute_duration(volume_ml, flow_rate)
        
        return IrrigationCalculation(
            water_volume_ml=volume_ml,
            duration_seconds=duration,
            flow_rate_ml_per_second=flow_rate,
            confidence=confidence,
            reasoning=f"Calculated for {plant.plant_type} in {plant.current_stage} stage, "
                      f"{plant.pot_size_liters}L {plant.growing_medium} pot",
        )
```

---

### Step 2: Add `GrowingMediumConfig` to Constants

**File:** `app/constants.py` (add to existing)

```python
# =============================================================================
# Growing Medium Configuration
# =============================================================================

@dataclass
class GrowingMediumProperties:
    """Properties of a growing medium affecting irrigation."""
    name: str
    retention_coefficient: float  # Water retention (1.0 = baseline soil)
    drainage_rate: float  # How fast water drains (ml/hour/liter)
    evaporation_multiplier: float  # Evaporation speed relative to soil
    recommended_moisture_range: tuple  # (min%, max%) for healthy growth

class GrowingMediumConfig:
    """Growing medium configurations for irrigation calculations."""
    
    SOIL = GrowingMediumProperties(
        name="soil",
        retention_coefficient=1.0,
        drainage_rate=5.0,
        evaporation_multiplier=1.0,
        recommended_moisture_range=(40, 70),
    )
    
    COCO_COIR = GrowingMediumProperties(
        name="coco",
        retention_coefficient=0.8,  # Drains faster, needs more frequent watering
        drainage_rate=10.0,
        evaporation_multiplier=1.2,
        recommended_moisture_range=(50, 80),
    )
    
    PERLITE = GrowingMediumProperties(
        name="perlite",
        retention_coefficient=0.6,  # Very fast drainage
        drainage_rate=20.0,
        evaporation_multiplier=1.5,
        recommended_moisture_range=(30, 60),
    )
    
    HYDRO = GrowingMediumProperties(
        name="hydro",
        retention_coefficient=0.4,  # Minimal retention
        drainage_rate=50.0,
        evaporation_multiplier=0.5,  # Less surface evaporation
        recommended_moisture_range=(80, 100),
    )
    
    CLAY_PEBBLES = GrowingMediumProperties(
        name="clay_pebbles",
        retention_coefficient=0.5,
        drainage_rate=30.0,
        evaporation_multiplier=0.8,
        recommended_moisture_range=(60, 90),
    )
    
    _REGISTRY = {
        "soil": SOIL,
        "coco": COCO_COIR,
        "coco_coir": COCO_COIR,
        "perlite": PERLITE,
        "hydro": HYDRO,
        "hydroponics": HYDRO,
        "clay_pebbles": CLAY_PEBBLES,
        "leca": CLAY_PEBBLES,
    }
    
    @classmethod
    def get(cls, medium_name: str) -> GrowingMediumProperties:
        """Get medium properties by name, defaults to SOIL."""
        return cls._REGISTRY.get(medium_name.lower().strip(), cls.SOIL)
```

---

### Step 3: Create `PumpCalibrationService`

**File:** `app/services/hardware/pump_calibration.py`

```python
"""
Pump Calibration Service
========================
Handles pump flow rate calibration through timed water collection.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, TYPE_CHECKING

from app.utils.time import iso_now, utc_now

if TYPE_CHECKING:
    from app.hardware.actuators.manager import ActuatorManager
    from infrastructure.database.repositories.actuators import ActuatorRepository

@dataclass
class CalibrationSession:
    """Active calibration session."""
    actuator_id: int
    start_time: datetime
    target_duration_seconds: int
    status: str  # "running", "awaiting_measurement", "completed", "cancelled"

@dataclass
class CalibrationResult:
    """Result of pump calibration."""
    actuator_id: int
    flow_rate_ml_per_second: float
    measured_volume_ml: float
    duration_seconds: float
    calibrated_at: str
    confidence: float  # 1.0 for manual, adjusted by ML feedback
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "actuator_id": self.actuator_id,
            "flow_rate_ml_per_second": round(self.flow_rate_ml_per_second, 3),
            "measured_volume_ml": round(self.measured_volume_ml, 1),
            "duration_seconds": round(self.duration_seconds, 1),
            "calibrated_at": self.calibrated_at,
            "confidence": round(self.confidence, 2),
        }


class PumpCalibrationService:
    """
    Service for calibrating pump flow rates.
    
    Calibration Flow:
    1. User clicks "Start Calibration" in UI
    2. System runs pump for fixed duration (e.g., 30 seconds)
    3. User measures collected water volume
    4. User enters measured_ml in UI
    5. System calculates flow_rate = measured_ml / duration
    6. Flow rate stored in actuator metadata
    
    ML Refinement:
    - When user gives feedback (too_little/too_much), system adjusts flow_rate
    - Feedback adjusts by small increments (±5%) to converge on true rate
    """
    
    def __init__(
        self,
        actuator_manager: "ActuatorManager",
        actuator_repo: "ActuatorRepository",
    ):
        self._actuator_manager = actuator_manager
        self._actuator_repo = actuator_repo
        self._active_sessions: Dict[int, CalibrationSession] = {}
    
    def start_calibration(
        self,
        actuator_id: int,
        duration_seconds: int = 30,
    ) -> Dict[str, Any]:
        """
        Start pump calibration by running pump for fixed duration.
        
        Returns:
            Status dict with session info
        """
        # Validate actuator is a pump
        actuator = self._actuator_repo.get_actuator(actuator_id)
        if not actuator or actuator.get("actuator_type", "").lower() not in ("pump", "water-pump"):
            return {"ok": False, "error": "Actuator is not a pump"}
        
        # Run pump
        success = self._actuator_manager.turn_on(
            actuator_id,
            duration_seconds=duration_seconds,
            reason="calibration",
        )
        
        if not success:
            return {"ok": False, "error": "Failed to activate pump"}
        
        # Create session
        session = CalibrationSession(
            actuator_id=actuator_id,
            start_time=utc_now(),
            target_duration_seconds=duration_seconds,
            status="running",
        )
        self._active_sessions[actuator_id] = session
        
        return {
            "ok": True,
            "actuator_id": actuator_id,
            "duration_seconds": duration_seconds,
            "message": f"Pump running for {duration_seconds}s. Collect the water and measure the volume.",
            "next_step": "Call complete_calibration(actuator_id, measured_ml) with the measured volume",
        }
    
    def complete_calibration(
        self,
        actuator_id: int,
        measured_ml: float,
    ) -> CalibrationResult:
        """
        Complete calibration with user's measured water volume.
        
        Args:
            actuator_id: The pump actuator ID
            measured_ml: Volume of water collected (measured by user)
            
        Returns:
            CalibrationResult with calculated flow rate
        """
        session = self._active_sessions.get(actuator_id)
        if not session:
            raise ValueError(f"No active calibration session for actuator {actuator_id}")
        
        # Calculate flow rate
        duration = session.target_duration_seconds
        flow_rate = measured_ml / duration if duration > 0 else 0
        
        # Store in actuator metadata
        self._actuator_repo.update_actuator_metadata(
            actuator_id,
            {
                "flow_rate_ml_per_second": flow_rate,
                "calibration_volume_ml": measured_ml,
                "calibration_duration_seconds": duration,
                "calibrated_at": iso_now(),
                "calibration_confidence": 1.0,
            }
        )
        
        # Clean up session
        del self._active_sessions[actuator_id]
        
        return CalibrationResult(
            actuator_id=actuator_id,
            flow_rate_ml_per_second=flow_rate,
            measured_volume_ml=measured_ml,
            duration_seconds=duration,
            calibrated_at=iso_now(),
            confidence=1.0,
        )
    
    def adjust_from_feedback(
        self,
        actuator_id: int,
        feedback: str,  # "too_little" or "too_much"
        adjustment_factor: float = 0.05,  # 5% adjustment per feedback
    ) -> Optional[float]:
        """
        Adjust flow rate based on irrigation feedback.
        
        If user says "too_little", we delivered less water than calculated,
        meaning actual flow rate is LOWER than stored → decrease stored rate.
        
        If user says "too_much", actual flow rate is HIGHER → increase stored rate.
        """
        actuator = self._actuator_repo.get_actuator(actuator_id)
        if not actuator:
            return None
        
        metadata = actuator.get("metadata", {})
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata) if metadata else {}
        
        current_rate = metadata.get("flow_rate_ml_per_second")
        if not current_rate:
            return None
        
        # Adjust rate
        if feedback == "too_little":
            # We thought we delivered X ml but it was less → rate is lower
            new_rate = current_rate * (1 - adjustment_factor)
        elif feedback == "too_much":
            # We delivered more than expected → rate is higher
            new_rate = current_rate * (1 + adjustment_factor)
        else:
            return current_rate  # "just_right" - no adjustment
        
        # Update confidence (decreases with each adjustment)
        confidence = metadata.get("calibration_confidence", 1.0)
        new_confidence = max(0.5, confidence - 0.05)  # Min 50% confidence
        
        self._actuator_repo.update_actuator_metadata(
            actuator_id,
            {
                "flow_rate_ml_per_second": new_rate,
                "calibration_confidence": new_confidence,
                "last_feedback_adjustment": iso_now(),
            }
        )
        
        return new_rate
    
    def get_flow_rate(self, actuator_id: int) -> Optional[float]:
        """Get calibrated flow rate for an actuator."""
        actuator = self._actuator_repo.get_actuator(actuator_id)
        if not actuator:
            return None
        
        metadata = actuator.get("metadata", {})
        if isinstance(metadata, str):
            import json
            metadata = json.loads(metadata) if metadata else {}
        
        return metadata.get("flow_rate_ml_per_second")
```

---

### Step 4: Extend `ActuatorConfig` Metadata Schema

**File:** `app/domain/actuators/actuator_entity.py` (update existing)

Add to `ActuatorConfig.metadata` documentation:

```python
# Pump-specific metadata fields:
# {
#     "flow_rate_ml_per_second": float,     # Calibrated flow rate
#     "calibration_volume_ml": float,        # Volume used in calibration
#     "calibration_duration_seconds": int,   # Duration of calibration run
#     "calibrated_at": str,                  # ISO timestamp
#     "calibration_confidence": float,       # 0-1, decreases with feedback adjustments
#     "last_feedback_adjustment": str,       # ISO timestamp of last ML adjustment
#     "pressure_rating_psi": float,          # Optional pump pressure
#     "max_flow_rate_ml_per_second": float,  # Manufacturer spec (optional)
# }
```

---

### Step 5: Add Stage Transition Threshold Handler

**File:** `app/services/application/plant_service.py` (modify `update_plant_stage`)

```python
def update_plant_stage(
    self,
    plant_id: int,
    new_stage: str,
    days_in_stage: int = 0
) -> bool:
    """
    Update plant growth stage.
    
    When stage changes, proposes new thresholds based on stage-specific
    requirements and sends notification for user confirmation.
    """
    try:
        plant = self.get_plant(plant_id)
        if not plant:
            return False

        old_stage = plant.current_stage
        unit_id = plant.unit_id
        
        # ... existing stage update logic ...
        
        # Propose threshold update if stage changed
        if old_stage != new_stage and self.threshold_service:
            self._propose_stage_thresholds(plant, old_stage, new_stage)
        
        return True
    except Exception as e:
        logger.error(f"Error updating plant stage: {e}")
        return False

def _propose_stage_thresholds(
    self,
    plant: PlantProfile,
    old_stage: str,
    new_stage: str,
) -> None:
    """
    Propose new thresholds when plant enters a new growth stage.
    
    Sends notification with Apply/Keep Current/Customize options.
    """
    # Get stage-specific thresholds from plant type
    plant_type = plant.plant_type or "default"
    
    # Get optimal thresholds for new stage via ThresholdService
    new_thresholds = self.threshold_service.get_thresholds(plant_type, new_stage)
    current_thresholds = self.threshold_service.get_unit_thresholds(plant.unit_id)
    
    # Build comparison data
    threshold_comparison = {
        "soil_moisture": {
            "current": current_thresholds.soil_moisture if current_thresholds else 50.0,
            "proposed": new_thresholds.soil_moisture,
        },
        "temperature": {
            "current": current_thresholds.temperature if current_thresholds else 24.0,
            "proposed": new_thresholds.temperature,
        },
        "humidity": {
            "current": current_thresholds.humidity if current_thresholds else 55.0,
            "proposed": new_thresholds.humidity,
        },
    }
    
    # Emit event for threshold proposal
    if self.event_bus:
        from app.schemas.events import ThresholdsProposedPayload
        payload = ThresholdsProposedPayload(
            unit_id=plant.unit_id,
            plant_id=plant.plant_id,
            old_stage=old_stage,
            new_stage=new_stage,
            proposed_thresholds=new_thresholds.to_dict(),
            current_thresholds=current_thresholds.to_dict() if current_thresholds else {},
            comparison=threshold_comparison,
        )
        self.event_bus.publish(RuntimeEvent.THRESHOLDS_PROPOSED, payload)
    
    # Send notification
    if self.notifications_service:
        self._send_threshold_proposal_notification(
            plant=plant,
            old_stage=old_stage,
            new_stage=new_stage,
            comparison=threshold_comparison,
        )

def _send_threshold_proposal_notification(
    self,
    plant: PlantProfile,
    old_stage: str,
    new_stage: str,
    comparison: Dict[str, Dict[str, float]],
) -> None:
    """Send notification for threshold proposal with action buttons."""
    # Get user_id from unit
    user_id = self._get_unit_owner(plant.unit_id)
    if not user_id:
        return
    
    # Format comparison for message
    changes = []
    for param, values in comparison.items():
        if values["current"] != values["proposed"]:
            direction = "↑" if values["proposed"] > values["current"] else "↓"
            changes.append(
                f"{param.replace('_', ' ').title()}: {values['current']:.1f}% → {values['proposed']:.1f}% {direction}"
            )
    
    message = (
        f"Plant '{plant.plant_name}' moved from {old_stage} to {new_stage}. "
        f"Recommended threshold changes:\n" + "\n".join(changes)
    )
    
    self.notifications_service.send_notification(
        user_id=user_id,
        notification_type=NotificationType.THRESHOLD_PROPOSAL,
        title=f"🌱 Threshold Update for {plant.plant_name}",
        message=message,
        severity=NotificationSeverity.INFO,
        unit_id=plant.unit_id,
        requires_action=True,
        action_type="threshold_proposal",
        action_data={
            "plant_id": plant.plant_id,
            "unit_id": plant.unit_id,
            "old_stage": old_stage,
            "new_stage": new_stage,
            "proposed_thresholds": comparison,
            "actions": ["apply", "keep_current", "customize"],
        },
    )
```

---

### Step 6: Refactor `detect_irrigation_need()` for Per-Plant Support

**File:** `app/services/application/irrigation_workflow_service.py`

```python
def detect_irrigation_need(
    self,
    unit_id: int,
    soil_moisture: float,
    threshold: float,
    user_id: int,
    plant_id: Optional[int] = None,
    actuator_id: Optional[int] = None,
    sensor_id: Optional[int] = None,
    plant_name: Optional[str] = None,
    plant_pump_assigned: bool = False,
    # ... other params ...
) -> Optional[int]:
    """
    Detect irrigation need and create pending request(s).
    
    Per-Plant Irrigation Logic:
    1. If plant_pump_assigned=True and plant_id provided:
       → Create request for that specific plant
    2. If unit has multiple plants with individual pumps:
       → Check each plant's threshold, create request per plant needing water
    3. If shared pump with multiple plants needing water:
       → Send selection notification, user picks which plants to water
    4. Fallback: Use active_plant from unit
    """
    # ... existing validation ...
    
    # Handle per-plant irrigation
    if plant_pump_assigned and plant_id and actuator_id:
        # Dedicated pump for this plant - create single request
        return self._create_plant_irrigation_request(
            unit_id=unit_id,
            plant_id=plant_id,
            actuator_id=actuator_id,
            soil_moisture=soil_moisture,
            threshold=threshold,
            user_id=user_id,
            sensor_id=sensor_id,
            config=config,
            # ... pass other params ...
        )
    
    # Check for multi-plant irrigation scenario
    if self._plant_service:
        plants_needing_water = self._check_all_plants_moisture(unit_id, user_id)
        
        if len(plants_needing_water) > 1:
            # Multiple plants need water - check pump assignment
            return self._handle_multi_plant_irrigation(
                unit_id=unit_id,
                plants=plants_needing_water,
                user_id=user_id,
                config=config,
            )
    
    # Fallback: Use active plant or unit-level request
    # ... existing logic ...

def _check_all_plants_moisture(
    self,
    unit_id: int,
    user_id: int,
) -> List[Dict[str, Any]]:
    """
    Check soil moisture for all plants in unit.
    
    Returns list of plants below their threshold.
    """
    plants = self._plant_service.list_plants(unit_id)
    plants_needing_water = []
    
    for plant in plants:
        # Get plant's soil moisture threshold (override or stage-specific)
        threshold = (
            plant.soil_moisture_threshold_override
            or self._threshold_service.get_thresholds(
                plant.plant_type or "default",
                plant.current_stage
            ).soil_moisture
        )
        
        # Get current moisture from plant's linked sensor
        sensor_ids = self._plant_service.get_plant_sensor_ids(plant.plant_id)
        current_moisture = self._get_plant_moisture(sensor_ids)
        
        if current_moisture is not None and current_moisture < threshold:
            # Get linked pump if any
            actuator_ids = self._plant_service.get_plant_actuator_ids(plant.plant_id)
            pump_id = self._find_pump_in_actuators(actuator_ids)
            
            plants_needing_water.append({
                "plant": plant,
                "current_moisture": current_moisture,
                "threshold": threshold,
                "pump_id": pump_id,
                "has_dedicated_pump": pump_id is not None,
            })
    
    return plants_needing_water

def _handle_multi_plant_irrigation(
    self,
    unit_id: int,
    plants: List[Dict[str, Any]],
    user_id: int,
    config: WorkflowConfig,
) -> Optional[int]:
    """
    Handle irrigation for multiple plants needing water.
    
    Strategy:
    - Plants with dedicated pumps: Create individual requests
    - Plants sharing pump: Send selection notification
    """
    # Separate plants by pump assignment
    dedicated_pump_plants = [p for p in plants if p["has_dedicated_pump"]]
    shared_pump_plants = [p for p in plants if not p["has_dedicated_pump"]]
    
    request_ids = []
    
    # Create requests for plants with dedicated pumps
    for plant_data in dedicated_pump_plants:
        plant = plant_data["plant"]
        request_id = self._create_plant_irrigation_request(
            unit_id=unit_id,
            plant_id=plant.plant_id,
            actuator_id=plant_data["pump_id"],
            soil_moisture=plant_data["current_moisture"],
            threshold=plant_data["threshold"],
            user_id=user_id,
            config=config,
        )
        if request_id:
            request_ids.append(request_id)
    
    # Handle shared pump plants - send selection notification
    if shared_pump_plants:
        self._send_plant_selection_notification(
            unit_id=unit_id,
            plants=shared_pump_plants,
            user_id=user_id,
        )
    
    return request_ids[0] if request_ids else None

def _send_plant_selection_notification(
    self,
    unit_id: int,
    plants: List[Dict[str, Any]],
    user_id: int,
) -> None:
    """
    Send notification for user to select which plants to irrigate.
    
    Used when multiple plants share a single pump.
    """
    plant_options = []
    for p in plants:
        plant = p["plant"]
        plant_options.append({
            "plant_id": plant.plant_id,
            "plant_name": plant.plant_name,
            "current_moisture": p["current_moisture"],
            "threshold": p["threshold"],
            "deficit": p["threshold"] - p["current_moisture"],
        })
    
    # Sort by deficit (most thirsty first)
    plant_options.sort(key=lambda x: x["deficit"], reverse=True)
    
    message = (
        f"{len(plants)} plants need water but share a pump. "
        "Select which plants to irrigate:"
    )
    
    self._notifications.send_notification(
        user_id=user_id,
        notification_type=NotificationType.IRRIGATION_SELECTION,
        title="🌱 Multiple Plants Need Water",
        message=message,
        severity=NotificationSeverity.WARNING,
        unit_id=unit_id,
        requires_action=True,
        action_type="irrigation_selection",
        action_data={
            "unit_id": unit_id,
            "plants": plant_options,
            "allow_multiple": True,
        },
    )
```

---

### Step 7: Update `_execute_irrigation()` to Use Calculator

**File:** `app/services/application/irrigation_workflow_service.py`

```python
def _execute_irrigation(self, request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute irrigation with calculated duration.
    
    Uses IrrigationCalculator for data-driven duration instead of hardcoded 30s.
    """
    actuator_id = request.get("actuator_id")
    plant_id = request.get("plant_id")
    unit_id = request["unit_id"]
    
    if not actuator_id:
        # Find pump for unit/plant
        actuator_id = self._find_pump_for_request(request)
    
    if not actuator_id:
        return {"ok": False, "error": "No pump available"}
    
    # Calculate irrigation parameters
    if self._irrigation_calculator and plant_id:
        # Get pump flow rate
        flow_rate = self._pump_calibration.get_flow_rate(actuator_id) if self._pump_calibration else None
        
        calculation = self._irrigation_calculator.calculate(
            plant_id=plant_id,
            pump_flow_rate=flow_rate,
        )
        
        duration = calculation.duration_seconds
        calculated_volume = calculation.water_volume_ml
        
        logger.info(
            f"Irrigation calculation for plant {plant_id}: "
            f"{calculated_volume:.1f}ml over {duration}s "
            f"(confidence: {calculation.confidence:.0%})"
        )
    else:
        # Fallback to config or default
        config = self.get_config(unit_id)
        duration = getattr(config, "default_duration_seconds", 30)
        calculated_volume = None
    
    # Execute pump
    start_time = utc_now()
    success = self._actuator_manager.turn_on(
        actuator_id,
        duration_seconds=duration,
        reason=f"irrigation_request_{request['request_id']}",
    )
    end_time = utc_now()
    
    # Record result
    actual_duration = (end_time - start_time).total_seconds()
    
    self._repo.record_execution(
        request_id=request["request_id"],
        actuator_id=actuator_id,
        duration_seconds=actual_duration,
        calculated_volume_ml=calculated_volume,
        success=success,
    )
    
    return {
        "ok": success,
        "actuator_id": actuator_id,
        "duration_seconds": actual_duration,
        "calculated_volume_ml": calculated_volume,
    }
```

---

### Step 8: Move UI to Settings > Automation Tab

**File:** `templates/settings.html` (add under Automation tab)

```html
<!-- Irrigation Settings Section -->
<div class="settings-section" id="irrigation-settings">
    <h5 class="mb-3 border-bottom pb-2">
        <i class="fas fa-tint me-2"></i>Irrigation Configuration
    </h5>
    
    <!-- Pump Calibration -->
    <div class="calibration-section mb-4 p-3 bg-light rounded">
        <h6 class="mb-3"><i class="fas fa-flask me-2"></i>Pump Calibration</h6>
        <p class="text-muted small mb-3">
            Calibrate your pump's flow rate for accurate water delivery calculations.
        </p>
        
        <div class="row g-3">
            <div class="col-md-6">
                {{ ui.select_field('calibration-pump', 'Select Pump', 
                    pump_options, name_attr='calibration_pump_id') }}
            </div>
            <div class="col-md-3">
                {{ ui.form_field('calibration-duration', 'Test Duration (sec)', 
                    type='number', value='30', min=10, max=120, 
                    name_attr='calibration_duration') }}
            </div>
            <div class="col-md-3 d-flex align-items-end">
                <button type="button" id="start-calibration" class="btn btn-primary w-100">
                    <i class="fas fa-play me-2"></i>Start Calibration
                </button>
            </div>
        </div>
        
        <!-- Calibration Result Entry -->
        <div id="calibration-result-entry" class="mt-3" style="display: none;">
            <div class="alert alert-info">
                <i class="fas fa-ruler me-2"></i>
                Pump ran for <span id="calibration-actual-duration">30</span> seconds.
                Measure the collected water and enter the volume below.
            </div>
            <div class="row g-3">
                <div class="col-md-6">
                    {{ ui.form_field('measured-volume', 'Measured Volume (ml)', 
                        type='number', min=1, max=10000, step=1,
                        name_attr='measured_volume_ml',
                        help_text='Volume of water collected during calibration') }}
                </div>
                <div class="col-md-6 d-flex align-items-end gap-2">
                    <button type="button" id="complete-calibration" class="btn btn-success">
                        <i class="fas fa-check me-2"></i>Save Calibration
                    </button>
                    <button type="button" id="cancel-calibration" class="btn btn-outline-secondary">
                        Cancel
                    </button>
                </div>
            </div>
        </div>
        
        <!-- Current Calibration Status -->
        <div id="calibration-status" class="mt-3">
            <small class="text-muted">
                <span id="pump-calibration-info">No pump calibrated</span>
            </small>
        </div>
    </div>
    
    <!-- Irrigation Timing -->
    <h6 class="mb-3 mt-4">Default Timing Settings</h6>
    <div class="row g-3">
        <div class="col-md-4">
            {{ ui.form_field('default-irrigation-time', 'Default Irrigation Time', 
                type='time', value='21:00', name_attr='default_scheduled_time',
                help_text='When to run approved irrigations') }}
        </div>
        <div class="col-md-4">
            {{ ui.form_field('delay-increment', 'Delay Increment (min)', 
                type='number', value='60', min=15, max=180,
                name_attr='delay_increment_minutes',
                help_text='Time added when user clicks Delay') }}
        </div>
        <div class="col-md-4">
            {{ ui.form_field('max-delay', 'Max Delay (hours)', 
                type='number', value='24', min=1, max=72,
                name_attr='max_delay_hours') }}
        </div>
    </div>
    
    <!-- Moisture Thresholds -->
    <h6 class="mb-3 mt-4">Moisture Control</h6>
    <div class="row g-3">
        <div class="col-md-6">
            {{ ui.checkbox_field('auto-irrigation', 'Enable Automatic Irrigation', 
                checked=true, name_attr='auto_irrigation_enabled',
                help_text='Automatically detect when plants need water') }}
        </div>
        <div class="col-md-6">
            {{ ui.checkbox_field('require-approval', 'Require User Approval', 
                checked=true, name_attr='require_approval',
                help_text='Wait for user approval before irrigating') }}
        </div>
    </div>
    
    <!-- Safety Settings -->
    <h6 class="mb-3 mt-4">Safety Limits</h6>
    <div class="row g-3">
        <div class="col-md-4">
            {{ ui.form_field('max-duration', 'Max Pump Runtime (min)', 
                type='number', value='10', min=1, max=60,
                name_attr='max_pump_runtime_minutes',
                help_text='Safety cutoff for pump operation') }}
        </div>
        <div class="col-md-4">
            {{ ui.form_field('min-interval', 'Min Irrigation Interval (hr)', 
                type='number', value='4', min=1, max=48,
                name_attr='min_irrigation_interval_hours',
                help_text='Minimum time between irrigations') }}
        </div>
        <div class="col-md-4">
            {{ ui.form_field('request-expiry', 'Request Expiry (hr)', 
                type='number', value='48', min=12, max=168,
                name_attr='expiration_hours',
                help_text='Auto-expire unanswered requests') }}
        </div>
    </div>
    
    <!-- ML Learning -->
    <h6 class="mb-3 mt-4">Machine Learning</h6>
    <div class="row g-3">
        <div class="col-md-4">
            {{ ui.checkbox_field('ml-learning', 'Enable ML Learning', 
                checked=true, name_attr='ml_learning_enabled',
                help_text='Learn from your irrigation feedback') }}
        </div>
        <div class="col-md-4">
            {{ ui.checkbox_field('ml-threshold-adjust', 'Auto-Adjust Thresholds', 
                checked=false, name_attr='ml_threshold_adjustment_enabled',
                help_text='Automatically adjust based on feedback') }}
        </div>
        <div class="col-md-4">
            {{ ui.checkbox_field('feedback-enabled', 'Request Feedback', 
                checked=true, name_attr='request_feedback_enabled',
                help_text='Ask for feedback after irrigation') }}
        </div>
    </div>
</div>
```

---

### Step 9: Add New Notification Types

**File:** `app/enums/__init__.py` (or wherever NotificationType is defined)

```python
class NotificationType(str, Enum):
    # ... existing types ...
    THRESHOLD_PROPOSAL = "threshold_proposal"
    IRRIGATION_SELECTION = "irrigation_selection"
```

---

### Step 10: Update Bayesian Priors to Use PlantViewService

**File:** `app/services/ai/bayesian_threshold.py`

```python
def get_prior(
    self,
    plant_type: str,
    growth_stage: str,
) -> ThresholdBelief:
    """
    Get prior belief for a plant type and growth stage.
    
    Uses ThresholdService (which uses PlantViewService) for real plant-specific data.
    """
    prior_mean = self._get_threshold_from_service(plant_type, growth_stage)
    
    return ThresholdBelief(
        mean=prior_mean,
        variance=self._default_prior_variance,
        sample_count=0,
        last_updated=iso_now(),
        plant_type=plant_type,
        growth_stage=growth_stage,
    )

def _get_threshold_from_service(
    self,
    plant_type: str,
    growth_stage: str,
) -> float:
    """
    Get soil moisture threshold from ThresholdService.
    
    ThresholdService internally uses PlantViewService.plant_json_handler
    for plant-specific data lookup.
    """
    if self._threshold_service:
        try:
            thresholds = self._threshold_service.get_thresholds(plant_type, growth_stage)
            if thresholds and thresholds.soil_moisture:
                return thresholds.soil_moisture
        except Exception:
            pass
    
    # Fallback: Get directly from PlantViewService if available
    if self._plant_service:
        try:
            watering = self._plant_service.plant_json_handler.get_watering_schedule(plant_type)
            trigger = watering.get("soil_moisture_trigger")
            if trigger:
                return float(trigger)
        except Exception:
            pass
    
    # Ultimate fallback
    return 50.0
```

---

## API Endpoints to Add

### Pump Calibration API

```
POST /api/irrigation/calibration/start
    Body: { "actuator_id": int, "duration_seconds": int }
    Response: { "ok": true, "message": "...", "next_step": "..." }

POST /api/irrigation/calibration/complete
    Body: { "actuator_id": int, "measured_ml": float }
    Response: { "ok": true, "flow_rate_ml_per_second": float, ... }

GET /api/irrigation/calibration/<actuator_id>
    Response: { "calibrated": bool, "flow_rate_ml_per_second": float, ... }
```

### Threshold Proposal API

```
POST /api/irrigation/threshold-proposal/<plant_id>/apply
    Body: { "thresholds": { "soil_moisture": float, ... } }

POST /api/irrigation/threshold-proposal/<plant_id>/keep
    (No body, keeps current thresholds)

POST /api/irrigation/threshold-proposal/<plant_id>/customize
    Body: { "thresholds": { "soil_moisture": float, ... } }
```

### Plant Selection API

```
POST /api/irrigation/selection/<unit_id>
    Body: { "plant_ids": [int, ...] }
    (Creates irrigation requests for selected plants)
```

---

## Migration Required

```sql
-- Add pump calibration fields to Actuator metadata (JSON column)
-- No schema change needed if metadata is already JSON

-- Add notification types
-- No schema change needed if notification_type is TEXT

-- Add irrigation selection tracking
ALTER TABLE PendingIrrigationRequest ADD COLUMN selection_group_id TEXT;
ALTER TABLE PendingIrrigationRequest ADD COLUMN calculated_volume_ml REAL;
```

---

## Testing Checklist

- [ ] Pump calibration flow (start → measure → complete)
- [ ] ML feedback adjustment of flow rate
- [ ] IrrigationCalculator with different pot sizes
- [ ] IrrigationCalculator with different growing media
- [ ] Stage transition threshold proposal notification
- [ ] Threshold proposal Apply/Keep/Customize actions
- [ ] Multi-plant selection notification
- [ ] Per-plant irrigation with dedicated pumps
- [ ] Shared pump plant selection
- [ ] UI in Settings > Automation tab

---

## Dependencies

- `PlantViewService` for all plant data access
- `ThresholdService` for threshold lookups  
- `NotificationsService` for proposal/selection notifications
- `ActuatorManager` for pump control
- `ActuatorRepository` for calibration metadata storage
