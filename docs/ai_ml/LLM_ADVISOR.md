# LLM Advisor Service

**Natural language Q&A for plant care decisions**

---

## Overview

The LLM Advisor Service provides a natural language interface for asking plant care questions, diagnosing symptoms, and generating care plans. It uses any configured LLM backend (OpenAI, Anthropic, or local models) to provide contextual, actionable advice.

---

## Key Features

- **Free-form questions** — Ask anything about plant care in natural language
- **Symptom diagnosis** — Analyze plant issues and suggest treatments
- **Irrigation decisions** — Get "should I water now?" answers with rationale
- **Care plan generation** — Daily/weekly care instructions for specific plants
- **Confidence scoring** — Every answer includes reliability estimate (0-1)
- **Multi-provider support** — Works with OpenAI, Anthropic, or local models

---

## Quick Start

### Basic Usage

```python
from app.services.ai import LLMAdvisorService, DecisionQuery

advisor = container.optional_ai.llm_advisor

if advisor:
    response = advisor.ask(DecisionQuery(
        question="My basil leaves are curling inward. What should I do?",
        plant_type="basil",
        growth_stage="vegetative",
        environmental_data={
            "temperature": 28.0,
            "humidity": 55.0,
            "soil_moisture": 35.0
        }
    ))
    
    print(response.answer)
    print(f"Confidence: {response.confidence:.2f}")
    for action in response.suggested_actions:
        print(f"  • {action}")
else:
    print("LLM advisor not available (set LLM_PROVIDER)")
```

---

## API Reference

### ask()

**Purpose:** Ask any plant care question in natural language

**Parameters:**
- `query` (DecisionQuery) — Question and context
  - `question` (str) — The question to ask
  - `plant_type` (str, optional) — Plant species
  - `plant_id` (int, optional) — Specific plant ID
  - `growth_stage` (str, optional) — Current growth stage
  - `environmental_data` (dict, optional) — Current sensor readings
  - `symptoms` (List[str], optional) — Observed symptoms
  - `recent_actions` (List[str], optional) — Recent care activities

**Returns:** `DecisionResponse`
- `answer` (str) — Natural language answer
- `confidence` (float) — Reliability score (0.0-1.0)
- `suggested_actions` (List[str]) — Actionable next steps
- `warnings` (List[str]) — Potential issues or cautions

**Example:**
```python
response = advisor.ask(DecisionQuery(
    question="Should I transplant my tomato seedlings now?",
    plant_type="tomato",
    growth_stage="seedling",
    environmental_data={
        "temperature": 22.0,
        "light_hours": 14
    },
    recent_actions=["germinated 14 days ago", "first true leaves appeared"]
))

print(response.answer)
# "Yes, your tomato seedlings are ready for transplanting. The presence of 
#  true leaves and 14 days of growth indicate they're strong enough. Wait 
#  for a cloudy day or transplant in evening to reduce shock."

print(f"Confidence: {response.confidence:.2f}")  # 0.87

for action in response.suggested_actions:
    print(f"  • {action}")
# • Water seedlings 1 hour before transplanting
# • Prepare pots with well-draining soil
# • Transplant in evening or on cloudy day
# • Keep soil moist but not waterlogged for first week
```

---

### diagnose()

**Purpose:** Analyze plant symptoms and suggest treatments

**Parameters:**
- `symptoms` (List[str]) — Observed symptoms
  - `"yellowing_leaves"`, `"brown_spots"`, `"wilting"`, `"leaf_curl"`, etc.
- `plant_type` (str) — Plant species
- `environmental_data` (dict, optional) — Current conditions
- `recent_care` (List[str], optional) — Recent watering, fertilizing, etc.

**Returns:** `DecisionResponse`
- `answer` (str) — Diagnosis and treatment plan
- `confidence` (float) — Diagnostic confidence
- `suggested_actions` (List[str]) — Treatment steps
- `warnings` (List[str]) — Urgency notes

