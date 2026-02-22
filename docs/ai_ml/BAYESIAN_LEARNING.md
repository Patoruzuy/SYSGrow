# Bayesian Threshold Adjuster

**Self-learning irrigation threshold optimization**

---

## Overview

The Bayesian Threshold Adjuster uses Bayesian inference to continuously learn optimal soil moisture thresholds from user feedback. When users accept, reject, or delay irrigation suggestions, the system updates its beliefs about the correct threshold, becoming more accurate over time.

---

## Key Features

- **Continuous learning** — Improves from every user interaction
- **Probabilistic reasoning** — Maintains uncertainty estimates (confidence)
- **Feedback-driven** — Learns from accept/reject/delay actions
- **Notification hooks** — Alerts when thresholds shift significantly
- **User-specific** — Each user gets personalized threshold learning
- **Graceful degradation** — Falls back to defaults when confidence is low

---

## Quick Start

### Basic Usage

```python
from app.services.ai import BayesianThresholdAdjuster

adjuster = container.optional_ai.bayesian_adjuster

# Update beliefs from user feedback
result = adjuster.update_from_feedback(
    unit_id=1,
    user_id=1,
    accepted=False,  # User rejected irrigation
    feedback_type="too_early"
)

print(f"Old threshold: {result.old_threshold}%")
print(f"New threshold: {result.new_threshold}%")
print(f"Adjustment: {result.adjustment:.1f}%")
print(f"Confidence: {result.confidence:.2f}")
```

---

## API Reference

### update_from_feedback()

**Purpose:** Update threshold beliefs based on user feedback

**Parameters:**
- `unit_id` (int) — Growth unit ID
- `user_id` (int) — User who provided feedback
- `accepted` (bool) — True if user accepted irrigation, False if rejected/delayed
- `feedback_type` (str) — Reason for feedback
  - `"too_early"` — Threshold too high, soil still moist enough
  - `"too_late"` — Threshold too low, soil was already too dry
  - `"delay"` — User wanted to delay (slight adjustment)
  - `"manual"` — Manual watering (implicit acceptance)
- `current_moisture` (float, optional) — Soil moisture at feedback time

**Returns:** `ThresholdAdjustmentResult`
- `old_threshold` (float) — Previous optimal threshold (%)
- `new_threshold` (float) — Updated optimal threshold (%)
- `adjustment` (float) — Threshold change (%)
- `confidence` (float) — Belief confidence (0.0-1.0)
- `reason` (str) — Explanation for adjustment

**Example:**
```python
# User rejected irrigation at 45% moisture
result = adjuster.update_from_feedback(
    unit_id=1,
    user_id=1,
    accepted=False,
    feedback_type="too_early",
    current_moisture=45.0
)

print(result.reason)
# "User rejected irrigation at 45.0% moisture (feedback: too_early).
#  Lowering threshold by 3.2% to 41.8%."

print(f"Confidence: {result.confidence:.2f}")  # 0.67
```

---

### get_learned_threshold()

**Purpose:** Get current learned threshold for a unit

**Parameters:**
- `unit_id` (int) — Growth unit ID
- `user_id` (int, optional) — Get user-specific threshold

**Returns:** `LearnedThreshold`
- `threshold` (float) — Current optimal threshold (%)
- `confidence` (float) — Belief confidence (0.0-1.0)
- `feedback_count` (int) — Number of feedback events
- `last_updated` (datetime) — Last adjustment timestamp

**Example:**
```python
learned = adjuster.get_learned_threshold(unit_id=1, user_id=1)

print(f"Learned threshold: {learned.threshold:.1f}%")
print(f"Confidence: {learned.confidence:.2f}")
print(f"Based on {learned.feedback_count} feedback events")

if learned.confidence > 0.8:
    print("High confidence - reliable threshold")
else:
    print("Low confidence - still learning")
```

---

### reset_threshold()

**Purpose:** Reset threshold to default for a unit

**Parameters:**
- `unit_id` (int) — Growth unit ID
- `user_id` (int, optional) — Reset user-specific threshold only

**Example:**
```python
adjuster.reset_threshold(unit_id=1, user_id=1)
print("Threshold reset to default (45%)")
```

---

## Bayesian Update Algorithm

### How It Works

**1. Prior Belief:**
- Initial threshold: 45% (default for most plants)
- Initial confidence: 0.5 (moderate uncertainty)

**2. Likelihood:**
- User feedback provides evidence:
  - **"too_early"** → Threshold likely too high
  - **"too_late"** → Threshold likely too low
  - **"accept"** → Threshold is correct

**3. Posterior Calculation:**
```python
# Bayesian update formula
P(threshold | feedback) = P(feedback | threshold) × P(threshold) / P(feedback)

# In practice:
if feedback == "too_early":
    new_threshold = old_threshold - adjustment_size
    confidence += 0.05  # Increase confidence
elif feedback == "too_late":
    new_threshold = old_threshold + adjustment_size
    confidence += 0.05
elif feedback == "accept":
    new_threshold = old_threshold  # Reinforce current belief
    confidence += 0.1
```

