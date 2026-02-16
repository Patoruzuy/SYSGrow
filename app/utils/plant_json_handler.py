import json
import logging
from pathlib import Path
from typing import Any

# Point to the authoritative plants_info.json in the backend root directory
_DEFAULT_DATASET = Path(__file__).resolve().parent.parent.parent / "plants_info.json"


class PlantJsonHandler:
    """
    Handles reading, writing, and updating the plant JSON dataset.
    Supports all enhanced fields: automation, common_issues, companion_plants, harvest_guide.
    """

    # Required fields for complete plant validation
    REQUIRED_FIELDS = [
        "id",
        "species",
        "common_name",
        "variety",
        "pH_range",
        "water_requirements",
        "sensor_requirements",
        "yield_data",
        "nutritional_info",
        "automation",
        "growth_stages",
        "common_issues",
        "companion_plants",
        "harvest_guide",
        "tips",
        "disease_prevention",
        "fertilizer_recommendations",
    ]

    def __init__(self, json_file: str | Path | None = None):
        self.json_path = Path(json_file) if json_file else _DEFAULT_DATASET
        self.data = self._load_json()

    def _load_json(self) -> dict[str, Any]:
        """Loads the JSON file. Creates a new structure if missing or invalid."""
        if not self.json_path.exists():
            logging.info("%s not found. Initialising empty dataset.", self.json_path)
            return {"plants_info": []}

        try:
            with self.json_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
        except json.JSONDecodeError:
            logging.error("Failed to parse %s. Falling back to empty dataset.", self.json_path)
            return {"plants_info": []}

        if "plants_info" not in data or not isinstance(data["plants_info"], list):
            logging.warning("Invalid plant dataset format. Resetting file.")
            return {"plants_info": []}
        return data

    def save_json(self) -> bool:
        """Saves the current dataset to disk."""
        try:
            with self.json_path.open("w", encoding="utf-8") as handle:
                json.dump(self.data, handle, indent=4)
            logging.info("Plant dataset persisted to %s.", self.json_path)
            return True
        except OSError as exc:
            logging.error("Failed to write plant dataset: %s", exc)
            return False

    def get_growth_stages(self, plant_name: str) -> list[dict[str, Any]]:
        """
        Retrieves growth stages for a specific plant by common or scientific name.

        Args:
            plant_name: Name of the plant to look up.

        Returns:
            Growth stages if found, otherwise an empty list.
        """
        target = plant_name.strip().lower()
        for entry in self.data["plants_info"]:
            candidates: list[str | None] = [
                entry.get("common_name"),
                entry.get("species"),
                entry.get("scientific_name"),
            ]
            # Support aliases if present in the dataset
            if "aliases" in entry and isinstance(entry["aliases"], list):
                candidates.extend(entry["aliases"])

            if any(name and name.lower() == target for name in candidates):
                return entry.get("growth_stages", [])

        logging.warning("Growth stages for '%s' not found in dataset.", plant_name)
        return []

    def get_gdd_base_temp_c(self, plant_name: str) -> float | None:
        """
        Retrieve base temperature (°C) for Growing Degree Days calculations.

        Looks for:
        - top-level `gdd_base_temp_c`
        - nested `thermal_time.base_temp_c`

        Returns None when unavailable.
        """
        target = plant_name.strip().lower()
        for entry in self.data["plants_info"]:
            candidates: list[str | None] = [
                entry.get("common_name"),
                entry.get("species"),
                entry.get("scientific_name"),
            ]
            if "aliases" in entry and isinstance(entry["aliases"], list):
                candidates.extend(entry["aliases"])

            if not any(name and name.lower() == target for name in candidates):
                continue

            raw = entry.get("gdd_base_temp_c")
            if raw is None:
                thermal = entry.get("thermal_time") or {}
                if isinstance(thermal, dict):
                    raw = thermal.get("base_temp_c")

            if raw is None:
                return None

            try:
                return float(raw)
            except (TypeError, ValueError):
                logging.warning("Invalid gdd_base_temp_c for '%s': %r", plant_name, raw)
                return None

        return None

    def _find_plant_entry(self, plant_name: str) -> dict[str, Any] | None:
        """
        Find a plant entry by common name, species, scientific name, or alias.

        Args:
            plant_name: Name to search for (case-insensitive).

        Returns:
            Plant entry dict if found, None otherwise.
        """
        target = plant_name.strip().lower()
        for entry in self.data["plants_info"]:
            candidates: list[str | None] = [
                entry.get("common_name"),
                entry.get("species"),
                entry.get("scientific_name"),
            ]
            if "aliases" in entry and isinstance(entry["aliases"], list):
                candidates.extend(entry["aliases"])

            if any(name and name.lower() == target for name in candidates):
                return entry
        return None

    def get_lighting_schedule(self, plant_name: str) -> dict[str, dict[str, Any]]:
        """
        Retrieves the lighting schedule for a plant, organized by growth stage.

        The lighting schedule provides hours and intensity for each stage,
        enabling automated light regulation based on plant growth progress.

        Args:
            plant_name: Name of the plant (common name, species, or alias).

        Returns:
            Dictionary mapping stage names to lighting settings:
            {
                "seedling": {"hours": 14, "intensity": 60},
                "vegetative": {"hours": 16, "intensity": 80},
                "flowering": {"hours": 16, "intensity": 100},
                "fruiting": {"hours": 14, "intensity": 85}
            }
            Returns empty dict if plant not found or no lighting schedule defined.
        """
        entry = self._find_plant_entry(plant_name)
        if not entry:
            logging.warning("Lighting schedule for '%s' not found in dataset.", plant_name)
            return {}

        automation = entry.get("automation") or {}
        lighting = automation.get("lighting_schedule") or {}

        if not lighting:
            logging.debug("No lighting schedule defined for '%s'.", plant_name)
            return {}

        return lighting

    def get_lighting_for_stage(self, plant_name: str, stage: str) -> dict[str, Any] | None:
        """
        Retrieves lighting settings for a specific growth stage.

        Args:
            plant_name: Name of the plant (common name, species, or alias).
            stage: Growth stage name (e.g., "seedling", "vegetative", "flowering").

        Returns:
            Lighting settings for the stage: {"hours": 16, "intensity": 80}
            Returns None if plant/stage not found.
        """
        lighting_schedule = self.get_lighting_schedule(plant_name)
        if not lighting_schedule:
            return None

        # Normalize stage name for lookup (lowercase, handle variations)
        stage_lower = stage.strip().lower()

        # Direct match
        if stage_lower in lighting_schedule:
            return lighting_schedule[stage_lower]

        # Try common variations
        stage_mappings = {
            "germination": "seedling",
            "veg": "vegetative",
            "flower": "flowering",
            "bloom": "flowering",
            "fruit": "fruiting",
            "fruit development": "fruiting",
            "harvest": "fruiting",  # Default to fruiting settings for harvest
        }

        mapped_stage = stage_mappings.get(stage_lower)
        if mapped_stage and mapped_stage in lighting_schedule:
            return lighting_schedule[mapped_stage]

        logging.debug(
            "No lighting settings for stage '%s' in plant '%s'. Available stages: %s",
            stage,
            plant_name,
            list(lighting_schedule.keys()),
        )
        return None

    def get_automation_settings(self, plant_name: str) -> dict[str, Any]:
        """
        Retrieves all automation settings for a plant.

        Includes watering schedule, lighting schedule, alert thresholds,
        and environmental controls.

        Args:
            plant_name: Name of the plant (common name, species, or alias).

        Returns:
            Full automation settings dictionary, or empty dict if not found.
        """
        entry = self._find_plant_entry(plant_name)
        if not entry:
            logging.warning("Automation settings for '%s' not found in dataset.", plant_name)
            return {}

        return entry.get("automation") or {}

    def get_watering_schedule(self, plant_name: str) -> dict[str, Any]:
        """
        Retrieves the watering schedule for a plant.

        Args:
            plant_name: Name of the plant (common name, species, or alias).

        Returns:
            Watering schedule dictionary with frequency_hours, amount_ml_per_plant,
            soil_moisture_trigger, etc. Returns empty dict if not found.
        """
        automation = self.get_automation_settings(plant_name)
        return automation.get("watering_schedule") or {}

    def get_soil_moisture_trigger(self, plant_name: str) -> float | None:
        """
        Resolve a soil moisture trigger threshold for irrigation.

        Priority:
        1) automation.watering_schedule.soil_moisture_trigger
        2) sensor_requirements.soil_moisture_range.min
        3) automation.alert_thresholds.soil_moisture_critical
        """
        entry = self._find_plant_entry(plant_name)
        if not entry:
            logging.warning("Plant '%s' not found for soil moisture trigger.", plant_name)
            return None

        automation = entry.get("automation") or {}
        watering = automation.get("watering_schedule") or {}
        raw = watering.get("soil_moisture_trigger")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                logging.debug("Invalid soil_moisture_trigger for '%s': %r", plant_name, raw)

        sensor_req = entry.get("sensor_requirements") or {}
        range_cfg = sensor_req.get("soil_moisture_range") or {}
        if isinstance(range_cfg, dict):
            raw = range_cfg.get("min")
            if raw is not None:
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    logging.debug("Invalid soil_moisture_range.min for '%s': %r", plant_name, raw)

        alert_thresholds = automation.get("alert_thresholds") or {}
        raw = alert_thresholds.get("soil_moisture_critical")
        if raw is not None:
            try:
                return float(raw)
            except (TypeError, ValueError):
                logging.debug("Invalid soil_moisture_critical for '%s': %r", plant_name, raw)

        return None

    def get_alert_thresholds(self, plant_name: str) -> dict[str, Any]:
        """
        Retrieves alert thresholds for a plant.

        Args:
            plant_name: Name of the plant (common name, species, or alias).

        Returns:
            Alert thresholds dictionary with temperature_min/max, humidity_min/max,
            soil_moisture_critical, etc. Returns empty dict if not found.
        """
        automation = self.get_automation_settings(plant_name)
        return automation.get("alert_thresholds") or {}

    def get_environmental_controls(self, plant_name: str) -> dict[str, Any]:
        """
        Retrieves environmental control triggers for a plant.

        Args:
            plant_name: Name of the plant (common name, species, or alias).

        Returns:
            Environmental controls dictionary with ventilation_trigger_temp,
            heating_trigger_temp, dehumidify_trigger, etc. Returns empty dict if not found.
        """
        automation = self.get_automation_settings(plant_name)
        return automation.get("environmental_controls") or {}

    def get_plants_info(self) -> list[dict[str, Any]]:
        """Retrieves all plant information from the dataset."""
        return list(self.data.get("plants_info", []))

    def add_plant(self, new_plant: dict[str, Any]) -> bool:
        """Adds a new plant to the dataset if it doesn't already exist."""
        target = new_plant.get("common_name", "").strip().lower()
        if not target:
            logging.warning("Cannot add plant without a common name.")
            return False

        for plant in self.data["plants_info"]:
            if plant.get("common_name", "").strip().lower() == target:
                logging.warning("Plant '%s' already exists in dataset.", new_plant["common_name"])
                return False

        next_id = max((p.get("id", 0) for p in self.data["plants_info"]), default=0) + 1
        new_plant["id"] = next_id
        self.data["plants_info"].append(new_plant)
        return self.save_json()

    def plant_exists(self, plant_name: str) -> bool:
        """Checks if a plant exists in the dataset."""
        target = plant_name.strip().lower()
        return any(plant.get("common_name", "").strip().lower() == target for plant in self.data["plants_info"])

    def list_plants(self) -> list[str]:
        """Returns a list of all plant names in the dataset."""
        return [plant.get("common_name", "") for plant in self.data["plants_info"] if plant.get("common_name")]

    # Enhanced CRUD Methods for Full Field Support

    def get_plant_by_id(self, plant_id: int) -> dict[str, Any] | None:
        """
        Retrieves a plant by its ID.

        Args:
            plant_id: The plant ID to search for.

        Returns:
            Plant data if found, None otherwise.
        """
        for plant in self.data["plants_info"]:
            if plant.get("id") == plant_id:
                return plant
        logging.warning("Plant with ID %d not found.", plant_id)
        return None

    def update_plant(self, plant_id: int, updated_data: dict[str, Any], validate: bool = True) -> bool:
        """
        Updates an existing plant with new data, supporting all enhanced fields.

        Args:
            plant_id: ID of the plant to update.
            updated_data: Dictionary containing fields to update.
            validate: Whether to validate the complete structure after update.

        Returns:
            True if update successful, False otherwise.
        """
        plant = self.get_plant_by_id(plant_id)
        if not plant:
            logging.error("Cannot update: Plant ID %d not found.", plant_id)
            return False

        # Update fields
        plant.update(updated_data)

        # Validate structure if requested
        if validate and not self.validate_plant_structure(plant):
            logging.warning("Plant ID %d updated but validation warnings exist.", plant_id)

        return self.save_json()

    def validate_plant_structure(self, plant_data: dict[str, Any], strict: bool = False) -> bool:
        """
        Validates that a plant has all required fields and proper structure.

        Args:
            plant_data: Plant dictionary to validate.
            strict: If True, requires all fields. If False, logs warnings only.

        Returns:
            True if valid (or warnings only), False if critical issues found.
        """
        missing_fields = [field for field in self.REQUIRED_FIELDS if field not in plant_data]

        if missing_fields:
            msg = f"Plant '{plant_data.get('common_name', 'Unknown')}' missing fields: {missing_fields}"
            if strict:
                logging.error(msg)
                return False
            else:
                logging.warning(msg)

        return True

    def delete_plant(self, plant_id: int) -> bool:
        """
        Deletes a plant from the dataset.

        Args:
            plant_id: ID of the plant to delete.

        Returns:
            True if deleted, False if not found.
        """
        initial_count = len(self.data["plants_info"])
        self.data["plants_info"] = [p for p in self.data["plants_info"] if p.get("id") != plant_id]

        if len(self.data["plants_info"]) < initial_count:
            logging.info("Deleted plant ID %d.", plant_id)
            return self.save_json()

        logging.warning("Plant ID %d not found for deletion.", plant_id)
        return False

    # Specialized Methods for Enhanced Fields

    def update_automation(self, plant_id: int, automation_data: dict[str, Any]) -> bool:
        """
        Updates the automation section for a plant.

        Args:
            plant_id: ID of the plant to update.
            automation_data: Dictionary with automation settings (watering_schedule, lighting_schedule, etc.).

        Returns:
            True if successful, False otherwise.
        """
        plant = self.get_plant_by_id(plant_id)
        if not plant:
            return False

        if "automation" not in plant:
            plant["automation"] = {}

        plant["automation"].update(automation_data)
        return self.save_json()

    def update_common_issues(self, plant_id: int, issues: list[dict[str, Any]]) -> bool:
        """
        Updates the common_issues section for a plant.

        Args:
            plant_id: ID of the plant to update.
            issues: List of issue dictionaries with problem, symptoms, causes, solution, prevention.

        Returns:
            True if successful, False otherwise.
        """
        plant = self.get_plant_by_id(plant_id)
        if not plant:
            return False

        plant["common_issues"] = issues
        return self.save_json()

    def add_companion_plant(self, plant_id: int, companion_data: dict[str, Any]) -> bool:
        """
        Adds a companion plant entry to a plant's companion_plants section.

        Args:
            plant_id: ID of the plant to update.
            companion_data: Dictionary with beneficial or plants_to_avoid information.

        Returns:
            True if successful, False otherwise.
        """
        plant = self.get_plant_by_id(plant_id)
        if not plant:
            return False

        if "companion_plants" not in plant:
            plant["companion_plants"] = {"beneficial": [], "plants_to_avoid": []}

        if "beneficial" in companion_data:
            plant["companion_plants"]["beneficial"].extend(companion_data["beneficial"])

        if "plants_to_avoid" in companion_data:
            plant["companion_plants"]["plants_to_avoid"].extend(companion_data["plants_to_avoid"])

        return self.save_json()

    def update_harvest_guide(self, plant_id: int, guide_data: dict[str, Any]) -> bool:
        """
        Updates the harvest_guide section for a plant.

        Args:
            plant_id: ID of the plant to update.
            guide_data: Dictionary with harvest indicators, timing, storage, processing.

        Returns:
            True if successful, False otherwise.
        """
        plant = self.get_plant_by_id(plant_id)
        if not plant:
            return False

        if "harvest_guide" not in plant:
            plant["harvest_guide"] = {}

        plant["harvest_guide"].update(guide_data)
        return self.save_json()

    # Search and Filter Methods

    def search_plants(self, **criteria) -> list[dict[str, Any]]:
        """
        Search plants by various criteria.

        Args:
            **criteria: Key-value pairs to match (e.g., species="Tomato", variety="Cherry")

        Returns:
            List of plants matching all criteria.
        """
        results = []
        for plant in self.data["plants_info"]:
            matches = all(plant.get(key, "").lower() == str(value).lower() for key, value in criteria.items())
            if matches:
                results.append(plant)

        return results

    def get_plants_by_difficulty(self, difficulty_level: str) -> list[dict[str, Any]]:
        """
        Filter plants by difficulty level.

        Args:
            difficulty_level: e.g., "Easy", "Medium", "Advanced"

        Returns:
            List of plants matching the difficulty level.
        """
        results = []
        target = difficulty_level.lower()

        for plant in self.data["plants_info"]:
            plant_difficulty = plant.get("yield_data", {}).get("difficulty_level", "").lower()
            if plant_difficulty == target:
                results.append(plant)

        return results

    def get_plants_requiring_automation(self) -> list[dict[str, Any]]:
        """
        Returns all plants that have automation configurations.

        Returns:
            List of plants with automation data.
        """
        return [plant for plant in self.data["plants_info"] if plant.get("automation")]

    def export_plant_summary(self, plant_id: int) -> dict[str, Any] | None:
        """
        Exports a simplified summary of a plant for API responses.

        Args:
            plant_id: ID of the plant.

        Returns:
            Simplified plant data dictionary or None if not found.
        """
        plant = self.get_plant_by_id(plant_id)
        if not plant:
            return None

        return {
            "id": plant.get("id"),
            "common_name": plant.get("common_name"),
            "species": plant.get("species"),
            "variety": plant.get("variety"),
            "difficulty_level": plant.get("yield_data", {}).get("difficulty_level", "unknown"),
            "harvest_frequency": plant.get("yield_data", {}).get("harvest_frequency", "unknown"),
            "automation_enabled": bool(plant.get("automation")),
            "companion_plants": plant.get("companion_plants", {}).get("beneficial", []),
        }
