# LLM Interface Setup Guide

**Complete guide to integrating ChatGPT, Claude, or local AI models into SYSGrow**

---

## Overview

SYSGrow's LLM interface enables natural language plant care recommendations and decision-making through three backend providers:

1. **OpenAI (ChatGPT)** — cloud-based, requires API key
2. **Anthropic (Claude)** — cloud-based, requires API key
3. **Local Models** — privacy-first, runs on-device (EXAONE 4.0 1.2B or any HuggingFace model)

**Architecture:**
```
┌─────────────────────────────────────────┐
│   Application Layer                     │
│   ┌──────────────────────────────────┐  │
│   │  LLMRecommendationProvider       │  │
│   │  LLMAdvisorService               │  │
│   └────────────┬─────────────────────┘  │
│                │                         │
│   ┌────────────▼─────────────────────┐  │
│   │  LLMBackend (ABC)                │  │
│   ├──────────────────────────────────┤  │
│   │ • OpenAIBackend                  │  │
│   │ • AnthropicBackend               │  │
│   │ • LocalTransformersBackend       │  │
│   └──────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

---

## Quick Start

### 1. Choose Your Provider

**OpenAI (Recommended for cloud)**
```bash
# .env or ops.env
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-xxxxxxxxxxxx
LLM_MODEL=gpt-4o-mini
```

**Anthropic Claude**
```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-xxxxxxxxxxxx
LLM_MODEL=claude-3-5-haiku-latest
```

**Local Model (Privacy-first)**
```bash
LLM_PROVIDER=local
LLM_LOCAL_MODEL_PATH=LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct
LLM_LOCAL_DEVICE=auto
LLM_LOCAL_QUANTIZE=true
```

### 2. Install Dependencies

**OpenAI:**
```bash
pip install openai
```

**Anthropic:**
```bash
pip install anthropic
```

**Local models:**
```bash
pip install torch transformers

# Optional: for 4-bit quantization (Raspberry Pi)
pip install bitsandbytes
```

### 3. Restart Application

```bash
python smart_agriculture_app.py
```

---

## Provider Configuration

### OpenAI (ChatGPT)

#### Basic Setup

```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-proj-...
LLM_MODEL=gpt-4o-mini  # Recommended: fast & cheap
LLM_MAX_TOKENS=512
LLM_TEMPERATURE=0.3
LLM_TIMEOUT=30
```

#### Model Options

| Model | Speed | Cost | Quality | Best For |
|-------|-------|------|---------|----------|
| `gpt-4o-mini` | ⚡⚡⚡ | 💰 | ⭐⭐⭐ | **Recommendations** (default) |
| `gpt-4o` | ⚡⚡ | 💰💰💰 | ⭐⭐⭐⭐⭐ | Complex diagnostics |
| `gpt-3.5-turbo` | ⚡⚡⚡ | 💰 | ⭐⭐ | Budget option |

#### Azure OpenAI

```bash
LLM_PROVIDER=openai
LLM_API_KEY=<azure-key>
LLM_BASE_URL=https://your-resource.openai.azure.com/
LLM_MODEL=gpt-4o-mini
```

#### Custom Proxy

```bash
LLM_PROVIDER=openai
LLM_BASE_URL=https://your-proxy.com/v1
LLM_API_KEY=your-proxy-key
```

#### Verification

```bash
# Test OpenAI connection
python -c "from app.services.ai.llm_backends import create_backend; \
  b = create_backend('openai', api_key='sk-...', model='gpt-4o-mini'); \
  print('Available:', b.is_available); \
  r = b.generate('You are a plant expert.', 'What is photosynthesis?'); \
  print(r.content[:100])"
