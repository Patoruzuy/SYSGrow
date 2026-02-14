"""
Plant Symptoms & Treatments — Domain Data
==========================================
Single source of truth for the symptom→cause and symptom→treatment
knowledge used by :class:`PlantHealthMonitor` and
:class:`RuleBasedRecommendationProvider`.

All symptom keys are ``snake_case`` (e.g. ``"yellowing_leaves"``).
"""

from typing import Dict, List

# ---------------------------------------------------------------------------
# Symptom database
# ---------------------------------------------------------------------------
#   Maps a symptom key to:
#     - likely_causes:  ranked list of probable root causes
#     - environmental_factors:  sensor / environment axes to inspect
#
SYMPTOM_DATABASE: Dict[str, Dict[str, List[str]]] = {
    "yellowing_leaves": {
        "likely_causes": ["overwatering", "nitrogen_deficiency", "root_rot"],
        "environmental_factors": ["soil_moisture", "drainage", "nutrition"],
    },
    "brown_spots": {
        "likely_causes": ["fungal_infection", "bacterial_spot", "nutrient_burn"],
        "environmental_factors": ["humidity", "air_circulation", "nutrition"],
    },
    "wilting": {
        "likely_causes": ["underwatering", "root_damage", "heat_stress"],
        "environmental_factors": ["soil_moisture", "temperature", "humidity"],
    },
    "stunted_growth": {
        "likely_causes": ["poor_lighting", "nutrient_deficiency", "root_bound"],
        "environmental_factors": ["lux", "nutrition", "space"],
    },
    "leaf_curl": {
        "likely_causes": ["heat_stress", "pest_damage", "overwatering"],
        "environmental_factors": ["temperature", "humidity", "soil_moisture"],
    },
    "white_powdery_coating": {
        "likely_causes": ["powdery_mildew", "high_humidity"],
        "environmental_factors": ["humidity", "air_circulation", "temperature"],
    },
    "webbing_on_leaves": {
        "likely_causes": ["spider_mites", "low_humidity"],
        "environmental_factors": ["humidity", "temperature", "air_circulation"],
    },
    "holes_in_leaves": {
        "likely_causes": ["caterpillars", "beetles", "slugs"],
        "environmental_factors": ["pest_control", "cleanliness"],
    },
    "drooping_leaves": {
        "likely_causes": ["underwatering", "overwatering", "temperature_stress"],
        "environmental_factors": ["soil_moisture", "temperature", "root_health"],
    },
    "pale_leaves": {
        "likely_causes": ["iron_deficiency", "low_light", "nutrient_lockout"],
        "environmental_factors": ["nutrition", "lux", "ph"],
    },
    "crispy_leaf_edges": {
        "likely_causes": ["low_humidity", "salt_buildup", "underwatering"],
        "environmental_factors": ["humidity", "nutrition", "soil_moisture"],
    },
    "black_spots": {
        "likely_causes": ["fungal_disease", "overwatering", "poor_drainage"],
        "environmental_factors": ["humidity", "drainage", "air_circulation"],
    },
}

# ---------------------------------------------------------------------------
# Treatment map
# ---------------------------------------------------------------------------
#   Maps a symptom key to an ordered list of treatment actions (most
#   important first).
#
TREATMENT_MAP: Dict[str, List[str]] = {
    "yellowing_leaves": [
        "Check drainage and reduce watering if overwatered",
        "Apply nitrogen fertilizer if deficiency suspected",
        "Inspect roots for rot and trim if necessary",
        "Ensure proper light levels for photosynthesis",
    ],
    "brown_spots": [
        "Improve air circulation",
        "Reduce humidity if too high",
        "Apply fungicide if fungal infection suspected",
        "Isolate plant to prevent spread",
    ],
    "wilting": [
        "Check soil moisture and water if dry",
        "Reduce temperature if heat stress suspected",
        "Inspect roots for damage",
        "Provide shade during peak sun hours",
    ],
    "white_powdery_coating": [
        "Reduce humidity below 60%",
        "Improve air circulation with fans",
        "Apply fungicide for powdery mildew",
        "Remove and dispose of affected leaves",
    ],
    "webbing_on_leaves": [
        "Increase humidity to discourage spider mites",
        "Apply miticide or neem oil treatment",
        "Improve air circulation",
        "Regularly mist leaves with water",
    ],
    "stunted_growth": [
        "Increase light intensity or duration",
        "Check and adjust nutrient levels",
        "Repot if plant is root-bound",
        "Ensure temperature is within optimal range",
    ],
    "leaf_curl": [
        "Check for pest infestation",
        "Reduce temperature if heat stressed",
        "Adjust watering schedule",
        "Check for herbicide drift",
    ],
    "holes_in_leaves": [
        "Inspect for caterpillars and remove manually",
        "Apply organic pest control (BT spray)",
        "Set up slug traps if slugs suspected",
        "Improve garden cleanliness",
    ],
    "drooping_leaves": [
        "Check soil moisture - water if dry",
        "Reduce watering if soil is soggy",
        "Provide temperature stability",
        "Check for root health issues",
    ],
    "pale_leaves": [
        "Apply iron supplement or chelated micronutrients",
        "Increase light exposure",
        "Check and adjust pH levels",
        "Ensure balanced nutrient solution",
    ],
    "crispy_leaf_edges": [
        "Increase humidity with humidifier or misting",
        "Flush soil to remove salt buildup",
        "Increase watering frequency slightly",
        "Move away from heat sources",
    ],
    "black_spots": [
        "Remove affected leaves immediately",
        "Reduce watering frequency",
        "Improve drainage in container",
        "Apply copper-based fungicide",
    ],
}
