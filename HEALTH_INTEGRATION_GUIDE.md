# System Health Integration Guide

## Overview

This guide shows how to integrate the health monitoring services into your application.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   SystemHealthService                        │
│              (Central Health Coordinator)                    │
│                                                              │
│  • Infrastructure monitoring (API, DB, Storage)              │
│  • Aggregates health from all sources                       │
│  • Creates alerts for critical issues                       │
│  • Publishes health events                                  │
└────────┬──────────────┬─────────────┬─────────────┬─────────┘
         │              │             │             │
         ▼              ▼             ▼             ▼
┌────────────┐  ┌─────────────┐  ┌──────────┐  ┌──────────┐
│   Health   │  │  Anomaly    │  │  Alert   │  │  Device  │
│ Monitoring │  │  Detection  │  │ Service  │  │  Health  │
│  Service   │  │   Service   │  │          │  │ Service  │
└────────────┘  └─────────────┘  └──────────┘  └──────────┘
```

## Step 1: Initialize Services

```python
# In your main.py or app initialization

from app.services.utilities.system_health_service import SystemHealthService
from app.services.utilities.health_monitoring_service import HealthMonitoringService
from app.services.utilities.anomaly_detection_service import AnomalyDetectionService
from app.services.application.alert_service import AlertService
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

# Initialize database
db_handler = SQLiteDatabaseHandler("path/to/database.db")

# Initialize services
alert_service = AlertService(database=db_handler)
health_monitoring = HealthMonitoringService()
anomaly_service = AnomalyDetectionService()

# Create central health coordinator
system_health = SystemHealthService(
    health_monitoring_service=health_monitoring,
    anomaly_service=anomaly_service,
    alert_service=alert_service
)
```

## Step 2: Add Health Tracking Middleware

```python
# In your FastAPI app setup

from fastapi import FastAPI
from app.middleware.health_tracking_middleware import HealthTrackingMiddleware

app = FastAPI()

# Add health tracking middleware
app.add_middleware(
    HealthTrackingMiddleware,
    system_health_service=system_health
)
```

## Step 3: Create Health Check Endpoints

```python
# In your router (e.g., app/routers/health.py)

from fastapi import APIRouter, Depends
from typing import Dict, Any

router = APIRouter(prefix="/health", tags=["health"])

@router.get("/")
async def basic_health_check() -> Dict[str, str]:
    """Basic health check - always returns 200 if API is running."""
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """Detailed health check with all system metrics."""
    # Perform full health check
    report = system_health.perform_full_health_check(db_handler=db_handler)
    return report

@router.get("/storage")
async def storage_health() -> Dict[str, Any]:
    """Get storage usage statistics."""
    return system_health.refresh_storage_usage()

@router.get("/api-metrics")
async def api_metrics() -> Dict[str, Any]:
    """Get API performance metrics."""
    return system_health.get_api_metrics()

@router.get("/database")
async def database_health() -> Dict[str, str]:
    """Check database connection health."""
    status = system_health.check_database_health(db_handler=db_handler)
    return {
        "status": status,
        "timestamp": datetime.utcnow().isoformat()
    }
```

## Step 4: Add Background Health Monitoring

```python
# In your main.py - add a background task