**Example:**
```python
diagnosis = advisor.diagnose(
    symptoms=["yellowing_leaves", "brown_spots", "wilting"],
    plant_type="tomato",
    environmental_data={
        "temperature": 30.0,
        "humidity": 45.0,
        "soil_moisture": 25.0
    },
    recent_care=["last watered 3 days ago", "no recent fertilization"]
)

print(diagnosis.answer)
# "Your tomato is showing signs of combined heat stress and water deficit.
#  The yellowing leaves, brown spots, and wilting are classic symptoms of
#  severe dehydration exacerbated by high temperature (30°C) and low humidity
#  (45%). The soil moisture at 25% is critically low."

for action in diagnosis.suggested_actions:
    print(f"  • {action}")
# • Water immediately until soil reaches 40-45% moisture
# • Move to cooler location or provide shade (target: 21-27°C)
# • Increase air circulation to reduce heat stress
# • Mist leaves to increase local humidity
# • Check for root damage after rehydration

for warning in diagnosis.warnings:
    print(f"  ⚠️  {warning}")
# • Urgent action required - plant may not recover if left untreated
```

---

### should_irrigate()

**Purpose:** Get irrigation decision with detailed rationale

**Parameters:**
- `plant_type` (str) — Plant species
- `environmental_data` (dict) — Current sensor readings
  - `soil_moisture` (float, required) — Current moisture level (%)
  - `temperature` (float, optional) — Temperature (°C)
  - `humidity` (float, optional) — Relative humidity (%)
- `last_irrigation` (datetime, optional) — Last watering timestamp
- `plant_stage` (str, optional) — Growth stage

**Returns:** `DecisionResponse`
- `answer` (str) — Yes/No with explanation
- `confidence` (float) — Decision confidence
- `suggested_actions` (List[str]) — Watering instructions

**Example:**
```python
decision = advisor.should_irrigate(
    plant_type="basil",
    environmental_data={
        "soil_moisture": 28.0,
        "temperature": 26.0,
        "humidity": 55.0
    },
    last_irrigation=datetime.now() - timedelta(days=2)
)

print(decision.answer)
# "Yes, water your basil now. Soil moisture at 28% is below the optimal
#  range (40-50% for basil in vegetative stage). The plant was last watered
#  2 days ago, and with current temperature (26°C) and humidity (55%),
#  water loss is moderate. Water until soil reaches 45-50% moisture."

print(f"Confidence: {decision.confidence:.2f}")  # 0.92

for action in decision.suggested_actions:
    print(f"  • {action}")
# • Water deeply until soil moisture reaches 45-50%
# • Check drainage to ensure no waterlogging
# • Monitor daily for next few days due to temperature
```

---

### care_plan()

**Purpose:** Generate daily/weekly care instructions

**Parameters:**
- `plant_type` (str) — Plant species
- `growth_stage` (str) — Current growth stage
- `environmental_data` (dict, optional) — Current conditions
- `duration` (str, optional) — "daily" | "weekly" | "monthly"

**Returns:** `DecisionResponse`
- `answer` (str) — Detailed care plan
- `suggested_actions` (List[str]) — Scheduled tasks

**Example:**
```python
care_plan = advisor.care_plan(
    plant_type="tomato",
    growth_stage="flowering",
    environmental_data={
        "temperature": 24.0,
        "humidity": 65.0,
        "light_hours": 14
    },
    duration="weekly"
)

print(care_plan.answer)
# "Weekly care plan for tomato in flowering stage:
#  
#  Daily:
#  - Check soil moisture and water when it drops below 40%
#  - Maintain temperature between 18-25°C (currently optimal at 24°C)
#  - Ensure 14-16 hours of light per day (currently 14h - increase if possible)
#  
#  Every 2-3 days:
#  - Gently shake plants to assist pollination
#  - Check for pests on undersides of leaves
#  - Remove any yellowing or dead leaves
#  
#  Weekly:
#  - Apply balanced fertilizer with higher phosphorus (NPK 5-10-10)
#  - Prune suckers from leaf axils
#  - Check and adjust support stakes
#  - Monitor for early blight or blossom end rot
#  
#  Monitor:
#  - Flower development and fruit set
#  - Any signs of nutrient deficiency (yellowing, curling)
#  - Pest activity (whiteflies, aphids common during flowering)"
```

---

## Decision Query Structure

### DecisionQuery

```python
@dataclass
class DecisionQuery:
    question: str                           # Required
    plant_type: Optional[str] = None
    plant_id: Optional[int] = None
    growth_stage: Optional[str] = None
    environmental_data: Optional[dict] = None
    symptoms: Optional[List[str]] = None
    recent_actions: Optional[List[str]] = None
```

**Tips for good questions:**
- ✅ Be specific: "My basil leaves are curling" > "My plant looks weird"
- ✅ Include context: Add environmental data when relevant
- ✅ Mention growth stage: Seedling vs mature plant matters
- ✅ List recent care: "Last watered 3 days ago" helps diagnosis

