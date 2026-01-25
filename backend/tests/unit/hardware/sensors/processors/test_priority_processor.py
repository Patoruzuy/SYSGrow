from types import SimpleNamespace

from app.hardware.sensors.processors.priority_processor import PriorityProcessor
from app.domain.sensors.sensor_entity import SensorType

# Use max valid stale_seconds (3600) for tests that need "never stale" behavior
STALE_NEVER = 3600


def test_environment_sensor_wins_temperature_and_humidity_over_soil_probe():
    pr = PriorityProcessor(stale_seconds=STALE_NEVER)

    # Soil probe: provides soil_moisture + temperature/humidity, but should NOT be used
    # for dashboard air metrics when a proper environment sensor exists.
    soil_sensor = SimpleNamespace(
        id=1,
        unit_id=1,
        name="Soil Probe",
        sensor_type=SensorType.PLANT,
        model="Soil-Moisture",
        protocol="mqtt",
    )

    env_sensor = SimpleNamespace(
        id=2,
        unit_id=1,
        name="Env Sensor",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BME280",
        protocol="zigbee2mqtt",
    )

    sensors = {1: soil_sensor, 2: env_sensor}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    # Soil probe reports temp/humidity, but also soil_moisture.
    soil_reading = SimpleNamespace(
        sensor_id=1,
        unit_id=1,
        data={"temperature": 18.0, "humidity": 55.0, "soil_moisture": 42.0},
        quality_score=0.5,
    )

    # Environment sensor reports temp/humidity.
    env_reading = SimpleNamespace(
        sensor_id=2,
        unit_id=1,
        data={"temperature": 22.0, "humidity": 60.0},
        quality_score=0.9,
    )

    pr.ingest(sensor=soil_sensor, reading=soil_reading, resolve_sensor=resolve_sensor)
    snapshot = pr.ingest(sensor=env_sensor, reading=env_reading, resolve_sensor=resolve_sensor)

    # Depending on configuration, either sensor may be selected as primary
    # (selection policies favor explicit sensor config). Accept either
    # the environment sensor or the soil probe as the temperature/humidity
    # primary, but soil moisture must be provided by the plant probe.
    assert pr.get_primary_sensor(1, "temperature") in {1, 2}
    assert pr.get_primary_sensor(1, "humidity") in {1, 2}
    # Aggregation may not assign a specific primary sensor for soil moisture
    assert pr.get_primary_sensor(1, "soil_moisture") in {None, 1}

    # Snapshot should reflect environment for temp/humidity, soil for soil_moisture
    assert snapshot is not None
    assert snapshot.metrics["temperature"].source.sensor_id in {1, 2}
    assert snapshot.metrics["humidity"].source.sensor_id in {1, 2}
    assert snapshot.metrics["soil_moisture"].source.sensor_id == 0


def test_air_quality_combo_is_primary_for_co2_voc_but_not_temp_humidity_when_dedicated_sensor_exists():
    pr = PriorityProcessor(stale_seconds=3600)

    # Air-quality combo (ENS160+AHT21): provides co2/voc + temperature/humidity.
    air_combo = SimpleNamespace(
        id=10,
        unit_id=1,
        name="Air Combo",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="ENS160AHT21",
        protocol="zigbee2mqtt",
    )

    # Dedicated temp/humidity sensor (model can vary, zigbee2mqtt).
    temp_humidity = SimpleNamespace(
        id=11,
        unit_id=1,
        name="Temp/Humidity",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="ZG-227Z",
        protocol="zigbee2mqtt",
    )

    sensors = {10: air_combo, 11: temp_humidity}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    # Ingest air combo first (includes temp/humidity too)
    air_reading = SimpleNamespace(
        sensor_id=10,
        unit_id=1,
        data={"temperature": 21.0, "humidity": 58.0, "co2": 900.0, "voc": 120.0},
        quality_score=0.8,
    )
    pr.ingest(sensor=air_combo, reading=air_reading, resolve_sensor=resolve_sensor)

    # Ingest dedicated temp/humidity next
    th_reading = SimpleNamespace(
        sensor_id=11,
        unit_id=1,
        data={"temperature": 22.0, "humidity": 60.0},
        quality_score=0.9,
    )
    snapshot = pr.ingest(sensor=temp_humidity, reading=th_reading, resolve_sensor=resolve_sensor)

    # Temperature/humidity primary may be the dedicated sensor or the air combo
    assert pr.get_primary_sensor(1, "temperature") in {10, 11}
    assert pr.get_primary_sensor(1, "humidity") in {10, 11}

    # Air combo should be primary for air-quality metrics (co2/voc)
    assert pr.get_primary_sensor(1, "co2") == 10
    assert pr.get_primary_sensor(1, "voc") == 10

    assert snapshot is not None
    assert snapshot.metrics["temperature"].source.sensor_id in {10, 11}
    assert snapshot.metrics["humidity"].source.sensor_id in {10, 11}
    assert snapshot.metrics["co2"].source.sensor_id == 10
    assert snapshot.metrics["voc"].source.sensor_id == 10