```

---

### Anthropic (Claude)

#### Basic Setup

```bash
LLM_PROVIDER=anthropic
LLM_API_KEY=sk-ant-...
LLM_MODEL=claude-3-5-haiku-latest  # Recommended: fast & smart
LLM_MAX_TOKENS=512
LLM_TEMPERATURE=0.3
LLM_TIMEOUT=30
```

#### Model Options

| Model | Speed | Cost | Quality | Best For |
|-------|-------|------|---------|----------|
| `claude-3-5-haiku-latest` | ⚡⚡⚡ | 💰 | ⭐⭐⭐⭐ | **Recommendations** (default) |
| `claude-sonnet-4-20250514` | ⚡⚡ | 💰💰 | ⭐⭐⭐⭐⭐ | Complex reasoning |
| `claude-3-opus-latest` | ⚡ | 💰💰💰💰 | ⭐⭐⭐⭐⭐ | Research-grade |

#### Custom Base URL

```bash
LLM_PROVIDER=anthropic
LLM_BASE_URL=https://your-proxy.com
LLM_API_KEY=your-key
```

#### Verification

```bash
python -c "from app.services.ai.llm_backends import create_backend; \
  b = create_backend('anthropic', api_key='sk-ant-...', model='claude-3-5-haiku-latest'); \
  print('Available:', b.is_available); \
  r = b.generate('You are a plant expert.', 'What causes yellowing leaves?'); \
  print(r.content[:100])"
```

---

### Local Models (HuggingFace)

#### EXAONE 4.0 1.2B (Recommended)

**Best for:** Raspberry Pi, privacy, offline operation

```bash
LLM_PROVIDER=local
LLM_LOCAL_MODEL_PATH=LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct
LLM_LOCAL_DEVICE=auto  # Automatically detects: cuda > mps > cpu
LLM_LOCAL_QUANTIZE=true  # 4-bit quantization (2GB → 500MB)
LLM_LOCAL_TORCH_DTYPE=float16
LLM_MAX_TOKENS=512
LLM_TEMPERATURE=0.3
```

**First run downloads model (~2GB):**
```bash
# Automatic download on first use
python smart_agriculture_app.py
# Model cached to: ~/.cache/huggingface/hub/
```

**Manual pre-download:**
```bash
python -c "from transformers import AutoTokenizer, AutoModelForCausalLM; \
  AutoTokenizer.from_pretrained('LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct'); \
  AutoModelForCausalLM.from_pretrained('LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct')"
```

#### Alternative Models

**Llama 3.2 1B:**
```bash
LLM_LOCAL_MODEL_PATH=meta-llama/Llama-3.2-1B-Instruct
```

**Qwen 2.5 0.5B (Smallest):**
```bash
LLM_LOCAL_MODEL_PATH=Qwen/Qwen2.5-0.5B-Instruct
LLM_LOCAL_QUANTIZE=false  # Already tiny
```

**Phi-3.5-mini (Microsoft):**
```bash
LLM_LOCAL_MODEL_PATH=microsoft/Phi-3.5-mini-instruct
```

#### Device Selection

```bash
# Auto (recommended)
LLM_LOCAL_DEVICE=auto  # cuda > mps > cpu

# Explicit GPU (NVIDIA)
LLM_LOCAL_DEVICE=cuda

# Apple Silicon GPU
LLM_LOCAL_DEVICE=mps

# CPU only
LLM_LOCAL_DEVICE=cpu
```

#### Quantization Options

**4-bit (Recommended for Pi):**
```bash
LLM_LOCAL_QUANTIZE=true
LLM_LOCAL_TORCH_DTYPE=float16
# Memory: ~500MB for 1.2B model
```

**No quantization (Desktop GPU):**
```bash
LLM_LOCAL_QUANTIZE=false
LLM_LOCAL_TORCH_DTYPE=float32
# Memory: ~2GB for 1.2B model
```

#### Performance Benchmarks

**Raspberry Pi 5 (8GB):**
| Model | Quantization | Memory | Speed | Quality |
|-------|--------------|--------|-------|---------|
| EXAONE 4.0 1.2B | 4-bit | ~600MB | 3-4s | ⭐⭐⭐ |
| Qwen 2.5 0.5B | None | ~400MB | 2-3s | ⭐⭐ |
| Llama 3.2 1B | 4-bit | ~550MB | 3-5s | ⭐⭐⭐ |

**Desktop (NVIDIA RTX 3060):**
| Model | Quantization | Memory | Speed | Quality |
|-------|--------------|--------|-------|---------|
| EXAONE 4.0 1.2B | None | ~2GB | <1s | ⭐⭐⭐ |
| Llama 3.2 3B | None | ~6GB | 1-2s | ⭐⭐⭐⭐ |

#### Verification

```bash
python -c "from app.services.ai.llm_backends import create_backend; \
  b = create_backend('local', \
    model='LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct', \
    device='auto', \
    quantize=True); \
  print('Available:', b.is_available); \
  print('Device:', b._device); \
  r = b.generate('You are a plant expert.', 'Name 3 common houseplants.'); \
  print(r.content)"
