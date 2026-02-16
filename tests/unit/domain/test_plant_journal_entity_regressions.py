from __future__ import annotations

import datetime as dt
import importlib.util
import sys
import types
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]

if not hasattr(dt, "UTC"):
    dt.UTC = dt.timezone.utc  # noqa: UP017


def _load_module(module_name: str, module_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module {module_name} from {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


if "app" not in sys.modules:
    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = [str(ROOT / "app")]
    sys.modules["app"] = app_pkg

if "app.enums" not in sys.modules:
    enums_pkg = types.ModuleType("app.enums")
    enums_pkg.__path__ = [str(ROOT / "app" / "enums")]
    sys.modules["app.enums"] = enums_pkg

if "app.utils" not in sys.modules:
    utils_pkg = types.ModuleType("app.utils")
    utils_pkg.__path__ = [str(ROOT / "app" / "utils")]
    sys.modules["app.utils"] = utils_pkg

if "app.domain" not in sys.modules:
    domain_pkg = types.ModuleType("app.domain")
    domain_pkg.__path__ = [str(ROOT / "app" / "domain")]
    sys.modules["app.domain"] = domain_pkg

_load_module("app.enums.common", ROOT / "app" / "enums" / "common.py")
_load_module("app.utils.time", ROOT / "app" / "utils" / "time.py")
entity_module = _load_module(
    "app.domain.plant_journal_entity",
    ROOT / "app" / "domain" / "plant_journal_entity.py",
)
PlantHealthObservationEntity = entity_module.PlantHealthObservationEntity


def _build_observation(**overrides):
    payload = {
        "unit_id": 1,
        "health_status": "stressed",
        "symptoms": ["yellowing_leaves"],
        "severity_level": 3,
        "affected_parts": ["leaves"],
        "environmental_factors": {},
        "notes": "test",
    }
    payload.update(overrides)
    return PlantHealthObservationEntity(**payload)


def test_observation_date_accepts_iso_z_suffix():
    obs = _build_observation(observation_date="2026-01-02T03:04:05.000Z")

    assert obs.observation_date is not None
    assert obs.observation_date.tzinfo is not None
    assert obs.observation_date.utcoffset() == timedelta(0)
    assert obs.observation_date.isoformat() == "2026-01-02T03:04:05+00:00"


def test_symptoms_rejects_string_payload():
    with pytest.raises(ValueError, match="symptoms must be a list of strings"):
        _build_observation(symptoms="yellowing")


def test_affected_parts_rejects_string_payload():
    with pytest.raises(ValueError, match="affected_parts must be a list of strings"):
        _build_observation(affected_parts="leaves")
