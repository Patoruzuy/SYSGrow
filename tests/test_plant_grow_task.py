import os
from datetime import date, timedelta

import app.utils.persistent_store as ps
from app.workers.scheduled_tasks import plant_grow_task


class FakePlant:
    def __init__(self, plant_id: int, name: str):
        self.plant_id = plant_id
        self.plant_name = name
        self.id = plant_id
        self.current_stage = "seed"
        self.days_in_stage = 0

    def grow(self):
        self.days_in_stage += 1


class FakeRuntime:
    def __init__(self, plants):
        self._plants = plants

    def get_all_plants(self):
        return list(self._plants)


class FakeGrowthService:
    def __init__(self, runtimes):
        self._runtimes = runtimes

    def get_unit_runtimes(self):
        return self._runtimes


class FakePlantService:
    def __init__(self):
        self.updated = []

    def __init__(self, growth_service=None):
        self.updated = []
        self.growth_service = growth_service

    def list_plants(self, unit_id):
        # Return plants from the provided growth_service runtimes if available
        if self.growth_service:
            runtimes = self.growth_service.get_unit_runtimes()
            runtime = runtimes.get(unit_id)
            if runtime:
                return runtime.get_all_plants()
        return []

    def update_plant_stage(self, plant_id, current_stage, days_in_stage):
        self.updated.append((plant_id, current_stage, days_in_stage))


class FakeContainer:
    def __init__(self, growth_service, plant_service, config=None):
        self.growth_service = growth_service
        self.plant_service = plant_service
        self.config = config


def test_plant_grow_single_run(tmp_path, monkeypatch):
    # Use a temp var dir
    monkeypatch.setattr(ps, "_VAR_DIR", str(tmp_path))
    os.makedirs(ps._VAR_DIR, exist_ok=True)

    plants = [FakePlant(1, "A"), FakePlant(2, "B")]
    runtime = FakeRuntime(plants)
    growth = FakeGrowthService({10: runtime})
    plant_service = FakePlantService(growth)
    container = FakeContainer(growth, plant_service)

    # Ensure no last-runs exist
    lr = ps.load_growth_last_runs()
    assert lr == {}

    res = plant_grow_task(container)
    assert res["plants_processed"] == 2

    # Verify file saved
    lr2 = ps.load_growth_last_runs()
    assert str(10) in lr2
    assert plant_service.updated, "PlantService.update_plant_stage was not called"


def test_plant_grow_missed_days(tmp_path, monkeypatch):
    monkeypatch.setattr(ps, "_VAR_DIR", str(tmp_path))
    os.makedirs(ps._VAR_DIR, exist_ok=True)

    plants = [FakePlant(3, "C")]
    runtime = FakeRuntime(plants)
    growth = FakeGrowthService({20: runtime})
    plant_service = FakePlantService(growth)
    container = FakeContainer(growth, plant_service)

    # Seed last run to two days ago
    two_days_ago = (date.today() - timedelta(days=2)).isoformat()
    ps.save_growth_last_runs({"20": two_days_ago})

    res = plant_grow_task(container)
    assert res["plants_processed"] == 1
    # Plant days_in_stage should be incremented twice
    assert plants[0].days_in_stage == 2