---

## Decision Response Structure

### DecisionResponse

```python
@dataclass
class DecisionResponse:
    answer: str                    # Natural language answer
    confidence: float              # 0.0-1.0 reliability score
    suggested_actions: List[str]   # Actionable next steps
    warnings: List[str]            # Cautions or urgent notes
```

**Confidence Levels:**
- **0.9-1.0** — High confidence (textbook scenario)
- **0.7-0.9** — Good confidence (standard diagnosis)
- **0.5-0.7** — Moderate confidence (requires monitoring)
- **<0.5** — Low confidence (consider expert consultation)

---

## System Prompt

The LLM Advisor uses a specialized system prompt:

```
You are an expert agricultural advisor AI with deep knowledge of plant 
physiology, environmental requirements, disease diagnosis, and integrated 
pest management.

Your role is to provide clear, actionable plant care advice based on:
- Environmental data (temperature, humidity, soil moisture, light)
- Plant symptoms and visual observations  
- Growth stage and species-specific requirements
- Recent care activities and user actions

Guidelines:
1. Be direct and actionable - users need clear next steps
2. Explain the "why" behind recommendations
3. Prioritize suggestions (urgent → important → optional)
4. Include confidence level (0.0-1.0) in your assessment
5. Warn about critical issues (e.g., "plant may die if not treated")
6. Use metric units (°C, %, cm) unless user specifies otherwise

Response format:
{
  "answer": "Direct answer to the question with explanation",
  "confidence": 0.0-1.0,
  "suggested_actions": ["Step 1", "Step 2", ...],
  "warnings": ["Warning 1", "Warning 2", ...] (if any)
}
```

---

## Integration Examples

### Web Interface Integration

```python
from flask import Blueprint, request, jsonify

advisor_bp = Blueprint('advisor', __name__)

@advisor_bp.route('/api/v1/advisor/ask', methods=['POST'])
def ask_advisor():
    data = request.json
    
    advisor = current_app.container.optional_ai.llm_advisor
    if not advisor:
        return jsonify({"error": "LLM advisor not available"}), 503
    
    query = DecisionQuery(
        question=data['question'],
        plant_type=data.get('plant_type'),
        environmental_data=data.get('environmental_data')
    )
    
    response = advisor.ask(query)
    
    return jsonify({
        "answer": response.answer,
        "confidence": response.confidence,
        "suggested_actions": response.suggested_actions,
        "warnings": response.warnings
    })
```

### Chat Interface

```python
class PlantCareChat:
    def __init__(self, advisor: LLMAdvisorService):
        self.advisor = advisor
        self.conversation_history = []
    
    def ask(self, question: str, plant_id: int = None):
        # Get plant context
        plant = plant_service.get_plant(plant_id) if plant_id else None
        
        # Get current environmental data
        env_data = None
        if plant:
            unit = growth_service.get_unit(plant.unit_id)
            env_data = unit.current_conditions
        
        # Build query
        query = DecisionQuery(
            question=question,
            plant_type=plant.plant_type if plant else None,
            growth_stage=plant.growth_stage if plant else None,
            environmental_data=env_data
        )
        
        # Get response
        response = self.advisor.ask(query)
        
        # Store in conversation history
        self.conversation_history.append({
            "question": question,
            "answer": response.answer,
            "timestamp": datetime.now()
        })
        
        return response
```

---

## API Endpoints

### POST /api/v1/advisor/ask

**Description:** Ask any plant care question

**Request:**
```json
{
  "question": "Should I water my tomatoes?",
  "plant_id": 1,
  "plant_type": "tomato",
  "growth_stage": "flowering",
  "environmental_data": {
    "temperature": 24.0,
    "humidity": 65.0,
    "soil_moisture": 35.0
  }
}
```

**Response:**
```json
{
  "answer": "Yes, water your tomatoes now. Soil moisture at 35% is below optimal (40-45% for flowering stage). With current temperature (24°C) and humidity (65%), water loss is moderate. Water until soil reaches 40-45% moisture.",
  "confidence": 0.89,
  "suggested_actions": [
    "Water deeply until soil moisture reaches 40-45%",
    "Check drainage to ensure proper water retention",
    "Monitor daily during flowering stage"
  ],
  "warnings": []
}
```

### POST /api/v1/advisor/diagnose