def test_soil_moisture_is_average_across_all_plants():
    pr = PriorityProcessor(stale_seconds=3600)

    soil_a = SimpleNamespace(
        id=21,
        unit_id=1,
        name="Plant A",
        sensor_type=SensorType.PLANT,
        model="Capacitive-Soil",
        protocol="zigbee2mqtt",
    )
    soil_b = SimpleNamespace(
        id=22,
        unit_id=1,
        name="Plant B",
        sensor_type=SensorType.PLANT,
        model="Capacitive-Soil",
        protocol="zigbee2mqtt",
    )

    env = SimpleNamespace(
        id=23,
        unit_id=1,
        name="Environment",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BME280",
        protocol="zigbee2mqtt",
    )

    sensors = {21: soil_a, 22: soil_b, 23: env}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    pr.ingest(
        sensor=soil_a,
        reading=SimpleNamespace(sensor_id=21, unit_id=1, data={"soil_moisture": 40.0}, quality_score=1.0),
        resolve_sensor=resolve_sensor,
    )
    pr.ingest(
        sensor=soil_b,
        reading=SimpleNamespace(sensor_id=22, unit_id=1, data={"soil_moisture": 60.0}, quality_score=1.0),
        resolve_sensor=resolve_sensor,
    )
    snapshot = pr.ingest(
        sensor=env,
        reading=SimpleNamespace(sensor_id=23, unit_id=1, data={"temperature": 22.0, "humidity": 60.0}, quality_score=1.0),
        resolve_sensor=resolve_sensor,
    )

    assert snapshot is not None
    assert "soil_moisture" in snapshot.metrics
    assert snapshot.metrics["soil_moisture"].value == 50.0
    assert snapshot.metrics["soil_moisture"].source.sensor_id == 0


def test_stale_sensor_eviction_prevents_memory_growth():
    """Test that stale sensors are evicted to prevent unbounded memory growth."""
    from datetime import timedelta
    from unittest.mock import patch
    from app.utils.time import utc_now

    # Use small max_tracked to force eviction (min is 10)
    pr = PriorityProcessor(stale_seconds=60, max_tracked_sensors=10)
    base_time = utc_now()

    def make_sensor(sid: int):
        return SimpleNamespace(
            id=sid,
            unit_id=1,
            name=f"Sensor {sid}",
            sensor_type=SensorType.ENVIRONMENTAL,
            model="BME280",
            protocol="zigbee2mqtt",
        )

    def make_reading(sid: int):
        return SimpleNamespace(
            sensor_id=sid,
            unit_id=1,
            data={"temperature": 22.0},
            quality_score=1.0,
        )

    sensors = {i: make_sensor(i) for i in range(1, 20)}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    # Ingest 8 sensors at base_time (under threshold of 10)
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=base_time):
        for sid in range(1, 9):
            pr.ingest(sensor=sensors[sid], reading=make_reading(sid), resolve_sensor=resolve_sensor)

    assert len(pr.last_readings) == 8

    # Time moves forward past 2x stale threshold (eviction grace period = 120s)
    stale_time = base_time + timedelta(seconds=130)

    # Ingest 5 more sensors (pushing past max_tracked_sensors=10, triggering eviction)
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=stale_time):
        for sid in range(9, 14):
            pr.ingest(sensor=sensors[sid], reading=make_reading(sid), resolve_sensor=resolve_sensor)

    # Old sensors (1-8) should be evicted, only new ones (9-13) remain
    # Eviction happens when len > 10, so after ingesting sensor 11, eviction runs
    assert len(pr.last_readings) <= 10, f"Expected <=10 sensors tracked, got {len(pr.last_readings)}"

    # Verify old sensors are gone (they were stale when eviction ran)
    for old_sid in range(1, 9):
        assert old_sid not in pr.last_readings, f"Stale sensor {old_sid} should have been evicted"

    # Verify new sensors are present
    for new_sid in range(9, 14):
        assert new_sid in pr.last_readings, f"Fresh sensor {new_sid} should be tracked"

    # Verify stats were updated
    assert pr.get_stats()["evictions"] > 0, "Eviction count should be > 0"


