import logging
import shutil
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

from flask import Flask

from infrastructure.database.ops.analytics import AnalyticsOperations
from infrastructure.database.ops.camera import CameraOperations
from infrastructure.database.ops.devices import DeviceOperations
from infrastructure.database.ops.growth import GrowthOperations
from infrastructure.database.ops.settings import SettingsOperations
from infrastructure.database.ops.alerts import AlertOperations
from infrastructure.database.ops.activity_log import ActivityOperations
from infrastructure.database.ops.notifications import NotificationOperations
from infrastructure.database.ops.irrigation_workflow import IrrigationWorkflowOperations
from infrastructure.database.ops.schedules import ScheduleOperations

logger = logging.getLogger(__name__)

class SQLiteDatabaseHandler(
    SettingsOperations,
    GrowthOperations,
    CameraOperations,
    AnalyticsOperations,
    DeviceOperations,
    AlertOperations,
    ActivityOperations,
    NotificationOperations,
    IrrigationWorkflowOperations,
    ScheduleOperations,
):
    """Thread-safe SQLite handler decoupled from Flask globals."""

    def __init__(self, database_path: str) -> None:
        self._database_path = database_path
        self._local = threading.local()
        
        # Ensure the directory for the database file exists
        db_path = Path(database_path)
        if not db_path.parent.exists():
            db_path.parent.mkdir(parents=True, exist_ok=True)
            logging.info(f"Created database directory: {db_path.parent}")

    # --- Lifecycle ------------------------------------------------------------
    def init_app(self, app: Flask | None = None) -> None:
        if app is not None:
            app.teardown_appcontext(self.close_db)
        self.create_tables()
        self.run_migrations()

    def run_migrations(self) -> None:
        """Run standard sequential migrations."""
        try:
            import os
            import importlib.util
            from pathlib import Path

            migrations_dir = Path(__file__).parent / "migrations"
            if not migrations_dir.exists():
                return

            # Get applied migrations from a table
            with self.connection() as db:
                db.execute("CREATE TABLE IF NOT EXISTS Migrations (migration_id INTEGER PRIMARY KEY)")
                cursor = db.execute("SELECT migration_id FROM Migrations")
                applied = {row[0] for row in cursor.fetchall()}

            # Find all .py migrations (e.g., 033_...)
            migration_files = sorted([
                f for f in migrations_dir.glob("*.py")
                if f.name[0].isdigit() and "_" in f.name
            ], key=lambda x: int(x.name.split("_")[0]))

            for migration_file in migration_files:
                try:
                    m_id = int(migration_file.name.split("_")[0])
                    if m_id in applied:
                        continue

                    logger.info("Running migration %s...", migration_file.name)
                    
                    # Import and run migrate()
                    spec = importlib.util.spec_from_file_location("migration_mod", str(migration_file))
                    if not spec or not spec.loader:
                        continue
                    mod = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(mod)
                    
                    if hasattr(mod, "migrate"):
                        if mod.migrate(self):
                            with self.connection() as db:
                                db.execute("INSERT INTO Migrations (migration_id) VALUES (?)", (m_id,))
                            logger.info("✓ Migration %s successful", migration_file.name)
                        else:
                            logger.error("❌ Migration %s failed", migration_file.name)
                except Exception as e:
                    logger.error("Failed to run migration %s: %s", migration_file.name, e)

        except Exception as e:
            logger.error("Migration runner failed: %s", e)

    def get_db(self) -> sqlite3.Connection:
        connection: Optional[sqlite3.Connection] = getattr(self._local, "connection", None)
        if connection is None:
            try:
                connection = self._open_connection()
            except sqlite3.DatabaseError as exc:
                if self._is_corruption_error(exc):
                    logger.error("Database appears corrupt (%s). Recreating a fresh database.", exc)
                    self._quarantine_corrupt_db()
                    connection = self._open_connection()
                else:
                    raise
            self._local.connection = connection
        return connection

    def _open_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, check_same_thread=False)
        try:
            connection.row_factory = sqlite3.Row
            self._configure_connection(connection)
            return connection
        except Exception:
            connection.close()
            raise

    def _is_corruption_error(self, exc: sqlite3.Error) -> bool:
        message = str(exc).lower()
        return (
            "database disk image is malformed" in message
            or "file is not a database" in message
            or "file is encrypted or is not a database" in message
            or "malformed" in message
        )

    def _quarantine_corrupt_db(self) -> Optional[Path]:
        db_path = Path(self._database_path)
        if not db_path.exists():
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        quarantine_dir = db_path.parent / "corrupt"
        quarantine_dir.mkdir(parents=True, exist_ok=True)

        suffix = db_path.suffix or ".db"
        quarantined = quarantine_dir / f"{db_path.stem}_corrupt_{timestamp}{suffix}"
        try:
            shutil.move(str(db_path), str(quarantined))
            for sidecar_suffix in ("-wal", "-shm"):
                sidecar = Path(f"{db_path}{sidecar_suffix}")
                if sidecar.exists():
                    sidecar_target = quarantine_dir / f"{sidecar.name}_{timestamp}"
                    shutil.move(str(sidecar), str(sidecar_target))
            logger.warning("Quarantined corrupt database to %s", quarantined)
            return quarantined
        except Exception as exc:
            logger.error("Failed to quarantine corrupt database %s: %s", db_path, exc)
            return None

    def _configure_connection(self, connection: sqlite3.Connection) -> None:
        """Configure SQLite connection with Raspberry Pi-friendly optimizations.

        Optimizations:
        - WAL mode: Enables concurrent reads, 20-40% faster writes
        - NORMAL synchronous: Faster than FULL, still safe with WAL
        - 64MB cache: Reduces disk I/O on Pi
        - Memory temp store: Avoids temp file creation
        """
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA cache_size=-64000")  # 64MB cache (negative = KB)
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
        connection.commit()

    def close_db(self, _e: Optional[BaseException] = None) -> None:
        connection: Optional[sqlite3.Connection] = getattr(self._local, "connection", None)
        if connection is not None:
            connection.close()
            delattr(self._local, "connection")

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        conn = self.get_db()
        try:
            yield conn
        finally:
            conn.commit()

    # --- Schema ----------------------------------------------------------------
    def create_tables(self) -> None:
        """Creates the necessary tables in the database if they do not already exist."""
        try:
            with self.connection() as db:
                # Users Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS Users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password_hash TEXT NOT NULL
                    )
                    """
                )
                # Recovery Codes for offline password reset
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS RecoveryCodes (
                        code_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        code_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        used_at TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
                    )
                    """
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_recovery_codes_user ON RecoveryCodes(user_id)"
                )
                # ✅ Hotspot WiFi Settings
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS HotspotSettings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        ssid TEXT NOT NULL,
                        encrypted_password TEXT NOT NULL
                    )
                    """
                )
                # Growth Units Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS GrowthUnits (
                        unit_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL DEFAULT 1,
                        name TEXT NOT NULL,
                        location TEXT DEFAULT "Indoor",
                        timezone TEXT,
                        dimensions TEXT,
                        custom_image TEXT,
                        active_plant_id INTEGER,
                        temperature_threshold REAL DEFAULT 24.0,
                        humidity_threshold REAL DEFAULT 50.0,
                        soil_moisture_threshold REAL DEFAULT 40.0,
                        co2_threshold REAL DEFAULT 800.0,
                        voc_threshold REAL DEFAULT 0.0,
                        lux_threshold INTEGER DEFAULT 500,
                        air_quality_threshold INTEGER DEFAULT 50,
                        camera_enabled BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP,
                        FOREIGN KEY (active_plant_id) REFERENCES Plants(plant_id),
                        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE
                    )
                    """
                )
                
                # Create indexes for GrowthUnits
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_growth_units_user_id ON GrowthUnits(user_id)"
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_growth_units_created_at ON GrowthUnits(created_at DESC)"
                )

                # =============================================================================
                # Device Schedules Table (centralized scheduling for all device types)
                # =============================================================================
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS DeviceSchedules (
                        schedule_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER NOT NULL,
                        name TEXT DEFAULT '',
                        device_type TEXT NOT NULL,
                        actuator_id INTEGER,
                        schedule_type TEXT NOT NULL DEFAULT 'simple',
                        start_time TEXT NOT NULL,
                        end_time TEXT NOT NULL,
                        interval_minutes INTEGER,
                        duration_minutes INTEGER,
                        days_of_week TEXT DEFAULT '[0,1,2,3,4,5,6]',
                        enabled BOOLEAN DEFAULT 1,
                        state_when_active TEXT DEFAULT 'on',
                        value REAL,
                        photoperiod_config TEXT,
                        priority INTEGER DEFAULT 0,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE,
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE SET NULL
                    )
                    """
                )
                
                # Indexes for DeviceSchedules
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_device_schedules_unit ON DeviceSchedules(unit_id)"
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_device_schedules_device_type ON DeviceSchedules(unit_id, device_type)"
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_device_schedules_actuator ON DeviceSchedules(actuator_id)"
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_device_schedules_enabled ON DeviceSchedules(unit_id, enabled)"
                )

                # Actuator Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS Actuator (
                        actuator_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        actuator_type VARCHAR(50) NOT NULL,
                        protocol VARCHAR(20) NOT NULL,
                        model VARCHAR(50) NOT NULL,
                        ieee_address TEXT,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )
                
                # Actuator Configuration Table (JSON-based flexible config)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ActuatorConfig (
                        config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        actuator_id INTEGER NOT NULL,
                        config_data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
                    )
                    """
                )
                
                # Actuator Calibration Table (Power profiles, PWM curves, timing)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ActuatorCalibration (
                        calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        actuator_id INTEGER NOT NULL,
                        calibration_type VARCHAR(20) DEFAULT 'power_profile',
                        calibration_data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
                    )
                    """
                )
                
                # Actuator Health History Table (Device health tracking)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ActuatorHealthHistory (
                        history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        actuator_id INTEGER NOT NULL,
                        health_score INTEGER NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        total_operations INTEGER DEFAULT 0,
                        failed_operations INTEGER DEFAULT 0,
                        average_response_time REAL DEFAULT 0.0,
                        last_successful_operation TIMESTAMP,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
                    )
                    """
                )
                
                # Actuator Anomaly Detection Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ActuatorAnomaly (
                        anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        actuator_id INTEGER NOT NULL,
                        anomaly_type VARCHAR(50) NOT NULL,
                        severity VARCHAR(20) NOT NULL,
                        details TEXT,
                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        resolved_at TIMESTAMP,
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
                    )
                    """
                )

                # Actuator State History (On/Off/PWM level changes)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ActuatorStateHistory (
                        state_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        actuator_id INTEGER NOT NULL,
                        state VARCHAR(20) NOT NULL,
                        value REAL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE CASCADE
                    )
                    """
                )

                # Device Connectivity History (MQTT/WiFi/Zigbee connectivity status)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS DeviceConnectivityHistory (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        connection_type VARCHAR(20) NOT NULL, -- e.g., mqtt, wifi, zigbee
                        status VARCHAR(20) NOT NULL,          -- connected/disconnected
                        endpoint VARCHAR(255),                -- host:port or SSID
                        broker VARCHAR(255),                  -- alias for endpoint when mqtt
                        port INTEGER,
                        unit_id INTEGER,
                        device_id VARCHAR(100),
                        details TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                # Sensor Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS Sensor (
                        sensor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER NOT NULL,
                        name VARCHAR(100) NOT NULL,
                        sensor_type VARCHAR(50) NOT NULL,
                        protocol VARCHAR(20) NOT NULL,
                        model VARCHAR(50) NOT NULL,
                        priority INTEGER DEFAULT 30,
                        is_active BOOLEAN DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )
                
                # Sensor Configuration Table (JSON-based flexible config)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS SensorConfig (
                        config_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sensor_id INTEGER NOT NULL,
                        config_data TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
                    )
                    """
                )
                
                # Sensor Calibration Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS SensorCalibration (
                        calibration_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sensor_id INTEGER NOT NULL,
                        measured_value REAL NOT NULL,
                        reference_value REAL NOT NULL,
                        calibration_type VARCHAR(20) DEFAULT 'linear',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
                    )
                    """
                )
                
                # Sensor Health History Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS SensorHealthHistory (
                        history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sensor_id INTEGER NOT NULL,
                        health_score INTEGER NOT NULL,
                        status VARCHAR(20) NOT NULL,
                        error_rate REAL DEFAULT 0.0,
                        total_readings INTEGER DEFAULT 0,
                        failed_readings INTEGER DEFAULT 0,
                        recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
                    )
                    """
                )
                
                # Sensor Anomaly Detection Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS SensorAnomaly (
                        anomaly_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sensor_id INTEGER NOT NULL,
                        value REAL NOT NULL,
                        mean_value REAL,
                        std_deviation REAL,
                        z_score REAL,
                        detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
                    )
                    """
                )

                # Sensor Readings Table (JSON-based flexible readings)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS SensorReading (
                        reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        sensor_id INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        reading_data TEXT NOT NULL,
                        quality_score REAL DEFAULT 1.0,
                        FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id) ON DELETE CASCADE
                    )
                    """
                )

                # Plants Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS Plants (
                        plant_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER,
                        name TEXT NOT NULL,
                        plant_type TEXT NOT NULL,
                        plant_species TEXT,
                        plant_variety TEXT,
                        current_stage TEXT,
                        days_in_stage INTEGER,
                        moisture_level REAL,
                        planted_date DATETIME,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                        pot_size_liters REAL DEFAULT 0.0,
                        pot_material TEXT DEFAULT 'plastic',
                        growing_medium TEXT DEFAULT 'soil',
                        medium_ph REAL DEFAULT 7.0,
                        strain_variety TEXT,
                        expected_yield_grams REAL DEFAULT 0.0,
                        light_distance_cm REAL DEFAULT 0.0,
                        temperature_threshold_override REAL,
                        humidity_threshold_override REAL,
                        soil_moisture_threshold_override REAL,
                        co2_threshold_override REAL,
                        voc_threshold_override REAL,
                        lux_threshold_override REAL,
                        air_quality_threshold_override REAL,
                        
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE SET NULL
                    )
                    """
                )

                # Actuator History Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ActuatorHistory (
                        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        actuator_id INTEGER NOT NULL,
                        unit_id INTEGER NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        action TEXT NOT NULL,
                        value INTEGER,
                        duration INTEGER,
                        reason TEXT,
                        triggered_by VARCHAR(50),
                        power_consumed_kwh REAL,
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id),
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )

                # AI Decision Logs
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS AI_DecisionLogs (
                        log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        ai_temperature REAL,
                        ai_humidity REAL,
                        ai_soil_moisture REAL,
                        actual_temperature REAL,
                        actual_humidity REAL,
                        actual_soil_moisture REAL,
                        actuator_triggered BOOLEAN DEFAULT 0,
                        override BOOLEAN DEFAULT 0,
                        reason TEXT,
                        confidence_level REAL,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS Feedback (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        decision_log_id INTEGER,
                        score INTEGER CHECK(score BETWEEN 1 AND 5),
                        comments TEXT,
                        FOREIGN KEY (decision_log_id) REFERENCES AI_DecisionLogs(log_id)
                    )
                    """
                )

                # Threshold Overrides Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ThresholdOverrides (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER NOT NULL,
                        temperature_threshold REAL,
                        humidity_threshold REAL,
                        soil_moisture_threshold REAL,
                        manual_override BOOLEAN DEFAULT 0,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )

                # Camera Settings
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS CameraSettings (
                        id INTEGER PRIMARY KEY,
                        camera_type TEXT,
                        ip_address TEXT,
                        usb_cam_index INTEGER,
                        last_used TEXT,
                        resolution INTEGER,
                        quality INTEGER,
                        brightness INTEGER,
                        contrast INTEGER,
                        saturation INTEGER,
                        flip INTEGER
                    )
                    """
                )

                # Per-unit camera configs (new multi-camera implementation)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS camera_configs (
                        camera_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER NOT NULL,
                        camera_type TEXT NOT NULL CHECK(camera_type IN ('esp32', 'usb', 'rtsp', 'mjpeg', 'http')),
                        stream_url TEXT,
                        ip_address TEXT,
                        port INTEGER DEFAULT 81,
                        device_index INTEGER,
                        username TEXT,
                        password TEXT,
                        resolution TEXT DEFAULT '640x480',
                        quality INTEGER DEFAULT 10,
                        brightness INTEGER DEFAULT 0,
                        contrast INTEGER DEFAULT 0,
                        saturation INTEGER DEFAULT 0,
                        flip INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(unit_id),
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE
                    )
                    """
                )
                db.execute(
                    "CREATE INDEX IF NOT EXISTS idx_camera_configs_unit_id ON camera_configs(unit_id)"
                )

                # Plant-level readings (aggregated per plant/unit snapshot)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS PlantReadings (
                        reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plant_id INTEGER,
                        unit_id INTEGER,
                        temperature REAL,
                        humidity REAL,
                        soil_moisture REAL,
                        ph REAL,
                        ec REAL,
                        co2 REAL,
                        voc REAL,
                        air_quality INTEGER,
                        pressure REAL,
                        lux REAL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )

                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS PlantSensors (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plant_id INTEGER,
                        sensor_id INTEGER,
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                        FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id)
                    )
                    """
                )

                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS PlantActuators (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plant_id INTEGER NOT NULL,
                        actuator_id INTEGER NOT NULL,
                        UNIQUE(actuator_id),
                        UNIQUE(plant_id, actuator_id),
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id)
                    )
                    """
                )

                # Plant History Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS plant_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plant_name TEXT,
                        days_germination INTEGER,
                        days_seed INTEGER,
                        days_veg INTEGER,
                        days_flower INTEGER,
                        days_fruit_dev INTEGER,
                        avg_temp REAL,
                        avg_humidity REAL,
                        light_hours REAL,
                        harvest_weight REAL,
                        photo_path TEXT,
                        date_harvested DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS GrowthUnitPlants (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER NOT NULL,
                        plant_id INTEGER NOT NULL,
                        UNIQUE(unit_id, plant_id),
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
                    )
                    """
                )
                # ZigBee Energy Monitor Tables
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ZigBeeEnergyMonitors (
                        monitor_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_name TEXT NOT NULL,
                        zigbee_address TEXT UNIQUE NOT NULL,
                        unit_id INTEGER,
                        device_type TEXT NOT NULL, -- 'lights', 'fan', 'extractor', 'heater', etc.
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        is_active BOOLEAN DEFAULT 1,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )
                
                # Unified Energy Monitoring Table (replaces ActuatorEnergyReadings & ActuatorPowerReading)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS EnergyReadings (
                        reading_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_id INTEGER NOT NULL,
                        plant_id INTEGER,
                        unit_id INTEGER NOT NULL,
                        growth_stage TEXT,
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        voltage REAL,
                        current REAL,
                        power_watts REAL NOT NULL,
                        energy_kwh REAL,
                        power_factor REAL,
                        frequency REAL,
                        temperature REAL,
                        source_type TEXT NOT NULL,
                        is_estimated BOOLEAN DEFAULT 0,
                        FOREIGN KEY (device_id) REFERENCES Devices(device_id) ON DELETE CASCADE,
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id) ON DELETE SET NULL,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE
                    )
                    """
                )
                
                # Plant Harvest Summary Table (comprehensive lifecycle report)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS PlantHarvestSummary (
                        harvest_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plant_id INTEGER NOT NULL,
                        unit_id INTEGER NOT NULL,
                        planted_date TIMESTAMP NOT NULL,
                        harvested_date TIMESTAMP NOT NULL,
                        total_days INTEGER NOT NULL,
                        seedling_days INTEGER,
                        vegetative_days INTEGER,
                        flowering_days INTEGER,
                        total_energy_kwh REAL NOT NULL,
                        energy_by_stage TEXT,
                        total_cost REAL,
                        cost_by_stage TEXT,
                        device_usage TEXT,
                        avg_daily_power_watts REAL,
                        total_light_hours REAL,
                        light_hours_by_stage TEXT,
                        avg_ppfd REAL,
                        health_incidents TEXT,
                        disease_days INTEGER DEFAULT 0,
                        pest_days INTEGER DEFAULT 0,
                        avg_health_score REAL,
                        avg_temperature REAL,
                        avg_humidity REAL,
                        avg_co2 REAL,
                        harvest_weight_grams REAL,
                        quality_rating INTEGER,
                        notes TEXT,
                        grams_per_kwh REAL,
                        cost_per_gram REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )
                
                # Environment Information Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS EnvironmentInfo (
                        env_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER NOT NULL,
                        room_width REAL, -- meters
                        room_length REAL, -- meters
                        room_height REAL, -- meters
                        room_volume REAL, -- cubic meters (calculated)
                        insulation_type TEXT, -- 'poor', 'average', 'good', 'excellent'
                        ventilation_type TEXT, -- 'natural', 'forced', 'hvac'
                        window_area REAL, -- square meters
                        light_source_type TEXT, -- 'led', 'hps', 'fluorescent', 'natural'
                        ambient_light_hours REAL, -- natural light hours per day
                        location_climate TEXT, -- 'tropical', 'temperate', 'arid', 'cold'
                        outdoor_temperature_avg REAL,
                        outdoor_humidity_avg REAL,
                        electricity_cost_per_kwh REAL, -- local electricity cost
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )
                
                # Plant Health and Disease Tracking
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS PlantHealthLogs (
                        health_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER,
                        plant_id INTEGER,
                        observation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        health_status TEXT NOT NULL, -- 'healthy', 'stressed', 'diseased', 'pest_infestation'
                        symptoms TEXT, -- JSON array of symptoms
                        disease_type TEXT, -- 'fungal', 'bacterial', 'viral', 'pest', 'nutrient_deficiency'
                        severity_level INTEGER, -- 1-5 scale
                        affected_parts TEXT, -- 'leaves', 'stem', 'roots', 'flowers', 'fruit'
                        environmental_factors TEXT, -- JSON of suspected environmental causes
                        treatment_applied TEXT,
                        recovery_time_days INTEGER,
                        notes TEXT,
                        image_path TEXT, -- path to uploaded image
                        user_id INTEGER,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                        FOREIGN KEY (user_id) REFERENCES Users(id)
                    )
                    """
                )
                
                # Energy Device Mapping (for consumption estimation)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS DeviceEnergyProfiles (
                        profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        device_type TEXT NOT NULL,
                        device_model TEXT,
                        rated_power_watts REAL NOT NULL,
                        efficiency_factor REAL DEFAULT 1.0, -- actual vs rated power
                        power_curve TEXT, -- JSON describing power consumption curve
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(device_type, device_model)
                    )
                    """
                )
                
                # ML Model Training History
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS MLModelTraining (
                        training_session_id TEXT PRIMARY KEY,
                        model_version TEXT NOT NULL,
                        training_start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        training_end_time TIMESTAMP,
                        data_points_used INTEGER,
                        model_accuracy REAL,
                        validation_score REAL,
                        model_file_path TEXT,
                        training_parameters TEXT, -- JSON of hyperparameters
                        features_used TEXT, -- JSON array of feature names
                        target_variables TEXT, -- JSON array of target variables
                        status TEXT DEFAULT 'running', -- 'running', 'completed', 'failed'
                        error_message TEXT,
                        scheduled_training BOOLEAN DEFAULT 0,
                        auto_deploy BOOLEAN DEFAULT 0
                    )
                    """
                )
                
                # Activity Logging System
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ActivityLog (
                        activity_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        user_id INTEGER,
                        activity_type TEXT NOT NULL CHECK(activity_type IN (
                            'plant_added', 'plant_removed', 'plant_updated',
                            'unit_created', 'unit_updated', 'unit_deleted',
                            'device_connected', 'device_disconnected', 'device_configured',
                            'sensor_reading', 'actuator_triggered',
                            'harvest_recorded', 'harvest_updated',
                            'threshold_override', 'manual_control',
                            'system_startup', 'system_shutdown',
                            'user_login', 'user_logout'
                        )),
                        severity TEXT NOT NULL DEFAULT 'info' CHECK(severity IN ('info', 'warning', 'error')),
                        entity_type TEXT,
                        entity_id INTEGER,
                        description TEXT NOT NULL,
                        metadata TEXT,
                        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE SET NULL
                    )
                    """
                )
                
                # Alert and Notification System
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS Alert (
                        alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        alert_type TEXT NOT NULL CHECK(alert_type IN (
                            'device_offline', 'device_malfunction',
                            'sensor_anomaly', 'actuator_failure',
                            'threshold_exceeded', 'plant_health_warning',
                            'low_battery', 'connection_lost',
                            'system_error', 'maintenance_required',
                            'harvest_ready', 'water_low'
                        )),
                        severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'critical')),
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        source_type TEXT,
                        source_id INTEGER,
                        unit_id INTEGER,
                        acknowledged BOOLEAN DEFAULT 0,
                        acknowledged_at DATETIME,
                        acknowledged_by INTEGER,
                        resolved BOOLEAN DEFAULT 0,
                        resolved_at DATETIME,
                        metadata TEXT,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE,
                        FOREIGN KEY (acknowledged_by) REFERENCES Users(id) ON DELETE SET NULL
                    )
                    """
                )
                
                # Create indexes for better performance
                
                # New unified energy table indexes
                db.execute("CREATE INDEX IF NOT EXISTS idx_energy_device_time ON EnergyReadings(device_id, timestamp DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_energy_plant ON EnergyReadings(plant_id) WHERE plant_id IS NOT NULL")
                db.execute("CREATE INDEX IF NOT EXISTS idx_energy_unit_stage ON EnergyReadings(unit_id, growth_stage)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_energy_timestamp ON EnergyReadings(timestamp DESC)")
                
                # Harvest summary indexes
                db.execute("CREATE INDEX IF NOT EXISTS idx_harvest_plant ON PlantHarvestSummary(plant_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_harvest_date ON PlantHarvestSummary(harvested_date DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_harvest_unit ON PlantHarvestSummary(unit_id)")
                
                db.execute("CREATE INDEX IF NOT EXISTS idx_plant_health_date ON PlantHealthLogs(observation_date)")
                
                # A/B Testing Tables
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ABTests (
                        test_id TEXT PRIMARY KEY,
                        model_name TEXT NOT NULL,
                        version_a TEXT NOT NULL,
                        version_b TEXT NOT NULL,
                        split_ratio REAL DEFAULT 0.5,
                        start_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                        end_date DATETIME,
                        status TEXT DEFAULT 'running' CHECK(status IN ('running', 'completed', 'cancelled')),
                        min_samples INTEGER DEFAULT 100,
                        winner TEXT,
                        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
                
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ABTestResults (
                        result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        test_id TEXT NOT NULL,
                        version TEXT NOT NULL CHECK(version IN ('a', 'b')),
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        predicted TEXT,
                        actual TEXT,
                        error REAL,
                        FOREIGN KEY (test_id) REFERENCES ABTests(test_id) ON DELETE CASCADE
                    )
                    """
                )
                
                # Drift Metrics Table
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS DriftMetrics (
                        metric_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        model_name TEXT NOT NULL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        prediction TEXT,
                        actual TEXT,
                        confidence REAL,
                        error REAL
                    )
                    """
                )
                
                # AB Test and Drift indexes
                db.execute("CREATE INDEX IF NOT EXISTS idx_abtest_status ON ABTests(status)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_abtest_model ON ABTests(model_name)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_abtestresults_test ON ABTestResults(test_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_drift_model_time ON DriftMetrics(model_name, timestamp DESC)")
                
                # Activity log indexes
                db.execute("CREATE INDEX IF NOT EXISTS idx_activity_timestamp ON ActivityLog(timestamp DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_activity_type ON ActivityLog(activity_type)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_activity_user ON ActivityLog(user_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_activity_entity ON ActivityLog(entity_type, entity_id)")
                
                # Alert system indexes
                db.execute("CREATE INDEX IF NOT EXISTS idx_alert_active ON Alert(resolved, acknowledged, severity, timestamp DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_alert_type ON Alert(alert_type)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_alert_unit ON Alert(unit_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_alert_source ON Alert(source_type, source_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_alert_timestamp ON Alert(timestamp DESC)")
                # Dedupe mapping table for reliable indexed deduplication across processes
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS AlertDedupe (
                        dedupe_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        dedup_key TEXT UNIQUE NOT NULL,
                        alert_id INTEGER NOT NULL,
                        occurrences INTEGER DEFAULT 1,
                        last_seen DATETIME,
                        FOREIGN KEY (alert_id) REFERENCES Alert(alert_id) ON DELETE CASCADE
                    )
                    """
                )
                db.execute("CREATE INDEX IF NOT EXISTS idx_alertdedupe_key ON AlertDedupe(dedup_key)")

                # Notification Settings (user preferences)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS NotificationSettings (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        email_enabled BOOLEAN DEFAULT 0,
                        in_app_enabled BOOLEAN DEFAULT 1,
                        email_address TEXT,
                        smtp_host TEXT,
                        smtp_port INTEGER DEFAULT 587,
                        smtp_username TEXT,
                        smtp_password_encrypted TEXT,
                        smtp_use_tls BOOLEAN DEFAULT 1,
                        notify_low_battery BOOLEAN DEFAULT 1,
                        notify_plant_needs_water BOOLEAN DEFAULT 1,
                        notify_irrigation_confirm BOOLEAN DEFAULT 1,
                        notify_threshold_exceeded BOOLEAN DEFAULT 1,
                        notify_device_offline BOOLEAN DEFAULT 1,
                        notify_harvest_ready BOOLEAN DEFAULT 1,
                        notify_plant_health_warning BOOLEAN DEFAULT 1,
                        irrigation_feedback_enabled BOOLEAN DEFAULT 1,
                        irrigation_feedback_delay_minutes INTEGER DEFAULT 30,
                        quiet_hours_enabled BOOLEAN DEFAULT 0,
                        quiet_hours_start TEXT,
                        quiet_hours_end TEXT,
                        min_notification_interval_seconds INTEGER DEFAULT 300,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                        UNIQUE(user_id)
                    )
                    """
                )

                # Notification Messages (history/queue)
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS NotificationMessage (
                        message_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        notification_type TEXT NOT NULL CHECK(notification_type IN (
                            'low_battery', 'plant_needs_water', 'irrigation_confirm',
                            'irrigation_feedback', 'threshold_exceeded', 'device_offline',
                            'harvest_ready', 'plant_health_warning', 'system_alert'
                        )),
                        title TEXT NOT NULL,
                        message TEXT NOT NULL,
                        severity TEXT NOT NULL CHECK(severity IN ('info', 'warning', 'critical')),
                        source_type TEXT,
                        source_id INTEGER,
                        unit_id INTEGER,
                        channel TEXT NOT NULL CHECK(channel IN ('email', 'in_app', 'both')),
                        email_sent BOOLEAN DEFAULT 0,
                        email_sent_at TIMESTAMP,
                        email_error TEXT,
                        in_app_sent BOOLEAN DEFAULT 0,
                        in_app_read BOOLEAN DEFAULT 0,
                        in_app_read_at TIMESTAMP,
                        requires_action BOOLEAN DEFAULT 0,
                        action_type TEXT,
                        action_data TEXT,
                        action_taken BOOLEAN DEFAULT 0,
                        action_response TEXT,
                        action_taken_at TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        expires_at TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE SET NULL
                    )
                    """
                )

                # Irrigation Feedback Records
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS IrrigationFeedback (
                        feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        unit_id INTEGER NOT NULL,
                        plant_id INTEGER,
                        soil_moisture_before REAL,
                        soil_moisture_after REAL,
                        irrigation_duration_seconds INTEGER,
                        actuator_id INTEGER,
                        feedback_response TEXT CHECK(feedback_response IN (
                            'too_little', 'just_right', 'too_much',
                            'triggered_too_early', 'triggered_too_late',
                            'skipped'
                        )),
                        feedback_notes TEXT,
                        suggested_threshold_adjustment REAL,
                        threshold_adjustment_applied BOOLEAN DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE CASCADE,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id) ON DELETE CASCADE,
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id) ON DELETE SET NULL,
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id) ON DELETE SET NULL
                    )
                    """
                )

                # Notification indexes
                db.execute("CREATE INDEX IF NOT EXISTS idx_notification_settings_user ON NotificationSettings(user_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_notification_message_user ON NotificationMessage(user_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_notification_message_unread ON NotificationMessage(user_id, in_app_read, created_at DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_notification_message_action ON NotificationMessage(requires_action, action_taken, user_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_notification_message_type ON NotificationMessage(notification_type, created_at DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_irrigation_feedback_unit ON IrrigationFeedback(unit_id, created_at DESC)")

                # =============================================================================
                # Irrigation Workflow Tables
                # =============================================================================

                # PendingIrrigationRequest - Stores pending irrigation requests awaiting approval
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS PendingIrrigationRequest (
                        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER NOT NULL,
                        plant_id INTEGER,
                        user_id INTEGER NOT NULL DEFAULT 1,
                        actuator_id INTEGER,
                        actuator_type TEXT DEFAULT 'water_pump',
                        soil_moisture_detected REAL NOT NULL,
                        soil_moisture_threshold REAL NOT NULL,
                        sensor_id INTEGER,
                        status TEXT NOT NULL DEFAULT 'pending',
                        execution_status TEXT,
                        claimed_at_utc TEXT,
                        attempt_count INTEGER DEFAULT 0,
                        last_attempt_at_utc TEXT,
                        detected_at TEXT NOT NULL,
                        scheduled_time TEXT,
                        delayed_until TEXT,
                        expires_at TEXT,
                        user_response TEXT,
                        user_response_at TEXT,
                        notification_id INTEGER,
                        executed_at TEXT,
                        execution_duration_seconds INTEGER,
                        soil_moisture_after REAL,
                        execution_success INTEGER DEFAULT 0,
                        execution_error TEXT,
                        feedback_id INTEGER,
                        feedback_requested_at TEXT,
                        ml_data_collected INTEGER DEFAULT 0,
                        ml_preference_score REAL,
                        temperature_at_detection REAL,
                        humidity_at_detection REAL,
                        vpd_at_detection REAL,
                        lux_at_detection REAL,
                        hours_since_last_irrigation REAL,
                        plant_type TEXT,
                        growth_stage TEXT,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                        FOREIGN KEY (actuator_id) REFERENCES Actuator(actuator_id),
                        FOREIGN KEY (sensor_id) REFERENCES Sensor(sensor_id),
                        FOREIGN KEY (notification_id) REFERENCES NotificationMessage(message_id),
                        FOREIGN KEY (feedback_id) REFERENCES IrrigationFeedback(feedback_id)
                    )
                    """
                )

                # IrrigationWorkflowConfig - Per-unit workflow configuration
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS IrrigationWorkflowConfig (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        unit_id INTEGER NOT NULL UNIQUE,
                        workflow_enabled INTEGER NOT NULL DEFAULT 1,
                        auto_irrigation_enabled INTEGER NOT NULL DEFAULT 0,
                        manual_mode_enabled INTEGER NOT NULL DEFAULT 0,
                        require_approval INTEGER NOT NULL DEFAULT 1,
                        default_scheduled_time TEXT DEFAULT '21:00',
                        delay_increment_minutes INTEGER DEFAULT 60,
                        max_delay_hours INTEGER DEFAULT 24,
                        expiration_hours INTEGER DEFAULT 48,
                        send_reminder_before_execution INTEGER DEFAULT 1,
                        reminder_minutes_before INTEGER DEFAULT 30,
                        request_feedback_enabled INTEGER DEFAULT 1,
                        feedback_delay_minutes INTEGER DEFAULT 30,
                        ml_learning_enabled INTEGER DEFAULT 1,
                        ml_threshold_adjustment_enabled INTEGER DEFAULT 0,
                        ml_response_predictor_enabled INTEGER DEFAULT 0,
                        ml_threshold_optimizer_enabled INTEGER DEFAULT 0,
                        ml_duration_optimizer_enabled INTEGER DEFAULT 0,
                        ml_timing_predictor_enabled INTEGER DEFAULT 0,
                        ml_response_predictor_notified_at TEXT,
                        ml_threshold_optimizer_notified_at TEXT,
                        ml_duration_optimizer_notified_at TEXT,
                        ml_timing_predictor_notified_at TEXT,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )

                # IrrigationUserPreference - User preferences learned from responses
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS IrrigationUserPreference (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        unit_id INTEGER,
                        preferred_irrigation_time TEXT,
                        preferred_day_of_week INTEGER,
                        total_requests INTEGER DEFAULT 0,
                        immediate_approvals INTEGER DEFAULT 0,
                        delayed_approvals INTEGER DEFAULT 0,
                        cancellations INTEGER DEFAULT 0,
                        auto_executions INTEGER DEFAULT 0,
                        approval_rate REAL,
                        responsiveness_score REAL,
                        avg_response_time_seconds REAL,
                        preferred_moisture_threshold REAL,
                        threshold_belief_json TEXT,
                        threshold_variance REAL,
                        threshold_sample_count INTEGER DEFAULT 0,
                        moisture_feedback_count INTEGER DEFAULT 0,
                        too_little_feedback_count INTEGER DEFAULT 0,
                        just_right_feedback_count INTEGER DEFAULT 0,
                        too_much_feedback_count INTEGER DEFAULT 0,
                        created_at TEXT DEFAULT (datetime('now')),
                        updated_at TEXT,
                        UNIQUE(user_id, unit_id),
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )

                # IrrigationExecutionLog - Execution telemetry
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS IrrigationExecutionLog (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        request_id INTEGER,
                        user_id INTEGER,
                        unit_id INTEGER NOT NULL,
                        plant_id INTEGER,
                        sensor_id TEXT,
                        trigger_reason TEXT NOT NULL,
                        trigger_moisture REAL,
                        threshold_at_trigger REAL,
                        triggered_at_utc TEXT NOT NULL,
                        planned_duration_s INTEGER,
                        actual_duration_s INTEGER,
                        pump_actuator_id TEXT,
                        valve_actuator_id TEXT,
                        assumed_flow_ml_s REAL,
                        estimated_volume_ml REAL,
                        execution_status TEXT NOT NULL,
                        execution_error TEXT,
                        executed_at_utc TEXT NOT NULL,
                        post_moisture REAL,
                        post_moisture_delay_s INTEGER,
                        post_measured_at_utc TEXT,
                        delta_moisture REAL,
                        recommendation TEXT,
                        created_at_utc TEXT NOT NULL,
                        FOREIGN KEY (request_id) REFERENCES PendingIrrigationRequest(request_id),
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id),
                        FOREIGN KEY (user_id) REFERENCES Users(id)
                    )
                    """
                )

                # IrrigationEligibilityTrace - Decision trace
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS IrrigationEligibilityTrace (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        plant_id INTEGER,
                        unit_id INTEGER NOT NULL,
                        sensor_id TEXT,
                        moisture REAL,
                        threshold REAL,
                        decision TEXT NOT NULL,
                        skip_reason TEXT,
                        evaluated_at_utc TEXT NOT NULL,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
                    )
                    """
                )

                # ManualIrrigationLog - Manual watering events
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS ManualIrrigationLog (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        unit_id INTEGER NOT NULL,
                        plant_id INTEGER NOT NULL,
                        watered_at_utc TEXT NOT NULL,
                        amount_ml REAL,
                        notes TEXT,
                        pre_moisture REAL,
                        pre_moisture_at_utc TEXT,
                        post_moisture REAL,
                        post_moisture_at_utc TEXT,
                        settle_delay_min INTEGER DEFAULT 15,
                        delta_moisture REAL,
                        created_at_utc TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES Users(id),
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id),
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
                    )
                    """
                )

                # PlantIrrigationModel - Per-plant dry-down model
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS PlantIrrigationModel (
                        plant_id INTEGER PRIMARY KEY,
                        drydown_rate_per_hour REAL,
                        sample_count INTEGER DEFAULT 0,
                        confidence REAL,
                        updated_at_utc TEXT NOT NULL,
                        FOREIGN KEY (plant_id) REFERENCES Plants(plant_id)
                    )
                    """
                )

                # IrrigationLock - Unit-level execution lock
                db.execute(
                    """
                    CREATE TABLE IF NOT EXISTS IrrigationLock (
                        unit_id INTEGER PRIMARY KEY,
                        locked_until_utc TEXT NOT NULL,
                        FOREIGN KEY (unit_id) REFERENCES GrowthUnits(unit_id)
                    )
                    """
                )

                # Irrigation workflow indexes
                db.execute("CREATE INDEX IF NOT EXISTS idx_pending_irrigation_unit ON PendingIrrigationRequest(unit_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_pending_irrigation_user ON PendingIrrigationRequest(user_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_pending_irrigation_status ON PendingIrrigationRequest(status)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_pending_irrigation_scheduled ON PendingIrrigationRequest(scheduled_time)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_pending_irrigation_detected ON PendingIrrigationRequest(detected_at)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_irrigation_workflow_config_unit ON IrrigationWorkflowConfig(unit_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_irrigation_user_pref_user ON IrrigationUserPreference(user_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_irrigation_user_pref_unit ON IrrigationUserPreference(unit_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_irrigation_execution_unit_time ON IrrigationExecutionLog(unit_id, executed_at_utc)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_irrigation_execution_plant_time ON IrrigationExecutionLog(plant_id, executed_at_utc)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_irrigation_execution_request ON IrrigationExecutionLog(request_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_irrigation_eligibility_unit_time ON IrrigationEligibilityTrace(unit_id, evaluated_at_utc)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_irrigation_eligibility_plant_time ON IrrigationEligibilityTrace(plant_id, evaluated_at_utc)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_manual_irrigation_plant_time ON ManualIrrigationLog(plant_id, watered_at_utc)")

                # Sensor table indexes (Enterprise Architecture)
                db.execute("CREATE INDEX IF NOT EXISTS idx_sensor_unit_id ON Sensor(unit_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_sensor_type ON Sensor(sensor_type)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_sensor_protocol ON Sensor(protocol)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_sensor_health_sensor_id ON SensorHealthHistory(sensor_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_sensor_anomaly_sensor_id ON SensorAnomaly(sensor_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_sensor_calibration_sensor_id ON SensorCalibration(sensor_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_sensor_reading_sensor_id ON SensorReading(sensor_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_sensor_reading_timestamp ON SensorReading(timestamp)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_plant_readings_time ON PlantReadings(timestamp DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_plant_readings_plant ON PlantReadings(plant_id)")
                
                # Create indexes for actuators
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_unit_id ON Actuator(unit_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_type ON Actuator(actuator_type)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_protocol ON Actuator(protocol)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_ieee_address ON Actuator(ieee_address)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_health_actuator_id ON ActuatorHealthHistory(actuator_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_anomaly_actuator_id ON ActuatorAnomaly(actuator_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_calibration_actuator_id ON ActuatorCalibration(actuator_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_history_actuator_id ON ActuatorHistory(actuator_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_history_unit_id ON ActuatorHistory(unit_id)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_history_timestamp ON ActuatorHistory(timestamp)")

                # Actuator State History indexes
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_state_time ON ActuatorStateHistory(timestamp DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_actuator_state_actuator_time ON ActuatorStateHistory(actuator_id, timestamp DESC)")

                # Connectivity History indexes
                db.execute("CREATE INDEX IF NOT EXISTS idx_connectivity_type_time ON DeviceConnectivityHistory(connection_type, timestamp DESC)")
                db.execute("CREATE INDEX IF NOT EXISTS idx_connectivity_time ON DeviceConnectivityHistory(timestamp DESC)")

                self._ensure_settings_seeded()
                self._seed_device_energy_profiles()
        except sqlite3.Error as exc:
            logging.error("Error creating tables: %s", exc)

        self._seed_default_plants()

    # --- User management ------------------------------------------------------
    def insert_user(self, username: str, password_hash: str) -> None:
        """Inserts a new user into the Users table."""
        try:
            with self.connection() as conn:
                conn.execute(
                    "INSERT INTO Users (username, password_hash) VALUES (?, ?)",
                    (username, password_hash),
                )
        except sqlite3.Error as exc:
            logging.error("Error inserting user: %s", exc)
            raise

    def get_user_by_username(self, username: str):
        """Fetches a user by username."""
        try:
            db = self.get_db()
            return db.execute("SELECT * FROM Users WHERE username = ?", (username,)).fetchone()
        except sqlite3.Error as exc:
            logging.error("Error fetching user: %s", exc)
            return None

    def _seed_default_plants(self) -> None:
        """Populate the Plants table with catalog data when empty."""
        try:
            with self.connection() as conn:
                # Check if table exists first
                table_check = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name='Plants'"
                ).fetchone()
                if not table_check:
                    logging.warning("Plants table does not exist yet, skipping seed")
                    return
                
                existing = conn.execute("SELECT COUNT(*) FROM Plants").fetchone()[0]
                if existing:
                    return
        except sqlite3.Error as exc:
            logging.error("Error checking Plants table: %s", exc)
            return

        try:
            from app.utils.plant_json_handler import PlantJsonHandler

            catalog = PlantJsonHandler().get_plants_info()
        except Exception as exc:  # pylint: disable=broad-except
            logging.error("Unable to load plant catalog: %s", exc)
            return

        if not catalog:
            logging.info("No catalog entries found for seeding Plants table.")
            return

        rows = []
        for entry in catalog:
            common_name = entry.get("common_name")
            species = entry.get("species") or entry.get("scientific_name")
            name = common_name or species
            if not name:
                continue
            plant_type = species or common_name or "Unknown"
            rows.append((name, plant_type, "Catalog", 0, None))

        if not rows:
            return

        with self.connection() as conn:
            conn.executemany(
                """
                INSERT INTO Plants (name, plant_type, current_stage, days_in_stage, moisture_level)
                VALUES (?, ?, ?, ?, ?)
                """,
                rows,
            )
        logging.info("Seeded Plants table with %d catalog entries.", len(rows))

    def _seed_device_energy_profiles(self) -> None:
        """Populate DeviceEnergyProfiles with default device power ratings."""
        with self.connection() as conn:
            existing = conn.execute("SELECT COUNT(*) FROM DeviceEnergyProfiles").fetchone()[0]
            if existing:
                return
        
        # Default device energy profiles (watts)
        default_profiles = [
            ('lights', 'LED Grow Light', 150, 0.9),
            ('lights', 'HPS Grow Light', 400, 0.85),
            ('lights', 'Fluorescent T5', 54, 0.8),
            ('fan', 'Circulation Fan 6"', 25, 0.95),
            ('fan', 'Circulation Fan 8"', 45, 0.95),
            ('extractor', 'Exhaust Fan 4"', 35, 0.9),
            ('extractor', 'Exhaust Fan 6"', 65, 0.9),
            ('extractor', 'Exhaust Fan 8"', 120, 0.9),
            ('heater', 'Space Heater Small', 500, 0.98),
            ('heater', 'Ceramic Heater', 1000, 0.98),
            ('humidifier', 'Ultrasonic Humidifier', 30, 0.85),
            ('humidifier', 'Evaporative Humidifier', 50, 0.8),
            ('water_pump', 'Submersible Pump Small', 15, 0.7),
            ('water_pump', 'Submersible Pump Medium', 40, 0.75),
            ('dehumidifier', 'Mini Dehumidifier', 300, 0.85),
            ('dehumidifier', 'Standard Dehumidifier', 500, 0.9),
        ]
        
        with self.connection() as conn:
            conn.executemany(
                """
                INSERT INTO DeviceEnergyProfiles (device_type, device_model, rated_power_watts, efficiency_factor)
                VALUES (?, ?, ?, ?)
                """,
                default_profiles
            )
        logging.info("Seeded DeviceEnergyProfiles table with %d default profiles.", len(default_profiles))
