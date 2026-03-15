from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

from app.config import AppConfig
from app.services.ai.environmental_health_scorer import EnvironmentalLeafHealthScorer
from app.services.ai.plant_health_scorer import PlantHealthScorer
from app.services.application.notifications_service import NotificationsService
from app.services.container_builder import ContainerBuilder
from infrastructure.database.repositories.notifications import NotificationRepository
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from infrastructure.database.repositories.settings import SettingsRepository
from infrastructure.database.repositories.growth import GrowthRepository
from infrastructure.database.repositories.camera import CameraRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.ai import AIHealthDataRepository, AITrainingDataRepository
from infrastructure.database.repositories.plant_journal import PlantJournalRepository
from infrastructure.logging.audit import AuditLogger
from app.services.application.activity_logger import ActivityLogger
from app.services.application.alert_service import AlertService
from app.hardware.mqtt.mqtt_broker_wrapper import MQTTClientWrapper
from app.services.hardware.camera_service import CameraService
from app.utils.event_bus import EventBus
from app.workers.unified_scheduler import UnifiedScheduler
from app.utils.plant_json_handler import PlantJsonHandler
from app.services.application.auth_service import UserAuthManager
from app.services.application.growth_service import GrowthService
from app.services.application.device_health_service import DeviceHealthService
from app.services.application.device_coordinator import DeviceCoordinator
from app.services.application.zigbee_management_service import ZigbeeManagementService
from app.services.application.analytics_service import AnalyticsService
from app.services.application.settings_service import SettingsService
from app.services.application.plant_service import PlantViewService
from app.services.application.harvest_service import PlantHarvestService
from app.services.application.plant_journal_service import PlantJournalService
from app.services.application.irrigation_workflow_service import IrrigationWorkflowService
from app.services.application.manual_irrigation_service import ManualIrrigationService
from app.services.application.plant_irrigation_model_service import PlantIrrigationModelService
from app.services.application.threshold_service import ThresholdService
from app.services.utilities.system_health_service import SystemHealthService
from app.services.utilities.anomaly_detection_service import AnomalyDetectionService
from app.services.hardware import SensorManagementService, ActuatorManagementService
from app.services.hardware.mqtt_sensor_service import MQTTSensorService
from app.utils.emitters import EmitterService
from app.hardware.sensors.processors import IDataProcessor
from app.services.ai import (
    ModelRegistry,
    DiseasePredictor,
    PlantHealthMonitor,
    PlantGrowthPredictor,
    ClimateOptimizer,
    MLTrainerService,
    ModelDriftDetectorService,
    ABTestingService,
    AutomatedRetrainingService,
)


logger = logging.getLogger(__name__)

