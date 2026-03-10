import sqlite3

from infrastructure.database.repositories.ai import AIHealthDataRepository


class _FakeAnalyticsBackend:
    def __init__(self, db: sqlite3.Connection) -> None:
        self._db = db

    def get_db(self) -> sqlite3.Connection:
        return self._db


def _setup_db() -> sqlite3.Connection:
    db = sqlite3.connect(":memory:")
    db.execute(
        """
        CREATE TABLE GrowthUnits (
            unit_id INTEGER PRIMARY KEY,
            active_plant_id INTEGER
        )
        """
    )
    db.execute(
        """
        CREATE TABLE plant_journal (
            entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
            plant_id INTEGER NOT NULL,
            unit_id INTEGER,
            entry_type TEXT NOT NULL,
            health_status TEXT,
            symptoms TEXT,
            disease_type TEXT,
            severity_level INTEGER,
            affected_parts TEXT,
            environmental_factors TEXT,
            treatment_applied TEXT,
            notes TEXT,
            plant_type TEXT,
            growth_stage TEXT,
            observation_date TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    return db


def test_get_recent_observations_defaults_to_unit_active_plant() -> None:
    db = _setup_db()
    db.execute("INSERT INTO GrowthUnits (unit_id, active_plant_id) VALUES (?, ?)", (1, 123))
    db.execute(
        """
        INSERT INTO plant_journal (plant_id, unit_id, entry_type, health_status, notes, observation_date)
        VALUES (?, ?, 'observation', ?, ?, ?)
        """,
        (123, 1, "healthy", "ok", "2025-01-01T00:00:00+00:00"),
    )
    db.execute(
        """
        INSERT INTO plant_journal (plant_id, unit_id, entry_type, health_status, notes, observation_date)
        VALUES (?, ?, 'observation', ?, ?, ?)
        """,
        (456, 1, "stressed", "other plant", "2025-01-01T00:00:00+00:00"),
    )

    repo = AIHealthDataRepository(_FakeAnalyticsBackend(db))
    observations = repo.get_recent_observations(unit_id=1, plant_id=None, limit=10, days=30)

    assert len(observations) == 1
    assert observations[0]["plant_id"] == 123


def test_get_recent_observations_returns_empty_when_unit_has_no_active_plant() -> None:
    db = _setup_db()
    db.execute("INSERT INTO GrowthUnits (unit_id, active_plant_id) VALUES (?, NULL)", (1,))
    db.execute(
        """
        INSERT INTO plant_journal (plant_id, unit_id, entry_type, health_status, notes, observation_date)
        VALUES (?, ?, 'observation', ?, ?, ?)
        """,
        (456, 1, "stressed", "other plant", "2025-01-01T00:00:00+00:00"),
    )

    repo = AIHealthDataRepository(_FakeAnalyticsBackend(db))
    observations = repo.get_recent_observations(unit_id=1, plant_id=None, limit=10, days=30)

    assert observations == []


def test_get_recent_observations_honors_explicit_plant_id() -> None:
    db = _setup_db()
    db.execute("INSERT INTO GrowthUnits (unit_id, active_plant_id) VALUES (?, ?)", (1, 123))
    db.execute(
        """
        INSERT INTO plant_journal (plant_id, unit_id, entry_type, health_status, notes, observation_date)
        VALUES (?, ?, 'observation', ?, ?, ?)
        """,
        (456, 1, "stressed", "explicit plant", "2025-01-01T00:00:00+00:00"),
    )

    repo = AIHealthDataRepository(_FakeAnalyticsBackend(db))
    observations = repo.get_recent_observations(unit_id=1, plant_id=456, limit=10, days=30)

    assert len(observations) == 1
    assert observations[0]["plant_id"] == 456
