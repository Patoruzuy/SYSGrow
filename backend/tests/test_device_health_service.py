"""DeviceHealthService initialization tests."""

from app.services.application.device_health_service import DeviceHealthService
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler


def test_device_health_service_initializes() -> None:
    db = SQLiteDatabaseHandler(":memory:")
    db.init_app(None)
    repo = DeviceRepository(db)

    service = DeviceHealthService(repository=repo, mqtt_client=None)

    assert service.calibration_service is not None
    assert service.anomaly_service is not None
    assert service.discovery_service is None

