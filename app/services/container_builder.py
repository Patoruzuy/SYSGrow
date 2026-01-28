"""
Container Builder
=================

Extracts service container construction logic from ServiceContainer.build().

This builder separates concerns and makes dependency construction testable and maintainable.
Each build_*() method focuses on one subsystem, making it easier to understand and modify.

Architecture:
- ContainerBuilder: Orchestrates the construction of all services
- Each build_*() method: Constructs a specific subsystem
- ServiceContainer.build(): Delegates to ContainerBuilder.build()

Author: SYSGrow Team
Date: December 2025
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Dict, Any

from app.config import AppConfig
from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
from infrastructure.database.repositories.settings import SettingsRepository
from infrastructure.database.repositories.growth import GrowthRepository
from infrastructure.database.repositories.units import UnitRepository
from infrastructure.database.repositories.plants import PlantRepository
from infrastructure.database.repositories.camera import CameraRepository
from infrastructure.database.repositories.devices import DeviceRepository
from infrastructure.database.repositories.analytics import AnalyticsRepository
from infrastructure.database.repositories.ai import AIHealthDataRepository, AITrainingDataRepository
from infrastructure.database.repositories.plant_journal import PlantJournalRepository
from infrastructure.database.repositories.alerts import AlertRepository
from infrastructure.database.repositories.activity_log import ActivityRepository
from infrastructure.database.repositories.notifications import NotificationRepository
from infrastructure.database.repositories.irrigation_workflow import IrrigationWorkflowRepository
from infrastructure.database.repositories.irrigation_ml import IrrigationMLRepository
from infrastructure.database.repositories.schedules import ScheduleRepository
from infrastructure.logging.audit import AuditLogger
from app.services.application.activity_logger import ActivityLogger
from app.services.application.alert_service import AlertService
from app.hardware.mqtt.mqtt_broker_wrapper import MQTTClientWrapper
from app.services.hardware.camera_service import CameraService
from app.utils.event_bus import EventBus
from app.workers.unified_scheduler import UnifiedScheduler, get_scheduler
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
from app.services.application.threshold_service import ThresholdService
from app.services.application.notifications_service import NotificationsService
from app.services.application.irrigation_workflow_service import IrrigationWorkflowService
from app.services.application.manual_irrigation_service import ManualIrrigationService
from app.services.application.plant_irrigation_model_service import PlantIrrigationModelService
from app.services.utilities.system_health_service import SystemHealthService
from app.services.utilities.anomaly_detection_service import AnomalyDetectionService
from app.services.utilities.email_service import EmailService
from app.services.hardware import SensorManagementService, ActuatorManagementService
from app.services.hardware.mqtt_sensor_service import MQTTSensorService
from app.services.hardware.pump_calibration import PumpCalibrationService
from app.domain.irrigation_calculator import IrrigationCalculator
from app.utils.emitters import EmitterService
from app.hardware.sensors.processors import (
    IDataProcessor,
    ValidationProcessor,
    CalibrationProcessor,
    TransformationProcessor,
    EnrichmentProcessor,
    CompositeProcessor,
    PriorityProcessor
)
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
    FeatureEngineer,
    EnvironmentalFeatureExtractor,
    EnvironmentalLeafHealthScorer,
    PlantHealthScorer,
    PlantHealthFeatureExtractor,
)


logger = logging.getLogger(__name__)


@dataclass
class InfrastructureComponents:
    """Infrastructure layer components (database, repos, logging)."""
    database: SQLiteDatabaseHandler
    settings_repo: SettingsRepository
    growth_repo: GrowthRepository  # Compatibility facade - will be removed after migration
    unit_repo: UnitRepository  # New: Unit operations for GrowthService
    plant_repo: PlantRepository  # New: Plant operations for PlantViewService
    device_repo: DeviceRepository
    analytics_repo: AnalyticsRepository
    ai_health_repo: AIHealthDataRepository
    training_data_repo: AITrainingDataRepository
    plant_journal_repo: PlantJournalRepository
    camera_repo: CameraRepository
    notification_repo: NotificationRepository
    irrigation_workflow_repo: IrrigationWorkflowRepository
    irrigation_ml_repo: Optional[IrrigationMLRepository]
    schedule_repo: ScheduleRepository
    audit_logger: AuditLogger
    activity_logger: ActivityLogger
    alert_service: AlertService
    notifications_service: NotificationsService
    irrigation_workflow_service: IrrigationWorkflowService


@dataclass
class MQTTComponents:
    """MQTT and Zigbee components."""
    mqtt_client: Optional[MQTTClientWrapper]
    zigbee_service: Optional[ZigbeeManagementService]


@dataclass
class SharedUtilities:
    """Shared utility services (emitters, processors, event bus)."""
    emitter_service: EmitterService
    sensor_processor: IDataProcessor
    event_bus: EventBus


@dataclass
class AIComponents:
    """AI and ML service components."""
    model_registry: ModelRegistry
    feature_engineer: FeatureEngineer
    feature_extractor: EnvironmentalFeatureExtractor
    climate_optimizer: ClimateOptimizer
    plant_health_monitor: PlantHealthMonitor
    growth_predictor: PlantGrowthPredictor
    disease_predictor: DiseasePredictor
    irrigation_predictor: Optional[object]  # IrrigationPredictor - avoiding import cycle
    ml_trainer: MLTrainerService
    drift_detector: ModelDriftDetectorService
    ab_testing: ABTestingService
    environmental_health_scorer: EnvironmentalLeafHealthScorer
    plant_health_scorer: PlantHealthScorer


@dataclass
class OptionalAIComponents:
    """Optional AI components (enabled via config)."""
    continuous_monitor: Optional[object]
    automated_retraining: Optional[AutomatedRetrainingService]
    personalized_learning: Optional[object]
    training_data_collector: Optional[object]


@dataclass
class HardwareComponents:
    """Hardware management services (sensors, actuators)."""
    sensor_management_service: SensorManagementService
    actuator_management_service: ActuatorManagementService
    mqtt_sensor_service: Optional[MQTTSensorService]


@dataclass
class ApplicationComponents:
    """Application-level services (growth, plants, health)."""
    auth_manager: UserAuthManager
    plant_catalog: PlantJsonHandler
    threshold_service: ThresholdService
    growth_service: GrowthService
    device_health_service: DeviceHealthService
    device_coordinator: DeviceCoordinator
    analytics_service: AnalyticsService
    settings_service: SettingsService
    plant_service: PlantViewService
    manual_irrigation_service: ManualIrrigationService
    plant_irrigation_model_service: PlantIrrigationModelService
    harvest_service: PlantHarvestService
    plant_journal_service: PlantJournalService
    scheduler: UnifiedScheduler
    camera_service: CameraService
    anomaly_detection_service: AnomalyDetectionService
    system_health_service: SystemHealthService


class ContainerBuilder:
    """
    Builder for constructing the service container.

    Breaks down the monolithic build() method into focused, single-responsibility methods.
    Each method constructs one subsystem, making the code more maintainable and testable.
    """

    def __init__(self, config: AppConfig):
        """Initialize builder with configuration."""
        self.config = config

    def build_infrastructure(self) -> InfrastructureComponents:
        """
        Build infrastructure layer (database, repositories, logging).

        Returns:
            InfrastructureComponents with all infrastructure services
        """
        logger.info("Building infrastructure components...")

        audit_logger = AuditLogger(self.config.audit_log_path, self.config.log_level)
        database = SQLiteDatabaseHandler(self.config.database_path)
        database.init_app(None)
        # Run idempotent startup migrations (backfill dedupe table if empty)
        try:
            from infrastructure.database.migrations import run_startup_migrations
            migrated = run_startup_migrations(database)
            if migrated:
                logger.info(f"Ran startup migrations: backfilled {migrated} dedupe entries")
        except Exception as e:
            logger.debug(f"Startup migrations failed or skipped: {e}")

        # Initialize repositories
        settings_repo = SettingsRepository(database)
        growth_repo = GrowthRepository(database)  # Compatibility facade
        unit_repo = UnitRepository(database)  # New: For GrowthService
        plant_repo = PlantRepository(database)  # New: For PlantViewService
        device_repo = DeviceRepository(database)
        analytics_repo = AnalyticsRepository(database)
        ai_health_repo = AIHealthDataRepository(database)
        training_data_repo = AITrainingDataRepository(database)
        plant_journal_repo = PlantJournalRepository(database)
        camera_repo = CameraRepository(database)
        schedule_repo = ScheduleRepository(database)

        # Initialize application loggers and alerts (pass repositories)
        activity_repo = ActivityRepository(database)
        alert_repo = AlertRepository(database)
        notification_repo = NotificationRepository(database)
        irrigation_workflow_repo = IrrigationWorkflowRepository(database)
        irrigation_ml_repo = IrrigationMLRepository(database)
        activity_logger = ActivityLogger(activity_repo)
        alert_service = AlertService(alert_repo)
        
        # Email service (standalone, can be used by multiple services)
        
        email_service = EmailService()

        # Notifications service (emitter will be wired later)
        notifications_service = NotificationsService(
            notification_repo=notification_repo,
            emitter_service=None,  # Will be set after emitter_service is created
            email_service=email_service,
        )

        # Irrigation workflow service (dependencies wired later)
        irrigation_workflow_service = IrrigationWorkflowService(
            workflow_repo=irrigation_workflow_repo,
            notifications_service=notifications_service,
            actuator_service=None,  # Will be set after actuator_service is created
            scheduler=None,  # Will be set after scheduler is created
        )

        logger.info("✓ Infrastructure components initialized")

        return InfrastructureComponents(
            database=database,
            settings_repo=settings_repo,
            growth_repo=growth_repo,
            unit_repo=unit_repo,
            plant_repo=plant_repo,
            device_repo=device_repo,
            analytics_repo=analytics_repo,
            ai_health_repo=ai_health_repo,
            training_data_repo=training_data_repo,
            plant_journal_repo=plant_journal_repo,
            camera_repo=camera_repo,
            notification_repo=notification_repo,
            irrigation_workflow_repo=irrigation_workflow_repo,
            irrigation_ml_repo=irrigation_ml_repo,
            schedule_repo=schedule_repo,
            audit_logger=audit_logger,
            activity_logger=activity_logger,
            alert_service=alert_service,
            notifications_service=notifications_service,
            irrigation_workflow_service=irrigation_workflow_service,
        )

    def build_mqtt_components(self) -> MQTTComponents:
        """
        Build MQTT and Zigbee components (if enabled).

        Returns:
            MQTTComponents with MQTT client and Zigbee service
        """
        logger.info("Building MQTT components...")

        mqtt_client: Optional[MQTTClientWrapper] = None
        zigbee_service: Optional[ZigbeeManagementService] = None

        if self.config.enable_mqtt:
            mqtt_client = MQTTClientWrapper(
                broker=self.config.mqtt_broker_host,
                port=self.config.mqtt_broker_port
            )

            # Initialize Zigbee service if MQTT connected
            try:
                if mqtt_client.connected:
                    zigbee_service = ZigbeeManagementService(mqtt_client=mqtt_client)
                    logger.info("✓ ZigbeeService initialized successfully")
                else:
                    logger.warning("⚠️  MQTT client not connected, skipping ZigbeeService")
            except Exception as e:
                logger.warning(f"⚠️  Failed to initialize ZigbeeService: {e}")
                zigbee_service = None

            logger.info("✓ MQTT components initialized")
        else:
            logger.info("MQTT disabled, skipping MQTT components")

        return MQTTComponents(mqtt_client=mqtt_client, zigbee_service=zigbee_service)

    def build_shared_utilities(self) -> SharedUtilities:
        """
        Build shared utility services (emitters, processors, event bus).

        Returns:
            SharedUtilities with shared services
        """
        logger.info("Building shared utilities...")

        # Import socketio here to avoid circular dependency at module level
        from app.extensions import socketio

        # Initialize emitter service
        emitter_service = EmitterService(sio=socketio, replay_maxlen=100)

        # Create sensor data processor pipeline
        sensor_processor = CompositeProcessor(
            validator=ValidationProcessor(sensor_type="generic"),
            calibrator=CalibrationProcessor(),
            transformer=TransformationProcessor(),
            enricher=EnrichmentProcessor(),
            priority=PriorityProcessor(),
            resolve_sensor=None,
        )

        # Initialize event bus
        event_bus = EventBus()

        logger.info("✓ Shared utilities initialized (pipeline: validate → calibrate → transform → enrich)")

        return SharedUtilities(
            emitter_service=emitter_service,
            sensor_processor=sensor_processor,
            event_bus=event_bus,
        )

    def build_ai_components(
        self,
        infra: InfrastructureComponents,
    ) -> AIComponents:
        """
        Build core AI and ML services.

        Args:
            infra: Infrastructure components

        Returns:
            AIComponents with AI services
        """
        logger.info("Building AI components...")

        models_path = Path(getattr(self.config, "models_path", "models"))

        # Initialize model registry
        model_registry = ModelRegistry(base_path=models_path)

        # Feature engineering
        feature_engineer = FeatureEngineer()
        feature_extractor = EnvironmentalFeatureExtractor()

        # Climate optimizer
        climate_optimizer = ClimateOptimizer(
            analytics_repo=infra.analytics_repo,
            model_registry=model_registry
        )

        # Plant health monitor (threshold_service will be set later)
        plant_health_monitor = PlantHealthMonitor(
            repo_health=infra.ai_health_repo,
            threshold_service=None  # Will be set after threshold_service initialization
        )

        # Growth predictor
        growth_predictor = PlantGrowthPredictor(
            model_registry=model_registry,
            enable_validation=True
        )

        # Disease predictor
        disease_predictor = DiseasePredictor(
            repo_health=infra.ai_health_repo,
            model_registry=model_registry
        )
        disease_predictor.load_models()

        # Environmental health scorer (threshold_service wired later)
        environmental_health_scorer = EnvironmentalLeafHealthScorer(
            threshold_service=None,
            analytics_repo=infra.analytics_repo
        )

        # Plant health feature extractor for ML predictions
        plant_health_feature_extractor = PlantHealthFeatureExtractor()

        # Plant health scorer (threshold_service & plant_service wired later)
        plant_health_scorer = PlantHealthScorer(
            analytics_repo=infra.analytics_repo,
            threshold_service=None,
            disease_predictor=disease_predictor,
            environmental_scorer=environmental_health_scorer,
            plant_service=None,
            model_registry=model_registry,
            feature_extractor=plant_health_feature_extractor,
        )
        # Try to load ML models (gracefully handles missing models)
        plant_health_scorer.load_models()

        # ML trainer
        ml_trainer = MLTrainerService(
            training_data_repo=infra.training_data_repo,
            model_registry=model_registry
        )

        # Drift detector (with persistence)
        drift_detector = ModelDriftDetectorService(
            model_registry=model_registry,
            training_data_repo=infra.training_data_repo,
            ai_health_repo=infra.training_data_repo,
        )

        # A/B testing (with persistence)
        ab_testing = ABTestingService(
            model_registry=model_registry,
            ai_repo=infra.training_data_repo,
        )

        # Irrigation predictor (ML-based irrigation optimization)
        irrigation_predictor = None
        if infra.irrigation_ml_repo:
            try:
                from app.services.ai.irrigation_predictor import IrrigationPredictor
                irrigation_predictor = IrrigationPredictor(
                    irrigation_ml_repo=infra.irrigation_ml_repo,
                    model_registry=model_registry,
                    feature_engineer=feature_engineer,
                )
                irrigation_predictor.load_models()
                logger.info("✓ IrrigationPredictor initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize IrrigationPredictor: {e}")

        logger.info(f"✓ AI components initialized (models_path: {models_path})")


        return AIComponents(
            model_registry=model_registry,
            feature_engineer=feature_engineer,
            feature_extractor=feature_extractor,
            climate_optimizer=climate_optimizer,
            plant_health_monitor=plant_health_monitor,
            growth_predictor=growth_predictor,
            disease_predictor=disease_predictor,
            irrigation_predictor=irrigation_predictor,
            ml_trainer=ml_trainer,
            drift_detector=drift_detector,
            ab_testing=ab_testing,
            environmental_health_scorer=environmental_health_scorer,
            plant_health_scorer=plant_health_scorer,
        )

    def build_optional_ai_components(
        self,
        ai: AIComponents,
        infra: InfrastructureComponents,
    ) -> OptionalAIComponents:
        """
        Build optional AI components (enabled via config).

        Args:
            ai: Core AI components

        Returns:
            OptionalAIComponents with optional services
        """
        logger.info("Building optional AI components...")

        continuous_monitor = None
        personalized_learning = None
        training_data_collector = None
        automated_retraining = None

        # Continuous monitoring
        enable_continuous_monitoring = getattr(self.config, "enable_continuous_monitoring", False)
        if enable_continuous_monitoring:
            from app.services.ai.continuous_monitor import ContinuousMonitoringService

            check_interval = 600 if self._is_raspberry_pi() else 300
            continuous_monitor = ContinuousMonitoringService(
                disease_predictor=ai.disease_predictor,
                climate_optimizer=ai.climate_optimizer,
                health_monitor=ai.plant_health_monitor,
                growth_predictor=ai.growth_predictor,
                analytics_repo=infra.analytics_repo,
                check_interval=check_interval
            )
            
            # Wire notification service for AI-generated alerts
            if infra.notifications_service:
                def get_user_for_unit(unit_id: int) -> int | None:
                    """Resolve user_id from unit_id via growth repository."""
                    try:
                        from infrastructure.database.repositories.growth import GrowthRepository
                        # Access the growth repo from the database
                        growth_repo = GrowthRepository(infra.database)
                        unit = growth_repo.get_unit(unit_id)
                        return unit.get("user_id") if unit else None
                    except Exception as e:
                        logger.warning(f"Failed to resolve user for unit {unit_id}: {e}")
                        return None
                
                continuous_monitor.set_notification_service(
                    notifications_service=infra.notifications_service,
                    user_resolver=get_user_for_unit
                )
                logger.info("✓ Continuous Monitor wired to NotificationsService")
            
            continuous_monitor.start_monitoring()
            logger.info(f"✓ Continuous Monitoring enabled (interval: {check_interval}s)")
        else:
            logger.info("Continuous Monitoring disabled")

        # Automated retraining
        enable_automated_retraining = getattr(self.config, "enable_automated_retraining", False)
        if enable_automated_retraining:
            automated_retraining = AutomatedRetrainingService(
                model_registry=ai.model_registry,
                drift_detector=ai.drift_detector,
                ml_trainer=ai.ml_trainer
            )

            # Schedule default retraining jobs
            automated_retraining.add_job(
                model_type='climate',
                schedule_type='weekly',
                schedule_day=0,  # Monday
                schedule_time='02:00',
                min_samples=100
            )
            automated_retraining.add_job(
                model_type='disease',
                schedule_type='on_drift',
                drift_threshold=0.15,
                min_samples=100
            )

            logger.info("✓ Automated Retraining enabled with default jobs")
        else:
            logger.info("Automated Retraining disabled")

        # Personalized learning
        enable_personalized_learning = getattr(self.config, "enable_personalized_learning", False)
        if enable_personalized_learning:
            from app.services.ai.personalized_learning import PersonalizedLearningService

            profiles_path = Path(getattr(self.config, "personalized_profiles_path", "personalized_profiles"))
            personalized_learning = PersonalizedLearningService(
                model_registry=ai.model_registry,
                training_data_repo=infra.training_data_repo,
                profiles_dir=profiles_path
            )
            logger.info(f"✓ Personalized Learning enabled (path: {profiles_path})")
        else:
            logger.info("Personalized Learning disabled")

        # Training data collector
        enable_training_data_collection = getattr(self.config, "enable_training_data_collection", False)
        if enable_training_data_collection:
            from app.services.ai.training_data_collector import TrainingDataCollector

            training_data_path = Path(getattr(self.config, "training_data_path", "training_data"))
            training_data_collector = TrainingDataCollector(
                training_data_repo=infra.training_data_repo,
                feature_engineer=ai.feature_engineer,
                storage_path=training_data_path
            )
            logger.info(f"✓ Training Data Collector enabled (path: {training_data_path})")

        return OptionalAIComponents(
            continuous_monitor=continuous_monitor,
            automated_retraining=automated_retraining,
            personalized_learning=personalized_learning,
            training_data_collector=training_data_collector,
        )

    def build_hardware_components(
        self,
        infra: InfrastructureComponents,
        mqtt: MQTTComponents,
        utils: SharedUtilities,
        system_health_service: SystemHealthService,
    ) -> HardwareComponents:
        """
        Build hardware management services (sensors, actuators).

        Args:
            infra: Infrastructure components
            mqtt: MQTT components
            utils: Shared utilities
            system_health_service: System health service

        Returns:
            HardwareComponents with hardware services
        """
        logger.info("Building hardware components...")

        # Sensor management service
        sensor_management_service = SensorManagementService(
            repository=infra.device_repo,
            emitter=utils.emitter_service,
            processor=utils.sensor_processor,
            mqtt_client=mqtt.mqtt_client,
            event_bus=utils.event_bus,
            system_health_service=system_health_service,
            zigbee_service=mqtt.zigbee_service,
            cache_ttl_seconds=self.config.cache_ttl_seconds,
            cache_maxsize=self.config.cache_maxsize
        )

        # Actuator management service
        actuator_management_service = ActuatorManagementService(
            repository=infra.device_repo,
            analytics_repository=infra.analytics_repo,
            mqtt_client=mqtt.mqtt_client,
            event_bus=utils.event_bus,
            device_health_service=None,  # Will be set after DeviceHealthService creation
            zigbee_service=mqtt.zigbee_service,
            schedule_repository=infra.schedule_repo,
            cache_ttl_seconds=self.config.cache_ttl_seconds,
            cache_maxsize=self.config.cache_maxsize
        )

        # MQTT sensor service (if MQTT enabled)
        mqtt_sensor_service: Optional[MQTTSensorService] = None
        if mqtt.mqtt_client is not None:
            mqtt_sensor_service = MQTTSensorService(
                mqtt_client=mqtt.mqtt_client,
                emitter=utils.emitter_service,
                sensor_manager=sensor_management_service,
                processor=utils.sensor_processor,
            )

            # Ensure dashboard snapshots can resolve sensor metadata.
            try:
                if hasattr(utils.sensor_processor, "set_resolve_sensor"):
                    utils.sensor_processor.set_resolve_sensor(mqtt_sensor_service._get_sensor_entity)
            except Exception:
                pass
            logger.info("✓ MQTTSensorService initialized (Zigbee + ESP32)")
        else:
            logger.info("⚠️  MQTT disabled, MQTTSensorService not initialized")

        logger.info("✓ Hardware components initialized")

        return HardwareComponents(
            sensor_management_service=sensor_management_service,
            actuator_management_service=actuator_management_service,
            mqtt_sensor_service=mqtt_sensor_service,
        )

    def build_application_components(
        self,
        infra: InfrastructureComponents,
        mqtt: MQTTComponents,
        ai: AIComponents,
        hardware: HardwareComponents,
        utils: SharedUtilities,
        start_coordinator: bool = False,
    ) -> ApplicationComponents:
        """
        Build application-level services (growth, plants, health, etc.).

        Args:
            infra: Infrastructure components
            mqtt: MQTT components
            ai: AI components
            hardware: Hardware components
            utils: Shared utilities
            start_coordinator: Whether to start DeviceCoordinator

        Returns:
            ApplicationComponents with application services
        """
        logger.info("Building application components...")

        # Auth manager
        auth_manager = UserAuthManager(
            database_handler=infra.database,
            audit_logger=infra.audit_logger
        )

        # Plant catalog
        plant_catalog = PlantJsonHandler()

        # Anomaly detection and system health
        anomaly_detection_service = AnomalyDetectionService()
        system_health_service = SystemHealthService(
            anomaly_service=anomaly_detection_service,
            alert_service=infra.alert_service
        )

        # Threshold service
        threshold_service = ThresholdService(
            plant_handler=plant_catalog,
            climate_optimizer=ai.climate_optimizer,
            growth_repo=infra.growth_repo,
        )

        # Set threshold service on plant health monitor
        ai.plant_health_monitor.threshold_service = threshold_service

        # Set threshold service on environmental and plant health scorers
        ai.environmental_health_scorer.threshold_service = threshold_service

        # Bayesian threshold adjuster with ThresholdService integration
        from app.services.ai.bayesian_threshold import BayesianThresholdAdjuster
        bayesian_adjuster = BayesianThresholdAdjuster(
            irrigation_ml_repo=None,  # Optional, for advanced ML features
            workflow_repo=infra.irrigation_workflow_repo,
            threshold_service=threshold_service,
        )
        infra.irrigation_workflow_service.set_bayesian_adjuster(bayesian_adjuster)
        logger.info("✓ BayesianThresholdAdjuster wired with ThresholdService")

        # Plant journal service
        plant_journal_service = PlantJournalService(
            journal_repo=infra.plant_journal_repo,
            health_monitor=ai.plant_health_monitor,
        )

        # Analytics service
        # Get scheduling service from actuator management service if available
        scheduling_service = None
        if hardware.actuator_management_service:
            scheduling_service = getattr(hardware.actuator_management_service, "scheduling_service", None)
        
        analytics_service = AnalyticsService(
            repository=infra.analytics_repo,
            device_repository=infra.device_repo,
            growth_repository=infra.growth_repo,
            threshold_service=threshold_service,
            scheduling_service=scheduling_service,
        )

        # Growth service
        growth_service = GrowthService(
            unit_repo=infra.unit_repo,
            analytics_repo=infra.analytics_repo,
            audit_logger=infra.audit_logger,
            activity_logger=infra.activity_logger,
            devices_repo=infra.device_repo,
            notifications_service=infra.notifications_service,
            irrigation_workflow_service=infra.irrigation_workflow_service,
            event_bus=utils.event_bus,
            mqtt_client=mqtt.mqtt_client,
            zigbee_service=mqtt.zigbee_service,
            threshold_service=threshold_service,
            sensor_management_service=hardware.sensor_management_service,
            actuator_management_service=hardware.actuator_management_service,
            sensor_processor=utils.sensor_processor,
            ai_health_repo=infra.ai_health_repo,
            cache_enabled=self.config.cache_enabled,
            cache_ttl_seconds=self.config.cache_ttl_seconds,
            cache_maxsize=self.config.cache_maxsize,
        )

        # Device health service
        device_health_service = DeviceHealthService(
            repository=infra.device_repo,
            mqtt_client=mqtt.mqtt_client,
            alert_service=infra.alert_service,
            system_health_service=system_health_service,
            sensor_management_service=hardware.sensor_management_service,
            actuator_management_service=hardware.actuator_management_service,
            zigbee_service=mqtt.zigbee_service
        )

        # Device coordinator
        device_coordinator = DeviceCoordinator(
            repository=infra.device_repo,
            event_bus=utils.event_bus
        )
        if start_coordinator:
            device_coordinator.start()

        # Settings service
        settings_service = SettingsService(
            repository=infra.settings_repo,
            growth_service=growth_service,
            sensor_service=hardware.sensor_management_service,
        )

        # Plant view service
        plant_service = PlantViewService(
            growth_service=growth_service,
            sensor_service=hardware.sensor_management_service,
            plant_repo=infra.plant_repo,
            unit_repo=infra.unit_repo,
            event_bus=utils.event_bus,
            activity_logger=infra.activity_logger,
            threshold_service=threshold_service,
            notifications_service=infra.notifications_service,
        )

        # Wire plant_service to plant_health_scorer
        ai.plant_health_scorer.threshold_service = threshold_service
        ai.plant_health_scorer.plant_service = plant_service

        # Unified scheduler (singleton)
        scheduler = get_scheduler()

        # Manual irrigation + dry-down model services
        plant_irrigation_model_service = PlantIrrigationModelService(
            irrigation_repo=infra.irrigation_workflow_repo,
            analytics_repo=infra.analytics_repo,
        )
        manual_irrigation_service = ManualIrrigationService(
            irrigation_repo=infra.irrigation_workflow_repo,
            analytics_repo=infra.analytics_repo,
            plant_service=plant_service,
            plant_model_service=plant_irrigation_model_service,
            notifications_service=infra.notifications_service,
            device_repo=infra.device_repo,
            growth_repo=infra.growth_repo,
            event_bus=utils.event_bus,
            scheduler=scheduler,
        )

        # ==== BIDIRECTIONAL DEPENDENCY WIRING ====
        # All circular dependencies are resolved here after service creation.
        # This ensures all services exist before wiring back-references.
        #
        # Pattern: Pass None to constructors, then wire via direct attribute assignment

        # GrowthService ↔ DeviceHealthService (for health monitoring)
        growth_service.device_health_service = device_health_service

        # PlantJournalService → ManualIrrigationService (optional watering logging)
        plant_journal_service.set_manual_irrigation_service(manual_irrigation_service)

        # ActuatorManagementService ↔ DeviceHealthService (for actuator health)
        hardware.actuator_management_service.device_health_service = device_health_service

        # GrowthService ↔ PlantService (for cross-service delegation)
        growth_service._plant_service = plant_service
        # PlantService already has growth_service from constructor (line 652)

        infra.notifications_service.register_action_handler(
            "threshold_update",
            growth_service.handle_threshold_update_action,
        )

        # Harvest service
        harvest_service = PlantHarvestService(analytics_repo=infra.analytics_repo)

        # Camera service
        camera_service = CameraService(repository=infra.camera_repo)

        # Log system startup
        infra.activity_logger.log_activity(
            activity_type=ActivityLogger.SYSTEM_STARTUP,
            description="Smart Agriculture System started",
            severity=ActivityLogger.INFO
        )

        logger.info("✓ Application components initialized")

        return ApplicationComponents(
            auth_manager=auth_manager,
            plant_catalog=plant_catalog,
            threshold_service=threshold_service,
            growth_service=growth_service,
            device_health_service=device_health_service,
            device_coordinator=device_coordinator,
            analytics_service=analytics_service,
            settings_service=settings_service,
            plant_service=plant_service,
            manual_irrigation_service=manual_irrigation_service,
            plant_irrigation_model_service=plant_irrigation_model_service,
            harvest_service=harvest_service,
            plant_journal_service=plant_journal_service,
            scheduler=scheduler,
            camera_service=camera_service,
            anomaly_detection_service=anomaly_detection_service,
            system_health_service=system_health_service,
        )

    def build(self, *, start_coordinator: bool = False) -> Dict[str, Any]:
        """
        Build the complete service container.

        Args:
            start_coordinator: Whether to start DeviceCoordinator event loop

        Returns:
            Dictionary with all components for ServiceContainer construction
        """
        logger.info("Building ServiceContainer with ContainerBuilder...")

        # Build each subsystem
        infra = self.build_infrastructure()
        mqtt = self.build_mqtt_components()
        utils = self.build_shared_utilities()
        ai = self.build_ai_components(infra)

        # Wire emitter to notifications_service (circular dependency resolution)
        infra.notifications_service._emitter = utils.emitter_service

        # Get scheduler for irrigation workflow
        scheduler = get_scheduler()

        # Build hardware (needs system_health_service, so we create a minimal one first)
        anomaly_service = AnomalyDetectionService()
        temp_system_health = SystemHealthService(
            anomaly_service=anomaly_service,
            alert_service=infra.alert_service
        )
        hardware = self.build_hardware_components(infra, mqtt, utils, temp_system_health)

        # Wire irrigation workflow service with actuator management service and scheduler
        # (ActuatorManagementService now contains all actuator manager functionality)
        infra.irrigation_workflow_service.set_actuator_manager(
            hardware.actuator_management_service
        )
        infra.irrigation_workflow_service.set_scheduler(scheduler)
        scheduling_service = getattr(
            hardware.actuator_management_service,
            "scheduling_service",
            None,
        )
        if scheduling_service:
            scheduling_service.set_scheduler(scheduler)
            infra.irrigation_workflow_service.set_scheduling_service(scheduling_service)
        infra.irrigation_workflow_service.register_scheduled_tasks()

        # Build application components (creates final system_health_service)
        app = self.build_application_components(
            infra,
            mqtt,
            ai,
            hardware,
            utils,
            start_coordinator=start_coordinator
        )

        app.manual_irrigation_service.register_scheduled_tasks()
        app.manual_irrigation_service.register_event_handlers()

        # Wire irrigation workflow service with data-driven irrigation dependencies
        # These require PlantViewService which is created in build_application_components
        irrigation_calculator = IrrigationCalculator(
            plant_service=app.plant_service,
            ml_predictor=ai.irrigation_predictor,
        )
        pump_calibration_service = PumpCalibrationService(
            hardware.actuator_management_service,
            device_repo=infra.device_repo)
        infra.irrigation_workflow_service.set_irrigation_calculator(irrigation_calculator)
        infra.irrigation_workflow_service.set_pump_calibration_service(pump_calibration_service)
        infra.irrigation_workflow_service.set_plant_service(app.plant_service)
        logger.info("✓ Irrigation workflow wired with calculator, pump calibration, and plant service")

        # Build optional AI components
        optional_ai = self.build_optional_ai_components(ai, infra)

        # Wire PersonalizedLearningService into AI components (if enabled)
        if optional_ai.personalized_learning:
            ai.climate_optimizer.personalized_learning = optional_ai.personalized_learning
            ai.disease_predictor.personalized_learning = optional_ai.personalized_learning
            app.threshold_service.set_personalized_learning(optional_ai.personalized_learning)
            optional_ai.personalized_learning.register_profile_update_callback(
                app.threshold_service.clear_cache
            )
            logger.info("✓ PersonalizedLearning wired into ClimateOptimizer and DiseasePredictor")

        logger.info("ServiceContainer built successfully.")

        # Return all components as a dictionary for ServiceContainer construction
        return {
            "config": self.config,
            "database": infra.database,
            "settings_repo": infra.settings_repo,
            "growth_repo": infra.growth_repo,
            "device_repo": infra.device_repo,
            "analytics_repo": infra.analytics_repo,
            "ai_health_repo": infra.ai_health_repo,
            "training_data_repo": infra.training_data_repo,
            "plant_journal_repo": infra.plant_journal_repo,
            "notification_repo": infra.notification_repo,
            "audit_logger": infra.audit_logger,
            "activity_logger": infra.activity_logger,
            "alert_service": infra.alert_service,
            "notifications_service": infra.notifications_service,
            "irrigation_workflow_service": infra.irrigation_workflow_service,
            "plant_catalog": app.plant_catalog,
            "auth_manager": app.auth_manager,
            "threshold_service": app.threshold_service,
            "growth_service": app.growth_service,
            "device_health_service": app.device_health_service,
            "device_coordinator": app.device_coordinator,
            "analytics_service": app.analytics_service,
            "settings_service": app.settings_service,
            "plant_service": app.plant_service,
            "manual_irrigation_service": app.manual_irrigation_service,
            "plant_irrigation_model_service": app.plant_irrigation_model_service,
            "harvest_service": app.harvest_service,
            "plant_journal_service": app.plant_journal_service,
            "scheduler": app.scheduler,
            "camera_service": app.camera_service,
            "mqtt_client": mqtt.mqtt_client,
            "zigbee_service": mqtt.zigbee_service,
            "anomaly_detection_service": app.anomaly_detection_service,
            "system_health_service": app.system_health_service,
            "sensor_management_service": hardware.sensor_management_service,
            "actuator_management_service": hardware.actuator_management_service,
            "mqtt_sensor_service": hardware.mqtt_sensor_service,
            "emitter_service": utils.emitter_service,
            "sensor_processor": utils.sensor_processor,
            "model_registry": ai.model_registry,
            "disease_predictor": ai.disease_predictor,
            "plant_health_monitor": ai.plant_health_monitor,
            "climate_optimizer": ai.climate_optimizer,
            "growth_predictor": ai.growth_predictor,
            "ml_trainer": ai.ml_trainer,
            "drift_detector": ai.drift_detector,
            "continuous_monitor": optional_ai.continuous_monitor,
            "ab_testing": ai.ab_testing,
            "automated_retraining": optional_ai.automated_retraining,
            "personalized_learning": optional_ai.personalized_learning,
            "training_data_collector": optional_ai.training_data_collector,
            "environmental_health_scorer": ai.environmental_health_scorer,
            "plant_health_scorer": ai.plant_health_scorer,
        }

    @staticmethod
    def _is_raspberry_pi() -> bool:
        """Detect if running on Raspberry Pi."""
        try:
            with open('/proc/device-tree/model', 'r') as f:
                model = f.read()
                return 'raspberry pi' in model.lower()
        except:
            return False
