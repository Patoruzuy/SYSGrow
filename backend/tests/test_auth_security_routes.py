from __future__ import annotations

import re
import sys
import types
from pathlib import Path
from unittest.mock import Mock

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


@pytest.fixture()
def app_csrf_enforced(tmp_path, monkeypatch):
    monkeypatch.setenv("SYSGROW_SECRET_KEY", "test-secret")
    monkeypatch.setenv("SYSGROW_ENABLE_MQTT", "False")
    monkeypatch.setenv("SYSGROW_ENABLE_REDIS", "False")
    database_path = tmp_path / "csrf-enforced.db"
    flask_app = create_app({"database_path": str(database_path), "debug": False})
    flask_app.config["TESTING"] = False
    try:
        yield flask_app
    finally:
        container = flask_app.config.get("CONTAINER")
        if container is not None:
            container.shutdown()


@pytest.fixture()
def client_csrf_enforced(app_csrf_enforced):
    return app_csrf_enforced.test_client()


def _set_user_session(
    client,
    *,
    username: str = "alice",
    user_id: int = 1,
    csrf_token: str | None = None,
) -> None:
    with client.session_transaction() as session_obj:
        session_obj["user"] = username
        session_obj["user_id"] = user_id
        if csrf_token is not None:
            session_obj["_csrf_token"] = csrf_token


def _auth_manager(client):
    return client.application.config["CONTAINER"].auth_manager


def _materialize_rule(rule: str) -> str:
    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        if token.startswith("<int:"):
            return "1"
        if token.startswith("<float:"):
            return "1.0"
        if token.startswith("<path:"):
            return "sample/path"
        if token.startswith("<uuid:"):
            return "00000000-0000-0000-0000-000000000000"
        return "sample"

    return re.sub(r"<[^>]+>", _replace, rule)


def test_reset_password_get_renders_form_for_valid_token(client):
    auth_manager = _auth_manager(client)
    auth_manager.validate_reset_token = Mock(
        return_value={"token_id": 10, "user_id": 1, "username": "alice", "email": "a@example.com"}
    )

    response = client.get("/auth/reset-password/valid-token")

    assert response.status_code == 200
    assert b"Reset Password" in response.data
    assert b"alice" in response.data
    auth_manager.validate_reset_token.assert_called_once_with("valid-token")


