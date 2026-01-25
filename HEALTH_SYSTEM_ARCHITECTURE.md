# Health Monitoring System - Visual Architecture

## Complete System Integration

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          YOUR SYSGROW APPLICATION                            │
│                              (Flask Backend)                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         SERVICE CONTAINER                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     HEALTH MONITORING SERVICES                        │   │
│  │                                                                       │   │
│  │  ┌──────────────────────────────────────────────────────────────┐    │   │
│  │  │          SystemHealthService (Central Coordinator)           │    │   │
│  │  │                                                               │    │   │
│  │  │  • Infrastructure monitoring (API, DB, storage, uptime)      │    │   │
│  │  │  • Aggregates health from all sources                        │    │   │
│  │  │  • Creates alerts for critical issues                        │    │   │
│  │  │  • Publishes health events                                   │    │   │
│  │  │  • Tracks API metrics                                        │    │   │
│  │  └─────┬─────────────┬──────────────┬───────────────┬───────────┘    │   │
│  │        │             │              │               │                │   │
│  │        ▼             ▼              ▼               ▼                │   │
│  │   ┌────────┐   ┌─────────┐   ┌──────────┐   ┌──────────┐           │   │
│  │   │ Health │   │ Anomaly │   │  Alert   │   │  Event   │           │   │
│  │   │Monitor │   │Detection│   │ Service  │   │   Bus    │           │   │
│  │   │Service │   │ Service │   │          │   │          │           │   │
│  │   └────────┘   └─────────┘   └──────────┘   └──────────┘           │   │
│  │        │             │              │               │                │   │
│  │        │             │              │               │                │   │
│  │   • Sensor      • Statistical  • Create       • Publish          │   │
│  │     health        outliers       alerts         events           │   │
│  │   • Success     • Rate of       • Manage       • Notify          │   │
│  │     rates         change         severity       subscribers      │   │
│  │   • Trends      • Stuck         • Track                          │   │
│  │                   values         history                         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                      OTHER SERVICES                                   │   │
│  │  • GrowthService      • DeviceService      • PlantService            │   │
│  │  • AnalyticsService   • SettingsService    • ThresholdService        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                            MIDDLEWARE LAYER                                  │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              HealthTrackingMiddleware (Flask)                         │   │
│  │                                                                       │   │
│  │  Every Request  →  Record Metrics  →  Update SystemHealthService     │   │
│  │                                                                       │   │
│  │  Tracks:  ✓ Success/failure    ✓ Response time    ✓ Error rate      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                          API ENDPOINTS                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    /api/health/* Endpoints                            │   │
│  │                                                                       │   │
│  │  GET  /ping          →  Basic liveness check                         │   │
│  │  GET  /detailed      →  Comprehensive health report                  │   │
│  │  GET  /storage       →  Storage usage statistics                     │   │
│  │  GET  /api-metrics   →  API performance metrics                      │   │
│  │  GET  /database      →  Database connection status                   │   │
│  │  GET  /infrastructure→  Infrastructure component status              │   │
│  │  POST /check-alerts  →  Manual health check + alert creation         │   │
│  │                                                                       │   │
│  │  Plus all existing endpoints:                                         │   │
│  │  GET  /system        →  Unit-level health                            │   │
│  │  GET  /units         →  All units health                             │   │
│  │  GET  /sensors/:id   →  Sensor health                                │   │
│  │  GET  /actuators/:id →  Actuator health                              │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       BACKGROUND TASKS                                       │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │              TaskScheduler (Every 5 minutes)                          │   │
│  │                                                                       │   │
│  │  ┌────────────────┐    ┌────────────────┐    ┌─────────────────┐    │   │
│  │  │ Refresh        │ →  │ Check          │ →  │ Check Sensor    │    │   │
│  │  │ Storage        │    │ Database       │    │ Health          │    │   │
│  │  └────────────────┘    └────────────────┘    └─────────────────┘    │   │
│  │                               ↓                                      │   │
│  │                    ┌──────────────────────┐                          │   │
│  │                    │ Create Alerts for    │                          │   │
│  │                    │ Critical Issues      │                          │   │
│  │                    └──────────────────────┘                          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         ALERT TRIGGERS                                       │
│                                                                              │
│  🔴 CRITICAL ALERTS                       🟡 WARNING ALERTS                 │
│  ├─ Storage > 90% used                    ├─ Storage > 75% used             │
│  ├─ Database disconnected                 ├─ API error rate > 10%           │
│  ├─ Sensor critical                       ├─ Sensor degraded                │
│  ├─ API offline (error rate > 50%)        ├─ Slow API responses             │
│  └─ System component failure              └─ Approaching limits             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW EXAMPLE                                    │
│                                                                              │
│  USER REQUEST                                                                │
│      ↓                                                                       │
│  HealthTrackingMiddleware  ────┐                                            │
│      ↓                          │                                            │
│  Your API Endpoint              │                                            │
│      ↓                          │                                            │
│  Response                       │                                            │
│      ↓                          │                                            │
│  HealthTrackingMiddleware  ◄───┘                                            │
│      ↓                                                                       │
│  Record: success=true, time=45ms                                             │
│      ↓                                                                       │
│  SystemHealthService.record_api_request(true, 45)                           │
│      ↓                                                                       │
│  Update metrics, calculate error rate                                        │
│      ↓                                                                       │
│  If error rate > threshold → Update API status                              │
│      ↓                                                                       │
│  If status changed → Publish event & create alert                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                   BACKGROUND HEALTH CHECK FLOW                               │
│                                                                              │
│  Every 5 minutes:                                                            │
│      ↓                                                                       │
│  TaskScheduler triggers health check                                         │
│      ↓                                                                       │
│  SystemHealthService.perform_full_health_check()                            │
│      ├─→ Refresh storage (psutil.disk_usage)                                │
│      ├─→ Check database (connection test)                                   │
│      ├─→ Get sensor health (HealthMonitoringService)                        │
│      └─→ Get active alerts (AlertService)                                   │
│      ↓                                                                       │
│  Analyze all metrics                                                         │
│      ↓                                                                       │
│  If storage > 90% → Create critical alert                                    │
│  If DB disconnected → Create critical alert                                  │
│  If sensors critical → Create sensor alert                                   │
│      ↓                                                                       │
│  Return: list of alert IDs created                                           │
│      ↓                                                                       │
│  Log results                                                                 │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                     HEALTH REPORT STRUCTURE                                  │
│                                                                              │
│  {                                                                           │
│    "timestamp": "2025-12-11T21:14:01Z",                                     │
│    "overall_status": "healthy|degraded|critical",                           │
│    "system_info": {                                                          │
│      "version": "1.0.0",                                                     │
│      "apiStatus": "online|degraded|offline",                                │
│      "dbStatus": "connected|error|unknown",                                 │
│      "uptime": 3600,  // seconds                                            │
│      "storageUsed": 983893344256,                                           │
│      "storageTotal": 1000186310656                                          │
│    },                                                                        │
│    "sensor_health": {                                                        │
│      "total_sensors": 10,                                                    │
│      "healthy_sensors": 8,                                                   │
│      "degraded_sensors": 2,                                                  │
│      "critical_sensors": 0,                                                  │
│      "offline_sensors": 0,                                                   │
│      "health_level": "healthy|degraded|critical",                           │
│      "average_success_rate": 95.5,                                          │
│      "issues": ["Sensor 3: High error rate", ...]                           │
│    },                                                                        │
│    "alerts": {                                                               │
│      "total_active": 1,                                                      │
│      "total_resolved": 15,                                                   │
│      "active_by_severity": {                                                 │
│        "info": 0,                                                            │
│        "warning": 1,                                                         │
│        "critical": 0                                                         │
│      }                                                                       │
│    },                                                                        │
│    "infrastructure_details": {                                               │
│      "storage": { /* full storage metrics */ },                             │
│      "api_metrics": { /* API performance */ },                              │
│      "database_status": "connected"                                         │
│    }                                                                         │
│  }                                                                           │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                        INTEGRATION POINTS                                    │
│                                                                              │
│  1. ServiceContainer                                                         │
│     └─→ Initializes all health services                                     │
│     └─→ Passes to TaskScheduler                                             │
│     └─→ Makes available to API endpoints                                    │
│                                                                              │
│  2. Flask App (__init__.py)                                                  │
│     └─→ Registers HealthTrackingMiddleware                                  │
│     └─→ Connects to SystemHealthService                                     │
│                                                                              │
│  3. Health API Blueprint                                                     │
│     └─→ Gets services from container                                        │
│     └─→ Exposes health endpoints                                            │
│                                                                              │
│  4. TaskScheduler                                                            │
│     └─→ Receives SystemHealthService + database                             │
│     └─→ Schedules health checks every 5 minutes                             │
└─────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
                              STATUS: ✅ COMPLETE
═══════════════════════════════════════════════════════════════════════════════