@dataclass
class ServiceContainer:
    """Aggregate and manage core backend services."""

    config: AppConfig
    database: SQLiteDatabaseHandler
    settings_repo: SettingsRepository
    growth_repo: GrowthRepository
    device_repo: DeviceRepository
    analytics_repo: AnalyticsRepository
    notification_repo: NotificationRepository
    ai_health_repo: AIHealthDataRepository
    training_data_repo: AITrainingDataRepository
    plant_journal_repo: PlantJournalRepository
    audit_logger: AuditLogger
    activity_logger: ActivityLogger
    alert_service: AlertService
    plant_catalog: PlantJsonHandler
    auth_manager: UserAuthManager
    threshold_service: ThresholdService
    growth_service: GrowthService
    device_health_service: DeviceHealthService
    device_coordinator: DeviceCoordinator
    analytics_service: AnalyticsService
    notifications_service: NotificationsService
    settings_service: SettingsService
    plant_service: PlantViewService
    manual_irrigation_service: ManualIrrigationService
    plant_irrigation_model_service: PlantIrrigationModelService
    harvest_service: PlantHarvestService
    plant_journal_service: PlantJournalService
    irrigation_workflow_service: IrrigationWorkflowService
    scheduler: UnifiedScheduler
    camera_service: CameraService
    mqtt_client: Optional[MQTTClientWrapper]
    zigbee_service: Optional[ZigbeeManagementService]
    # Health monitoring services
    anomaly_detection_service: AnomalyDetectionService
    system_health_service: SystemHealthService  # Now handles both sensor and infrastructure health
    # Hardware management services (singleton, memory-first)
    sensor_management_service: SensorManagementService
    actuator_management_service: ActuatorManagementService
    mqtt_sensor_service: Optional[MQTTSensorService]
    # Shared utilities
    emitter_service: EmitterService
    sensor_processor: IDataProcessor
    # AI Services
    model_registry: ModelRegistry
    disease_predictor: DiseasePredictor
    plant_health_monitor: PlantHealthMonitor
    environmental_health_scorer: EnvironmentalLeafHealthScorer
    plant_health_scorer: PlantHealthScorer
    climate_optimizer: ClimateOptimizer
    growth_predictor: PlantGrowthPredictor
    # Phase 2 AI Services
    ml_trainer: MLTrainerService
    drift_detector: ModelDriftDetectorService
    continuous_monitor: Optional[object]  # ContinuousMonitoringService - avoiding import cycle
    ab_testing: ABTestingService
    automated_retraining: Optional[AutomatedRetrainingService]
    personalized_learning: Optional[object]  # PersonalizedLearningService - avoiding import cycle
    training_data_collector: Optional[object]  # TrainingDataCollector - avoiding import cycle

    @classmethod
    def build(cls, config: AppConfig, *, start_coordinator: bool = False) -> "ServiceContainer":
        """Construct the service container with all dependencies.

        Args:
            config: Application configuration
            start_coordinator: Whether to start the DeviceCoordinator event loop
        """
        logger.info("Building ServiceContainer using ContainerBuilder...")
        builder = ContainerBuilder(config)
        components = builder.build(start_coordinator=start_coordinator)
        container = cls(**components)

        # Initialize unified scheduler after the full container exists (tasks need real services).
        from app.workers.scheduled_tasks import configure_scheduler

        try:
            configure_scheduler(container.scheduler, container)
            logger.info("✓ UnifiedScheduler initialized and started")
        except Exception as e:
            raise RuntimeError("Failed to initialize UnifiedScheduler") from e

        logger.info("ServiceContainer built successfully.")
        return container

    def shutdown(self) -> None:
        """Release external resources before process exit."""
        # Log system shutdown
        try:
            self.activity_logger.log_activity(
                activity_type=ActivityLogger.SYSTEM_SHUTDOWN,
                description="Smart Agriculture System shutting down",
                severity=ActivityLogger.INFO
            )
        except Exception as e:
            logger.warning(f"Failed to log shutdown activity: {e}")
        
        # Stop device coordinator event subscriptions
        self.device_coordinator.stop()

        # Stop unified scheduler
        try:
            self.scheduler.shutdown()
            logger.info("✓ UnifiedScheduler stopped")
        except Exception as e:
            logger.warning(f"Failed to stop UnifiedScheduler: {e}")
        
        # Stop continuous monitoring if enabled
        if self.continuous_monitor is not None:
            try:
                self.continuous_monitor.stop_monitoring()
                logger.info("✓ Continuous monitoring stopped")
            except Exception as e:
                logger.warning(f"Failed to stop continuous monitoring: {e}")
        
        # Shutdown health monitoring
        self.system_health_service.shutdown()
        
        # Stop MQTT sensor service
        if self.mqtt_sensor_service is not None:
            try:
                self.mqtt_sensor_service.shutdown()
                logger.info("✓ MQTTSensorService stopped")
            except Exception as e:
                logger.warning(f"Failed to stop MQTTSensorService: {e}")
        
        # Stop all unit runtimes (includes per-unit hardware managers and actuator managers)
        self.growth_service.shutdown()

        # Then close connections
        self.database.close_db()
        if self.mqtt_client is not None:
            self.mqtt_client.disconnect()
        logger.info("ServiceContainer shutdown complete.")
