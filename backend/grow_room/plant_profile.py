"""
Description: This script defines classes for managing plant growth, including plant stages and a plant factory for creating different types of plants.

Author: Sebastian Gomez
Date: 26/05/24
"""
from utils.event_bus import EventBus
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, filename="growth_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class PlantProfile:
    """
    Represents a plant with various stages and a soil moisture sensor.

    Attributes:
        name (str): The name of the plant.
        sensor_id (int): Sensor ID associated with the plant.
        moisture_level (float): Current soil moisture level.
        stage_durations (dict): Durations for each growth stage.
        days_in_current_stage (int): Days the plant has been in the current stage.
        event_bus (EventBus): Event system for plant growth automation.
        ai_model (PlantGrowthPredictor): AI model for growth predictions.
    """
    def __init__(self, plant_id, plant_name, current_stage, growth_stages, database_handler):
        """
        Initializes a plant instance from the database.

        Args:
            plant_id (int): The ID of the plant in the database.
            plant_name (str): The name of the plant.
            database_handler (DatabaseHandler): The database handler instance.
            growth_stages (dict): Information about the plant's growth stages.
        """
        self.id = plant_id
        self.plant_name = plant_name
        self.database_handler = database_handler
        self.current_stage_index = 0
        self.days_in_stage = 0
        self.current_stage = current_stage
        self.sensor_id = None
        self.moisture_level = 0
        self.event_bus = EventBus()
        # Load growth information for the plant.
        self.growth_stages = growth_stages

        # Compute lighting hours for each stage
        self.stage_lighting_hours = {
            stage["stage"]: stage["conditions"]["light_hours"]
            for stage in self.growth_stages
        }
        # Compute stage durations from growth stages
        self.stage_durations = {
            stage["stage"]: {
                "min_days": stage["duration"]["min_days"],
                "max_days": stage["duration"]["max_days"]
            } for stage in self.growth_stages
        }
        # Subscribe to environmental updates
        self.event_bus.subscribe(f"plant_stage_update_{self.id}", self.handle_stage_update)
        self.event_bus.subscribe(f"moisture_level_updated", self.handle_moisture_update)
        # AI-Based Growth Prediction
        self.days_left = self.stage_durations.get(self.get_current_stage_name(), 0) - self.days_in_stage

    def set_stage(self, new_stage, days_in_stage=0):
        """
        Sets the current stage of the plant.

        Args:
            new_stage (str): The new stage of the plant.
            days_in_current_stage (int): The number of days in the current stage.
        """
        try:
            logging.info(f"{self.plant_name} (ID: {self.id}) setting stage to {new_stage}, days_in_stage: {days_in_stage}")
            self.current_stage = new_stage
            self.days_in_stage = days_in_stage
            self.update_days_left()
            self.update_database()

            # Notify system about stage change
            self.event_bus.publish(f"plant_stage_update_{self.id}", {
                "plant_id": self.id,
                "new_stage": new_stage,
                "days_in_stage": days_in_stage
            })
        except Exception as e:
            logging.error(f"Error setting stage for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)

    def grow(self):
        """
        Advances the plant's growth stage based on time spent in the current stage.
        Uses EventBus to trigger warnings and transitions.
        """
        try:
            if self.current_stage_index >= len(self.growth_stages) - 1:
                logging.info(f"{self.plant_name} (ID: {self.id}) has reached full maturity at '{self.get_current_stage_name()}' stage.")
                return

            self.days_in_stage += 1
            current_stage_name = self.get_current_stage_name()
            min_days = self.stage_durations[current_stage_name]["min_days"]
            max_days = self.stage_durations[current_stage_name]["max_days"]

            # Trigger warning if the plant is overdue
            if self.days_in_stage == min_days:
                self.update_database()
                self.event_bus.publish(f"growth_warning_{self.id}", {
                    "plant_id": self.id,
                    "stage": current_stage_name,
                    "message": f"⚠️ {self.plant_name} (ID: {self.id}) should transition from '{current_stage_name}'!"
                })
            elif self.days_in_stage > max_days:
                day_to_transition = self.days_in_stage - max_days
                self.update_database()
                self.event_bus.publish(f"growth_warning_{self.id}", {
                    "plant_id": self.id,
                    "stage": current_stage_name,
                    "days_to_transition": day_to_transition,
                    "message": f"🚨 {self.plant_name} (ID: {self.id}) has exceeded the '{current_stage_name}' minimum stage limit, transition in '{day_to_transition}' days!"
                })
            # Transition if minimum duration met
            if self.days_in_stage >= max_days:
                self.advance_stage()
                self.update_database()
        except Exception as e:
            logging.error(f"Error in grow for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)

    def advance_stage(self):
        """Moves the plant to the next stage if possible."""
        try:
            if self.current_stage_index < len(self.growth_stages) - 1:
                self.current_stage_index += 1
                self.days_in_stage = 0
                new_stage = self.get_current_stage_name()
                logging.info(f"🌱 {self.plant_name} (ID: {self.id}) advanced to '{self.get_current_stage_name()}' stage.")
                self.document_plant_data()
                self.update_database()
                # Publish the stage update event
                self.event_bus.publish(f"plant_stage_update", {
                    "plant_id": self.id,
                    "new_stage": new_stage,
                    "days_in_stage": self.days_in_stage
                })
            else:
                logging.info(f"🌿 {self.plant_name} (ID: {self.id}) has fully matured!")
        except Exception as e:
             logging.error(f"Error advancing stage for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)

    def get_name(self) -> str:
        """
        Returns the name of the plant.

        Returns:
            str: The name of the plant.
        """
        return self.plant_name
        
    def link_sensor(self, sensor_id):
        """
        Associates a sensor with the plant by storing the sensor's ID.
        args:
            sensor_id (int): The ID of the sensor.
        """
        try:
            logging.info(f"{self.plant_name} (ID: {self.id}) setting sensor ID to {sensor_id}")
            self.sensor_id = sensor_id
        except Exception as e:
            logging.error(f"Error setting sensor ID for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)

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
        try:
            # Data Validation
            if not (0 <= moisture_level <= 100):
                raise ValueError(f"Moisture level {moisture_level} is outside the valid range (0-100).")
            logging.info(f"{self.plant_name} (ID: {self.id}) setting moisture level: {moisture_level}")
            self.moisture_level = moisture_level
            self.event_bus.publish(f"moisture_level_updated_{self.id}", {"plant_id": self.id, "moisture_level": moisture_level}) # Publish Event
        except ValueError as ve:
            logging.error(f"Invalid moisture level for {self.plant_name} (ID: {self.id}): {ve}")
        except Exception as e:
            logging.error(f"Error setting moisture level for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)

    def get_moisture_level(self):
        """
        Returns the moisture level from the plant.
        """
        return self.moisture_level

    def get_growth_stages(self):
        """Returns the list of growth stages for the plant."""
        return self.growth_stages if self.growth_stages else []
    
    def get_current_stage_name(self):
        """Returns the name of the current growth stage."""
        return self.growth_stages[self.current_stage_index]["stage"]

    def get_current_stage_index(self):
        """Returns the name of the plant's current growth stage."""
        return self.growth_stages[self.current_stage_index]["stage"]

    def increase_days_in_stage(self):
        """Increases the days in the current stage by 1."""
        try:
            self.days_in_stage += 1
            self.update_days_left()
            self.update_database()
            logging.info(f"{self.plant_name} (ID: {self.id}) increased days in stage. Current days: {self.days_in_stage}")
        except Exception as e:
            logging.error(f"Error increasing days in stage for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)

    def decrease_days_in_stage(self):
        """Decreases the days in the current stage by 1."""
        try:
            if self.days_in_stage > 0:
                self.days_in_stage -= 1
                self.update_days_left()
                self.update_database()
                logging.info(f"{self.plant_name} (ID: {self.id}) decreased days in stage. Current days: {self.days_in_stage}")
            else:
                logging.warning(f"{self.plant_name} (ID: {self.id}) days in stage is already 0. Cannot decrease further.")
        except Exception as e:
            logging.error(f"Error decreasing days in stage for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)

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
        try:
            logging.info(f"Documenting plant data for {self.plant_name} (ID: {self.id})")
            average_temp = self.database_handler.get_average_temperature(self.id)
            average_humidity = self.database_handler.get_average_humidity(self.id)
            light_hours = self.database_handler.get_total_light_hours(self.id)
            date_harvested = datetime.now().strftime('%Y-%m-%d')

            self.database_handler.insert_plant_history(
                self.plant_name,
                self.current_stage,
                self.get_days_current_stage(),
                average_temp,
                average_humidity,
                light_hours,
                harvest_weight,
                photo_path,
                date_harvested
            )
            logging.info(f"Plant data documented for {self.plant_name} (ID: {self.id})")
        except Exception as e:
            logging.error(f"Error documenting plant data for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)

    def handle_stage_update(self, data):
        """Handles plant stage updates triggered by EventBus."""
        if data["plant_id"] == self.id:
            logging.info(f"🔄 {self.plant_name} (ID: {self.id}) received stage update: {data['new_stage']}.")
            self.set_stage(data["new_stage"], data["days_in_stage"])

    def handle_moisture_update(self, data):
        """Handles moisture level updates."""
        if data["sensor_id"] == self.sensor_id:
            try:
                self.moisture_level = data["moisture_level"]
                self.update_database()
                logging.info(f"💧 {self.plant_name} (ID: {self.id}) moisture level updated: {self.moisture_level}")
            except Exception as e:
                logging.error(f"Error handling moisture update for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)
    
    def update_days_left(self):
        """Update the days left in the current stage."""
        stage_name = self.get_current_stage_name()
        if stage_name in self.stage_durations:
            max_days = self.stage_durations[stage_name]["max_days"]
            self.days_left = max(max_days - self.days_in_stage, 0)
        else:
            self.days_left = 0
    
    def update_database(self):
        """Updates the current stage days in the plant's record in the database."""
        try:
            self.database_handler.update_plant_days(self.id, self.current_stage, self.moisture_level, self.days_in_stage)
            logging.info(f"Database updated for {self.plant_name} (ID: {self.id})")
        except Exception as e:
            logging.error(f"Error updating database for {self.plant_name} (ID: {self.id}): {e}", exc_info=True)

    def to_dict(self):
        """
        Returns a dictionary representation of the plant.
        """
        return {
            "plant_id": self.id,
            "plant_name": self.plant_name,
            "current_stage": self.current_stage,
            "days_in_stage": self.days_in_stage,
            "sensor_id": self.sensor_id,
            "moisture_level": self.moisture_level,
            "days_left": self.days_left
        }