```

---

## Configuration Reference

### All Environment Variables

```bash
# === Provider Selection ===
LLM_PROVIDER=openai  # openai | anthropic | local | none
# none = use RuleBasedRecommendationProvider only

# === API Configuration (OpenAI / Anthropic) ===
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
LLM_BASE_URL=  # Optional: for Azure/proxies

# === Local Model Configuration ===
LLM_LOCAL_MODEL_PATH=LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct
LLM_LOCAL_DEVICE=auto  # auto | cuda | mps | cpu
LLM_LOCAL_QUANTIZE=true  # 4-bit quantization
LLM_LOCAL_TORCH_DTYPE=float16  # float16 | float32 | bfloat16

# === Generation Settings ===
LLM_MAX_TOKENS=512  # Response length limit
LLM_TEMPERATURE=0.3  # Creativity: 0.0 (deterministic) - 1.0 (creative)
LLM_TIMEOUT=30  # API call timeout (seconds)
```

### AppConfig Properties

```python
from app.config import AppConfig

config = AppConfig()

# Provider selection
config.llm_provider: str  # "openai" | "anthropic" | "local" | "none"

# API settings
config.llm_api_key: Optional[str]
config.llm_model: str
config.llm_base_url: Optional[str]

# Local model settings
config.llm_local_model_path: str
config.llm_local_device: str
config.llm_local_quantize: bool
config.llm_local_torch_dtype: str

# Generation settings
config.llm_max_tokens: int
config.llm_temperature: float
config.llm_timeout: int
```

---

## Usage Examples

### 1. Recommendation Provider (Automatic)

**The recommendation provider automatically uses LLM if configured, falls back to rules otherwise.**

```python
from app.services.ai import RecommendationContext

# Get AI container (automatically wired)
ai = app.container.ai

# Get recommendations (uses LLM if available)
context = RecommendationContext(
    plant_id=1,
    unit_id=1,
    plant_type="tomato",
    growth_stage="flowering",
    symptoms=["yellowing_leaves", "brown_spots"],
    environmental_data={
        "temperature": 32.0,
        "humidity": 45.0,
        "soil_moisture": 28.0
    }
)

recommendations = ai.recommendation_provider.get_recommendations(context)

for rec in recommendations:
    print(f"[{rec.priority}] {rec.action}")
    print(f"  {rec.rationale}")
    print(f"  Confidence: {rec.confidence:.2f}")
```

**Output (LLM-generated):**
```
[high] Increase watering frequency immediately
  Low soil moisture (28%) combined with high temperature (32°C) and low humidity (45%) indicates severe water stress. Yellowing leaves and brown spots are classic dehydration symptoms in tomatoes during flowering.
  Confidence: 0.92

[high] Improve air circulation and humidity
  Low humidity during flowering can reduce fruit set. Consider misting or adding humidity trays.
  Confidence: 0.85

[medium] Check for nutrient deficiency (nitrogen)
  Yellowing leaves during flowering may indicate nitrogen depletion as plant redirects resources to fruit development.
  Confidence: 0.71
```

---

### 2. LLM Advisor (Direct Questions)

**Ask free-form questions to the AI advisor.**

```python
from app.services.ai import LLMAdvisorService, DecisionQuery

# Get advisor (only available if LLM configured)
advisor = app.container.optional_ai.llm_advisor

if advisor:
    # Ask any plant care question
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
    print("Actions:", response.suggested_actions)
else:
    print("LLM advisor not available (LLM_PROVIDER=none)")