**Description:** Diagnose plant symptoms

**Request:**
```json
{
  "symptoms": ["yellowing_leaves", "brown_spots"],
  "plant_type": "tomato",
  "environmental_data": {
    "temperature": 30.0,
    "humidity": 45.0
  }
}
```

**Response:**
```json
{
  "answer": "Your tomato is showing signs of heat stress combined with possible nutrient deficiency...",
  "confidence": 0.76,
  "suggested_actions": [
    "Reduce temperature to 21-27°C range",
    "Increase humidity to 60-70%",
    "Check soil for nitrogen deficiency"
  ],
  "warnings": [
    "Heat stress can become critical above 32°C"
  ]
}
```

---

## Performance Considerations

### Response Times

**OpenAI (gpt-4o-mini):**
- Average: 500-800ms
- 95th percentile: 1200ms

**Anthropic (claude-3-5-haiku):**
- Average: 600-900ms
- 95th percentile: 1400ms

**Local (EXAONE 4.0 1.2B):**
- Raspberry Pi 5: 3-4 seconds
- Desktop (GPU): <1 second

### Token Usage

**Average tokens per query:**
- System prompt: ~200 tokens
- User query: ~150 tokens (with context)
- Response: ~300 tokens
- **Total: ~650 tokens per question**

**Cost estimates (1000 queries):**
- OpenAI gpt-4o-mini: ~$0.30
- Anthropic claude-3-5-haiku: ~$1.80
- Local: $0 (just electricity)

---

## Troubleshooting

### Issue: Advisor returns None

**Cause:** LLM backend not configured or unavailable

**Check configuration:**
```bash
python -c "from app.config import AppConfig; c = AppConfig(); \
  print('Provider:', c.llm_provider); \
  print('API Key:', c.llm_api_key[:10] if c.llm_api_key else 'NONE')"
```

**Verify advisor availability:**
```python
advisor = container.optional_ai.llm_advisor
if not advisor:
    print("LLM_PROVIDER not set or backend initialization failed")
```

### Issue: Low confidence scores

**Possible causes:**
- Ambiguous question ("My plant looks bad" is too vague)
- Missing context (no environmental data provided)
- Unusual scenario (outside training distribution)

**Improve confidence:**
```python
# ❌ Vague question
query = DecisionQuery(question="My plant looks bad")

# ✅ Specific question with context
query = DecisionQuery(
    question="My tomato leaves are yellowing from bottom up. Is this nitrogen deficiency?",
    plant_type="tomato",
    growth_stage="vegetative",
    environmental_data={"temperature": 24.0, "humidity": 65.0},
    recent_actions=["last fertilized 2 weeks ago"]
)
```

### Issue: Slow responses (local model)

**Optimizations:**
```bash
# Enable 4-bit quantization
LLM_LOCAL_QUANTIZE=true

# Reduce max tokens
LLM_MAX_TOKENS=256  # Instead of 512

# Use smaller model
LLM_LOCAL_MODEL_PATH=Qwen/Qwen2.5-0.5B-Instruct
```

---

## Best Practices

### 1. Provide Context

```python
# ❌ Without context
advisor.ask(DecisionQuery(question="Should I water?"))

# ✅ With full context
advisor.ask(DecisionQuery(
    question="Should I water?",
    plant_type="basil",
    environmental_data={"soil_moisture": 30.0, "temperature": 26.0}
))
```

### 2. Use Convenience Methods

```python
# ❌ Generic question
advisor.ask(DecisionQuery(question="Should I water my basil?"))

# ✅ Dedicated method
advisor.should_irrigate(plant_type="basil", environmental_data={...})
```

### 3. Handle Errors Gracefully

```python
if not advisor:
    # Fallback to rule-based recommendations
    recommendations = rule_based_provider.get_recommendations(context)
else:
    response = advisor.ask(query)
    if response.confidence < 0.5:
        # Low confidence - consider additional diagnostics
        print(f"⚠️  Low confidence ({response.confidence:.2f})")
```

---

## Related Documentation

- **[LLM Setup Guide](LLM_SETUP.md)** — Configure OpenAI, Anthropic, or local models
- **[AI Services Overview](README.md)** — Complete AI feature guide
- **[Quick Reference](QUICK_REFERENCE.md)** — Code snippets
- **[FAQ](FAQ.md)** — Common questions

---

**Questions?** Check the [FAQ](FAQ.md) or open an issue on GitHub.
