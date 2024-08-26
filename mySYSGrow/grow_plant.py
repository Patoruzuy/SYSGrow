"""
Description: This script defines classes for managing plant growth, including plant stages and a plant factory for creating different types of plants.

Author: Sebastian Gomez
Date: 26/05/24
"""
from datetime import datetime, timedelta
from sensor_manager import SoilMoistureSensor
from db_manager import DatabaseManager as database_manager

class Plant:
    """
    Represents a plant with various stages and a soil moisture sensor.

    Attributes:
        id (int): The unique ID of the plant.
        name (str): The name of the plant.
        stage (PlantStage): The current stage of the plant.
        soil_moisture_sensor (SoilMoistureSensor): Sensor to monitor soil moisture.
        stage_durations (dict): The durations for each growth stage.
        days_in_current_stage (int): Number of days the plant has been in the current stage.
        sensor_id (int): The ID of the sensor linked to this plant.
    """
    def __init__(self, name):
        """
        Initializes a new plant with a seed stage and a soil moisture sensor.

        Args:
            name (str): The name of the plant.
        """
        self.id = None  # ID will be assigned by the PlantFactory
        self.name = name
        self.stage = SeedStage(self)
        self.sensor_id = None
        self.soil_moisture_sensor = None
        self.stage_durations = {
            'Seedling': 7,
            'Vegetative': 23,
            'Flowering': 30
        }
        self.days_in_current_stage = 0

    def set_sensor(self, sensor):
        if isinstance(sensor, SoilMoistureSensor):
            self.soil_moisture_sensor = sensor
            self.sensor_id = sensor.sensor_id
            database_manager.update_plant_sensor_link(self.id, sensor.sensor_id)

    def set_stage(self, stage):
        """
        Sets the current stage of the plant.

        Args:
            stage (PlantStage or str): The new stage of the plant.
        """
        if isinstance(stage, str):
            stage = stage.lower()
            if stage == 'seedling':
                self.stage = SeedStage(self)
            elif stage == 'vegetative':
                self.stage = GrowStage(self)
            elif stage == 'flowering':
                self.stage = FloweringStage(self)
            else:
                raise ValueError(f"Unknown stage: {stage}")
        elif isinstance(stage, PlantStage):
            self.stage = stage
        else:
            raise TypeError("Stage must be a string or a PlantStage object")
        self.days_in_current_stage = 0

    def set_stage_durations(self, seed_days, veg_days, flowering_days):
        """
        Sets the durations for each growth stage of the plant.

        Args:
            seed_days (int): The number of days for the seedling stage.
            veg_days (int): The number of days for the vegetative stage.
            flowering_days (int): The number of days for the flowering stage.
        """
        self.stage_durations['Seedling'] = seed_days
        self.stage_durations['Vegetative'] = veg_days
        self.stage_durations['Flowering'] = flowering_days

    def grow(self):
        """
        Triggers the grow process for the plant, changing its stage as it grows.
        """
        self.stage.grow()
        self.days_in_current_stage += 1
        self.update_days_in_database()

    def get_name(self) -> str:
        """
        Returns the name of the plant.

        Returns:
            str: The name of the plant.
        """
        return self.name

    def get_moisture_level(self):
        """
        Reads the moisture level from the soil moisture sensor.
        """
        if self.soil_moisture_sensor:
            return self.soil_moisture_sensor.read()
        print(f"Error: No sensor linked to plant {self.name}")
        return None

    def increase_days_in_stage(self):
        """Increases the days in the current stage by 1."""
        self.days_in_current_stage += 1
        self.update_days_in_database()

    def decrease_days_in_stage(self):
        """Decreases the days in the current stage by 1."""
        if self.days_in_current_stage > 0:
            self.days_in_current_stage -= 1
            self.update_days_in_database()

    def update_days_in_database(self):
        """Updates the current stage days in the plant's record in the database."""
        self.database_manager.update_plant_days(self.id, self.days_in_current_stage)

    def set_day_current_stage(self, days_current_stage):
        self.days_in_current_stage = days_current_stage

    def get_days_current_stage(self) -> int:
        """
        Returns the days in the current stage of the plant.

        Returns:
            int: The days in the current stage of the plant.
        """
        return self.days_in_current_stage 
    
    def get_day_left(self) -> int:
        """
        Returns the days left in the current stage of the plant.

        Returns:
            int: The days left in the current stage of the plant.
        """
        self.days_left = self.days_left - self.days_in_current_stage
        return self.days_left

class PlantFactory:
    """
    Factory class for creating plant objects.

    Attributes:
        count (int): Class variable to keep track of the number of plants created.
    """
    count = 0  # Class variable to keep track of the number of plants created

    @staticmethod
    def create_plant(plant_name, database_manager, current_stage='Seedling', days_in_current_stage=0, moisture_level=None) -> Plant:
        """
        Creates a plant and assigns it a unique ID.

        Args:
            plant_name (str): The name of the plant to create.
            current_stage (str): The current stage of the plant.
            days_in_current_stage (int): Days in the current stage.
            moisture_level (float, optional): The initial moisture level, if available.
            database_manager (DatabaseManager): An instance of the database manager.

        Returns:
            Plant: The created plant object with a unique ID.
        """
        if plant_name:
            PlantFactory.count += 1  # Increment the count for each new plant
            plant_id = PlantFactory.count  # Assign the current count as the plant ID
            plant = Plant(plant_name)
            plant.id = plant_id  # Assign the ID to the plant
            plant.set_stage(current_stage)
            plant.set_day_current_stage(days_in_current_stage)

            # Store the plant in the database
            database_manager.insert_plant(plant_id, plant_name, current_stage, days_in_current_stage, moisture_level)
            print(f"Created plant '{plant_name}' with ID {plant_id}.")
            return plant
        else:
            raise ValueError("Could not create the plant")
        
class PlantStage:
    """
    Represents a generic stage of a plant.

    Attributes:
        plant (Plant): The plant associated with this stage.
    """
    def __init__(self, plant):
        """
        Initializes the stage with the given plant.

        Args:
            plant (Plant): The plant associated with this stage.
        """
        self.plant = plant

    def grow(self):
        """
        Defines the grow behavior for the stage. This should be overridden by subclasses.
        """
        pass


class SeedStage(PlantStage):
    """
    Represents the seedling stage of a plant.
    """
    def grow(self):
        """
        Transitions the plant from the seedling stage to the grow stage.
        """
        print(f"{self.plant.name} is growing from a seed.")
        self.plant.set_stage(GrowStage(self.plant))

class GrowStage(PlantStage):
    """
    Represents the grow stage of a plant.
    """
    def grow(self):
        """
        Transitions the plant from the grow stage to the harvest stage.
        """
        print(f"{self.plant.name} is in vegetative stage.")
        self.plant.set_stage(FloweringStage(self.plant))

class FloweringStage(PlantStage):
    """
    Represents the harvest stage of a plant.
    """
    def grow(self):
        """
        Indicates that the plant is in the flowering stage.
        """
        print(f"{self.plant.name} is in flowering stage.")
