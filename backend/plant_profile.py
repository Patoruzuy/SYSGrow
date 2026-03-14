"""
Description: This script defines classes for managing plant growth, including plant stages and a plant factory for creating different types of plants.

Author: Sebastian Gomez
Date: 26/05/24
"""
from datetime import datetime
import json
import logging
import os

logging.basicConfig(level=logging.INFO, filename="growth_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class PlantProfile:
    """
    Represents a plant with various stages and a soil moisture sensor.

    Attributes:
        name (str): The name of the plant.
        stage (PlantStage): The current stage of the plant.
        sensor_name (str): Sensor name linked to the plant
        sensor_id (int): Sensor ID.
        moisture_level (float): the moisture level of the plant
        stage_durations (dict): The durations for each growth stage.
        days_in_current_stage (int): Number of days the plant has been in the current stage.
    """
    def __init__(self, plant_id, database_handler, json_file="plants_info.json"):
        """
        Initializes a plant instance from the database.

        Args:
            plant_id (int): The ID of the plant in the database.
            database_handler (DatabaseHandler): The database handler instance.
            plant_data_file (str): Path to the plant data JSON file.
        """
        self.database_handler = database_handler
        plant_data = database_handler.get_plant_by_id(plant_id)

        if not plant_data:
            logging.error(f"Plant with ID {plant_id} not found.")
            raise ValueError("Plant not found.")

        # Load plant attributes
        self.id = plant_data["id"]
        self.name = plant_data["name"]
        self.type = plant_data["plant_type"]
        self.sensor_id = plant_data["sensor_id"]
        self.current_stage = plant_data["current_stage"]
        self.days_in_stage = plant_data["days_in_stage"]
        self.moisture_level = plant_data["moisture_level"]

        # Load growth stages from JSON
        self.growth_stages = self.load_plant_stages(json_file)

        # Compute stage durations
        self.stage_durations = {
            stage["stage"]: (int(stage["time"].split("-")[0]) + int(stage["time"].split("-")[1])) // 2
            for stage in self.growth_stages
        }
        self.days_left = self.stage_durations.get(self.get_current_stage_name(), 0) - self.days_in_stage

    def load_plant_stages(self, json_file):
        """Loads growth stages for the plant type from the JSON file."""
        if not os.path.exists(json_file):
            logging.warning(f"{json_file} missing.")
            return []
        try:
            with open(json_file, "r") as file:
                plant_data = json.load(file)

            for plant in plant_data:
                if plant["name"].lower() == self.type.lower():
                    return plant["growth_stages"]
            logging.warning(f"Stages for {self.type} not found.")
            return []

        except json.JSONDecodeError:
            logging.warning(f"Failed to parse {json_file}. Ensure it is properly formatted.")
            return []
        
    def set_stage(self, current_stage, days_in_stage=0):
        """
        Sets the current stage of the plant.

        Args:
            current_stagex (str): The new stage of the plant.
            days_in_current_stage (int): The number of days in the current stage.
        """
        self.current_stage = current_stage
        self.days_in_stage = days_in_stage
        self.update_days_left()
        self.update_database()

    def grow(self):
        """Advances the plant's stage if enough days have passed."""
        if not self.growth_stages:
            logging.error(f"Stage {self.current_stage} missing.")
            return
        
        current_stage = next((s for s in self.growth_stages if s["stage"] == self.get_current_stage_name()), None)

        if not current_stage:
            logging.error(f"No stage found for plant {self.name}.")
            return

        self.days_in_stage += 1
        # Convert 'time' string range (e.g., "3-7") to integers
        min_days, max_days = map(int, current_stage["time"].split("-"))

        if self.days_in_stage >= (min_days + max_days) // 2:
            next_stage_index = self.growth_stages.index(current_stage) + 1
            if next_stage_index < len(self.growth_stages):
                self.set_stage(self.growth_stages[next_stage_index]["stage"])
                logging.info(f"{self.name} advanced to {self.growth_stages[next_stage_index]['stage']}.")
                self.document_plant_data()
            else:
                logging.info(f"{self.name} is fully grown!")
                self.document_plant_data()
            self.update_database()
            self.update_days_left()

    def get_name(self) -> str:
        """
        Returns the name of the plant.

        Returns:
            str: The name of the plant.
        """
        return self.name
        
    def set_sensor_id(self, sensor_id):
        """
        Associates a sensor with the plant by storing the sensor's ID.
        args:
            sensor_id (int): The ID of the sensor.
        """
        self.sensor_id = sensor_id

    def get_sensor_id(self) -> int:
        """
        The sensor ID associated with the plant.

            int: The sensor ID.
        """
        return self.sensor_id
    
    def set_moisture_level(self, moisture_level):
        """
        Set the moisture level from the soil moisture sensor
        args:
            moisture_level (float): The moisture level of the plant
        """
        print(f"Set plant moisture: {moisture_level}")
        self.moisture_level = moisture_level

    def get_growth_stages(self):
        """
        Retrieve the growth stages for this plant type.
        """
        for plant in self.plant_data:
            if plant["name"] == self.type:
                return plant["growth_stages"]
        return []

    def get_current_stage_index(self):
        """Returns the name of the plant's current growth stage."""
        stage = self.database_handler.get_stage_by_index(self.current_stage)
        return stage["stage_name"] if stage else "Unknown Stage"

    def increase_days_in_stage(self):
        """Increases the days in the current stage by 1."""
        self.days_in_stage += 1
        self.update_day_left()
        self.update_database()

    def decrease_days_in_stage(self):
        """Decreases the days in the current stage by 1."""
        if self.days_in_stage > 0:
            self.days_in_stage -= 1
            self.update_day_left()
            self.update_database()

    def get_days_current_stage(self) -> int:
        """
        Returns the days in the current stage of the plant.

        Returns:
            int: The days in the current stage of the plant.
        """
        return self.days_in_stage
    
    def document_plant_data(self, harvest_weight=None, photo_path=None) -> None:
        """
        Records the plant's details to the database.

        Args:
            harvest_weight (float): The weight of the harvest.
            photo_path (str): The file path to the photo of the plant.
        """
        average_temp = self.database_handler.get_average_temperature(self.id)
        average_humidity = self.database_handler.get_average_humidity(self.id)
        light_hours = self.database_handler.get_total_light_hours(self.id)
        date_harvested = datetime.now().strftime('%Y-%m-%d')

        self.database_handler.insert_plant_history(
            self.name,
            self.current_stage,
            self.get_days_current_stage(),
            average_temp,
            average_humidity,
            light_hours,
            harvest_weight,
            photo_path,
            date_harvested
        )

    def get_recommended_conditions(self):
        """Fetches recommended environmental conditions for the current stage."""
        current_stage = next((s for s in self.growth_stages if s["stage"] == self.get_current_stage_index()), None)
        return current_stage if current_stage else {}
    
    def update_days_left(self):
        """
        Update the days left in the current stage of the plant.
        """
        stage_name = self.get_current_stage_index()
        stage_duration = self.stage_durations.get(stage_name, 0)
        self.days_left = max(stage_duration - self.days_in_stage, 0)
    
    def update_database(self):
        """Updates the current stage days in the plant's record in the database."""
        self.database_handler.update_plant_days(self.id, self.current_stage, self.moisture_level, self.days_in_stage)
