"""
UnitRuntimeFactory - Factory for creating UnitRuntime instances
=================================================================

Extracts the responsibility of creating UnitRuntime domain objects from GrowthService.
Follows the Factory pattern for clean separation of concerns.

Responsibilities:
- Create UnitRuntime instances from database data
- Load plants from repository
- Create PlantProfile domain objects
- Wire up service dependencies

Architecture:
    GrowthService -> UnitRuntimeFactory -> (UnitRuntime, PlantProfile)

Author: Architecture Refactoring Team
Date: December 2025
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from app.domain.plant_profile import PlantProfile
from app.domain.unit_runtime import UnitRuntime, UnitSettings

if TYPE_CHECKING:
    from infrastructure.database.repositories.growth import GrowthRepository
    from app.services.application.threshold_service import ThresholdService
    from app.services.application.plant_service import PlantViewService
    from app.utils.plant_json_handler import PlantJsonHandler

logger = logging.getLogger(__name__)


class UnitRuntimeFactory:
    """
    Factory for creating UnitRuntime instances from database data.

    Separates runtime creation logic from GrowthService, making it:
    - Testable in isolation
    - Reusable across contexts
    - Single responsibility (construction only)

    Example:
        factory = UnitRuntimeFactory(
            growth_repo=growth_repo,
            plant_handler=plant_handler,
            threshold_service=threshold_service
        )

        runtime = factory.create_runtime(unit_data)
    """

    def __init__(
        self,
        plant_handler: 'PlantJsonHandler',
        threshold_service: Optional['ThresholdService'] = None,
        plant_service: Optional['PlantViewService'] = None
    ):
        """
        Initialize the factory with required dependencies.

        Args:
            plant_handler: Handler for plant growth stage definitions
            threshold_service: Optional service for unified threshold management
            plant_service: Optional PlantService for creating PlantProfile instances.
                          If provided, factory delegates to PlantService.create_plant_profile().
                          If not provided, factory uses its own _create_plant_profile().
        """
        self.plant_handler = plant_handler
        self.threshold_service = threshold_service
        self._plant_service = plant_service

        logger.debug("UnitRuntimeFactory initialized")

    def create_runtime(
        self,
        unit_data: Dict[str, Any],
    ) -> UnitRuntime:
        """
        Create a UnitRuntime instance from database data.

        Creates the runtime WITHOUT loading plants. Plant loading is now the
        responsibility of PlantService, called by GrowthService after runtime creation.
        
        This separation ensures:
        - PlantService is the single source of truth for plant data
        - UnitRuntime is a pure domain model without DB dependencies
        - Plants can be reloaded independently of runtime lifecycle

        Args:
            unit_data: Unit dictionary from database (must contain unit_id, name, etc.)

        Returns:
            UnitRuntime instance (plants NOT loaded - caller must load via PlantService)

        Raises:
            KeyError: If unit_data is missing required fields
            Exception: If construction fails
        """
        try:
            # Validate required fields
            unit_id = unit_data['unit_id']
            unit_name = unit_data['name']

            logger.debug(f"Creating runtime for unit {unit_id} ({unit_name})")

            # Extract settings from unit data
            settings = UnitSettings.from_dict(unit_data)

            # Create runtime without plants
            # Plants are loaded by PlantService.load_plants_for_unit() after creation
            runtime = UnitRuntime(
                unit_id=unit_id,
                unit_name=unit_name,
                location=unit_data.get('location', 'Indoor'),
                user_id=unit_data.get('user_id', 1),
                settings=settings,
                custom_image=unit_data.get('custom_image'),
                threshold_service=self.threshold_service,
            )

            logger.info(
                f"Created runtime for unit {unit_id} ({unit_name}) "
                f"(plants to be loaded by PlantService)"
            )

            return runtime

        except KeyError as e:
            logger.error(f"Missing required field in unit_data: {e}")
            raise
        except Exception as e:
            logger.error(f"Error creating runtime for unit: {e}", exc_info=True)
            raise

    def create_plant_profile(self, **kwargs: Any) -> PlantProfile:
        """
        Create PlantProfile instances via PlantService.
        
        PlantService is the single source of truth for PlantProfile creation.
        This factory delegates all plant creation to PlantService.
        
        Args:
            **kwargs: Plant attributes passed to PlantService.create_plant_profile()
            
        Returns:
            PlantProfile instance
            
        Raises:
            RuntimeError: If PlantService is not wired (required dependency)
        """
        if self._plant_service is None:
            raise RuntimeError(
                "PlantService is required but not provided. "
                "UnitRuntimeFactory must be initialized with plant_service parameter."
            )
        return self._plant_service.create_plant_profile(**kwargs)
