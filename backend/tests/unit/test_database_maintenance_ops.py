from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from infrastructure.database.ops.maintenance import (
    _BACKUP_CONNECT_TIMEOUT_SECONDS,
    _SQLITE_BUSY_TIMEOUT_MS,
    MaintenanceOperations,
)


class _TestMaintenanceHandler(MaintenanceOperations):
    def __init__(self, database_path: Path) -> None:
        self._database_path = str(database_path)
        self._connection: sqlite3.Connection | None = None

    def get_db(self) -> sqlite3.Connection:
        if self._connection is None:
            self._connection = sqlite3.connect(self._database_path, check_same_thread=False)
        return self._connection

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None


def test_delete_sensor_readings_before_propagates_sqlite_errors(tmp_path: Path) -> None:
    db_path = tmp_path / "broken.db"
    sqlite3.connect(db_path).close()

    handler = _TestMaintenanceHandler(db_path)
    try:
        with pytest.raises(sqlite3.Error):
            handler.delete_sensor_readings_before("2026-03-01 00:00:00")
    finally:
        handler.close()


def test_vacuum_database_raises_when_database_file_is_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "missing.db"
    handler = _TestMaintenanceHandler(db_path)

    with pytest.raises(FileNotFoundError):
        handler.vacuum_database()

    assert not db_path.exists()


def test_backup_database_uses_legacy_busy_timeout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = tmp_path / "live.db"
    backup_path = tmp_path / "backup.db"

    with sqlite3.connect(source_path) as conn:
        conn.execute("CREATE TABLE sample (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO sample (name) VALUES (?)", ("sensor",))
        conn.commit()

    real_connect = sqlite3.connect
    connect_timeouts: list[float | None] = []
    executed_sql: list[str] = []

    class TrackingConnection(sqlite3.Connection):
        def execute(self, sql: str, parameters=(), /):
            executed_sql.append(sql)
            return super().execute(sql, parameters)

    def tracking_connect(database, *args, **kwargs):
        connect_timeouts.append(kwargs.get("timeout"))
        kwargs["factory"] = TrackingConnection
        return real_connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", tracking_connect)

    handler = _TestMaintenanceHandler(source_path)
    backup_bytes = handler.backup_database(backup_path)

    assert backup_bytes > 0
    assert connect_timeouts == [_BACKUP_CONNECT_TIMEOUT_SECONDS, _BACKUP_CONNECT_TIMEOUT_SECONDS]
    assert executed_sql.count(f"PRAGMA busy_timeout = {_SQLITE_BUSY_TIMEOUT_MS}") == 2

    with real_connect(backup_path) as conn:
        copied_rows = conn.execute("SELECT COUNT(*) FROM sample").fetchone()[0]

    assert copied_rows == 1