def test_reset_password_get_redirects_for_invalid_token(client):
    auth_manager = _auth_manager(client)
    auth_manager.validate_reset_token = Mock(return_value=None)

    response = client.get("/auth/reset-password/expired-token", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/forgot-password")
    auth_manager.validate_reset_token.assert_called_once_with("expired-token")


def test_reset_password_post_rejects_short_password(client):
    auth_manager = _auth_manager(client)
    auth_manager.reset_password_with_token = Mock()

    response = client.post(
        "/auth/reset-password/t1",
        data={"password": "short", "confirm_password": "short"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/reset-password/t1")
    auth_manager.reset_password_with_token.assert_not_called()


def test_reset_password_post_rejects_mismatched_passwords(client):
    auth_manager = _auth_manager(client)
    auth_manager.reset_password_with_token = Mock()

    response = client.post(
        "/auth/reset-password/t2",
        data={"password": "verysecure", "confirm_password": "different"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/reset-password/t2")
    auth_manager.reset_password_with_token.assert_not_called()


def test_reset_password_post_redirects_to_login_on_success(client):
    auth_manager = _auth_manager(client)
    auth_manager.reset_password_with_token = Mock(return_value=True)

    response = client.post(
        "/auth/reset-password/t3",
        data={"password": "verysecure", "confirm_password": "verysecure"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")
    auth_manager.reset_password_with_token.assert_called_once_with("t3", "verysecure")


def test_reset_password_post_redirects_to_forgot_password_on_failure(client):
    auth_manager = _auth_manager(client)
    auth_manager.reset_password_with_token = Mock(return_value=False)

    response = client.post(
        "/auth/reset-password/t4",
        data={"password": "verysecure", "confirm_password": "verysecure"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/forgot-password")
    auth_manager.reset_password_with_token.assert_called_once_with("t4", "verysecure")


def test_generate_recovery_codes_requires_api_auth_session(client):
    response = client.post("/api/settings/security/recovery-codes/generate", json={})
    payload = response.get_json() or {}

    assert response.status_code == 401
    assert payload.get("ok") is False
    assert payload.get("error", {}).get("code") == "UNAUTHORIZED"


def test_generate_recovery_codes_requires_user_id_even_with_api_auth(client):
    with client.session_transaction() as session_obj:
        session_obj["user"] = "alice"
        session_obj.pop("user_id", None)

    response = client.post("/api/settings/security/recovery-codes/generate", json={"current_password": "x"})
    payload = response.get_json() or {}

    assert response.status_code == 401
    assert payload.get("ok") is False
    assert "User not authenticated" in (payload.get("message") or "")


def test_generate_recovery_codes_rejects_missing_current_password(client):
    _set_user_session(client)
    auth_manager = _auth_manager(client)
    auth_manager.authenticate_user = Mock()

    response = client.post("/api/settings/security/recovery-codes/generate", json={})
    payload = response.get_json() or {}

    assert response.status_code == 400
    assert payload.get("ok") is False
    auth_manager.authenticate_user.assert_not_called()


def test_generate_recovery_codes_rejects_invalid_current_password(client):
    _set_user_session(client)
    auth_manager = _auth_manager(client)
    auth_manager.authenticate_user = Mock(return_value=False)
    auth_manager.generate_recovery_codes = Mock()

    response = client.post(
        "/api/settings/security/recovery-codes/generate",
        json={"current_password": "wrong-password"},
    )
    payload = response.get_json() or {}

    assert response.status_code == 403
    assert payload.get("ok") is False
    auth_manager.authenticate_user.assert_called_once_with("alice", "wrong-password")
    auth_manager.generate_recovery_codes.assert_not_called()


def test_generate_recovery_codes_returns_500_when_generation_fails(client):
    _set_user_session(client)
    auth_manager = _auth_manager(client)
    auth_manager.authenticate_user = Mock(return_value=True)
    auth_manager.generate_recovery_codes = Mock(return_value=None)

    response = client.post(
        "/api/settings/security/recovery-codes/generate",
        json={"current_password": "correct-password"},
    )
    payload = response.get_json() or {}

    assert response.status_code == 500
    assert payload.get("ok") is False
    auth_manager.authenticate_user.assert_called_once_with("alice", "correct-password")
    auth_manager.generate_recovery_codes.assert_called_once_with(1)


def test_generate_recovery_codes_returns_codes_on_success(client):
    _set_user_session(client)
    auth_manager = _auth_manager(client)
    auth_manager.authenticate_user = Mock(return_value=True)
    auth_manager.generate_recovery_codes = Mock(return_value=["ABCD-EFGH", "JKLM-NPQR"])

    response = client.post(
        "/api/settings/security/recovery-codes/generate",
        json={"current_password": "correct-password"},
    )
    payload = response.get_json() or {}
    data = payload.get("data") or {}

    assert response.status_code == 200
    assert payload.get("ok") is True
    assert data.get("codes") == ["ABCD-EFGH", "JKLM-NPQR"]
    assert data.get("count") == 2
    auth_manager.authenticate_user.assert_called_once_with("alice", "correct-password")
    auth_manager.generate_recovery_codes.assert_called_once_with(1)


def test_api_write_rejects_authenticated_session_without_csrf_token(client_csrf_enforced):
    _set_user_session(client_csrf_enforced)

    response = client_csrf_enforced.post("/api/v1/devices/zigbee2mqtt/command", json={})
    payload = response.get_json() or {}

    assert response.status_code == 400
    assert payload.get("ok") is False
    assert payload.get("message") == "CSRF token missing or invalid"


def test_api_write_allows_authenticated_session_with_valid_csrf_token(client_csrf_enforced):
    csrf_token = "csrf-token-123"
    _set_user_session(client_csrf_enforced, csrf_token=csrf_token)

    response = client_csrf_enforced.post(
        "/api/v1/devices/zigbee2mqtt/command",
        json={},
        headers={"X-CSRF-Token": csrf_token},
    )
    payload = response.get_json() or {}

    # Route validation error proves request passed auth + CSRF middleware.
    assert response.status_code == 400
    assert payload.get("ok") is False
    assert payload.get("message") == "friendly_name and command are required"


def test_all_mutating_api_routes_require_authenticated_session(client):
    exempt_blueprints = {"auth", "health_api", "help_api", "blog_api"}
    write_methods = {"POST", "PUT", "PATCH", "DELETE"}
    checked_routes: list[str] = []

    for rule in client.application.url_map.iter_rules():
        if not rule.rule.startswith("/api/"):
            continue
        blueprint = rule.endpoint.split(".", 1)[0]
        if blueprint in exempt_blueprints:
            continue

        methods = sorted((rule.methods or set()) & write_methods)
        if not methods:
            continue

        path = _materialize_rule(rule.rule)
        for method in methods:
            response = client.open(path, method=method, json={})
            payload = response.get_json() or {}
            checked_routes.append(f"{method} {rule.rule}")

            assert response.status_code == 401, f"{method} {rule.rule} escaped API auth with {response.status_code}"
            assert payload.get("error", {}).get("code") == "UNAUTHORIZED"

    assert checked_routes, "expected at least one mutating API route to be checked"


def test_pump_calibration_service_errors_do_not_leak_runtime_details(client_csrf_enforced, monkeypatch):
    import app.blueprints.api.irrigation as irrigation_module

    def _raise_service_error():
        raise RuntimeError("sqlite error: /srv/sysgrow/private.db")

    csrf_token = "csrf-pump"
    _set_user_session(client_csrf_enforced, csrf_token=csrf_token)
    monkeypatch.setattr(irrigation_module, "get_pump_calibration_service", _raise_service_error)

    response = client_csrf_enforced.post(
        "/api/v1/irrigation/calibration/pump/start",
        json={"actuator_id": 1},
        headers={"X-CSRF-Token": csrf_token},
    )
    payload = response.get_json() or {}

    assert response.status_code == 503
    assert payload.get("message") == "Pump calibration service not available"
    assert "private.db" not in str(payload)


def test_database_backup_missing_file_does_not_leak_path(client_csrf_enforced, monkeypatch):
    import app.blueprints.api.settings.database as database_api

    class _MissingDatabaseService:
        def create_backup(self, *args, **kwargs):
            raise FileNotFoundError("/srv/sysgrow/private/sysgrow.db")

    csrf_token = "csrf-db"
    _set_user_session(client_csrf_enforced, csrf_token=csrf_token)
    monkeypatch.setattr(database_api, "_get_maintenance_service", lambda: _MissingDatabaseService())

    response = client_csrf_enforced.post(
        "/api/v1/settings/database/backup",
        json={"label": "manual"},
        headers={"X-CSRF-Token": csrf_token},
    )
    payload = response.get_json() or {}

    assert response.status_code == 404
    assert payload.get("message") == "Database file not found"
    assert "private" not in str(payload)


def test_manual_prediction_service_errors_do_not_leak_runtime_details(client, monkeypatch):
    import app.blueprints.api.irrigation as irrigation_module

    def _raise_service_error():
        raise RuntimeError("model load failed from /opt/sysgrow/models/private.joblib")

    monkeypatch.setattr(irrigation_module, "get_plant_irrigation_model_service", _raise_service_error)

    response = client.get("/api/v1/irrigation/manual/predict/1?threshold=30&soil_moisture=20")
    payload = response.get_json() or {}

    assert response.status_code == 503
    assert payload.get("message") == "Service unavailable"
    assert "private.joblib" not in str(payload)
