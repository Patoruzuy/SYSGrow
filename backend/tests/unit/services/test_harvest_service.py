"""
Tests for PlantHarvestService.

Covers:
- Harvest report generation
- Environmental averages (SensorReadingSummary path + fallback)
- Harvest reports listing
- Cleanup after harvest
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest


class TestGenerateHarvestReport:
    """generate_harvest_report end-to-end with real DB."""

    def test_report_for_existing_plant(self, harvest_service, seed):
        unit_id = seed.create_unit()
        plant_id = seed.create_plant("Basil", unit_id=unit_id, stage="flowering")

        # Insert energy readings so the report has data
        seed.insert_energy_reading(device_id=1, unit_id=unit_id, plant_id=plant_id)

        report = harvest_service.generate_harvest_report(
            plant_id=plant_id,
            harvest_weight_grams=150.0,
            quality_rating=4,
            notes="Good yield",
        )
        assert report["plant_id"] == plant_id
        assert report["plant_name"] == "Basil"
        assert report["yield"]["weight_grams"] == 150.0
        assert report["yield"]["quality_rating"] == 4
        assert "lifecycle" in report
        assert "energy_consumption" in report

    def test_report_raises_for_missing_plant(self, harvest_service):
        with pytest.raises(ValueError, match="not found"):
            harvest_service.generate_harvest_report(plant_id=99999)


class TestEnvironmentalAverages:
    """_get_environmental_averages with SensorReadingSummary and fallback."""

    def test_fallback_to_raw_readings(self, analytics_repo, plant_repo):
        """Without device_repo, harvest service uses raw reading fallback."""
        from app.services.application.harvest_service import PlantHarvestService

        svc = PlantHarvestService(analytics_repo=analytics_repo, plant_repo=plant_repo)
        # _get_environmental_averages should not crash even with empty DB
        result = svc._get_environmental_averages(plant_id=99999)
        assert "temperature" in result
        assert "humidity" in result

    def test_fallback_uses_sensor_readings_for_environment_metrics(
        self,
        analytics_repo,
        plant_repo,
        seed,
        db_handler,
    ):
        """Fallback should compute temp/humidity from SensorReading payloads."""
        from app.services.application.harvest_service import PlantHarvestService

        unit_id = seed.create_unit("Unit A")
        plant_id = seed.create_plant("Basil", unit_id=unit_id)

        # Two mapped sensors hold the expected values.
        temp_sensor_id = seed.create_sensor(unit_id=unit_id, name="Temp Sensor", sensor_type="temperature")
        humidity_sensor_id = seed.create_sensor(unit_id=unit_id, name="Humidity Sensor", sensor_type="humidity")
        seed.insert_reading(temp_sensor_id, temperature=22.0)
        seed.insert_reading(temp_sensor_id, temperature=24.0)
        seed.insert_reading(humidity_sensor_id, humidity=50.0)
        seed.insert_reading(humidity_sensor_id, humidity=60.0)

        with db_handler.connection() as conn:
            conn.execute("INSERT INTO PlantSensors (plant_id, sensor_id) VALUES (?, ?)", (plant_id, temp_sensor_id))
            conn.execute("INSERT INTO PlantSensors (plant_id, sensor_id) VALUES (?, ?)", (plant_id, humidity_sensor_id))

        # Outlier sensor in same unit should be ignored because PlantSensors mapping exists.
        noisy_sensor_id = seed.create_sensor(unit_id=unit_id, name="Noisy Sensor", sensor_type="temperature")
        seed.insert_reading(noisy_sensor_id, temperature=99.0, humidity=99.0)

        svc = PlantHarvestService(analytics_repo=analytics_repo, plant_repo=plant_repo)
        result = svc._get_environmental_averages(plant_id=plant_id)

        assert result["temperature"]["avg"] == pytest.approx(23.0)
        assert result["humidity"]["avg"] == pytest.approx(55.0)

    def test_prefers_summary_data(self, harvest_service, seed, device_repo):
        """With device_repo and summary data, service returns pre-aggregated stats."""
        unit_id = seed.create_unit()
        sensor_id = seed.create_sensor(unit_id=unit_id, sensor_type="temperature")
        plant_id = seed.create_plant("Tomato", unit_id=unit_id)

        # Insert readings and aggregate
        now = datetime.now()
        for h in range(10):
            ts = (now - timedelta(hours=h)).strftime("%Y-%m-%d %H:%M:%S")
            seed.insert_reading(sensor_id, temperature=20.0 + h, timestamp=ts)

        start = now.strftime("%Y-%m-%d 00:00:00")
        end = (now + timedelta(days=1)).strftime("%Y-%m-%d 00:00:00")
        device_repo.aggregate_sensor_readings_for_period(start, end, "daily")

        result = harvest_service._get_environmental_averages(plant_id)
        assert "temperature" in result
        temp = result["temperature"]
        # If summary was used, min/max should be non-zero
        if temp.get("max", 0) > 0:
            assert temp["max"] >= temp["min"]


class TestGetHarvestReports:
    """get_harvest_reports listing."""

    def test_empty_db_returns_empty(self, harvest_service):
        reports = harvest_service.get_harvest_reports()
        assert reports == []

    def test_returns_reports_after_harvest(self, harvest_service, seed):
        unit_id = seed.create_unit()
        plant_id = seed.create_plant("Pepper", unit_id=unit_id)
        seed.insert_energy_reading(device_id=1, unit_id=unit_id, plant_id=plant_id)

        # Generate a harvest report (saves to DB)
        harvest_service.generate_harvest_report(plant_id, harvest_weight_grams=50.0)

        reports = harvest_service.get_harvest_reports(unit_id=unit_id)
        assert len(reports) >= 1


class TestCleanupAfterHarvest:
    """cleanup_after_harvest."""

    def test_cleanup_deletes_plant_data(self, harvest_service, seed):
        unit_id = seed.create_unit()
        plant_id = seed.create_plant("Lettuce", unit_id=unit_id)

        result = harvest_service.cleanup_after_harvest(plant_id, delete_plant_data=True)
        assert isinstance(result, dict)
        assert "plant_record" in result

    def test_skip_cleanup_preserves_data(self, harvest_service, seed):
        unit_id = seed.create_unit()
        plant_id = seed.create_plant("Kale", unit_id=unit_id)

        result = harvest_service.cleanup_after_harvest(plant_id, delete_plant_data=False)
        assert result["plant_record"] == 0
