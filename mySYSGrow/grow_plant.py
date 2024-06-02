"""
Description: This script defines classes for managing plant growth, including plant states and a plant factory for creating different types of plants.

Author: Sebastian Gomez
Date: 26/05/24
"""

from grow_tent import Tent
from sensor import SoilMoistureSensor

class Plant:
    """
    Represents a plant with various states and a soil moisture sensor.

    Attributes:
        name (str): The name of the plant.
        state (PlantState): The current state of the plant.
        soil_moisture_sensor (SoilMoistureSensor): Sensor to monitor soil moisture.
        stage (str): The current stage of the plant.
        stage_durations (dict): The durations for each growth stage.
        days_in_current_stage (int): Number of days the plant has been in the current stage.
    """
    def __init__(self, name):
        """
        Initializes a new plant with a seed state and a soil moisture sensor.

        Args:
            name (str): The name of the plant.
        """
        self.name = name
        self.state = SeedState(self)
        self.soil_moisture_sensor = SoilMoistureSensor(self)
        self.stage_durations = {'Seed': 7,
                                'Vegetative' : 23,
                                'Flowering': 30}
        self.days_in_current_stage = 0

    def set_state(self, state):
        """
        Sets the current state of the plant.

        Args:
            state (PlantState): The new state of the plant.
        """
        self.state = state
        self.days_in_current_stage = 0

    def set_stage_durations(self, seed_days, veg_days, flowering_days):
        """
        Sets the durations for each growth stage of the plant.

        Args:
            seed_days (int): The number of days for the seed stage.
            veg_days (int): The number of days for the vegetative stage.
            flowering_days (int): The number of days for the flowering stage.
        """
        self.stage_durations['Seed'] = seed_days
        self.stage_durations['Vegetative'] = veg_days
        self.stage_durations['Flowering'] = flowering_days

    def grow(self):
        """
        Triggers the grow process for the plant, changing its state as it grows and adds 
        one day to the current stage.
        """
        self.state.grow()
        self.days_in_current_stage +=1
        # Check and transition to the next stage if the current stage duration is met
        if self.stage.__class__.__name__ == 'SeedState' and self.days_in_current_stage >= self.stage_durations['Seed']:
            self.set_state(GrowState(self))
        elif self.stage.__class__.__name__ == 'GrowState' and self.days_in_current_stage >= self.stage_durations['Vegetative']:
            self.set_state(FloweringState(self))

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
        return self.soil_moisture_sensor.read_moisture_level()

    def set_stage(self, stage: str):
        """
        Sets the current stage of the plant.

        Args:
            stage (str): The new stage of the plant.
        """
        self.stage = stage

    def get_days_current_stage(self) -> int:
        """
        Returns the days in the current stage of the plant.

        Returns:
            int: The days in the current stage of the plant.
        """
        return self.days_in_current_stage 


class PlantFactory:
    """
    Factory class for creating plant objects.
    """
    @staticmethod
    def create_plant(plant_type, state) -> Plant:
        """
        Creates a plant of the specified type.

        Args:
            plant_type (str): The type of plant to create.
            state (str): The stage of the plant (seeding, vegetative or flowering)

        Returns:
            Plant: The created plant object.

        Raises:
            ValueError: If the plant could not be created.
        """
        if plant_type:
            return Plant(plant_type, state)
        else:
            raise ValueError("Could not create the plant")
        

class PlantState:
    """
    Represents a generic state of a plant.

    Attributes:
        plant (Plant): The plant associated with this state.
    """
    def __init__(self, plant):
        """
        Initializes the state with the given plant.

        Args:
            plant (Plant): The plant associated with this state.
        """
        self.plant = plant

    def grow(self):
        """
        Defines the grow behavior for the state. This should be overridden by subclasses.
        """
        pass


class SeedState(PlantState):
    """
    Represents the seed state of a plant.
    """
    def grow(self):
        """
        Transitions the plant from the seed state to the grow state.
        """
        print(f"{self.plant.name} is growing from a seed.")
        self.plant.set_state(GrowState(self.plant))

class GrowState(PlantState):
    """
    Represents the grow state of a plant.
    """
    def grow(self):
        """
        Transitions the plant from the grow state to the harvest state.
        """
        print(f"{self.plant.name} is in vegetative stage.")
        self.plant.set_state(FloweringState(self.plant))

class FloweringState(PlantState):
    """
    Represents the harvest state of a plant.
    """
    def grow(self):
        """
        Indicates that the plant is in the flowering stage.
        """
        print(f"{self.plant.name} is in flowering stage.")
