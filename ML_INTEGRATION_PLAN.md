# ML Integration Completion Plan

## Status: IrrigationPredictor exists but isn't connected to the workflow

### Missing Pieces

1. **Wire IrrigationPredictor to IrrigationCalculator**
   - IrrigationCalculator has ML hooks but doesn't call IrrigationPredictor
   - Need to pass IrrigationPredictor as `ml_predictor` parameter
   - Update container configuration to inject predictor

2. **Feedback Flow**
   - User feedback (too_little/just_right/too_much) goes to PumpCalibrationService
   - Need to ALSO send to IrrigationPredictor for threshold learning
   - Add irrigation_ml repository methods to store training data

3. **Next Irrigation Time Prediction**
   - Currently missing: prediction of WHEN next irrigation is needed
   - Need to track moisture decline rate
   - Predict time when moisture will hit threshold

4. **Automatic Threshold Adjustment**
   - Predictor calculates optimal threshold
   - Need workflow to actually apply adjustments (with user notification)

---

## Implementation Tasks

### Task 1: Create IrrigationMLRepository
**Priority: HIGH**

```python
# infrastructure/database/repositories/irrigation_ml.py

class IrrigationMLRepository:
    """Repository for irrigation ML training data."""
    
    def record_feedback(
        self,
        request_id: int,
        feedback_type: str,  # too_little/just_right/too_much
        user_id: int,
    ):
        """Record user feedback for ML training."""
        
    def get_training_data_for_model(
        self,
        model_name: str,
        unit_id: int,
        limit: int = 100,
    ) -> List[Dict]:
        """Get training data for a specific ML model."""
        
    def record_moisture_reading(
        self,
        unit_id: int,
        plant_id: int,
        moisture: float,
        timestamp: datetime,
    ):
        """Record moisture reading for decline rate calculation."""
```

**Tables needed:**
- `irrigation_feedback` - stores user feedback
- `moisture_history` - tracks moisture over time for predictions

---

### Task 2: Connect IrrigationPredictor to Workflow
**Priority: HIGH**

Update `app/services/application/irrigation_workflow_service.py`:

```python
class IrrigationWorkflowService:
    def __init__(
        self,
        # ... existing params ...
        irrigation_predictor: Optional[IrrigationPredictor] = None,
    ):
        self._predictor = irrigation_predictor
        
    def record_feedback(
        self,
        request_id: int,
        feedback: str,
    ):
        """Record feedback to BOTH pump calibration AND ML predictor."""
        # Existing pump calibration
        if self._pump_calibration:
            self._pump_calibration.adjust_from_feedback(...)
            
        # NEW: Also feed to predictor
        if self._predictor and self._irrigation_ml_repo:
            self._irrigation_ml_repo.record_feedback(
                request_id=request_id,
                feedback_type=feedback,
                user_id=...,
            )
```

---

### Task 3: Add Next Irrigation Time Prediction
**Priority: MEDIUM**

Create new service `app/services/ai/moisture_decline_predictor.py`:

```python
class MoistureDeclinePredictor:
    """Predicts when next irrigation is needed based on moisture decline rate."""
    
    def predict_next_irrigation_time(
        self,
        unit_id: int,
        plant_id: int,
        current_moisture: float,
        threshold: float,
    ) -> Tuple[datetime, float]:
        """
        Predict when moisture will hit threshold.
        
        Returns:
            (predicted_time, confidence)
        """
        # Get recent moisture readings
        history = self._repo.get_moisture_history(
            unit_id=unit_id,
            plant_id=plant_id,
            hours=72,  # Last 3 days
        )
        
        if len(history) < 5:
            return None, 0.0
            
        # Calculate decline rate (linear regression)
        decline_rate = self._calculate_decline_rate(history)
        
        # Predict time to threshold
        moisture_deficit = current_moisture - threshold
        hours_until_threshold = moisture_deficit / decline_rate
        
        predicted_time = utc_now() + timedelta(hours=hours_until_threshold)
        
        # Confidence based on R² of regression
        confidence = self._calculate_prediction_confidence(history, decline_rate)
        
        return predicted_time, confidence
```

---

### Task 4: Add Automatic Threshold Adjustment Workflow
**Priority: MEDIUM**

Add to `IrrigationWorkflowService`:

```python
async def check_and_propose_threshold_adjustments(self, unit_id: int):
    """
    Periodic task to check if thresholds should be adjusted based on ML.
    
    Runs daily/weekly to analyze feedback and propose optimizations.
    """
    if not self._predictor:
        return
        
    # Get current settings
    unit = self._unit_repo.get_unit(unit_id)
    plant = self._plant_service.get_active_plant(unit_id)
    
    # Get ML prediction
    prediction = self._predictor.predict_threshold(
        unit_id=unit_id,
        plant_type=plant.plant_type,
        growth_stage=plant.current_stage,
        current_threshold=unit.settings.soil_moisture_threshold,
    )
    
    # Only propose if confidence is high and change is significant
    if prediction.confidence > 0.7 and prediction.adjustment_amount > 3.0:
        # Send notification with comparison
        self._send_threshold_adjustment_notification(
            unit_id=unit_id,
            user_id=unit.user_id,
            current=prediction.current_threshold,
            proposed=prediction.optimal_threshold,
            reasoning=prediction.reasoning,
            confidence=prediction.confidence,
        )
```

