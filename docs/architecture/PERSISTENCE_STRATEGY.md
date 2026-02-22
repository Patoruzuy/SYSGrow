# Persistence Strategy

> **Status:** Living document — updated as new features land.
> **Last updated:** 2026-02

## Overview

SYSGrow uses **two** complementary persistence mechanisms.  The choice is
intentional and documented here to prevent drift or accidental duplication.

| Mechanism | Backing store | Good for | Bad for |
|-----------|--------------|----------|---------|
| **SQLite (WAL mode)** | `sysgrow.db` / migration-managed tables | Relational data with queries, audit trails, time-series | Large blobs, high-write-throughput streams |
| **JSON files** (`PersistentStore`) | `data/user_profiles/*.json`, `data/training/*.json` | Human-editable config, ML training snapshots, per-user preferences | Concurrent writes from multiple processes, large collections |

---

## When to use SQLite

Use the database when:

- Data is **relational** — e.g. plants belong to units, sensors produce readings.
- You need **indexed queries** — filtering by date, sensor id, severity.
- The data forms an **audit trail** — activity logs, anomaly history,
  irrigation feedback.
- **Transactional integrity** matters — locking, ACID guarantees.

### Examples

| Table / Migration | Purpose |
|-------------------|---------|
| `GrowthUnit`, `Plant`, `SensorConfig`, `ActuatorConfig` | Core domain entities |
| `SensorReading` | Time-series sensor data |
| `SensorAnomaly` (migration 061) | Persisted anomaly detections |
| `ActivityLog` | Auditable system events |
| `IrrigationLock` | Mutual-exclusion token for irrigation operations |

### Pattern

All SQL access goes through **repository** classes in
`infrastructure/database/repositories/`.  Blueprints and services never run
raw SQL; they call repository methods.

---

## When to use JSON (`PersistentStore`)

Use JSON files when:

- Data is a **user-editable document** — condition profiles, notification
  preferences.
- The payload is a **snapshot** rather than a growing collection — e.g. the
  latest ML training summary.
- You want the file to be **human-readable and diffable** in version control
  (for development / debugging convenience).
- The data is **per-user or per-profile** and read-heavy / write-infrequent.

### Examples

| File pattern | Purpose |
|-------------|---------|
| `data/user_profiles/{user_id}.json` | Per-user dashboard preferences |
| `data/training/irrigation_model.json` | Serialised ML model metadata |
| `plants_info.json` | Reference plant database (read-only at runtime) |

### Pattern

`PersistentStore` (in `app/utils/persistent_store.py`) provides a
dict-like API backed by a JSON file.  It is **not** safe for concurrent
writers — if two processes write simultaneously the last one wins.  This is
acceptable because writes are rare (settings changes, training completion).

---

## Decision rules for new features

1. **Will the data grow unbounded?** → SQLite with `prune` / retention policy.
2. **Do you need to query by multiple fields?** → SQLite with proper indexes.
3. **Is it a user-facing config blob?** → JSON via `PersistentStore`.
4. **Is it reference data shipped with the repo?** → Static JSON, read-only.
5. **Unsure?** Default to SQLite — it is harder to migrate away from JSON
   once the feature grows.

---

## Anti-patterns to avoid

| ❌ Anti-pattern | ✅ Preferred |
|----------------|-------------|
| Raw `sqlite3` in blueprints / controllers | Use a repository in `infrastructure/database/repositories/` |
| Storing time-series in JSON files | Use a SQLite table with date-based retention |
| Duplicating the same data in DB *and* JSON | Pick one canonical source; derive the other if needed |
| Using `PersistentStore` for high-frequency writes (> 1/s) | Use SQLite with WAL mode |
