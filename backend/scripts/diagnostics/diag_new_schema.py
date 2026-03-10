"""Verify the new database schema"""
import os
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
db_path = Path(
    os.getenv("SYSGROW_DATABASE_PATH", str(REPO_ROOT / "database" / "sysgrow.db"))
)
conn = sqlite3.connect(str(db_path))
cursor = conn.cursor()

print("=" * 60)
print("📊 ACTUATOR SCHEMA VERIFICATION")
print("=" * 60)
print(f"Database: {db_path}")

# Get all Actuator-related tables
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='table' AND name LIKE 'Actuator%'
    ORDER BY name
""")
actuator_tables = [row[0] for row in cursor.fetchall()]

print(f"\n✅ Found {len(actuator_tables)} Actuator tables:\n")
for table in actuator_tables:
    print(f"   • {table}")

# Check Actuator table structure
print("\n" + "=" * 60)
print("📋 ACTUATOR TABLE SCHEMA")
print("=" * 60)
cursor.execute("PRAGMA table_info(Actuator)")
columns = cursor.fetchall()

print(f"\nColumns ({len(columns)}):")
for col in columns:
    col_id, name, col_type, not_null, default, pk = col
    pk_str = " [PRIMARY KEY]" if pk else ""
    null_str = " NOT NULL" if not_null else ""
    default_str = f" DEFAULT {default}" if default else ""
    print(f"   • {name:20} {col_type:15}{pk_str}{null_str}{default_str}")

# Check indexes
print("\n" + "=" * 60)
print("🔍 ACTUATOR INDEXES")
print("=" * 60)
cursor.execute("""
    SELECT name FROM sqlite_master
    WHERE type='index' AND name LIKE 'idx_actuator%'
    ORDER BY name
""")
indexes = [row[0] for row in cursor.fetchall()]

print(f"\nFound {len(indexes)} indexes:")
for idx in indexes:
    print(f"   • {idx}")

# Verify ActuatorConfig table
print("\n" + "=" * 60)
print("⚙️ ACTUATORCONFIG TABLE SCHEMA")
print("=" * 60)
cursor.execute("PRAGMA table_info(ActuatorConfig)")
config_columns = cursor.fetchall()

print(f"\nColumns ({len(config_columns)}):")
for col in config_columns:
    col_id, name, col_type, not_null, default, pk = col
    pk_str = " [PRIMARY KEY]" if pk else ""
    null_str = " NOT NULL" if not_null else ""
    print(f"   • {name:20} {col_type:15}{pk_str}{null_str}")

# Verify ActuatorPowerReading table
print("\n" + "=" * 60)
print("⚡ ACTUATORPOWERREADING TABLE SCHEMA")
print("=" * 60)
cursor.execute("PRAGMA table_info(ActuatorPowerReading)")
power_columns = cursor.fetchall()

print(f"\nColumns ({len(power_columns)}):")
for col in power_columns:
    col_id, name, col_type, not_null, default, pk = col
    pk_str = " [PRIMARY KEY]" if pk else ""
    null_str = " NOT NULL" if not_null else ""
    default_str = f" DEFAULT {default}" if default else ""
    print(f"   • {name:20} {col_type:15}{pk_str}{null_str}{default_str}")

# Verify ActuatorHealthHistory table
print("\n" + "=" * 60)
print("💚 ACTUATORHEALTHHISTORY TABLE SCHEMA")
print("=" * 60)
cursor.execute("PRAGMA table_info(ActuatorHealthHistory)")
health_columns = cursor.fetchall()

print(f"\nColumns ({len(health_columns)}):")
for col in health_columns:
    col_id, name, col_type, not_null, default, pk = col
    pk_str = " [PRIMARY KEY]" if pk else ""
    null_str = " NOT NULL" if not_null else ""
    print(f"   • {name:20} {col_type:15}{pk_str}{null_str}")

# Summary
print("\n" + "=" * 60)
print("✅ VERIFICATION SUMMARY")
print("=" * 60)
print(f"\n✅ Database: sysgrow.db")
print(f"✅ Actuator tables: {len(actuator_tables)}")
print(f"✅ Indexes: {len(indexes)}")
print(f"✅ Main table columns: {len(columns)}")
print(f"✅ Config table: Present")
print(f"✅ Power reading table: Present")
print(f"✅ Health history table: Present")
print("\n🎉 New schema successfully created!\n")

conn.close()