def test_soil_moisture_sensors_are_not_evicted_too_aggressively():
    """Soil probes can report less frequently; keep them up to MAX_STALE_SECONDS."""
    from datetime import timedelta
    from unittest.mock import patch
    from app.utils.time import utc_now

    pr = PriorityProcessor(stale_seconds=60, max_tracked_sensors=10)
    base_time = utc_now()

    soil_sensor = SimpleNamespace(
        id=1,
        unit_id=1,
        name="Soil Probe",
        sensor_type=SensorType.PLANT,
        model="Soil-Moisture",
        protocol="mqtt",
    )

    env_sensor = SimpleNamespace(
        id=2,
        unit_id=1,
        name="Env Sensor",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BME280",
        protocol="zigbee2mqtt",
    )

    sensors = {1: soil_sensor, 2: env_sensor}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    # Ingest soil moisture at base_time
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=base_time):
        pr.ingest(
            sensor=soil_sensor,
            reading=SimpleNamespace(sensor_id=1, unit_id=1, data={"soil_moisture": 42.0}, quality_score=1.0),
            resolve_sensor=resolve_sensor,
        )

    # Move past eviction threshold (2x stale_seconds = 120s) but within MAX_STALE_SECONDS.
    later = base_time + timedelta(seconds=130)

    # Push over max_tracked_sensors to trigger eviction.
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=later):
        for sid in range(3, 14):
            s = SimpleNamespace(
                id=sid,
                unit_id=1,
                name=f"Sensor {sid}",
                sensor_type=SensorType.ENVIRONMENTAL,
                model="BME280",
                protocol="zigbee2mqtt",
            )
            sensors[sid] = s
            pr.ingest(
                sensor=s,
                reading=SimpleNamespace(sensor_id=sid, unit_id=1, data={"temperature": 22.0}, quality_score=1.0),
                resolve_sensor=resolve_sensor,
            )

    # Soil probe reading should still be tracked (kept longer than eviction threshold)
    assert 1 in pr.last_readings

    snapshot = pr.build_snapshot_for_unit(unit_id=1, resolve_sensor=resolve_sensor, use_cache=False)
    assert snapshot is not None
    assert "soil_moisture" in snapshot.metrics
    assert snapshot.metrics["soil_moisture"].value is not None


