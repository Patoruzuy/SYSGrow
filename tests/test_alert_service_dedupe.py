import os
import sys
import json

# Ensure repository root is on sys.path so tests can import application modules
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import pytest

from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from infrastructure.database.repositories.alerts import AlertRepository
from app.services.application.alert_service import AlertService


@pytest.fixture
def db_handler(tmp_path):
    db_path = str(tmp_path / "test_alerts.db")
    db = SQLiteDatabaseHandler(db_path)
    db.create_tables()
    return db


def test_alert_dedupe_db(db_handler):
    repo = AlertRepository(db_handler)
    svc = AlertService(repo)

    # Create first alert
    aid1 = svc.create_alert(
        alert_type=svc.DEVICE_OFFLINE,
        severity=svc.WARNING,
        title="Device lost",
        message="Device X not reachable",
        source_type="sensor",
        source_id=42,
        metadata={"dedup_key": "dev42"},
        dedupe=True,
    )

    assert isinstance(aid1, int)

    # Create duplicate alert - should return existing id and increment occurrences
    aid2 = svc.create_alert(
        alert_type=svc.DEVICE_OFFLINE,
        severity=svc.WARNING,
        title="Device lost",
        message="Device X not reachable again",
        source_type="sensor",
        source_id=42,
        metadata={"dedup_key": "dev42"},
        dedupe=True,
    )

    assert aid2 == aid1

    # Verify occurrences updated in DB
    with db_handler.connection() as conn:
        cur = conn.execute("SELECT metadata FROM Alert WHERE alert_id = ?", (aid1,))
        row = cur.fetchone()
        meta = json.loads(row[0]) if row and row[0] else {}
        assert int(meta.get("occurrences", 0)) >= 2
