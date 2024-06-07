"""
Description: This script defines the Tent classes, managing the plants in the grow tent.

Author: Sebastian Gomez
Date: May 2024
"""

class Tent:
    """
    Singleton class representing a growing tent that holds plants
    
    Attributes:
        _instance (Tent): The singleton instance of the Tent class.
        plants (list): A list to store plants added to the tent.
    """
    _instance = None
    
    def __new__(cls):
        """
        Ensures that only one instance of Tent exists (singleton pattern).
        
        Returns:
            Tent: The singleton instance of the Tent class.
        """
        if cls._instance is None:
            cls._instance = super(Tent, cls).__new__(cls)
            cls._instance.plants = []
        return cls._instance
        
    def add_plant(self, plant):
        """
        Adds a plant to the tent.
        
        Args:
            plant (Plant): The plant to be added.
        """
        self.plants.append(plant)
    
    def remove_plant(self, plant):
        """
        Removes a plant from the tent.
        
        Args:
            plant (Plant): The plant to be removed.
        """
        self.plants.remove(plant)

    def get_plant_by_name(self, plant_name) -> str:
        """
        Retrieves a plant by its name.
        
        Args:
            plant_name (str): The name of the plant to retrieve.
        
        Returns:
            Plant: The plant with the given name, or None if not found.
        """
        for plant in self.plants:
            if plant.get_name() == plant_name:
                return plant
        return None

    def get_all_plants(self) -> list:
        """
        Retrieves the list of plants in the tent.
        
        Returns:
            list: A list of plants in the tent.
        """
        return self.plants

    
        