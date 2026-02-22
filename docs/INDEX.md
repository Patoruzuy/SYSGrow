# SYSGrow Documentation

> **Current version:** v3.0.0 · February 2026

---

## Getting Started

| Doc | Description |
|-----|-------------|
| [Quick Start](setup/QUICK_START.md) | Up and running in 5 minutes |
| [Installation Guide](setup/INSTALLATION_GUIDE.md) | Full setup with all options |
| [Windows Setup](setup/WINDOWS_INSTALL_GUIDE.md) | Windows-specific steps |
| [Enhanced Features](setup/ENHANCED_FEATURES_SETUP.md) | Camera, MQTT, Redis configuration |

---

## Architecture

| Doc | Description |
|-----|-------------|
| [Architecture Overview](architecture/ARCHITECTURE.md) | System layers, modules, and data flow |
| [AI Architecture](architecture/AI_ARCHITECTURE.md) | ML services, training pipeline, model lifecycle |
| [Persistence Strategy](architecture/PERSISTENCE_STRATEGY.md) | Database design decisions and SQLite usage |
| [Design Guide](architecture/DESIGN_GUIDE.md) | UI design system and CSS conventions |
| [Quick Start Guide](architecture/QUICK_START_GUIDE.md) | Developer onboarding checklist |

---

## API Reference

| Doc | Description |
|-----|-------------|
| [API Usage (JS client)](API_USAGE.md) | How to call the backend from `api.js` |
| [ML / AI API](api/ML_AI_API.md) | ML prediction, training, and health endpoints |
| [Actuator Endpoints](ACTUATOR_API_ENDPOINTS.md) | Actuator control and status API |
| [Device Schedule Class](api/DEVICE_SCHEDULE_CLASS.md) | `DeviceSchedule` model and schedule endpoints |
| [API Updates Summary](api/API_UPDATES_SUMMARY.md) | Changelog of API additions by release |
| [ESP32-C3 API](api/ESP32-C3-API-Documentation.md) | ESP32-C3 firmware integration reference |
| [ESP32-C6 Irrigation](api/ESP32-C6-Irrigation-Module-Implementation.md) | Irrigation module firmware integration |

---

## AI / ML

| Doc | Description |
|-----|-------------|
| [AI/ML Overview](ai_ml/README.md) | Index of all ML docs |
| [Irrigation ML Operations](ai_ml/IRRIGATION_ML_OPERATIONS.md) | Irrigation predictor models, gating, retraining |
| [Bayesian Learning](ai_ml/BAYESIAN_LEARNING.md) | Bayesian threshold optimizer |
| [Automated Retraining](ai_ml/AUTOMATED_RETRAINING.md) | Scheduled and drift-triggered retraining |
| [Climate Optimizer](ai_ml/CLIMATE_OPTIMIZER.md) | Climate prediction model |
| [Continuous Monitoring](ai_ml/CONTINUOUS_MONITORING.md) | Real-time ML health monitoring |
| [Plant Health Monitoring](ai_ml/PLANT_HEALTH_MONITORING.md) | Disease risk and health scoring |
| [Plant Health API](ai_ml/PLANT_HEALTH_API_REFERENCE.md) | Plant health endpoints reference |
| [LLM Advisor](ai_ml/LLM_ADVISOR.md) | LLM-based recommendation system |
| [LLM Setup](ai_ml/LLM_SETUP.md) | Configuring Ollama / OpenAI / Claude backends |
| [Quick Reference](ai_ml/QUICK_REFERENCE.md) | Common ML commands and patterns |
| [FAQ](ai_ml/FAQ.md) | Common ML questions |

---

## Hardware & Sensors

| Doc | Description |
|-----|-------------|
| [Sensor Integration Guide](SENSOR_INTEGRATION_GUIDE.md) | Wiring, calibration, and adding new sensor types |
| [Sensors Reference](hardware/sensors.md) | Supported sensor types and their schemas |
| [Actuators Reference](hardware/actuators.md) | Supported actuator types and control API |
| [Device Schedules Quick Ref](DEVICE_SCHEDULES_QUICK_REF.md) | Schedule API cheat sheet |
| [Plant Handler Quick Ref](PLANT_HANDLER_QUICK_REFERENCE.md) | Plant management API cheat sheet |
| [ESP32-C6 UX Recommendations](ESP32-C6-User-Experience-Recommendations.md) | UX guidelines for ESP32-C6 firmware |

---

## Features

| Doc | Description |
|-----|-------------|
| [Energy Monitoring Quick Ref](ENERGY_MONITORING_QUICK_REFERENCE.md) | Energy API cheat sheet |
| [Threshold Service Integration](THRESHOLD_SERVICE_INTEGRATION.md) | How thresholds integrate with AI and hardware |
| [Frontend Plant Health](FRONTEND_PLANT_HEALTH_IMPLEMENTATION.md) | Plant health UI integration guide |
| [Frontend Design](frontend-design.md) | UI component patterns and styling guide |
| [Configuration Reference](CONFIGURATION.md) | All environment variables and config keys |

---

## Project

| Doc | Description |
|-----|-------------|
| [Audit Executive Report](AUDIT_EXECUTIVE_REPORT.md) | Feb 2026 code audit — grades, findings, priorities |
| [Release Notes (EN)](../releases/v3.0.0-RELEASE-EN.md) | v3.0.0 changelog (English) |
| [Release Notes (ES)](../releases/v3.0.0-RELEASE-ES.md) | v3.0.0 changelog (Spanish) |
| [Backlog](../BACKLOG.md) | Open work items — security, infra, features, testing |

---

## Structure

```
docs/
├── INDEX.md                    ← you are here
├── AUDIT_EXECUTIVE_REPORT.md
├── CONFIGURATION.md
├── API_USAGE.md
├── ACTUATOR_API_ENDPOINTS.md
├── DEVICE_SCHEDULES_QUICK_REF.md
├── ENERGY_MONITORING_QUICK_REFERENCE.md
├── SENSOR_INTEGRATION_GUIDE.md
├── THRESHOLD_SERVICE_INTEGRATION.md
├── PLANT_HANDLER_QUICK_REFERENCE.md
├── FRONTEND_PLANT_HEALTH_IMPLEMENTATION.md
├── frontend-design.md
├── ESP32-C6-User-Experience-Recommendations.md
├── enhanced_plant_template.json
├── ai_ml/                      ← all ML/AI documentation
├── api/                        ← API references and changelogs
├── architecture/               ← system design and strategy
├── hardware/                   ← sensor and actuator references
└── setup/                      ← installation and configuration guides
```

When creating new documentation:
1. Place in the appropriate subdirectory (`setup/`, `architecture/`, `api/`, or `development/`)
2. Update this INDEX.md with a link and description
3. Cross-reference related documentation
4. Update the main README.md if necessary

---

## 📝 Documentation Standards

All documentation should:
- ✅ Use clear, descriptive titles
- ✅ Include a table of contents for long documents
- ✅ Provide code examples where applicable
- ✅ Link to related documentation
- ✅ Include date or version information
- ✅ Use emojis for visual navigation
- ✅ Follow Markdown best practices

---

## 🤝 Contributing

To contribute to documentation:
1. Follow the existing structure and style
2. Test all code examples
3. Use clear, concise language
4. Include screenshots where helpful
5. Update the index when adding new files

---

## 📧 Support

For questions or issues:
- Check the relevant documentation section
- Review [Troubleshooting](setup/WINDOWS_SUCCESS.md#troubleshooting)
- Open an issue on GitHub
- Contact the development team

---

**Last Updated:** November 9, 2025  
**Documentation Version:** 1.1.0
