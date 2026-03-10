#!/usr/bin/env python3
"""
DECREPATED: Old implementation of SYSGrow Smart Agriculture Integration.
SYSGrow Smart Agriculture Integration Module
==========================================

This module demonstrates how to use the enhanced plants dataset
for automated IoT agriculture decisions and monitoring.

Features:
- Automated watering decisions based on plant requirements
- Environmental alerts and triggers
- Yield predictions and economic calculations
- Problem diagnosis from sensor data
- Harvest timing recommendations

Usage:
    from integrations.smart_agriculture import SmartAgricultureManager

    manager = SmartAgricultureManager()
    decisions = manager.get_watering_decisions(plant_id=2, current_moisture=65)
    alerts = manager.check_environmental_alerts(plant_id=2, temp=30, humidity=80)
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class SmartAgricultureManager:
    """
    Main manager class for smart agriculture automation using enhanced plant data
    """

    def __init__(self, plants_json_path: str = "plants_info.json"):
        self.plants_json_path = Path(plants_json_path)
        self.plants_data = self.load_plants_data()
        self.plant_lookup = {plant["id"]: plant for plant in self.plants_data["plants_info"]}

    def load_plants_data(self) -> dict:
        """Load plants data from JSON file"""
        try:
            with open(self.plants_json_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error(f"Plants data file not found: {self.plants_json_path}")
            return {"plants_info": []}

    def get_plant_data(self, plant_id: int) -> dict | None:
        """Get plant data by ID"""
        return self.plant_lookup.get(plant_id)

    def get_watering_decisions(
        self, plant_id: int, current_moisture: float, last_watered: datetime | None = None
    ) -> dict:
        """
        Determine watering decisions based on plant requirements and current conditions

        Args:
            plant_id: Plant ID from plants_info.json
            current_moisture: Current soil moisture percentage (0-100)
            last_watered: When the plant was last watered

        Returns:
            Dict with watering recommendations
        """
        plant = self.get_plant_data(plant_id)
        if not plant:
            return {"error": f"Plant ID {plant_id} not found"}

        # Get plant's sensor requirements
        sensor_reqs = plant.get("sensor_requirements", {})
        moisture_range = sensor_reqs.get("soil_moisture_range", {"min": 50, "max": 80})

        # Get automation settings
        automation = plant.get("automation", {})
        watering_schedule = automation.get("watering_schedule", {})

        trigger_moisture = watering_schedule.get("soil_moisture_trigger", 60)
        water_amount = watering_schedule.get("amount_ml_per_plant", 200)
        frequency_hours = watering_schedule.get("frequency_hours", 24)

        # Decision logic
        should_water = current_moisture <= trigger_moisture
        urgency = "normal"

        if current_moisture < moisture_range["min"]:
            urgency = "urgent"
            should_water = True
        elif current_moisture < trigger_moisture:
            urgency = "normal"
        elif current_moisture > moisture_range["max"]:
            should_water = False
            urgency = "hold"

        # Check timing if last watered is provided
        timing_ok = True
        if last_watered and should_water:
            hours_since_watering = (datetime.now() - last_watered).total_seconds() / 3600
            timing_ok = hours_since_watering >= frequency_hours

        return {
            "plant_id": plant_id,
            "plant_name": plant["common_name"],
            "should_water": should_water and timing_ok,
            "water_amount_ml": water_amount if should_water else 0,
            "urgency": urgency,
            "current_moisture": current_moisture,
            "target_range": moisture_range,
            "trigger_point": trigger_moisture,
            "timing_ok": timing_ok,
            "reasoning": self._get_watering_reasoning(current_moisture, moisture_range, trigger_moisture, urgency),
        }

    def check_environmental_alerts(
        self, plant_id: int, temperature: float, humidity: float, soil_temp: float | None = None
    ) -> list[dict]:
        """
        Check for environmental alerts based on plant thresholds

        Args:
            plant_id: Plant ID from plants_info.json
            temperature: Current air temperature (°C)
            humidity: Current humidity percentage
            soil_temp: Optional soil temperature (°C)

        Returns:
            List of alert dictionaries
        """
        plant = self.get_plant_data(plant_id)
        if not plant:
            return [{"error": f"Plant ID {plant_id} not found"}]

        alerts = []
        automation = plant.get("automation", {})
        thresholds = automation.get("alert_thresholds", {})

        # Temperature alerts
        temp_min = thresholds.get("temperature_min", 15)
        temp_max = thresholds.get("temperature_max", 30)

        if temperature < temp_min:
            alerts.append(
                {
                    "type": "temperature_low",
                    "severity": "warning",
                    "message": f"Temperature {temperature}°C is below minimum {temp_min}°C",
                    "recommendation": "Consider heating or moving to warmer location",
                    "current_value": temperature,
                    "threshold": temp_min,
                }
            )
        elif temperature > temp_max:
            alerts.append(
                {
                    "type": "temperature_high",
                    "severity": "warning",
                    "message": f"Temperature {temperature}°C is above maximum {temp_max}°C",
                    "recommendation": "Increase ventilation or provide cooling",
                    "current_value": temperature,
                    "threshold": temp_max,
                }
            )

        # Humidity alerts
        humidity_min = thresholds.get("humidity_min", 40)
        humidity_max = thresholds.get("humidity_max", 70)

        if humidity < humidity_min:
            alerts.append(
                {
                    "type": "humidity_low",
                    "severity": "warning",
                    "message": f"Humidity {humidity}% is below minimum {humidity_min}%",
                    "recommendation": "Increase humidity with humidifier or water trays",
                    "current_value": humidity,
                    "threshold": humidity_min,
                }
            )
        elif humidity > humidity_max:
            alerts.append(
                {
                    "type": "humidity_high",
                    "severity": "warning",
                    "message": f"Humidity {humidity}% is above maximum {humidity_max}%",
                    "recommendation": "Increase ventilation or use dehumidifier",
                    "current_value": humidity,
                    "threshold": humidity_max,
                }
            )

        # Soil temperature alerts (if provided)
        if soil_temp is not None:
            sensor_reqs = plant.get("sensor_requirements", {})
            soil_temp_range = sensor_reqs.get("soil_temperature_C", {"min": 18, "max": 25})

            if soil_temp < soil_temp_range["min"]:
                alerts.append(
                    {
                        "type": "soil_temperature_low",
                        "severity": "warning",
                        "message": f"Soil temperature {soil_temp}°C is below minimum {soil_temp_range['min']}°C",
                        "recommendation": "Consider soil heating mat or greenhouse",
                        "current_value": soil_temp,
                        "threshold": soil_temp_range["min"],
                    }
                )
            elif soil_temp > soil_temp_range["max"]:
                alerts.append(
                    {
                        "type": "soil_temperature_high",
                        "severity": "warning",
                        "message": f"Soil temperature {soil_temp}°C is above maximum {soil_temp_range['max']}°C",
                        "recommendation": "Provide shade or cooling",
                        "current_value": soil_temp,
                        "threshold": soil_temp_range["max"],
                    }
                )

        return alerts

    def diagnose_problems(self, plant_id: int, symptoms: list[str]) -> list[dict]:
        """
        Diagnose potential problems based on observed symptoms

        Args:
            plant_id: Plant ID from plants_info.json
            symptoms: List of observed symptoms

        Returns:
            List of potential problem matches with solutions
        """
        plant = self.get_plant_data(plant_id)
        if not plant:
            return [{"error": f"Plant ID {plant_id} not found"}]

        common_issues = plant.get("common_issues", [])
        matches = []

        for issue in common_issues:
            issue_symptoms = [s.lower() for s in issue.get("symptoms", [])]
            symptom_matches = 0

            for symptom in symptoms:
                for issue_symptom in issue_symptoms:
                    if symptom.lower() in issue_symptom or issue_symptom in symptom.lower():
                        symptom_matches += 1
                        break

            if symptom_matches > 0:
                confidence = (symptom_matches / len(symptoms)) * 100
                matches.append(
                    {
                        "problem": issue["problem"],
                        "confidence_percent": round(confidence, 1),
                        "symptoms": issue["symptoms"],
                        "causes": issue["causes"],
                        "solutions": issue["solutions"],
                        "prevention": issue.get("prevention", ""),
                        "matched_symptoms": symptom_matches,
                    }
                )

        # Sort by confidence
        matches.sort(key=lambda x: x["confidence_percent"], reverse=True)
        return matches

    def calculate_yield_projection(self, plant_id: int, plants_count: int, growth_stage: str = "vegetative") -> dict:
        """
        Calculate yield projection and economic value

        Args:
            plant_id: Plant ID from plants_info.json
            plants_count: Number of plants
            growth_stage: Current growth stage

        Returns:
            Dict with yield and economic projections
        """
        plant = self.get_plant_data(plant_id)
        if not plant:
            return {"error": f"Plant ID {plant_id} not found"}

        yield_data = plant.get("yield_data", {})
        yield_range = yield_data.get("expected_yield_per_plant", {"min": 100, "max": 300})
        market_value = yield_data.get("market_value_per_kg", 10.0)
        harvest_weeks = yield_data.get("harvest_period_weeks", 8)
        difficulty = yield_data.get("difficulty_level", "intermediate")

        # Calculate projections
        min_yield_total = (yield_range["min"] * plants_count) / 1000  # Convert to kg
        max_yield_total = (yield_range["max"] * plants_count) / 1000
        avg_yield_total = (min_yield_total + max_yield_total) / 2

        min_value = min_yield_total * market_value
        max_value = max_yield_total * market_value
        avg_value = avg_yield_total * market_value

        # Adjust based on difficulty (affects success rate)
        difficulty_multipliers = {"beginner": 0.9, "intermediate": 0.8, "expert": 0.7}
        success_rate = difficulty_multipliers.get(difficulty, 0.8)

        return {
            "plant_id": plant_id,
            "plant_name": plant["common_name"],
            "plants_count": plants_count,
            "harvest_weeks": harvest_weeks,
            "difficulty_level": difficulty,
            "success_rate_percent": success_rate * 100,
            "yield_projection_kg": {
                "minimum": round(min_yield_total, 2),
                "maximum": round(max_yield_total, 2),
                "average": round(avg_yield_total, 2),
                "realistic": round(avg_yield_total * success_rate, 2),
            },
            "economic_value": {
                "minimum": round(min_value, 2),
                "maximum": round(max_value, 2),
                "average": round(avg_value, 2),
                "realistic": round(avg_value * success_rate, 2),
                "currency": "USD",
            },
            "market_value_per_kg": market_value,
        }

    def get_harvest_recommendations(self, plant_id: int, days_since_planting: int) -> dict:
        """
        Get harvest timing recommendations based on plant data

        Args:
            plant_id: Plant ID from plants_info.json
            days_since_planting: Days since planting

        Returns:
            Dict with harvest recommendations
        """
        plant = self.get_plant_data(plant_id)
        if not plant:
            return {"error": f"Plant ID {plant_id} not found"}

        # Find harvest stage from growth stages
        growth_stages = plant.get("growth_stages", [])
        harvest_stage = None
        total_min_days = 0
        total_max_days = 0

        for stage in growth_stages:
            stage_min = stage["duration"]["min_days"]
            stage_max = stage["duration"]["max_days"]
            total_min_days += stage_min
            total_max_days += stage_max

            if stage["stage"].lower() == "harvest":
                harvest_stage = stage
                break

        if not harvest_stage:
            # Calculate based on total growth time
            harvest_min = total_min_days - harvest_stage["duration"]["min_days"] if harvest_stage else total_min_days
            harvest_max = total_max_days - harvest_stage["duration"]["max_days"] if harvest_stage else total_max_days
        else:
            harvest_min = total_min_days - harvest_stage["duration"]["max_days"]
            harvest_max = total_max_days - harvest_stage["duration"]["min_days"]

        # Get harvest guide
        harvest_guide = plant.get("harvest_guide", {})
        indicators = harvest_guide.get("indicators", [])
        storage_tips = harvest_guide.get("storage_tips", [])

        # Determine harvest readiness
        harvest_ready = harvest_min <= days_since_planting <= harvest_max
        days_to_harvest = max(0, harvest_min - days_since_planting)
        days_overdue = max(0, days_since_planting - harvest_max)

        status = "not_ready"
        if harvest_ready:
            status = "ready"
        elif days_overdue > 0:
            status = "overdue"

        return {
            "plant_id": plant_id,
            "plant_name": plant["common_name"],
            "days_since_planting": days_since_planting,
            "harvest_window": {"min_days": harvest_min, "max_days": harvest_max},
            "status": status,
            "harvest_ready": harvest_ready,
            "days_to_harvest": days_to_harvest,
            "days_overdue": days_overdue,
            "indicators": indicators,
            "storage_tips": storage_tips,
            "recommendation": self._get_harvest_recommendation(status, days_to_harvest, days_overdue),
        }

    def get_lighting_schedule(self, plant_id: int, growth_stage: str) -> dict:
        """
        Get optimal lighting schedule for current growth stage

        Args:
            plant_id: Plant ID from plants_info.json
            growth_stage: Current growth stage (seedling, vegetative, flowering, etc.)

        Returns:
            Dict with lighting recommendations
        """
        plant = self.get_plant_data(plant_id)
        if not plant:
            return {"error": f"Plant ID {plant_id} not found"}

        automation = plant.get("automation", {})
        lighting_schedule = automation.get("lighting_schedule", {})

        # Get stage-specific lighting or fall back to defaults
        stage_lighting = lighting_schedule.get(growth_stage.lower())
        if not stage_lighting:
            # Try to find a similar stage
            fallback_stages = {
                "germination": "seedling",
                "vegetative": "vegetative",
                "flowering": "flowering",
                "fruiting": "flowering",
                "harvest": "vegetative",
            }
            fallback_stage = fallback_stages.get(growth_stage.lower())
            stage_lighting = lighting_schedule.get(fallback_stage) if fallback_stage else {}

        if not stage_lighting:
            # Default lighting
            stage_lighting = {"hours": 14, "intensity": 80}

        # Get light spectrum requirements
        sensor_reqs = plant.get("sensor_requirements", {})
        light_spectrum = sensor_reqs.get("light_spectrum", {})

        return {
            "plant_id": plant_id,
            "plant_name": plant["common_name"],
            "growth_stage": growth_stage,
            "lighting_schedule": {
                "hours_per_day": stage_lighting.get("hours", 14),
                "intensity_percent": stage_lighting.get("intensity", 80),
                "spectrum": light_spectrum,
            },
            "recommendations": self._get_lighting_recommendations(stage_lighting, light_spectrum),
        }

    def _get_watering_reasoning(
        self, current_moisture: float, moisture_range: dict, trigger_point: float, urgency: str
    ) -> str:
        """Generate reasoning for watering decision"""
        if urgency == "urgent":
            return f"Soil moisture {current_moisture}% is critically low (below {moisture_range['min']}%)"
        elif urgency == "normal":
            return f"Soil moisture {current_moisture}% is at trigger point ({trigger_point}%)"
        elif urgency == "hold":
            return f"Soil moisture {current_moisture}% is too high (above {moisture_range['max']}%)"
        else:
            return f"Soil moisture {current_moisture}% is within optimal range"

    def _get_harvest_recommendation(self, status: str, days_to_harvest: int, days_overdue: int) -> str:
        """Generate harvest recommendation text"""
        recommendations = {
            "ready": "Plant is ready for harvest! Check indicators and harvest soon for best quality.",
            "not_ready": f"Plant needs {days_to_harvest} more days to reach harvest window.",
            "overdue": f"Plant is {days_overdue} days past optimal harvest time. Quality may be declining.",
        }
        return recommendations.get(status, "Unable to determine harvest status.")

    def _get_lighting_recommendations(self, stage_lighting: dict, light_spectrum: dict) -> list[str]:
        """Generate lighting recommendations"""
        recommendations = []

        hours = stage_lighting.get("hours", 14)
        intensity = stage_lighting.get("intensity", 80)

        if hours >= 18:
            recommendations.append("Long photoperiod - ensure plants don't get light stress")
        elif hours <= 10:
            recommendations.append("Short photoperiod - may slow growth in some plants")

        if intensity >= 90:
            recommendations.append("High intensity - monitor for light burn on leaves")
        elif intensity <= 50:
            recommendations.append("Low intensity - may cause stretching in some plants")

        if light_spectrum:
            blue_percent = light_spectrum.get("blue_percent", 25)
            red_percent = light_spectrum.get("red_percent", 45)

            if blue_percent > 30:
                recommendations.append("High blue spectrum - good for compact growth")
            if red_percent > 50:
                recommendations.append("High red spectrum - promotes flowering and fruiting")

        return recommendations


# Example usage and testing
def demo_smart_agriculture():
    """Demonstrate the Smart Agriculture Manager capabilities"""
    manager = SmartAgricultureManager()

    # Test watering decisions
    manager.get_watering_decisions(plant_id=2, current_moisture=65)

    # Test environmental alerts
    alerts = manager.check_environmental_alerts(plant_id=2, temperature=35, humidity=85)
    for _alert in alerts:
        pass

    # Test problem diagnosis
    problems = manager.diagnose_problems(plant_id=2, symptoms=["yellowing leaves", "brown spots"])
    for _problem in problems:
        pass

    # Test yield projection
    manager.calculate_yield_projection(plant_id=2, plants_count=10)

    # Test harvest recommendations
    manager.get_harvest_recommendations(plant_id=2, days_since_planting=75)


if __name__ == "__main__":
    demo_smart_agriculture()
