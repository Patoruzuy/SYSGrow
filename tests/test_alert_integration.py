import logging
from pathlib import Path

from app.services.application.alert_service import AlertService
from app.services.application.device_health_service import DeviceHealthService
from infrastructure.database.repositories.alerts import AlertRepository
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler

# Setup logging for test run
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


# Minimal fake repository and services to exercise device_health_service
class FakeRepo:
    def __init__(self):
        self.logged = []

    def log_anomaly(self, sensor_id, value, mean_value, std_deviation, z_score):
        self.logged.append({"sensor_id": sensor_id, "value": value, "z": z_score})
        return 1

    def find_sensor_config_by_id(self, sensor_id):
        return {"sensor_id": sensor_id, "name": f"TestSensor{sensor_id}", "unit_id": 1}


class FakeSensorReading:
    def __init__(self, value):
        self.value = value


class FakeSensorService:
    def __init__(self, value):
        self._value = value

    def read_sensor(self, sensor_id):
        return FakeSensorReading(self._value)


class FakeAnomalyService:
    def __init__(self, is_anomaly=True):
        self.threshold = 1.0
        self._is_anomaly = is_anomaly

    def detect_anomaly(self, sensor_id, value):
        return self._is_anomaly

    def get_statistics(self, sensor_id):
        return {"mean": 10.0, "std_dev": 1.0, "count": 100, "min": 0.0, "max": 20.0}


def test_create_alert_end_to_end():
    base = Path(__file__).resolve().parent.parent
    dbpath = base / "data" / "sysgrow_integration_test.db"
    if dbpath.exists():
        dbpath.unlink()

    db = SQLiteDatabaseHandler(str(dbpath))
    db.create_tables()

    alert_repo = AlertRepository(db)
    alert_service = AlertService(alert_repo)

    fake_repo = FakeRepo()
    dhs = DeviceHealthService(
        repository=fake_repo,
        alert_service=alert_service,
        sensor_management_service=FakeSensorService(999.0),
    )
    # inject fake anomaly service that always flags anomaly
    dhs.anomaly_service = FakeAnomalyService(is_anomaly=True)

    result = dhs.check_sensor_anomalies(1)
    logger.info("check_sensor_anomalies result: %s", result)

    # Query DB for active alerts
    active = alert_repo.list_active(limit=10)
    assert isinstance(active, list)
    assert len(active) >= 1
    # ensure at least one alert has type SENSOR_ANOMALY
    types = [a["alert_type"] for a in active]
    assert "sensor_anomaly" in types

    # Cleanup DB file
    try:
        dbpath.unlink()
    except Exception:
        pass


if __name__ == "__main__":
    test_create_alert_end_to_end()
    print("Integration test completed")
