"""
Description: This script defines the GrowthEnvironment classes, managing the plants in the grow tent.

Author: Sebastian Gomez
Date: May 2024
"""
import logging
import time
from plant_profile import PlantProfile

logging.basicConfig(level=logging.INFO, filename="growth_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class GrowthEnvironment:
    """
    Singleton class representing a growing environment that holds plants and manages database interactions.

    Attributes:
        _instance (GrowthEnvironment): The singleton instance of the GrowthEnvironment class.
        plants (dict): A dictionary to store plants in the tent, keyed by their unique ID.
        database_manager (DatabaseManager): An instance of the database manager.
    """
    _instance = None
    
    def __new__(cls, database_handler):
        """
        Ensures that only one instance of GrowthEnvironment exists (singleton pattern).
        
        Args:
            database_handler (DatabaseHandler): An instance of the database manager.
        
        Returns:
            GrowthEnvironment: The singleton instance of the GrowthEnvironment class.
        """
        if cls._instance is None:
            cls._instance = super(GrowthEnvironment, cls).__new__(cls)
            cls._instance.plants = {}
            cls._instance.database_handler = database_handler
            cls._instance.last_sync_time = time.time()
            if database_handler:
                cls._instance._load_plants_from_db()
        return cls._instance

    def _load_plants_from_db(self):
        """
        Loads all plant instances from the database into memory.
        This prevents excessive database queries and improves Raspberry Pi performance.
        """
        logging.info("Loading plants into memory...")
        plant_data_list = self.database_handler.get_all_plants()
        plant_sensors = self.database_handler.get_plant_sensors()
        sensor_map = {ps['sensor_id']: ps['plant_id'] for ps in plant_sensors}

        for plant_data in plant_data_list:
            plant = PlantProfile(plant_data["id"], self.database_handler)
            self.plants[plant.id] = plant
        logging.info(f"Loaded {len(self.plants)} plants.")
 
    def add_plant(self, plant_name, plant_type, sensor_id=None):
        """
        Creates a new plant and stores it in memory (and syncs to DB).

        Args:
            plant_name (str): Name of the plant instance.
            plant_type (str): Type of plant (e.g., 'Lettuce', 'Tomato', 'CustomPlant').
            sensor_id (int, optional): Sensor ID linked to the plant.

        Returns:
            Plant: The newly created plant instance.
        """
        plant_id = self.database_manager.insert_plant(plant_name, plant_type, sensor_id)

        if plant_id:
            new_plant = PlantProfile(plant_id, self.database_manager)
            self.plants[plant_id] = new_plant
            logging.info(f"Plant '{plant_name}' added to the growth environment.")
            return new_plant
        else:
            logging.warning("Failed to add plant.")
            return None
    
    def remove_plant(self, plant_id):
        """
        Removes a plant from memory and database.

        Args:
            plant_id (int): The ID of the plant to remove.
        """
        if plant_id in self.plants:
            self.database_manager.remove_plant(plant_id)
            del self.plants[plant_id]
            logging.info(f"Plant {plant_id} removed from memory and database.")
        else:
            logging.warning(f"Plant {plant_id} not found.")
    
    def get_plant_by_id(self, plant_id: int) -> PlantProfile:
        """
        Retrieves a plant by its unique ID.

        Args:
            plant_id (int): The ID of the plant to retrieve.

        Returns:
            Plant: The plant with the given ID, or None if not found.
        """
        print("checkint type in get_plant by id:", type(plant_id))
        return self.plants.get(plant_id)
    
    def update_plant_soil_moisture(self, plant, moisture_level):
        """
        Updates the soil moisture level of a specific plant.

        Args:
            plant (Plant): The plant object.
            moisture_level (float): The new soil moisture level.

        Raises:
            ValueError: If the plant with the given name is not found.
        """
        if plant:
            plant.set_moisture_level(moisture_level)
        else:
            logging.error(f"Plant with name {plant.get_name()} not found.")

    def get_all_plants(self) -> list:
        """
        Retrieves the list of plants in the growth environment.

        Returns:
            list: A list of plants in the growth environment.
        """
        return list(self.plants.values())
    
    def sync_to_db(self, interval=60):
        """
        Periodically syncs plant data to the database.
        This reduces Raspberry Pi write overhead by batching updates.

        Args:
            interval (int): Sync interval in seconds.
        """
        current_time = time.time()
        if current_time - self.last_sync_time > interval:
            print("Syncing plants to database...")
            for plant in self.plants.values():
                plant.update_plant_in_database()
            self.last_sync_time = current_time
            logging.info("Database synced.")

    
        