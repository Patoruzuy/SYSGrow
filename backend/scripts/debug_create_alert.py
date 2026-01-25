from pathlib import Path
import json
import sys
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from infrastructure.database.repositories.alerts import AlertRepository
from app.services.application.alert_service import AlertService

BASE = Path(__file__).resolve().parent.parent
DB = BASE / "database" / "sysgrow.db"
DB.parent.mkdir(parents=True, exist_ok=True)

print("Using DB:", DB)

db = SQLiteDatabaseHandler(str(DB))
# ensure tables exist
db.create_tables()

repo = AlertRepository(db)
svc = AlertService(repo)

try:
    aid = svc.create_alert(
        alert_type=svc.DEVICE_OFFLINE,
        severity=svc.CRITICAL,
        title="Test Alert",
        message="This is a test alert created by debug script",
        source_type="debug",
        source_id=123,
        unit_id=1,
        metadata={"debug": True},
    )
    print("Created alert id:", aid)
    row = repo.get_by_id(aid)
    if row:
        d = dict(row)
        if d.get('metadata'):
            try:
                d['metadata'] = json.loads(d['metadata'])
            except Exception:
                pass
        print("Row:", d)
    else:
        print("No row returned for created alert")

    print("Active alerts:")
    alerts = repo.get_by_id(aid) and repo.get_by_id(aid)
    # list active via repo
    active = repo.list_active(limit=10)
    for a in active:
        print(dict(a))
except Exception as e:
    print("Error during test:", e)
    raise
