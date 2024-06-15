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
        name (str): The name of the plant.
        stage (PlantStage): The current stage of the plant.
        soil_moisture_sensor (SoilMoistureSensor): Sensor to monitor soil moisture.
        stage (str): The current stage of the plant.
        stage_durations (dict): The durations for each growth stage.
        days_in_current_stage (int): Number of days the plant has been in the current stage.
    """
    def __init__(self, name):
        """
        Initializes a new plant with a seed stage and a soil moisture sensor.

        Args:
            name (str): The name of the plant.
        """
        self.name = name
        self.stage = SeedStage(self)
        self.sensor_id = None
        self.soil_moisture_sensor = None
        self.stage_durations = {'Seedling': 7,
                                'Vegetative' : 23,
                                'Flowering': 30}
        self.days_in_current_stage = 0
        self.days_left = self.stage_durations['Seedling']

    def set_sensor(self, sensor):
        if isinstance(sensor, SoilMoistureSensor):
            self.soil_moisture_sensor = sensor
            self.sensor_id = sensor.sensor_id
            database_manager.update_plant_sensor_link(self.name, sensor.sensor_id)

    def set_stage(self, stage):
        """
        Sets the current stage of the plant.

        Args:
            stage (PlantStage): The new stage of the plant.
        """
        self.stage = stage
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
        Triggers the grow process for the plant, changing its stage as it grows and adds 
        one day to the current stage.
        """
        self.stage.grow()
        self.days_in_current_stage +=1
        # Check and transition to the next stage if the current stage duration is met
        if self.stage.__class__.__name__ == 'SeedStage' and self.days_in_current_stage >= self.stage_durations['Seedling']:
            self.set_stage(GrowStage(self))
        elif self.stage.__class__.__name__ == 'GrowStage' and self.days_in_current_stage >= self.stage_durations['Vegetative']:
            self.set_stage(FloweringStage(self))

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
        moisture_level = self.soil_moisture_sensor.read_moisture_level()
        if moisture_level is not None:
            return moisture_level
        print(f"Error reading moisture level for plant {self.name}")
        return None

    def set_stage(self, stage: str):
        """
        Sets the current stage of the plant.

        Args:
            stage (str): The new stage of the plant.
        """
        self.stage = stage

    def increase_days_in_stage(self):
        """Increases the days in the current stage by 1."""
        self.days_in_current_stage += 1

    def decrease_days_in_stage(self):
        """Decreases the days in the current stage by 1."""
        if self.days_in_current_stage > 0:
            self.days_in_current_stage -= 1

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
    """
    @staticmethod
    def create_plant(plant_type, sensor_pin=None) -> Plant:
        """
        Creates a plant of the specified type.

        Args:
            plant_type (str): The type of plant to create.
            stage (str): The stage of the plant (seeding, vegetative or flowering)

        Returns:
            Plant: The created plant object.

        Raises:
            ValueError: If the plant could not be created.
        """
        if plant_type:
            plant = Plant(plant_type)
        else:
            raise ValueError("Could not create the plant")
        if sensor_pin:
            sensor = SoilMoistureSensor(plant, sensor_pin)
            plant.set_sensor(sensor)
        return plant
        

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