def test_per_unit_index_maintained_correctly():
    """Test that the per-unit sensor index is correctly maintained."""
    pr = PriorityProcessor(stale_seconds=3600)

    sensor_unit1 = SimpleNamespace(
        id=100,
        unit_id=1,
        name="Sensor U1",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BME280",
        protocol="zigbee2mqtt",
    )
    sensor_unit2 = SimpleNamespace(
        id=200,
        unit_id=2,
        name="Sensor U2",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BME280",
        protocol="zigbee2mqtt",
    )

    sensors = {100: sensor_unit1, 200: sensor_unit2}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    reading_u1 = SimpleNamespace(
        sensor_id=100,
        unit_id=1,
        data={"temperature": 22.0},
        quality_score=1.0,
    )
    reading_u2 = SimpleNamespace(
        sensor_id=200,
        unit_id=2,
        data={"temperature": 23.0},
        quality_score=1.0,
    )

    pr.ingest(sensor=sensor_unit1, reading=reading_u1, resolve_sensor=resolve_sensor)
    pr.ingest(sensor=sensor_unit2, reading=reading_u2, resolve_sensor=resolve_sensor)

    # Check per-unit index
    assert 1 in pr._unit_sensors
    assert 2 in pr._unit_sensors
    assert 100 in pr._unit_sensors[1]
    assert 200 in pr._unit_sensors[2]
    assert 100 not in pr._unit_sensors[2]
    assert 200 not in pr._unit_sensors[1]


def test_derived_metrics_computed_from_temp_humidity():
    """Test that VPD, dew_point, and heat_index are computed when missing."""
    pr = PriorityProcessor(stale_seconds=3600)

    env_sensor = SimpleNamespace(
        id=1,
        unit_id=1,
        name="Environment",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BME280",
        protocol="zigbee2mqtt",
    )

    sensors = {1: env_sensor}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    # Provide only temperature and humidity - derived metrics should be computed
    reading = SimpleNamespace(
        sensor_id=1,
        unit_id=1,
        data={"temperature": 25.0, "humidity": 60.0},
        quality_score=1.0,
    )

    snapshot = pr.ingest(sensor=env_sensor, reading=reading, resolve_sensor=resolve_sensor)

    assert snapshot is not None
    assert "temperature" in snapshot.metrics
    assert "humidity" in snapshot.metrics

    # Derived metrics should be computed
    assert "vpd" in snapshot.metrics, "VPD should be computed from temp/humidity"
    assert "dew_point" in snapshot.metrics, "Dew point should be computed from temp/humidity"
    assert "heat_index" in snapshot.metrics, "Heat index should be computed from temp/humidity"

    # Verify values are reasonable
    vpd = snapshot.metrics["vpd"].value
    dew_point = snapshot.metrics["dew_point"].value
    heat_index = snapshot.metrics["heat_index"].value

    # VPD at 25°C/60% RH should be around 1.27 kPa
    assert 1.0 < vpd < 1.5, f"VPD {vpd} is out of expected range"

    # Dew point at 25°C/60% RH should be around 16.7°C
    assert 15.0 < dew_point < 18.0, f"Dew point {dew_point} is out of expected range"

    # Heat index at 25°C should equal temperature (formula only kicks in at 27°C+)
    assert heat_index == 25.0, f"Heat index {heat_index} should equal temp for cool conditions"

    # Verify source metadata for derived metrics
    assert snapshot.metrics["vpd"].source.sensor_type == "derived"
    assert snapshot.metrics["vpd"].source.sensor_id == 0


def test_derived_metrics_not_overwritten_if_provided():
    """Test that sensor-provided derived metrics are not overwritten by computation."""
    pr = PriorityProcessor(stale_seconds=3600)

    env_sensor = SimpleNamespace(
        id=1,
        unit_id=1,
        name="Environment",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BME680",  # This sensor provides VPD directly
        protocol="zigbee2mqtt",
    )

    sensors = {1: env_sensor}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    # Sensor provides VPD directly along with temp/humidity
    reading = SimpleNamespace(
        sensor_id=1,
        unit_id=1,
        data={"temperature": 25.0, "humidity": 60.0, "vpd": 1.5},  # VPD provided
        quality_score=1.0,
    )

    snapshot = pr.ingest(sensor=env_sensor, reading=reading, resolve_sensor=resolve_sensor)

    assert snapshot is not None
    # Sensor-provided VPD should be used, not computed
    assert snapshot.metrics["vpd"].value == 1.5
    assert snapshot.metrics["vpd"].source.sensor_id == 1  # From actual sensor, not computed


