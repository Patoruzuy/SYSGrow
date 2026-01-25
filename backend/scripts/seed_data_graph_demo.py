"""
Seed demo data for the Sensor Data Graph page.

Creates a unit, sensor, plant, sensor readings, and plant health logs
so the multi-metric chart and plant overlay have data to display.
"""

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler


def ensure_unit(conn, name: str, location: str) -> int:
    existing = conn.execute(
        "SELECT unit_id FROM GrowthUnits WHERE name = ? LIMIT 1", (name,)
    ).fetchone()
    if existing:
        return existing["unit_id"]
    cursor = conn.execute(
        """
        INSERT INTO GrowthUnits (name, location)
        VALUES (?, ?)
        """,
        (name, location),
    )
    return cursor.lastrowid


def ensure_sensor(conn, unit_id: int, name: str, model: str) -> int:
    existing = conn.execute(
        "SELECT sensor_id FROM Sensor WHERE unit_id = ? AND name = ? LIMIT 1",
        (unit_id, name),
    ).fetchone()
    if existing:
        return existing["sensor_id"]
    cursor = conn.execute(
        """
        INSERT INTO Sensor (unit_id, name, sensor_type, protocol, model, is_active)
        VALUES (?, ?, ?, ?, ?, 1)
        """,
        (unit_id, name, "environment_sensor", "MQTT", model),
    )
    return cursor.lastrowid


def ensure_plant(conn, unit_id: int, name: str, plant_type: str) -> int:
    existing = conn.execute(
        "SELECT plant_id FROM Plants WHERE unit_id = ? AND name = ? LIMIT 1",
        (unit_id, name),
    ).fetchone()
    if existing:
        return existing["plant_id"]
    cursor = conn.execute(
        """
        INSERT INTO Plants (unit_id, name, plant_type, current_stage, days_in_stage, moisture_level, planted_date)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (unit_id, name, plant_type, "Vegetative", 10, 42.0, datetime.utcnow().date().isoformat()),
    )
    return cursor.lastrowid


def seed_readings(conn, sensor_id: int, hours: int = 48):
    now = datetime.utcnow()
    rows = []
    for i in range(hours):
        ts = now - timedelta(hours=hours - i)
        payload = {
            "temperature": round(22.5 + i * 0.05, 2),
            "humidity": round(55 + i * 0.1, 2),
            "soil_moisture": round(40 + i * 0.03, 2),
            "co2_ppm": 420 + i * 1.5,
            "voc_ppb": 30 + i * 0.5,
            "aqi": 15 + i % 5,
            "pressure": 1012 + i * 0.1,
        }
        rows.append((sensor_id, ts.isoformat(sep=" "), json.dumps(payload), 1.0))

    conn.executemany(
        """
        INSERT INTO SensorReading (sensor_id, timestamp, reading_data, quality_score)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )


def seed_health_logs(conn, unit_id: int, plant_id: int):
    base = datetime.utcnow() - timedelta(days=7)
    logs = []
    for i, status in enumerate(["healthy", "stressed", "stressed", "healthy", "healthy"]):
        ts = base + timedelta(days=i * 2)
        severity = 1 if status == "healthy" else 3
        logs.append(
            (
                unit_id,
                plant_id,
                ts.isoformat(sep=" "),
                status,
                json.dumps(["wilting"]) if status == "stressed" else None,
                "environmental_stress",
                severity,
                json.dumps(["leaves"]),
                None,
                "Adjusted irrigation schedule" if status == "stressed" else "No issues",
                None,
                None,
                None,
            )
        )

    conn.executemany(
        """
        INSERT INTO PlantHealthLogs (
            unit_id, plant_id, observation_date, health_status, symptoms, disease_type,
            severity_level, affected_parts, environmental_factors, treatment_applied,
            recovery_time_days, notes, image_path, user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
        """,
        logs,
    )


def main():
    parser = argparse.ArgumentParser(description="Seed demo data for sensor graphs")
    parser.add_argument("--db", default=Path.cwd() / "temp_graph.db", help="SQLite DB path")
    parser.add_argument("--unit", default="Demo Unit", help="Unit name")
    parser.add_argument("--location", default="Lab", help="Unit location")
    parser.add_argument("--sensor", default="Env Sensor A", help="Sensor name")
    parser.add_argument("--plant", default="Demo Plant", help="Plant name")
    parser.add_argument("--plant-type", default="Tomato", dest="plant_type", help="Plant type")
    args = parser.parse_args()

    handler = SQLiteDatabaseHandler(str(args.db))
    handler.create_tables()

    with handler.connection() as conn:
        unit_id = ensure_unit(conn, args.unit, args.location)
        sensor_id = ensure_sensor(conn, unit_id, args.sensor, model="DHT22")
        plant_id = ensure_plant(conn, unit_id, args.plant, args.plant_type)
        seed_readings(conn, sensor_id)
        seed_health_logs(conn, unit_id, plant_id)

    print(f"Seeded demo data into {args.db}")
    print(f"Unit ID: {unit_id}, Sensor ID: {sensor_id}, Plant ID: {plant_id}")
    print("To use this DB temporarily:")
    print(f"  export SYSGROW_DATABASE_PATH={args.db}")
    print("  python start_dev.py  # or your usual entrypoint")


if __name__ == "__main__":
    main()
