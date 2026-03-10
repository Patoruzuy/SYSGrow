from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# Minimal psutil shim for environments where optional system package is unavailable.
if "psutil" not in sys.modules:
    fake_psutil = types.ModuleType("psutil")

    class _FakeProcess:
        def __init__(self, _pid):
            self._pid = _pid

        def create_time(self):
            return 0.0

    class _FakeDiskUsage:
        total = 1
        used = 0
        free = 1
        percent = 0

    fake_psutil.Process = _FakeProcess
    fake_psutil.disk_usage = lambda _path: _FakeDiskUsage()
    sys.modules["psutil"] = fake_psutil

# Minimal flask_compress shim for environments where optional package is unavailable.
if "flask_compress" not in sys.modules:
    fake_compress_mod = types.ModuleType("flask_compress")

    class _FakeCompress:
        def init_app(self, _app):
            return None

    fake_compress_mod.Compress = _FakeCompress
    sys.modules["flask_compress"] = fake_compress_mod

from app import create_app


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("SYSGROW_SECRET_KEY", "test-secret")
    monkeypatch.setenv("SYSGROW_ENABLE_MQTT", "False")
    monkeypatch.setenv("SYSGROW_ENABLE_REDIS", "False")
    database_path = tmp_path / "test.db"
    flask_app = create_app({"database_path": str(database_path), "debug": True})
    flask_app.config["TESTING"] = True
    try:
        yield flask_app
    finally:
        container = flask_app.config.get("CONTAINER")
        if container is not None:
            container.shutdown()


@pytest.fixture()
def client(app):
    return app.test_client()


def test_devices_utils_reexports_shared_aliases():
    module = importlib.import_module("app.blueprints.api.devices.utils")

    for name in (
        "_success",
        "_fail",
        "_growth_service",
        "_sensor_service",
        "_actuator_service",
        "_device_repo",
        "_device_coordinator",
        "_device_health_service",
        "_analytics_service",
        "_zigbee_service",
    ):
        assert hasattr(module, name), f"Missing expected re-export: {name}"


def test_irrigation_predictor_exports_prediction_confidence():
    module = importlib.import_module("app.services.ai.irrigation_predictor")

    assert hasattr(module, "PredictionConfidence")


def test_api_error_handler_preserves_404_for_unknown_api_route(client):
    response = client.get("/api/this-route-does-not-exist")
    payload = response.get_json() or {}

    assert response.status_code == 404
    assert payload.get("ok") is False


def test_api_error_handler_preserves_405_for_method_not_allowed(client):
    response = client.get("/api/devices/actuators/1/toggle")
    payload = response.get_json() or {}

    assert response.status_code == 405
    assert payload.get("ok") is False


def test_startup_critical_modules_avoid_datetime_utc_import():
    paths = [
        "app/__init__.py",
        "app/blueprints/api/dashboard.py",
        "app/blueprints/api/_common.py",
        "app/utils/time.py",
        "app/services/application/dashboard_service.py",
        "app/services/ai/irrigation_predictor.py",
    ]

    for path in paths:
        source_path = Path(path)
        if not source_path.exists():
            continue
        source = source_path.read_text(encoding="utf-8")
        assert "from datetime import UTC" not in source
