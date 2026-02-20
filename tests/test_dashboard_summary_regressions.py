import importlib.util
import sys
import types
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask, jsonify

DASHBOARD_PATH = Path(__file__).resolve().parents[1] / "app/blueprints/api/dashboard.py"


@pytest.fixture
def dashboard_api_module(monkeypatch):
    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = []
    domain_pkg = types.ModuleType("app.domain")
    domain_pkg.__path__ = []
    utils_pkg = types.ModuleType("app.utils")
    utils_pkg.__path__ = []
    blueprints_pkg = types.ModuleType("app.blueprints")
    blueprints_pkg.__path__ = []
    api_pkg = types.ModuleType("app.blueprints.api")
    api_pkg.__path__ = []

    agronomics_mod = types.ModuleType("app.domain.agronomics")
    agronomics_mod.infer_gdd_base_temp_c = lambda growth_stages, stage_name=None, default=10.0: default

    psychrometrics_mod = types.ModuleType("app.utils.psychrometrics")
    psychrometrics_mod.calculate_vpd_kpa = lambda temperature, humidity: 1.0

    time_mod = types.ModuleType("app.utils.time")
    time_mod.iso_now = lambda: "2026-02-14T00:00:00Z"
    time_mod.utc_now = lambda: datetime(2026, 2, 14, 0, 0, 0)

    common_mod = types.ModuleType("app.blueprints.api._common")

    def _success(data=None, status=200, message=None):
        payload = {"ok": True, "data": data, "error": None}
        if message is not None:
            payload["message"] = message
        response = jsonify(payload)
        response.status_code = status
        return response

    def _fail(message, status=400, details=None):
        payload = {"ok": False, "data": None, "error": {"message": message}, "message": message}
        if details:
            payload["details"] = details
        response = jsonify(payload)
        response.status_code = status
        return response

    common_mod.success = _success
    common_mod.fail = _fail
    common_mod.ensure_utc = lambda dt: dt
    common_mod.parse_datetime = lambda value, default: default
    common_mod.coerce_datetime = lambda value: value if isinstance(value, datetime) else None
    common_mod.get_plant_service = lambda: None
    common_mod.get_growth_service = lambda: None
    common_mod.get_scheduling_service = lambda: None

    monkeypatch.setitem(sys.modules, "app", app_pkg)
    monkeypatch.setitem(sys.modules, "app.domain", domain_pkg)
    monkeypatch.setitem(sys.modules, "app.utils", utils_pkg)
    monkeypatch.setitem(sys.modules, "app.blueprints", blueprints_pkg)
    monkeypatch.setitem(sys.modules, "app.blueprints.api", api_pkg)
    monkeypatch.setitem(sys.modules, "app.domain.agronomics", agronomics_mod)
    monkeypatch.setitem(sys.modules, "app.utils.psychrometrics", psychrometrics_mod)
    monkeypatch.setitem(sys.modules, "app.utils.time", time_mod)
    monkeypatch.setitem(sys.modules, "app.blueprints.api._common", common_mod)

    module_name = "dashboard_regression_under_test"
    spec = importlib.util.spec_from_file_location(module_name, DASHBOARD_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _SensorServiceStub:
    def list_sensors(self, unit_id=None):
        return [
            {"sensor_id": 1, "is_active": True},
            {"sensor_id": 2, "is_active": 0},
            {"sensor_id": 3, "status": "active"},
        ]


class _ActuatorServiceStub:
    def list_actuators(self, unit_id=None):
        return [
            {"actuator_id": 10, "is_active": "true"},
            {"actuator_id": 11, "is_active": False},
        ]


def test_build_devices_summary_counts_active_from_is_active_and_sensors(dashboard_api_module):
    container = SimpleNamespace(
        sensor_management_service=_SensorServiceStub(),
        actuator_management_service=_ActuatorServiceStub(),
    )

    sensors, actuators, devices_summary = dashboard_api_module._build_devices_summary(container, selected_unit_id=1)

    assert len(sensors) == 3
    assert len(actuators) == 2
    # Active sensors: sensor 1 + sensor 3(status fallback) = 2
    # Active actuators: actuator 10 = 1
    assert devices_summary["active"] == 3
    assert devices_summary["total"] == 5


def test_dashboard_summary_preserves_actuators_and_passes_them_to_unit_settings(dashboard_api_module, monkeypatch):
    app = Flask(__name__)
    app.secret_key = "test-secret"
    app.register_blueprint(dashboard_api_module.dashboard_api, url_prefix="/api/dashboard")

    app.config["CONTAINER"] = SimpleNamespace(
        growth_service=object(),
        plant_health_scorer=object(),
    )

    sensors_from_devices = [{"sensor_id": 100, "is_active": True}]
    actuators_from_devices = [{"actuator_id": 200, "is_active": True}]
    captured = {}

    monkeypatch.setattr(
        dashboard_api_module,
        "_get_service",
        lambda: None,
    )
    monkeypatch.setattr(
        dashboard_api_module,
        "_build_snapshot_or_analytics",
        lambda container, selected_unit_id: ({}, {}, None),
    )
    monkeypatch.setattr(
        dashboard_api_module,
        "_build_plants_summary",
        lambda container, selected_unit_id, growth_service, plant_health_scorer: ([], None, None),
    )
    monkeypatch.setattr(
        dashboard_api_module,
        "_build_alerts_summary",
        lambda container, selected_unit_id: {"count": 0, "recent": [], "critical": 0, "warning": 0},
    )
    monkeypatch.setattr(
        dashboard_api_module,
        "_build_devices_summary",
        lambda container, selected_unit_id: (
            sensors_from_devices,
            actuators_from_devices,
            {"active": 2, "total": 2},
        ),
    )
    monkeypatch.setattr(
        dashboard_api_module,
        "_build_system_summary",
        lambda container, summary: summary.get("system", {}),
    )

    def _fake_unit_settings_summary(container, growth_service, selected_unit_id, sensors=None, actuators=None):
        captured["sensors"] = sensors
        captured["actuators"] = actuators
        return {"sensors": sensors or [], "actuators": actuators or []}

    monkeypatch.setattr(
        dashboard_api_module,
        "_build_unit_settings_summary",
        _fake_unit_settings_summary,
    )

    client = app.test_client()
    with client.session_transaction() as session_obj:
        session_obj["selected_unit"] = 1

    response = client.get("/api/dashboard/summary")
    assert response.status_code == 200

    payload = response.get_json() or {}
    assert payload.get("ok") is True
    summary = payload.get("data") or {}

    assert summary.get("actuators") == actuators_from_devices
    assert captured.get("actuators") == actuators_from_devices
    unit_settings = summary.get("unit_settings") or {}
    assert unit_settings.get("actuators") == actuators_from_devices