**4. Adjustment Size:**
```python
adjustment_size = base_adjustment × (1 - confidence)

# Examples:
# confidence=0.3 → adjustment=5.0% × 0.7 = 3.5%
# confidence=0.7 → adjustment=5.0% × 0.3 = 1.5%
# confidence=0.9 → adjustment=5.0% × 0.1 = 0.5%
```

**Result:** As confidence increases, adjustments become smaller (more stable).

---

## Feedback Types

### "too_early"

**When to use:** User feels irrigation is premature; soil is still moist enough

**Effect:**
- Lowers threshold by 3-5% (depending on confidence)
- Increases confidence by 0.05
- Stores moisture level at rejection time

**Example scenario:**
```
System: "Irrigate now (moisture: 45%)"
User: [Rejects] "Too early, soil is still moist"
Result: Threshold 45% → 42%
```

---

### "too_late"

**When to use:** User feels irrigation should have happened earlier; soil is too dry

**Effect:**
- Raises threshold by 3-5%
- Increases confidence by 0.05
- Stores moisture level at feedback time

**Example scenario:**
```
System: "Irrigate now (moisture: 35%)"
User: [Rejects] "Too late, plant is already wilting"
Result: Threshold 35% → 38%
```

---

### "delay"

**When to use:** User wants to postpone irrigation (not now, but soon)

**Effect:**
- Lowers threshold by 1-2% (smaller adjustment)
- Slight confidence increase
- Less aggressive than "too_early"

**Example scenario:**
```
System: "Irrigate now (moisture: 43%)"
User: [Delays] "I'll water in 2 hours"
Result: Threshold 43% → 41.5%
```

---

### "accept" / "manual"

**When to use:** User accepts suggestion or waters manually

**Effect:**
- No threshold change
- Confidence increases by 0.1 (reinforces current belief)
- Signals "this threshold is correct"

**Example scenario:**
```
System: "Irrigate now (moisture: 42%)"
User: [Accepts] Waters plant
Result: Threshold stays at 42%, confidence 0.6 → 0.7
```

---

## Notification Callback

### Purpose

Fire custom callback when threshold adjustment exceeds tolerance

### Configuration

```python
adjuster = BayesianThresholdAdjuster(
    irrigation_ml_repo=ml_repo,
    workflow_repo=workflow_repo,
    threshold_service=threshold_service,
    notification_callback=lambda unit_id, user_id, result: 
        send_notification(
            user_id=user_id,
            title="Irrigation Threshold Updated",
            message=f"New optimal moisture: {result.new_threshold:.1f}% "
                    f"(was {result.old_threshold:.1f}%)"
        ),
    notification_tolerance=3.0  # Fire if adjustment >= 3%
)
```

### Example Callback

```python
def threshold_notification_callback(unit_id: int, user_id: int, result: ThresholdAdjustmentResult):
    """Send notification when threshold changes significantly"""
    
    unit = growth_service.get_unit(unit_id)
    
    notification = {
        "type": "threshold_update",
        "unit_id": unit_id,
        "unit_name": unit.name,
        "old_threshold": result.old_threshold,
        "new_threshold": result.new_threshold,
        "adjustment": result.adjustment,
        "confidence": result.confidence,
        "reason": result.reason
    }
    
    # Send via SocketIO
    socketio.emit('threshold_update', notification, room=f'user_{user_id}')
    
    # Store in database
    analytics_repo.store_insight(
        type="threshold_adjustment",
        unit_id=unit_id,
        severity="info",
        data=notification
    )
```

---

## Integration Examples

### Irrigation Workflow Integration

```python
from app.services.ai import IrrigationPredictor, BayesianThresholdAdjuster

predictor = container.ai.irrigation_predictor
adjuster = container.optional_ai.bayesian_adjuster

# 1. Get ML prediction
prediction = predictor.predict_irrigation(unit_id=1)

# 2. Check if user previously learned a better threshold
if adjuster:
    learned = adjuster.get_learned_threshold(unit_id=1, user_id=current_user.id)
    if learned.confidence > 0.7:
        # Use learned threshold instead of ML prediction
        optimal_threshold = learned.threshold
    else:
        optimal_threshold = prediction.threshold.optimal_threshold
else:
    optimal_threshold = prediction.threshold.optimal_threshold

# 3. Present to user
if current_moisture < optimal_threshold:
    show_irrigation_prompt(
        unit_id=1,
        current_moisture=current_moisture,
        optimal_threshold=optimal_threshold
    )

# 4. Process user response
if user_accepted:
    adjuster.update_from_feedback(
        unit_id=1,
        user_id=current_user.id,
        accepted=True,
        feedback_type="accept",
        current_moisture=current_moisture
    )
elif user_rejected_too_early:
    adjuster.update_from_feedback(
        unit_id=1,
        user_id=current_user.id,
        accepted=False,
        feedback_type="too_early",
        current_moisture=current_moisture
    )
```

