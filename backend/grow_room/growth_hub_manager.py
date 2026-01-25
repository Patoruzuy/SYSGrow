"""
Description: Manages multiple independent growth environments.

Author: Sebastian Gomez
Date: October 2023
"""
import logging
from grow_room.growth_unit import GrowthUnit
from utils.event_bus import EventBus
from flask import current_app
import threading

logging.basicConfig(level=logging.INFO, filename="growth_system.log",
                    format="%(asctime)s - %(levelname)s - %(message)s")

class GrowthUnitManager:
    """
    Manages multiple growth units and tracks plants.

    Attributes:
        database_handler (DatabaseHandler): Handles plant storage.
        event_bus (EventBus): Handles real-time events.
        growth_units (dict):  A dictionary of GrowthUnit instances, keyed by their IDs.
        plant_lock (threading.Lock):  A lock to ensure thread-safe access to shared data.
    """
    def __init__(self, database_handler):
        """
        Initializes the Growth Unit Manager.

        Args:
            database_handler: Handles database operations.
        """
        self.database_handler = database_handler
        self.growth_units = {} 
        self.event_bus = EventBus()
        self.plant_lock = threading.Lock()

        # Load existing units from the database on startup
        self._load_units_from_db()
        
        self.event_bus.subscribe("growth_warning", self.handle_growth_warning)
        self.event_bus.subscribe("plant_added", self.handle_plant_added)
        self.event_bus.subscribe("plant_removed", self.handle_plant_removed)
        logging.info("Growth Unit Manager Initialized")

    def _load_units_from_db(self):
        """
        Loads all existing growth units from the database.
        """
                # Tries to load settings when it is safe within app context.
        
        logging.info("Loading growth units from database...")
        try:
            with current_app.app_context():
                unit_data_list = self.database_handler.get_all_growth_units()
            for unit_data in unit_data_list:
                try:
                    unit_id = unit_data["id"]
                    name = unit_data["name"]
                    location = unit_data["location"]
                    self.growth_units[unit_id] = GrowthUnit(unit_id, name, location, self.database_handler)
                    logging.info(f"Growth Unit {unit_id} loaded.")
                except Exception as e:
                    logging.error(f"Error loading growth unit {unit_data}: {e}", exc_info=True)
        except Exception as db_error:
            logging.error(f"Database error loading growth units: {db_error}", exc_info=True)

    def add_growth_unit(self, name, location="Indoor", redis_client=None):
        """
        Adds a new growth unit.

        Args:
            name (str): Name of the unit.
            location (str): Indoor or Outdoor.
        """
        try:
            if not name:  # Data validation
                raise ValueError("Growth unit name cannot be empty.")
            if location not in ["Indoor", "Outdoor"]:
                raise ValueError(f"Invalid location: {location}. Must be 'Indoor' or 'Outdoor'.")

            unit_id = self.database_handler.insert_growth_unit(name, location)
            self.growth_units[unit_id] = GrowthUnit(unit_id, name, location, redis_client, self.database_handler)
            logging.info(f"Growth Unit {unit_id} ({name}) added.")
            return unit_id # return the unit_id
        except ValueError as ve:
            logging.error(f"Error adding growth unit: {ve}")
            return None  # Return None to indicate failure
        except Exception as e:
            logging.error(f"Error adding growth unit {name}: {e}", exc_info=True)
            return None

    def remove_growth_unit(self, unit_id):
        """
        Removes a growth unit.

        Args:
            unit_id (int): The ID of the growth unit to remove.
        """
        try:
            if unit_id not in self.growth_units:
                logging.warning(f"Growth Unit {unit_id} not found.")
                return  # Or raise an exception

            # Delete from database first to maintain consistency
            self.database_handler.delete_growth_unit(unit_id)
            del self.growth_units[unit_id]
            logging.info(f"Growth Unit {unit_id} removed.")
        except Exception as e:
            logging.error(f"Error removing growth unit {unit_id}: {e}", exc_info=True)

    def edit_growth_unit(self, unit_id, name, location, redis_client=None):
        """
        Edits an existing growth unit.

        Args:
            unit_id (int): The ID of the growth unit to edit.
            name (str): The new name of the unit.
            location (str): The new location of the unit.
        """
        try:
            if unit_id not in self.growth_units:
                logging.warning(f"Growth Unit {unit_id} not found.")
                return  # Or raise an exception

            if not name:  # Data validation
                raise ValueError("Growth unit name cannot be empty.")
            if location not in ["Indoor", "Outdoor"]:
                raise ValueError(f"Invalid location: {location}. Must be 'Indoor' or 'Outdoor'.")

            self.database_handler.update_growth_unit(unit_id, name, location)
            self.growth_units[unit_id].name = name
            self.growth_units[unit_id].location = location
            logging.info(f"Growth Unit {unit_id} edited.")
        except ValueError as ve:
            logging.error(f"Error editing growth unit: {ve}")
        except Exception as e:
            logging.error(f"Error editing growth unit {unit_id}: {e}", exc_info=True)

    def get_all_units(self):
        """
        Returns details of all growth units.

        Returns:
            dict: All registered growth units and their statuses.
        """
        with self.plant_lock:
            return {unit_id: unit.get_status() for unit_id, unit in self.growth_units.items()}
    
    def handle_growth_warning(self, data):
        """Handles plant growth warnings."""
        logging.warning(f"Warning for {data['plant_id']} - {data['message']}")

    def handle_plant_added(self, data):
        """
        Handles the plant_added event.  Adds the plant to the appropriate growth unit.
        """
        unit_id = data["unit_id"]
        plant_id = data["plant_id"]
        logging.info(f"GrowthUnitManager received plant_added event for unit {unit_id}, plant {plant_id}")
        with self.plant_lock: # Use the lock
            if unit_id in self.growth_units:
                growth_unit = self.growth_units[unit_id]
                #  Delegate the actual adding of the plant to the GrowthUnit instance.
                #growth_unit.add_plant(plant_id) # changed
                logging.info(f"Plant {plant_id} added to Growth Unit {unit_id} in GrowthUnitManager.")
            else:
                logging.error(f"Growth Unit {unit_id} not found when trying to add plant {plant_id}.")

    def handle_plant_removed(self, data):
        """
        Handles the plant_removed event. Removes the plant from the appropriate growth unit.
        """
        unit_id = data["unit_id"]
        plant_id = data["plant_id"]
        logging.info(f"GrowthUnitManager received plant_removed event for unit {unit_id}, plant {plant_id}")
        with self.plant_lock: # Use the lock
            if unit_id in self.growth_units:
                growth_unit = self.growth_units[unit_id]
                # Delegate the actual removal of the plant to the GrowthUnit instance.
                growth_unit.remove_plant(plant_id)
                logging.info(f"Plant {plant_id} removed from Growth Unit {unit_id} in GrowthUnitManager.")
            else:
                logging.error(f"Growth Unit {unit_id} not found when trying to remove plant {plant_id}.")

    def get_all_plants(self):
        """
        Returns a list of all plants across all growth units.

        Returns:
            list: A list of PlantProfile objects.
        """
        all_plants = []
        with self.plant_lock:
            for growth_unit in self.growth_units.values():
                all_plants.extend(growth_unit.get_all_plants())
        return all_plants

    def get_plant_by_id(self, plant_id):
        """
        Returns a specific plant given its ID, searching across all growth units.

        Args:
            plant_id (int): The ID of the plant.

        Returns:
            PlantProfile or None: The plant instance, or None if not found.
        """
        with self.plant_lock:
            for growth_unit in self.growth_units.values():
                plant = growth_unit.get_plant_by_id(plant_id)
                if plant:
                    return plant
        return None