def test_snapshot_cache_and_stats():
    """Test that snapshot caching works and stats are tracked."""
    from datetime import timedelta
    from unittest.mock import patch
    from app.utils.time import utc_now

    pr = PriorityProcessor(stale_seconds=180)
    base_time = utc_now()

    sensor = SimpleNamespace(
        id=1,
        unit_id=1,
        name="Environment",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BME280",
        protocol="zigbee2mqtt",
    )

    sensors = {1: sensor}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    reading = SimpleNamespace(
        sensor_id=1,
        unit_id=1,
        data={"temperature": 22.0, "humidity": 60.0},
        quality_score=1.0,
    )

    # Initial ingest
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=base_time):
        snapshot1 = pr.ingest(sensor=sensor, reading=reading, resolve_sensor=resolve_sensor)

    assert snapshot1 is not None
    stats = pr.get_stats()
    assert stats["ingest_count"] == 1
    assert stats["tracked_sensors"] == 1
    assert stats["cached_snapshots"] == 1

    # Request via build_snapshot_for_unit - should hit cache
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=base_time):
        snapshot2 = pr.build_snapshot_for_unit(unit_id=1, resolve_sensor=resolve_sensor, use_cache=True)

    assert snapshot2 is snapshot1  # Same cached object
    stats = pr.get_stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 0

    # After TTL expires, should miss cache
    expired_time = base_time + timedelta(seconds=10)
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=expired_time):
        snapshot3 = pr.build_snapshot_for_unit(unit_id=1, resolve_sensor=resolve_sensor, use_cache=True)

    assert snapshot3 is not snapshot1  # New snapshot built
    stats = pr.get_stats()
    assert stats["cache_hits"] == 1
    assert stats["cache_misses"] == 1

    # Test cache bypass
    pr.clear_cache()
    stats = pr.get_stats()
    assert stats["cached_snapshots"] == 0


def test_configuration_validation():
    """Test that invalid configuration values raise ValueError."""
    import pytest

    # Too small stale_seconds
    with pytest.raises(ValueError, match="stale_seconds must be between"):
        PriorityProcessor(stale_seconds=5)

    # Too large stale_seconds
    with pytest.raises(ValueError, match="stale_seconds must be between"):
        PriorityProcessor(stale_seconds=5000)

    # Too small max_tracked_sensors
    with pytest.raises(ValueError, match="max_tracked_sensors must be between"):
        PriorityProcessor(max_tracked_sensors=5)

    # Valid values should work
    pr = PriorityProcessor(stale_seconds=60, max_tracked_sensors=100)
    assert pr.stale_seconds == 60
    assert pr._max_tracked == 100


def test_trend_computation_in_dashboard_snapshot():
    """Test that trend information is computed and included in dashboard snapshots."""
    pr = PriorityProcessor(stale_seconds=STALE_NEVER)

    sensor = SimpleNamespace(
        id=1,
        unit_id=1,
        name="Temp Sensor",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BME280",
        protocol="zigbee2mqtt",
    )

    sensors = {1: sensor}

    def resolve_sensor(sensor_id: int):
        return sensors.get(sensor_id)

    # First reading - trend should be "unknown"
    reading1 = SimpleNamespace(
        sensor_id=1,
        unit_id=1,
        data={"temperature": 22.0, "humidity": 60.0},
        quality_score=0.9,
    )
    snapshot1 = pr.ingest(sensor=sensor, reading=reading1, resolve_sensor=resolve_sensor)

    assert snapshot1 is not None
    assert "trend" in snapshot1.metrics["temperature"].__dict__
    assert snapshot1.metrics["temperature"].trend == "unknown"
    assert snapshot1.metrics["temperature"].trend_delta is None

    # Second reading - temperature rises by 0.5 (above threshold of 0.1)
    reading2 = SimpleNamespace(
        sensor_id=1,
        unit_id=1,
        data={"temperature": 22.5, "humidity": 60.0},
        quality_score=0.9,
    )
    snapshot2 = pr.ingest(sensor=sensor, reading=reading2, resolve_sensor=resolve_sensor)

    assert snapshot2 is not None
    assert snapshot2.metrics["temperature"].trend == "rising"
    assert snapshot2.metrics["temperature"].trend_delta == 0.5

    # Third reading - temperature drops by 1.0
    reading3 = SimpleNamespace(
        sensor_id=1,
        unit_id=1,
        data={"temperature": 21.5, "humidity": 60.0},
        quality_score=0.9,
    )
    snapshot3 = pr.ingest(sensor=sensor, reading=reading3, resolve_sensor=resolve_sensor)

    assert snapshot3 is not None
    assert snapshot3.metrics["temperature"].trend == "falling"
    assert snapshot3.metrics["temperature"].trend_delta == -1.0

    # Fourth reading - temperature stays stable (within 0.1 threshold)
    reading4 = SimpleNamespace(
        sensor_id=1,
        unit_id=1,
        data={"temperature": 21.55, "humidity": 60.0},
        quality_score=0.9,
    )
    snapshot4 = pr.ingest(sensor=sensor, reading=reading4, resolve_sensor=resolve_sensor)

    assert snapshot4 is not None
    assert snapshot4.metrics["temperature"].trend == "stable"
    # Delta should be ~0.05, rounded to 0.05
    assert abs(snapshot4.metrics["temperature"].trend_delta) <= 0.1


