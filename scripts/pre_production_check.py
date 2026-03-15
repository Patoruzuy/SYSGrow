#!/usr/bin/env python
"""Run repo-side pre-production checks for the SYSGrow backend."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = BACKEND_ROOT.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

ROUTE_SMOKE_SCRIPT = r"""
from app import create_app

paths = [
    "/",
    "/units",
    "/devices",
    "/device-health",
    "/notifications",
    "/plants",
    "/sensor-analytics",
    "/system-health",
    "/ml-dashboard",
]

app = create_app()
failures = []

with app.test_client() as client:
    with client.session_transaction() as session:
        session["user"] = "preflight"
        session["user_id"] = 1
        session["selected_unit"] = 1

    for path in paths:
        response = client.get(path)
        print(f"{path} {response.status_code}")
        if response.status_code != 200:
            failures.append((path, response.status_code))

if failures:
    raise SystemExit(1)
"""

PYTEST_ARGS = [
    "tests/test_auth_security_routes.py::test_all_mutating_api_routes_require_authenticated_session",
    "tests/test_auth_security_routes.py::test_api_write_rejects_authenticated_session_without_csrf_token",
    "tests/test_auth_security_routes.py::test_api_write_allows_authenticated_session_with_valid_csrf_token",
    "tests/test_auth_security_routes.py::test_pump_calibration_service_errors_do_not_leak_runtime_details",
    "tests/test_auth_security_routes.py::test_database_backup_missing_file_does_not_leak_path",
    "tests/test_auth_security_routes.py::test_manual_prediction_service_errors_do_not_leak_runtime_details",
    "tests/test_api.py",
    "tests/test_settings_api.py",
    "-q",
    "--tb=short",
    "--timeout=30",
]


@dataclass
class CheckResult:
    label: str
    ok: bool
    command: str
    output: str


def _run(label: str, command: list[str], *, cwd: Path = BACKEND_ROOT, env: dict[str, str] | None = None) -> CheckResult:
    result = subprocess.run(
        command,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    stdout = (result.stdout or "").strip()
    stderr = (result.stderr or "").strip()
    output = "\n".join(part for part in [stdout, stderr] if part).strip()
    return CheckResult(
        label=label,
        ok=result.returncode == 0,
        command=" ".join(command),
        output=output,
    )


def _file_probe() -> CheckResult:
    requirements = {
        BACKEND_ROOT / "deployment" / "sysgrow.service": [
            "EnvironmentFile=-/opt/sysgrow/ops.env",
            "Restart=on-failure",
            "ProtectSystem=strict",
            "WantedBy=multi-user.target",
        ],
        BACKEND_ROOT / "scripts" / "install_linux.sh": [
            "systemctl enable --now sysgrow",
            "systemctl enable --now mosquitto",
            "mosquitto-clients",
            "SYSGROW_SECRET_KEY",
        ],
        BACKEND_ROOT / "ops.env.example": [
            "SYSGROW_ENV=production",
            "SYSGROW_DEBUG=False",
            "SYSGROW_MQTT_HOST=localhost",
        ],
        WORKSPACE_ROOT / ".github" / "workflows" / "backend-ci.yml": [
            "ruff check .",
            "ruff format --check .",
            "bandit -r app/ infrastructure/",
            "tests/test_settings_api.py",
        ],
    }

    failures: list[str] = []
    passes: list[str] = []
    for path, markers in requirements.items():
        if not path.exists():
            failures.append(f"Missing required file: {path}")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [marker for marker in markers if marker not in text]
        if missing:
            failures.append(f"{path}: missing {', '.join(missing)}")
        else:
            passes.append(str(path))

    if failures:
        return CheckResult(
            label="File/config probes",
            ok=False,
            command="internal file checks",
            output="\n".join(failures),
        )

    return CheckResult(
        label="File/config probes",
        ok=True,
        command="internal file checks",
        output="\n".join(f"OK: {item}" for item in passes),
    )


def _base_test_env() -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "FLASK_ENV": "testing",
            "TESTING": "1",
            "SYSGROW_ENABLE_MQTT": "False",
            "SYSGROW_ENABLE_REDIS": "False",
            "SYSGROW_SECRET_KEY": "preflight-test-secret",
        }
    )
    return env


def main() -> int:
    parser = argparse.ArgumentParser(description="SYSGrow backend pre-production preflight")
    parser.add_argument("--skip-bandit", action="store_true", help="Skip the Bandit security scan")
    parser.add_argument("--skip-tests", action="store_true", help="Skip the pytest gate")
    parser.add_argument("--skip-smoke", action="store_true", help="Skip the Flask route smoke test")
    args = parser.parse_args()

    checks: list[CheckResult] = []
    checks.append(_file_probe())
    checks.append(_run("Installer shell syntax", ["bash", "-n", "scripts/install_linux.sh"]))
    checks.append(_run("Ruff lint", [sys.executable, "-m", "ruff", "check", "."]))
    checks.append(_run("Ruff format", [sys.executable, "-m", "ruff", "format", "--check", "."]))

    if not args.skip_bandit:
        checks.append(
            _run(
                "Bandit security scan",
                [sys.executable, "-m", "bandit", "-r", "app/", "infrastructure/", "-c", "pyproject.toml", "-q", "-ll"],
            )
        )

    if not args.skip_tests:
        checks.append(_run("Pytest release gate", [sys.executable, "-m", "pytest", *PYTEST_ARGS], env=_base_test_env()))

    if not args.skip_smoke:
        checks.append(_run("Critical route smoke", [sys.executable, "-c", ROUTE_SMOKE_SCRIPT], env=_base_test_env()))

    banner = "=" * 72
    print(banner)
    print("SYSGrow pre-production preflight")
    print(banner)
    for check in checks:
        status = "PASS" if check.ok else "FAIL"
        print(f"[{status}] {check.label}")
        print(f"  command: {check.command}")
        if check.output:
            for line in check.output.splitlines():
                print(f"  {line}")
        print("")

    manual_gates = [
        "Fresh Raspberry Pi install from a clean Raspberry Pi OS image",
        "Boot-time startup validation after reboot for sysgrow and mosquitto",
        "LAN MQTT connectivity from real ESP32 / Zigbee bridge devices",
        "Backup + restore drill on the production SQLite database",
        "Power-loss and broker-loss recovery test",
        "12-24 hour soak test with real polling and scheduled jobs",
        "Browser QA on Pi Chromium plus at least one mobile browser",
    ]
    print(banner)
    print("Manual gates still required")
    print(banner)
    for item in manual_gates:
        print(f"- {item}")

    failed = [check.label for check in checks if not check.ok]
    if failed:
        print("")
        print("FAILED CHECKS:")
        for label in failed:
            print(f"- {label}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