```

---

### 3. Convenience Methods

#### Diagnose Symptoms

```python
diagnosis = advisor.diagnose(
    symptoms=["yellowing_leaves", "wilting", "brown_spots"],
    plant_type="tomato",
    environmental_data={"temperature": 30.0}
)

print(diagnosis.answer)  # "Likely heat stress combined with..."
print(diagnosis.suggested_actions)  # ["Water deeply", "Provide shade", ...]
```

#### Should I Irrigate?

```python
decision = advisor.should_irrigate(
    plant_type="basil",
    environmental_data={
        "temperature": 26.0,
        "humidity": 50.0,
        "soil_moisture": 25.0
    }
)

print(decision.answer)  # "Yes, irrigate now. Soil moisture is critically low..."
print(decision.confidence)  # 0.95
```

#### Generate Care Plan

```python
care_plan = advisor.care_plan(
    plant_type="tomato",
    growth_stage="flowering",
    environmental_data=sensor_data
)

print(care_plan.answer)  # Detailed daily care instructions
```

---

### 4. Direct Backend Usage (Advanced)

```python
from app.services.ai.llm_backends import create_backend

# Create backend directly
backend = create_backend(
    provider="openai",
    api_key="sk-...",
    model="gpt-4o-mini",
    max_tokens=512,
    temperature=0.3
)

# Check availability
if backend.is_available:
    response = backend.generate(
        system_prompt="You are a plant disease expert.",
        user_prompt="What causes powdery mildew on roses?",
        max_tokens=256,
        temperature=0.2,
        json_mode=False
    )
    
    print(response.content)
    print(f"Tokens: {response.token_usage}")
    print(f"Latency: {response.latency_ms}ms")
```

---

## API Endpoints

### Ask Advisor

```bash
POST /api/v1/advisor/ask
Content-Type: application/json

{
  "question": "Should I water my tomatoes?",
  "plant_id": 1,
  "plant_type": "tomato",
  "growth_stage": "flowering",
  "environmental_data": {
    "temperature": 26.0,
    "humidity": 55.0,
    "soil_moisture": 30.0
  }
}
```

**Response:**
```json
{
  "answer": "Yes, water your tomatoes now. Soil moisture at 30% is below the optimal range...",
  "confidence": 0.87,
  "suggested_actions": [
    "Water deeply until soil moisture reaches 40-45%",
    "Check drainage to ensure proper water retention",
    "Monitor temperature - consider shade if consistently above 30°C"
  ]
}
```

### Get Recommendations

```bash
GET /api/v1/recommendations/unit/1?include_llm=true
```

**Response:**
```json
{
  "recommendations": [
    {
      "action": "Increase watering frequency",
      "priority": "high",
      "rationale": "Soil moisture at 28% is critically low for tomatoes in flowering stage",
      "confidence": 0.92,
      "category": "irrigation"
    }
  ],
  "provider": "llm",
  "fallback_used": false
}
```

---

## Troubleshooting

### LLM Not Working

**Check provider configuration:**
```bash
python -c "from app.config import AppConfig; c = AppConfig(); \
  print('Provider:', c.llm_provider); \
  print('API Key:', c.llm_api_key[:10] + '...' if c.llm_api_key else 'NONE'); \
  print('Model:', c.llm_model)"
```

**Check backend availability:**
```bash
python -c "from app.services.container_builder import ContainerBuilder; \
  from app.config import AppConfig; \
  cb = ContainerBuilder(AppConfig()); \
  ai = cb.build_ai_components(); \
  print('Provider type:', type(ai.recommendation_provider).__name__); \
  print('LLM available:', hasattr(ai.recommendation_provider, '_backend'))"
