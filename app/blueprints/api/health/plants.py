"""
Plant Health Endpoints
======================

Health monitoring endpoints for plants including:
- Health summaries across units
- Per-plant health scores
- Plants needing attention
"""
import logging
from flask import Blueprint, request

from app.enums.common import PlantHealthStatus

from app.blueprints.api._common import (
    success as _success,
    fail as _fail,
    get_growth_service as _growth_service,
    get_plant_service as _plant_service,
    get_container as _container,
)

logger = logging.getLogger('health_api')


def register_plant_routes(health_api: Blueprint):
    """Register plant health routes on the blueprint."""

    @health_api.get('/plants/summary')
    def get_plants_health_summary():
        """
        Get health summary for all plants across all units.
        
        Returns:
            {
                "plants": [
                    {
                        "plant_id": 1,
                        "plant_name": "Tomato 1",
                        "unit_id": 1,
                        "unit_name": "Unit 1",
                        "plant_species": "Tomato",
                        "current_stage": "Vegetative",
                        "current_health_status": "healthy",
                        "last_observation_date": "2025-12-07",
                        "issues": []
                    }
                ],
                "count": 5
            }
        """
        try:
            growth_service = _growth_service()
            plant_service = _plant_service()
            
            units = growth_service.list_units()
            all_plants_health = []
            
            for unit in units:
                unit_id = unit.get('unit_id')
                unit_name = unit.get('name')
                # list_plants returns PlantProfile objects
                plants = plant_service.list_plants(unit_id)
                
                for plant in plants:
                    # PlantProfile is a dataclass - use attribute access
                    health_data = {
                        "plant_id": plant.plant_id,
                        "plant_name": plant.plant_name,
                        "unit_id": unit_id,
                        "unit_name": unit_name,
                        "plant_species": plant.plant_type,
                        "current_stage": plant.current_stage,
                        "current_health_status": getattr(plant, 'health_status', 'healthy'),
                        "last_observation_date": getattr(plant, 'last_health_check', None),
                        "issues": []
                    }
                    all_plants_health.append(health_data)
                    
            return _success({
                "plants": all_plants_health,
                "count": len(all_plants_health)
            })
            
        except Exception as e:
            logger.exception(f"Error getting plants health summary: {e}")
            return _fail("Failed to get plants health summary", 500)

    @health_api.get('/plants/symptoms')
    def get_health_symptoms():
        """
        Get list of available plant health symptoms for recording observations.
        
        Returns:
            {
                "symptoms": [
                    "yellowing_leaves",
                    "wilting",
                    "brown_spots",
                    ...
                ]
            }
        """
        symptoms = [
            "yellowing_leaves",
            "wilting",
            "brown_spots",
            "curling_leaves",
            "stunted_growth",
            "leaf_drop",
            "discoloration",
            "mold",
            "pests",
            "root_rot"
        ]
        return _success({"symptoms": symptoms})

    @health_api.get('/plants/statuses')
    def get_health_statuses():
        """
        Get list of available plant health statuses.

        Returns:
            {
                "statuses": [
                    "healthy",
                    "stressed",
                    "diseased",
                    "pest_infestation",
                    "nutrient_deficiency",
                    "dying"
                ]
            }
        """
        statuses = [status.value for status in PlantHealthStatus]
        return _success({"statuses": statuses})

    @health_api.get('/plants/<int:plant_id>/score')
    def get_plant_health_score(plant_id: int):
        """
        Get comprehensive health score for a single plant.

        Combines plant-specific metrics (soil moisture, pH, EC) with
        unit-level environmental data (temperature, humidity, VPD).

        Returns:
            {
                "plant_id": 1,
                "overall_score": 85,
                "component_scores": {
                    "soil_moisture": 90,
                    "ph": 85,
                    "ec": 80,
                    "temperature": 88,
                    "humidity": 82,
                    "vpd": 85
                },
                "health_status": "healthy",
                "disease_risk": "low",
                "nutrient_status": "optimal",
                "recommendations": ["Maintain current watering schedule"],
                "urgent_actions": [],
                "data_completeness": 0.9,
                "timestamp": "2026-01-24T10:30:00Z"
            }
        """
        try:
            container = _container()
            scorer = getattr(container, "plant_health_scorer")

            if not scorer:
                return _fail("Plant health scorer not available", 503)

            score = scorer.score_plant_health(plant_id)
            return _success(score.to_dict())

        except Exception as e:
            logger.exception(f"Error getting health score for plant {plant_id}: {e}")
            return _fail(f"Failed to get health score: {str(e)}", 500)

    @health_api.get('/units/<int:unit_id>/plants/scores')
    def get_unit_plants_health_scores(unit_id: int):
        """
        Get health scores for all plants in a unit.

        Returns:
            {
                "unit_id": 1,
                "plants": [
                    {
                        "plant_id": 1,
                        "overall_score": 85,
                        "health_status": "healthy",
                        ...
                    }
                ],
                "count": 3,
                "average_score": 78.5
            }
        """
        try:
            container = _container()
            scorer = container.get("plant_health_scorer")

            if not scorer:
                return _fail("Plant health scorer not available", 503)

            scores = scorer.score_plants_in_unit(unit_id)
            scores_data = [s.to_dict() for s in scores]

            avg_score = 0.0
            if scores:
                avg_score = sum(s.overall_score for s in scores) / len(scores)

            return _success({
                "unit_id": unit_id,
                "plants": scores_data,
                "count": len(scores),
                "average_score": round(avg_score, 1),
            })

        except Exception as e:
            logger.exception(f"Error getting health scores for unit {unit_id}: {e}")
            return _fail(f"Failed to get health scores: {str(e)}", 500)

    @health_api.get('/plants/attention')
    def get_plants_needing_attention():
        """
        Get plants needing attention across all units.

        Query params:
            - unit_id: Optional filter by unit
            - threshold: Score threshold (default 65.0)

        Returns:
            {
                "plants": [
                    {
                        "plant_id": 1,
                        "unit_id": 1,
                        "overall_score": 45,
                        "health_status": "stressed",
                        "urgent_actions": ["Water immediately"],
                        "top_issues": ["Low Soil Moisture", "High Temperature"]
                    }
                ],
                "count": 2
            }
        """
        try:
            container = _container()
            scorer = container.get("plant_health_scorer")

            if not scorer:
                return _fail("Plant health scorer not available", 503)

            # Parse query params
            unit_id = request.args.get('unit_id', type=int)
            threshold = request.args.get('threshold', default=65.0, type=float)

            plants = scorer.get_plants_needing_attention(
                unit_id=unit_id,
                score_threshold=threshold,
            )

            return _success({
                "plants": plants,
                "count": len(plants),
                "threshold": threshold,
            })

        except Exception as e:
            logger.exception(f"Error getting plants needing attention: {e}")
            return _fail(f"Failed to get plants needing attention: {str(e)}", 500)
