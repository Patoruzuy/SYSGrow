from datetime import datetime, timedelta
from .db import get_db

class GrowthManager:
    def __init__(self):
        self.db = get_db()

    def calculate_end_date(self, start_date, duration_days):
        return start_date + timedelta(days=duration_days)

    def check_stage_transition(self, grow_id):
        timestamps = self.db.fetch_one("SELECT stage_seeding, stage_vegetation, stage_flowering, stage_harvest FROM grow_timestamp WHERE grow_id = ?", (grow_id,))
        stage_duration = self.db.fetch_one("SELECT stage_duration FROM grow WHERE grow_id = ?", (grow_id,))[0]
        
        if not timestamps or not stage_duration:
            print("No data found for the given grow_id.")
            return

        stage_seeding, stage_vegetation, stage_flowering, stage_harvest = timestamps
        current_date = datetime.now()

        if stage_vegetation:
            veg_end_date = self.calculate_end_date(stage_vegetation, stage_duration)
            if current_date >= veg_end_date:
                print("Vegetation stage complete. Time to move to flowering stage.")
                self.db.execute_query("UPDATE grow SET stage = ? WHERE grow_id = ?", ('Flowering', grow_id))
                self.db.execute_query("UPDATE grow_timestamp SET stage_flowering = ? WHERE grow_id = ?", (current_date, grow_id))
        else:
            print("Vegetation stage has not started yet.")

