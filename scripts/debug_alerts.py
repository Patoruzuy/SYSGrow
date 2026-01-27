from ..infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from app.services.application.alert_service import AlertService

from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from infrastructure.database.repositories.alerts import AlertRepository
from app.services.application.alert_service import AlertService

import json


def run():
    db = SQLiteDatabaseHandler(':memory:')
    db.create_tables()
    alert_repo = AlertRepository(db)
    svc = AlertService(alert_repo)
    aid1 = svc.create_alert(alert_type=svc.DEVICE_OFFLINE, severity=svc.WARNING, title='t', message='m', source_type='sensor', source_id=42, metadata={'dedup_key':'dev42'}, dedupe=True)
    print('aid1', aid1)
    with db.connection() as conn:
        rows = list(conn.execute('SELECT alert_id, alert_type, source_type, source_id, timestamp, metadata FROM Alert'))
        print('rows after first:', rows)
    aid2 = svc.create_alert(alert_type=svc.DEVICE_OFFLINE, severity=svc.WARNING, title='t2', message='m2', source_type='sensor', source_id=42, metadata={'dedup_key':'dev42'}, dedupe=True)
    print('aid2', aid2)
    with db.connection() as conn:
        rows = list(conn.execute('SELECT alert_id, alert_type, source_type, source_id, timestamp, metadata FROM Alert'))
        for r in rows:
            print('row:', r)


if __name__ == '__main__':
    run()
