import runpy
import sys
import types
from pathlib import Path
from unittest.mock import Mock

RUN_SERVER_PATH = Path(__file__).resolve().parents[1] / "run_server.py"


def _install_fake_app_module(monkeypatch):
    fake_app_module = types.ModuleType("app")
    fake_socketio = Mock()
    fake_socketio.run = Mock()
    fake_app_module.socketio = fake_socketio
    fake_app_module.create_app = Mock(return_value=object())
    monkeypatch.setitem(sys.modules, "app", fake_app_module)
    return fake_app_module


def _force_devhost_missing(monkeypatch):
    monkeypatch.setitem(sys.modules, "devhost_cli", None)
    for name in list(sys.modules.keys()):
        if name.startswith("devhost_cli."):
            monkeypatch.delitem(sys.modules, name, raising=False)


def test_run_server_import_does_not_crash_without_devhost_cli(monkeypatch):
    fake_app_module = _install_fake_app_module(monkeypatch)
    _force_devhost_missing(monkeypatch)

    module_globals = runpy.run_path(str(RUN_SERVER_PATH), run_name="run_server_test")

    assert module_globals.get("run_flask") is None
    fake_app_module.create_app.assert_called_once_with(bootstrap_runtime=True)


def test_run_server_main_falls_back_to_socketio_run_when_devhost_cli_missing(monkeypatch):
    fake_app_module = _install_fake_app_module(monkeypatch)
    _force_devhost_missing(monkeypatch)
    monkeypatch.setenv("FLASK_RUN_PORT", "8765")

    runpy.run_path(str(RUN_SERVER_PATH), run_name="__main__")

    fake_app_module.create_app.assert_called_once_with(bootstrap_runtime=True)
    fake_app_module.socketio.run.assert_called_once()
    _, kwargs = fake_app_module.socketio.run.call_args
    assert kwargs["port"] == 8765