import asyncio
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan with background health monitoring."""
    
    # Start background health monitoring
    health_task = asyncio.create_task(background_health_monitor())
    
    yield
    
    # Cleanup on shutdown
    health_task.cancel()
    system_health.shutdown()

async def background_health_monitor():
    """Background task to periodically check health and create alerts."""
    while True:
        try:
            # Check every 5 minutes
            await asyncio.sleep(300)
            
            # Refresh storage
            system_health.refresh_storage_usage()
            
            # Check database
            system_health.check_database_health(db_handler=db_handler)
            
            # Check for health issues and create alerts
            alert_ids = system_health.check_and_alert_on_health_issues()
            
            if alert_ids:
                logger.info(f"Created {len(alert_ids)} health alerts")
            
        except asyncio.CancelledError:
            logger.info("Health monitoring task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in health monitoring: {e}")

# Use lifespan
app = FastAPI(lifespan=lifespan)
```

## Step 5: Manual Health Checks

You can also manually trigger health checks:

```python
# In your code, whenever needed

# Check storage
storage_info = system_health.refresh_storage_usage()
print(f"Storage: {storage_info['percent']}% used")

# Check database
db_status = system_health.check_database_health(db_handler)
print(f"Database: {db_status}")

# Get comprehensive report
report = system_health.perform_full_health_check(db_handler)
print(f"Overall status: {report['overall_status']}")

# Check for issues and alert
alert_ids = system_health.check_and_alert_on_health_issues()
if alert_ids:
    print(f"Created {len(alert_ids)} alerts")
```

## Step 6: Update Infrastructure Status Manually

```python
# When you detect status changes in your code

# API degradation detected
system_health.update_infrastructure_status(
    api_status="degraded"
)

# Database reconnected
system_health.update_infrastructure_status(
    db_status="connected"
)

# Backup completed
system_health.update_infrastructure_status(
    last_backup=datetime.utcnow().isoformat()
)
```

## Example: Complete Health Report Response

When you call `/health/detailed`, you get:

```json
{
  "timestamp": "2025-12-11T10:30:00Z",
  "overall_status": "healthy",
  "system_info": {
    "version": "1.0.0",
    "apiStatus": "online",
    "dbStatus": "connected",
    "lastBackup": "2025-12-11T08:00:00Z",
    "uptime": 86400,
    "storageUsed": 5368709120,
    "storageTotal": 107374182400
  },
  "sensor_health": {
    "total_sensors": 10,
    "healthy_sensors": 8,
    "degraded_sensors": 2,
    "critical_sensors": 0,
    "offline_sensors": 0,
    "health_level": "degraded",
    "average_success_rate": 95.5,
    "issues": [
      "Sensor 3 (Temperature): High error rate",
      "Sensor 7 (Humidity): Slow response time"
    ]
  },
  "alerts": {
    "total_active": 2,
    "total_resolved": 15,
    "active_by_severity": {
      "info": 0,
      "warning": 2,
      "critical": 0
    }
  },
  "infrastructure_details": {
    "storage": {
      "total": 107374182400,
      "used": 5368709120,
      "free": 102005473280,
      "percent": 5.0
    },
    "api_metrics": {
      "total_requests": 1523,
      "failed_requests": 12,
      "slow_requests": 5,
      "error_rate": 0.79,
      "avg_response_time_ms": 45.2,
      "status": "online"
    },
    "database_status": "connected"
  }
}
```

## Testing

Test your health monitoring:

```python
# Test script
import requests
import time

BASE_URL = "http://localhost:8000"

# 1. Test basic health
response = requests.get(f"{BASE_URL}/health")
print(f"Basic health: {response.json()}")

# 2. Test detailed health
response = requests.get(f"{BASE_URL}/health/detailed")
print(f"Detailed health: {response.json()}")

# 3. Generate some API traffic to test metrics
for i in range(10):
    requests.get(f"{BASE_URL}/api/v1/units")
    time.sleep(0.1)

# 4. Check API metrics
response = requests.get(f"{BASE_URL}/health/api-metrics")
print(f"API metrics: {response.json()}")

# 5. Test storage check
response = requests.get(f"{BASE_URL}/health/storage")
print(f"Storage: {response.json()}")
```

## Best Practices

1. **Periodic Checks**: Run health checks every 5-10 minutes
2. **Alert Thresholds**: Adjust alert thresholds based on your needs
3. **Storage Monitoring**: Monitor the actual data directory, not just root
4. **Database Health**: Include connection pool metrics if using SQLAlchemy
5. **API Metrics**: Track per-endpoint metrics for better insights
6. **Event Bus**: Subscribe to health events for reactive monitoring
7. **Logging**: Ensure all health changes are logged for auditing

## Troubleshooting

### Storage Not Updating
```python
# Ensure you're checking the right path
storage = system_health.refresh_storage_usage(path="/var/lib/sysgrow")
```

### API Status Stuck on "online"
```python
# Ensure middleware is installed
print(app.middleware)  # Should show HealthTrackingMiddleware

# Check metrics
print(system_health.get_api_metrics())
```

### Database Status Not Updating
```python
# Ensure you're passing the db_handler
system_health.check_database_health(db_handler=your_db_handler)
```

## Next Steps

1. Add custom health checks for your specific components
2. Integrate with monitoring tools (Prometheus, Grafana)
3. Set up alerting webhooks (Slack, email, etc.)
4. Create dashboards for health visualization