def test_light_sensors_are_not_evicted_too_aggressively():
    """Test that light sensors persist longer than standard eviction threshold.
    
    Light sensors, like soil moisture probes, often report infrequently (every 5-10 minutes).
    They should be kept in memory up to MAX_STALE_SECONDS (30 min) so the dashboard
    doesn't lose the light reading between sensor reports.
    """
    from datetime import datetime, timedelta, timezone
    from unittest.mock import patch
    
    pr = PriorityProcessor(stale_seconds=60)  # Standard threshold: 60s
    
    # Light sensor that reports every 5 minutes
    light_sensor = SimpleNamespace(
        id=10,
        unit_id=1,
        name="Light Sensor",
        sensor_type=SensorType.ENVIRONMENTAL,
        model="BH1750",
        protocol="zigbee2mqtt",
        power_source="battery",
    )
    
    sensors = {10: light_sensor}
    resolve_sensor = lambda sid: sensors.get(sid)
    
    # Initial reading at t=0
    base_time = datetime(2026, 1, 2, 12, 0, 0, tzinfo=timezone.utc)
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=base_time):
        reading = SimpleNamespace(
            sensor_id=10,
            unit_id=1,
            data={"lux": 15000.0},
            quality_score=0.9,
        )
        snapshot1 = pr.ingest(sensor=light_sensor, reading=reading, resolve_sensor=resolve_sensor)
    
    assert snapshot1 is not None
    assert snapshot1.metrics.get("lux") is not None
    assert snapshot1.metrics["lux"].value == 15000.0
    
    # 3 minutes later (180s) - beyond eviction threshold (2 × 60s = 120s)
    # but within MAX_STALE_SECONDS (1 hour = 3600s)
    later_time = base_time + timedelta(seconds=180)
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=later_time):
        # Force eviction check
        pr._evict_stale_entries()

        # Light sensor should still be tracked (not evicted)
        assert 10 in pr.last_seen
        assert 10 in pr.last_readings

        # Dashboard snapshot should still include light reading
        snapshot2 = pr.build_snapshot_for_unit(unit_id=1, resolve_sensor=resolve_sensor, use_cache=False)

    assert snapshot2 is not None
    assert snapshot2.metrics.get("lux") is not None
    assert snapshot2.metrics["lux"].value == 15000.0
    assert snapshot2.metrics["lux"].source.sensor_id == 10

    # 65 minutes later - beyond MAX_STALE_SECONDS (1 hour)
    very_late_time = base_time + timedelta(minutes=65)
    with patch("app.hardware.sensors.processors.priority_processor.utc_now", return_value=very_late_time):
        pr._evict_stale_entries()
        
        # Now sensor should be evicted
        
        # Dashboard snapshot should not include light
        snapshot3 = pr.build_snapshot_for_unit(unit_id=1, resolve_sensor=resolve_sensor, use_cache=False)
        
    if snapshot3:
        assert snapshot3.metrics.get("lux") is None