---

### Task 5: Dashboard Enhancements
**Priority: LOW**

Add new API endpoint and widget:

```python
# API: GET /api/irrigation/predictions/<unit_id>
{
    "next_irrigation": {
        "predicted_time": "2026-01-15T14:30:00Z",
        "hours_from_now": 6.5,
        "confidence": 0.85,
        "current_moisture": 42.3,
        "threshold": 40.0
    },
    "threshold_optimization": {
        "current": 40.0,
        "recommended": 42.5,
        "adjustment": "increase",
        "confidence": 0.72,
        "reasoning": "Based on 23 feedbacks showing 'too little'"
    },
    "effectiveness_score": 0.88
}
```

Dashboard widget showing:
- **Next Irrigation**: "In 6.5 hours (2:30 PM)"
- **Threshold Status**: "Optimal" or "Adjustment Recommended"
- **Learning Progress**: "23 feedbacks analyzed"
- **Effectiveness**: "88% - Working well!"

---

### Task 6: Irrigation Effectiveness Tracking
**Priority: LOW**

Add new analytics:

```python
def calculate_irrigation_effectiveness(
    self,
    unit_id: int,
    days: int = 30,
) -> Dict[str, Any]:
    """
    Calculate how well irrigation is working.
    
    Metrics:
    - Success rate (just_right feedback %)
    - Over-watering rate (too_much %)
    - Under-watering rate (too_little %)
    - Average confidence score
    - Moisture stability (variance)
    """
```

Show in dashboard:
- Chart of moisture over time with irrigation events
- Feedback distribution pie chart
- Trend line showing improvement over time

---

### Task 7: Moisture Decline Rate Tracking
**Priority: MEDIUM**

Add background task to record moisture periodically:

```python
# In sensor update handler
def on_sensor_update(self, sensor_data: Dict):
    """When moisture sensor updates, record for ML."""
    if sensor_data.get("type") == "soil_moisture":
        self._irrigation_ml_repo.record_moisture_reading(
            unit_id=sensor_data["unit_id"],
            plant_id=sensor_data.get("plant_id"),
            moisture=sensor_data["value"],
            timestamp=utc_now(),
        )
```

This enables:
- Next irrigation time prediction
- Evaporation rate calculation
- Growing medium validation

---

## Database Migrations Needed

```sql
-- Migration: Add irrigation ML tables

CREATE TABLE irrigation_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id INTEGER NOT NULL,
    unit_id INTEGER NOT NULL,
    plant_id INTEGER,
    user_id INTEGER NOT NULL,
    feedback_type TEXT NOT NULL, -- too_little, just_right, too_much
    soil_moisture_detected REAL,
    soil_moisture_after REAL,
    execution_duration_seconds INTEGER,
    detected_at TEXT,
    executed_at TEXT,
    feedback_at TEXT NOT NULL,
    FOREIGN KEY (request_id) REFERENCES PendingIrrigationRequest(id)
);

CREATE TABLE moisture_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    unit_id INTEGER NOT NULL,
    plant_id INTEGER,
    sensor_id INTEGER,
    moisture_percent REAL NOT NULL,
    temperature_c REAL,
    humidity_percent REAL,
    recorded_at TEXT NOT NULL,
    FOREIGN KEY (unit_id) REFERENCES GrowthUnit(unit_id)
);

CREATE INDEX idx_moisture_history_unit_time 
    ON moisture_history(unit_id, recorded_at);
    
CREATE INDEX idx_irrigation_feedback_unit 
    ON irrigation_feedback(unit_id, feedback_at);
```

---

## Priority Order

**Phase 1 (Complete ML Learning):**
1. Create IrrigationMLRepository
2. Wire predictor to feedback flow
3. Test feedback collection

**Phase 2 (Next Irrigation Prediction):**
4. Add moisture history tracking
5. Implement decline rate predictor
6. Add API endpoint for predictions

**Phase 3 (Automation):**
7. Add automatic threshold adjustment workflow
8. Add effectiveness tracking
9. Dashboard analytics widget

**Phase 4 (Polish):**
10. Historical charts
11. Effectiveness reporting
12. Optimization suggestions

---

## Benefits After Completion

✅ **Self-Learning System**
- Automatically learns optimal thresholds from feedback
- Adjusts to each user's preferences
- Adapts to growing medium differences

✅ **Predictive Capabilities**
- Tells user WHEN next irrigation will be needed
- Predicts if user will approve (send notification accordingly)
- Learns user's preferred irrigation times

✅ **Reduced Maintenance**
- Fewer manual threshold adjustments needed
- System gets better over time
- Less over/under watering

✅ **Visibility**
- Dashboard shows learning progress
- Charts show irrigation effectiveness
- Confidence scores for all predictions

---

## Estimated Effort

- Phase 1: 4-6 hours
- Phase 2: 6-8 hours
- Phase 3: 4-6 hours
- Phase 4: 6-8 hours
- **Total: ~20-28 hours**

---

## Next Steps

Would you like me to:
1. **Implement Phase 1** (complete ML learning integration)?
2. **Implement Phase 2** (next irrigation time prediction)?
3. **Create all database migrations** first?
4. **Something else from the plan**?
