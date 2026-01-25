import os
import json
import logging

class PlantJsoneHandler:
    """Handles reading, writing, and updating the plant JSON dataset."""

    def __init__(self, json_file="plants_data.json"):
        self.json_file = json_file
        self.data = self._load_json()

    def _load_json(self):
        """Loads the JSON file. Creates a new one if missing."""
        if not os.path.exists(self.json_file):
            logging.info(f"{self.json_file} not found. Creating a new one.")
            return {"plants_info": []}  # Empty dataset structure

        try:
            with open(self.json_file, "r") as file:
                data = json.load(file)
                if "plants_info" not in data:
                    logging.warning(f"Invalid format: 'plants_info' key missing. Resetting file.")
                    return {"plants_info": []}  # Reset if format is incorrect
                return data
        except json.JSONDecodeError:
            logging.error(f"Failed to parse {self.json_file}. Check JSON syntax.")
            return {"plants_info": []}

    def save_json(self):
        """Saves the current dataset to the JSON file."""
        try:
            with open(self.json_file, "w") as file:
                json.dump(self.data, file, indent=4)
            logging.info(f"Database successfully saved to {self.json_file}.")
            return True
        except IOError:
            logging.error(f"Failed to write to {self.json_file}. Check file permissions.")
            return False

    def get_growth_stages(self, plant_name):
        """Retrieves growth stages for a specific plant by common name."""
        for plant in self.data["plants_info"]:
            if plant["common_name"].lower() == plant_name.lower():
                return plant["growth_stages"]
        logging.warning(f"Stages for '{plant_name}' not found.")
        return []
    
    def get_plants_info(self):
        """Retrieves all plant information from the dataset."""
        return self.data["plants_info"]

    def add_plant(self, new_plant):
        """Adds a new plant to the dataset if it doesn't already exist."""
        for plant in self.data["plants_info"]:
            if plant["common_name"].lower() == new_plant["common_name"].lower():
                logging.warning(f"Plant '{new_plant['common_name']}' already exists.")
                return False

        # Assign a new ID
        new_plant["id"] = max([p["id"] for p in self.data["plants_info"]], default=0) + 1

        # Append and save
        self.data["plants_info"].append(new_plant)
        return self.save_json()

    def plant_exists(self, plant_name):
        """Checks if a plant exists in the dataset."""
        return any(plant["common_name"].lower() == plant_name.lower() for plant in self.data["plants_info"])

    def list_plants(self):
        """Returns a list of all plant names in the dataset."""
        return [plant["common_name"] for plant in self.data["plants_info"]]
