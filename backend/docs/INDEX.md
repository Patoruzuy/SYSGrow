# SYSGrow Documentation

> **Current version:** v3.0.0 · March 2026

## Getting Started

| Doc | Description |
|-----|-------------|
| [Quick Start](setup/QUICK_START.md) | Raspberry Pi-first install checklist |
| [Installation Guide](setup/INSTALLATION_GUIDE.md) | Full Raspberry Pi, Linux, and development setup |
| [Pre-Production Checklist](setup/PRE_PRODUCTION_CHECKLIST.md) | Final release gate before production deployment |
| [Windows Setup](setup/WINDOWS_INSTALL_GUIDE.md) | Windows-specific setup |
| [Enhanced Features](setup/ENHANCED_FEATURES_SETUP.md) | Optional camera and advanced integrations |
| [Deployment Guide](../deployment/DEPLOYMENT.md) | systemd, environment files, and production deployment |

## Architecture

| Doc | Description |
|-----|-------------|
| [Architecture Overview](architecture/ARCHITECTURE.md) | System layers, modules, and data flow |
| [AI Architecture](architecture/AI_ARCHITECTURE.md) | ML services, training pipeline, and model lifecycle |
| [Persistence Strategy](architecture/PERSISTENCE_STRATEGY.md) | Database design decisions and SQLite usage |

## API & Integration

| Doc | Description |
|-----|-------------|
| [ML / AI API](api/ML_AI_API.md) | ML prediction, training, and health endpoints |
| [Actuator Endpoints](ACTUATOR_API_ENDPOINTS.md) | Actuator control and status API |
| [Device Schedule Class](api/DEVICE_SCHEDULE_CLASS.md) | `DeviceSchedule` model and schedule endpoints |
| [ESP32-C3 API](api/ESP32-C3-API-Documentation.md) | ESP32-C3 firmware integration reference |
| [ESP32-C6 Irrigation](api/ESP32-C6-Irrigation-Module-Implementation.md) | Irrigation module firmware integration |
| [Device Schedules Quick Ref](DEVICE_SCHEDULES_QUICK_REF.md) | Schedule API cheat sheet |
| [Plant Handler Quick Ref](PLANT_HANDLER_QUICK_REFERENCE.md) | Plant management API cheat sheet |

## AI / ML

| Doc | Description |
|-----|-------------|
| [AI/ML Overview](ai_ml/README.md) | Index of all ML docs |
| [Irrigation ML Operations](ai_ml/IRRIGATION_ML_OPERATIONS.md) | Irrigation predictor models, gating, and retraining |
| [Bayesian Learning](ai_ml/BAYESIAN_LEARNING.md) | Bayesian threshold optimizer |
| [Automated Retraining](ai_ml/AUTOMATED_RETRAINING.md) | Scheduled and drift-triggered retraining |
| [Climate Optimizer](ai_ml/CLIMATE_OPTIMIZER.md) | Climate prediction model |
| [Continuous Monitoring](ai_ml/CONTINUOUS_MONITORING.md) | Real-time ML health monitoring |
| [Plant Health Monitoring](ai_ml/PLANT_HEALTH_MONITORING.md) | Disease risk and health scoring |
| [Plant Health API](ai_ml/PLANT_HEALTH_API_REFERENCE.md) | Plant health endpoints reference |
| [LLM Advisor](ai_ml/LLM_ADVISOR.md) | LLM-based recommendation system |
| [LLM Setup](ai_ml/LLM_SETUP.md) | Configuring Ollama, OpenAI, or Claude backends |
| [Quick Reference](ai_ml/QUICK_REFERENCE.md) | Common ML commands and patterns |
| [FAQ](ai_ml/FAQ.md) | Common ML questions |

## Hardware & Sensors

| Doc | Description |
|-----|-------------|
| [Sensor Integration Guide](SENSOR_INTEGRATION_GUIDE.md) | Wiring, calibration, and adding new sensor types |
| [Sensors Reference](hardware/sensors.md) | Supported sensor types and their schemas |
| [Actuators Reference](hardware/actuators.md) | Supported actuator types and control API |

## Operations & Configuration

| Doc | Description |
|-----|-------------|
| [Configuration Reference](CONFIGURATION.md) | Environment variables and config keys |
| [Energy Monitoring Quick Ref](ENERGY_MONITORING_QUICK_REFERENCE.md) | Energy API cheat sheet |
| [Release Notes](../releases/README.md) | Current curated release notes |

## Structure

```text
docs/
├── INDEX.md
├── CONFIGURATION.md
├── ACTUATOR_API_ENDPOINTS.md
├── DEVICE_SCHEDULES_QUICK_REF.md
├── ENERGY_MONITORING_QUICK_REFERENCE.md
├── PLANT_HANDLER_QUICK_REFERENCE.md
├── SENSOR_INTEGRATION_GUIDE.md
├── ai_ml/
├── api/
├── architecture/
├── hardware/
├── setup/
└── archive/        # engineering-history docs, not part of the public surface
```

## Archive Policy

`docs/archive/` stores audits, migration summaries, implementation notes, and
other engineering-history documents. Those files are preserved for maintainers
but are intentionally excluded from the public documentation index.

## Support

- Start with the setup guides in `docs/setup/`
- Review [Deployment](../deployment/DEPLOYMENT.md) for production setup
- Open an issue on GitHub if the published docs do not cover your case

**Last Updated:** March 8, 2026  
**Documentation Version:** 3.0.0