```

### OpenAI Errors

**Invalid API key:**
```
Error: Authentication failed. Check LLM_API_KEY.
```
→ Verify key at https://platform.openai.com/api-keys

**Rate limit:**
```
Error: Rate limit exceeded.
```
→ Upgrade tier or reduce `LLM_TEMPERATURE` for caching

**Timeout:**
```
Error: Request timeout after 30s.
```
→ Increase `LLM_TIMEOUT` or reduce `LLM_MAX_TOKENS`

### Anthropic Errors

**Invalid API key:**
```
Error: Authentication failed. Check LLM_API_KEY.
```
→ Verify key at https://console.anthropic.com/

**Model not found:**
```
Error: Model 'claude-xyz' not found.
```
→ Use exact model names from Anthropic docs

### Local Model Errors

**Out of memory:**
```
RuntimeError: CUDA out of memory
```
→ Enable quantization: `LLM_LOCAL_QUANTIZE=true`
→ Use smaller model: `Qwen/Qwen2.5-0.5B-Instruct`

**Model download fails:**
```
OSError: Unable to download model from HuggingFace
```
→ Check internet connection
→ Pre-download: `huggingface-cli download LGAI-EXAONE/EXAONE-4.0-1.2B-Instruct`

**Slow inference (>10s):**
→ Check device: `print(backend._device)` (should be `cuda` or `mps`, not `cpu`)
→ Enable quantization for CPU: `LLM_LOCAL_QUANTIZE=true`
→ Reduce max_tokens: `LLM_MAX_TOKENS=256`

**Torch not available:**
```
ModuleNotFoundError: No module named 'torch'
```
→ Install: `pip install torch transformers`

---

## Best Practices

### 1. Choose the Right Provider

**Use OpenAI/Claude if:**
- ✅ Internet connectivity is reliable
- ✅ Latency <1s is acceptable
- ✅ API costs are reasonable (~$0.001 per recommendation)
- ✅ Privacy is not critical

**Use local models if:**
- ✅ Privacy is essential (sensitive plant data)
- ✅ Offline operation required (greenhouses without internet)
- ✅ API costs are prohibitive (>1000 recommendations/day)
- ✅ Latency 3-5s is acceptable

### 2. Temperature Settings

```bash
# Deterministic (recommendations)
LLM_TEMPERATURE=0.1

# Balanced (default)
LLM_TEMPERATURE=0.3

# Creative (research, care plans)
LLM_TEMPERATURE=0.7
```

### 3. Token Limits

```bash
# Short recommendations (default)
LLM_MAX_TOKENS=512

# Detailed diagnostics
LLM_MAX_TOKENS=1024

# Quick yes/no answers
LLM_MAX_TOKENS=128
```

### 4. Caching (OpenAI)

Enable prompt caching to reduce costs:
```python
# System prompts are automatically cached
# Keep system prompts >1000 chars to trigger caching
```

### 5. Fallback Strategy

**Always ensure rule-based provider works:**
```python
# container_builder.py automatically falls back to rules
# Test fallback:
LLM_PROVIDER=none python smart_agriculture_app.py
```

---

## Cost Estimates

### OpenAI (gpt-4o-mini)

**Pricing:** $0.150 per 1M input tokens, $0.600 per 1M output tokens

**Per recommendation:**
- Input: ~800 tokens (system prompt + context)
- Output: ~300 tokens
- **Cost: ~$0.0003 per recommendation**

**Monthly (1000 recommendations/day):**
- Daily: $0.30
- Monthly: **~$9**

### Anthropic (claude-3-5-haiku)

**Pricing:** $0.80 per 1M input tokens, $4.00 per 1M output tokens

**Per recommendation:**
- Input: ~800 tokens
- Output: ~300 tokens
- **Cost: ~$0.0018 per recommendation**

**Monthly (1000 recommendations/day):**
- Daily: $1.80
- Monthly: **~$54**

### Local Models (EXAONE 4.0 1.2B)

**One-time:**
- Model download: ~2GB bandwidth
- Setup time: 5 minutes

**Ongoing:**
- Electricity (Raspberry Pi): ~$0.02/day
- Monthly: **~$0.60**

---

## Next Steps

- **[AI Services Overview](README.md)** — Complete AI feature guide
- **[Plant Health API](PLANT_HEALTH_API_REFERENCE.md)** — Health monitoring
- **[Architecture](../architecture/AI_ARCHITECTURE.md)** — System design

---

**Need help?** Open an issue on GitHub or check the [FAQ](FAQ.md).