---

### Scheduled Learning

```python
from app.workers import ScheduledTask

@ScheduledTask(interval=86400)  # Daily
def review_threshold_learning():
    """Review all learned thresholds and report on learning progress"""
    
    units = growth_service.get_active_units()
    
    for unit in units:
        learned = adjuster.get_learned_threshold(unit.id)
        
        if learned.confidence > 0.8:
            print(f"✅ Unit {unit.id}: High confidence ({learned.confidence:.2f})")
        elif learned.feedback_count < 10:
            print(f"⚠️  Unit {unit.id}: Needs more feedback ({learned.feedback_count} events)")
        else:
            print(f"📊 Unit {unit.id}: Learning... ({learned.confidence:.2f})")
```

---

## API Endpoints

### POST /api/v1/irrigation/feedback

**Description:** Submit user feedback for threshold learning

**Request:**
```json
{
  "unit_id": 1,
  "accepted": false,
  "feedback_type": "too_early",
  "current_moisture": 45.0
}
```

**Response:**
```json
{
  "old_threshold": 45.0,
  "new_threshold": 42.3,
  "adjustment": -2.7,
  "confidence": 0.68,
  "reason": "User rejected irrigation at 45.0% moisture (feedback: too_early). Lowering threshold by 2.7% to 42.3%."
}
```

### GET /api/v1/irrigation/learned-threshold/{unit_id}

**Description:** Get current learned threshold

**Response:**
```json
{
  "threshold": 42.3,
  "confidence": 0.68,
  "feedback_count": 12,
  "last_updated": "2026-02-14T10:30:00Z"
}
```

---

## Performance Considerations

### Memory Usage

- **Per unit:** ~200 bytes (threshold + confidence + metadata)
- **1000 units:** ~200KB
- Negligible impact

### Processing Time

- **Feedback processing:** <10ms
- **Bayesian update:** <5ms
- **Database write:** ~20ms
- **Total:** <50ms per feedback event

---

## Best Practices

### 1. Collect Sufficient Feedback

```python
learned = adjuster.get_learned_threshold(unit_id=1, user_id=1)

if learned.feedback_count < 10:
    print("⚠️  Learning in progress. Recommend collecting 10+ feedback events.")
elif learned.confidence < 0.7:
    print("⚠️  Low confidence. Review feedback quality.")
else:
    print("✅ Reliable learned threshold.")
```

### 2. Handle Edge Cases

```python
# Don't adjust too aggressively
if abs(result.adjustment) > 10:
    print("⚠️  Large adjustment detected. Review feedback.")
    
# Reset if confidence drops too low
if learned.confidence < 0.3 and learned.feedback_count > 20:
    print("⚠️  Low confidence despite feedback. Resetting threshold.")
    adjuster.reset_threshold(unit_id=1, user_id=1)
```

### 3. Monitor Learning Progress

```python
# Track adjustment history
adjustments = analytics_repo.get_insights(
    type="threshold_adjustment",
    unit_id=1,
    time_range="last_30d"
)

# Check for oscillation (unstable learning)
if len(adjustments) > 20:
    recent_adjustments = [a.data['adjustment'] for a in adjustments[-10:]]
    if all(abs(adj) < 1.0 for adj in recent_adjustments):
        print("✅ Stable learning (small adjustments)")
    else:
        print("⚠️  Unstable learning (large oscillations)")
```

---

## Troubleshooting

### Issue: Threshold keeps changing wildly

**Cause:** Conflicting feedback or inconsistent user behavior

**Check feedback history:**
```python
feedback_history = adjuster.get_feedback_history(unit_id=1, limit=20)

for fb in feedback_history:
    print(f"{fb.timestamp}: {fb.feedback_type} at {fb.moisture:.1f}%")
```

**Look for patterns:**
- Mixed feedback at similar moisture levels
- Frequent "too_early" followed by "too_late"
- Multiple users with different preferences

**Solution:**
- Use user-specific thresholds
- Increase notification_tolerance to reduce noise
- Reset threshold and start fresh

---

### Issue: Low confidence despite many feedback events

**Cause:** Inconsistent feedback quality or environmental variability

**Check confidence progression:**
```python
adjustments = analytics_repo.get_insights(
    type="threshold_adjustment",
    unit_id=1,
    order_by="timestamp"
)

for adj in adjustments:
    print(f"{adj.timestamp}: confidence={adj.data['confidence']:.2f}")
```

**Possible fixes:**
- Educate user on feedback types
- Check for sensor calibration issues
- Consider environmental factors (temperature affects optimal moisture)

---

## Related Documentation

- **[Irrigation ML Operations](IRRIGATION_ML_OPERATIONS.md)** — Complete irrigation ML guide
- **[AI Services Overview](README.md)** — All AI features
- **[Architecture](../architecture/AI_ARCHITECTURE.md)** — System design
- **[FAQ](FAQ.md)** — Common questions

---

**Questions?** Check the [FAQ](FAQ.md) or open an issue on GitHub.
