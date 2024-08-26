"""
Description: This script defines the Tent classes, managing the plants in the grow tent.

Author: Sebastian Gomez
Date: May 2024
"""
from grow_plant import Plant, PlantFactory

class Tent:
    """
    Singleton class representing a growing tent that holds plants and manages database interactions.

    Attributes:
        _instance (Tent): The singleton instance of the Tent class.
        plants (dict): A dictionary to store plants in the tent, keyed by their unique ID.
        database_manager (DatabaseManager): An instance of the database manager.
    """
    _instance = None
    
    def __new__(cls, database_manager):
        """
        Ensures that only one instance of Tent exists (singleton pattern).
        
        Args:
            database_manager (DatabaseManager): An instance of the database manager.
        
        Returns:
            Tent: The singleton instance of the Tent class.
        """
        if cls._instance is None:
            cls._instance = super(Tent, cls).__new__(cls)
            cls._instance.plants = {}
            cls._instance.database_manager = database_manager
            if database_manager:
                cls._instance._load_plants_from_db()
        return cls._instance

    def _load_plants_from_db(self):
        """
        Loads plant configurations from the database and creates Plant objects.
        """
        plant_configs = self.database_manager.get_all_plants()
        for config in plant_configs:
            plant = Plant(name=config['name'])
            plant.id = config['plant_id']
            plant.set_stage(config['current_stage'])
            plant.set_day_current_stage(config['days_in_current_stage'])
            plant.set_moisture_level(config.get('moisture_level'))
            self.plants[plant.id] = plant  # Use the plant ID from the database as the key

    def add_plant(self, plant_name, plant_type):
        """
        Adds a new plant to the tent and stores it in the database.

        Args:
            plant_name (str): The name of the plant.
            plant_type (str): The type of the plant.

        Returns:
            int: The unique ID of the newly added plant.
        """
        plant = PlantFactory.create_plant(plant_name, self.database_manager, plant_type)
        self.plants[plant.id] = plant
        print(f"Added plant '{plant_name}' with ID {plant.id} to the tent.")
        return plant.id
    
    def remove_plant(self, plant_id):
        """
        Removes a plant from the tent and the database.

        Args:
            plant_id (int): The ID of the plant to be removed.
        """
        if plant_id in self.plants:
            del self.plants[plant_id]
            self.database_manager.remove_plant(plant_id)
            print(f"Removed plant with ID {plant_id} from the tent.")
        else:
            print(f"Plant with ID {plant_id} not found in the tent.")

    def get_plant_by_id(self, plant_id: int) -> Plant:
        """
        Retrieves a plant by its unique ID.

        Args:
            plant_id (int): The ID of the plant to retrieve.

        Returns:
            Plant: The plant with the given ID, or None if not found.
        """
        return self.plants.get(plant_id)

    def get_plant_by_name(self, plant_name: str) -> Plant:
        """
        Retrieves a plant by its name.

        Args:
            plant_name (str): The name of the plant to retrieve.

        Returns:
            Plant: The plant with the given name, or None if not found.
        """
        for plant in self.plants.values():
            if plant.get_name() == plant_name:
                return plant
        return None

    def get_all_plants(self) -> list:
        """
        Retrieves the list of plants in the tent.

        Returns:
            list: A list of plants in the tent.
        """
        return list(self.plants.values())

    def grow_all_plants(self):
        """
        Updates the growth stage of all plants and stores the data in the database.
        """
        for plant_id, plant in self.plants.items():
            plant.grow()
            self.database_manager.update_plant_current_stage(plant.name, plant.get_stage_name())
            print(f"Grew plant '{plant.name}' (ID: {plant_id}) to stage '{plant.get_stage_name()}'.")
