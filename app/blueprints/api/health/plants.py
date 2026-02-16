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

from app.blueprints.api._common import (
    fail as _fail,
    get_container as _container,
    get_growth_service as _growth_service,
    get_plant_service as _plant_service,
    success as _success,
)
from app.enums.common import PlantHealthStatus

logger = logging.getLogger("health_api")


def register_plant_routes(health_api: Blueprint):
    """Register plant health routes on the blueprint."""

    @health_api.get("/plants/summary")
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
                unit_id = unit.get("unit_id")
                unit_name = unit.get("name")
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
                        "current_health_status": getattr(plant, "health_status", "healthy"),
                        "last_observation_date": getattr(plant, "last_health_check", None),
                        "issues": [],
                    }
                    all_plants_health.append(health_data)

            return _success({"plants": all_plants_health, "count": len(all_plants_health)})

        except Exception as e:
            logger.exception(f"Error getting plants health summary: {e}")
            return _fail("Failed to get plants health summary", 500)

    @health_api.get("/plants/symptoms")
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
            "root_rot",
        ]
        return _success({"symptoms": symptoms})

    @health_api.get("/plants/statuses")
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

    @health_api.get("/plants/<int:plant_id>/score")
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
            scorer = container.plant_health_scorer

            if not scorer:
                return _fail("Plant health scorer not available", 503)

            score = scorer.score_plant_health(plant_id)
            return _success(score.to_dict())

        except Exception as e:
            logger.exception(f"Error getting health score for plant {plant_id}: {e}")
            return _fail(f"Failed to get health score: {e!s}", 500)

    @health_api.get("/units/<int:unit_id>/plants/scores")
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

            return _success(
                {
                    "unit_id": unit_id,
                    "plants": scores_data,
                    "count": len(scores),
                    "average_score": round(avg_score, 1),
                }
            )

        except Exception as e:
            logger.exception(f"Error getting health scores for unit {unit_id}: {e}")
            return _fail(f"Failed to get health scores: {e!s}", 500)

    @health_api.get("/plants/attention")
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
            unit_id = request.args.get("unit_id", type=int)
            threshold = request.args.get("threshold", default=65.0, type=float)

            plants = scorer.get_plants_needing_attention(
                unit_id=unit_id,
                score_threshold=threshold,
            )

            return _success(
                {
                    "plants": plants,
                    "count": len(plants),
                    "threshold": threshold,
                }
            )

        except Exception as e:
            logger.exception(f"Error getting plants needing attention: {e}")
            return _fail(f"Failed to get plants needing attention: {e!s}", 500)

    @health_api.post("/plants/<int:plant_id>/observe")
    def record_health_observation(plant_id: int):
        """
        Record a health observation for a plant.

        This endpoint allows users to report plant health status,
        which feeds ML model training data.

        Request body:
            {
                "health_status": "healthy" | "stressed" | "critical" | "diseased",
                "symptoms": ["yellowing_leaves", "wilting"],  # optional
                "severity_level": 1-5,  # optional, default 1
                "disease_type": "fungal",  # optional
                "affected_parts": ["leaves", "stem"],  # optional
                "environmental_factors": {"temperature": 28, "humidity": 75},  # optional
                "treatment_applied": "Applied fungicide",  # optional
                "notes": "Noticed spots on lower leaves",  # optional
                "image_path": "/uploads/plant_1_obs.jpg"  # optional
            }

        Returns:
            {
                "entry_id": 123,
                "plant_id": 1,
                "health_status": "stressed",
                "message": "Health observation recorded successfully"
            }
        """
        try:
            container = _container()
            journal_service = container.get("plant_journal_service")
            plant_service = _plant_service()

            if not journal_service:
                return _fail("Plant journal service not available", 503)

            # Get request data
            data = request.get_json()
            if not data:
                return _fail("Request body required", 400)

            # Validate required field
            health_status = data.get("health_status")
            if not health_status:
                return _fail("health_status is required", 400)

            valid_statuses = ["healthy", "stressed", "critical", "diseased", "recovering"]
            if health_status not in valid_statuses:
                return _fail(f"Invalid health_status. Must be one of: {', '.join(valid_statuses)}", 400)

            # Get plant info for context
            plant_info = plant_service.get_plant(plant_id)
            if not plant_info:
                return _fail(f"Plant {plant_id} not found", 404)

            # Extract optional fields
            symptoms = data.get("symptoms", [])
            severity_level = data.get("severity_level", 1)
            disease_type = data.get("disease_type")
            affected_parts = data.get("affected_parts", [])
            environmental_factors = data.get("environmental_factors", {})
            treatment_applied = data.get("treatment_applied")
            notes = data.get("notes", "")
            image_path = data.get("image_path")
            observation_date = data.get("observation_date")  # ISO format

            # Validate severity level
            if not isinstance(severity_level, int) or severity_level < 1 or severity_level > 5:
                severity_level = 1

            # Record the observation
            entry_id = journal_service.record_health_observation(
                plant_id=plant_id,
                health_status=health_status,
                symptoms=symptoms,
                severity_level=severity_level,
                unit_id=getattr(plant_info, "unit_id", None),
                disease_type=disease_type,
                affected_parts=affected_parts,
                environmental_factors=environmental_factors,
                treatment_applied=treatment_applied,
                plant_type=getattr(plant_info, "plant_type", None),
                growth_stage=getattr(plant_info, "current_stage", None),
                notes=notes,
                image_path=image_path,
                user_id=None,  # TODO: Get from auth when available
                observation_date=observation_date,
            )

            if not entry_id:
                return _fail("Failed to record health observation", 500)

            return _success(
                {
                    "entry_id": entry_id,
                    "plant_id": plant_id,
                    "health_status": health_status,
                    "message": "Health observation recorded successfully",
                }
            ), 201

        except Exception as e:
            logger.exception(f"Error recording health observation for plant {plant_id}: {e}")
            return _fail(f"Failed to record health observation: {e!s}", 500)

    @health_api.get("/plants/<int:plant_id>/observations")
    def get_plant_observations(plant_id: int):
        """
        Get health observations for a specific plant.

        Query params:
            - days: Number of days to look back (default 30)
            - limit: Max number of entries (default 50)
            - health_status: Filter by status (optional)

        Returns:
            {
                "observations": [
                    {
                        "entry_id": 1,
                        "health_status": "stressed",
                        "symptoms": ["yellowing_leaves"],
                        "severity_level": 2,
                        "created_at": "2025-01-20T10:30:00"
                    }
                ],
                "count": 5
            }
        """
        try:
            container = _container()
            journal_service = container.get("plant_journal_service")

            if not journal_service:
                return _fail("Plant journal service not available", 503)

            # Parse query params
            days = request.args.get("days", default=30, type=int)
            limit = request.args.get("limit", default=50, type=int)
            health_status = request.args.get("health_status")

            # Get observations
            entries = journal_service.get_health_timeline(
                plant_id=plant_id,
                days=days,
            )

            # Filter by health_status if provided
            if health_status:
                entries = [e for e in entries if e.get("health_status") == health_status]

            # Limit results
            entries = entries[:limit]

            return _success(
                {
                    "observations": entries,
                    "count": len(entries),
                    "plant_id": plant_id,
                }
            )

        except Exception as e:
            logger.exception(f"Error getting observations for plant {plant_id}: {e}")
            return _fail(f"Failed to get plant observations: {e!s}", 500)
