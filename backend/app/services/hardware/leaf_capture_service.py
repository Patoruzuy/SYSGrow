"""
Leaf Capture Service
====================
Automated leaf image capture and analysis scheduling.
"""
import logging
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

from app.hardware.devices.camera_service import CameraService
from app.hardware.sensors.processors.leaf_health_processor import LeafHealthProcessor
from app.domain.leaf_health import LeafHealthAnalysis
from app.utils.event_bus import EventBus
from app.enums.events import SensorEvent

logger = logging.getLogger(__name__)


class LeafCaptureService:
    """
    Service for automated leaf image capture and health analysis.
    
    Features:
    - Scheduled captures during light periods
    - Image storage and management
    - Automatic health analysis
    - WebSocket emission of results
    """
    
    def __init__(
        self,
        camera_service: CameraService,
        leaf_processor: LeafHealthProcessor,
        event_bus: EventBus,
        storage_path: str = "data/leaf_images"
    ):
        """
        Initialize leaf capture service.
        
        Args:
            camera_service: Camera service for image capture
            leaf_processor: Leaf health processor
            event_bus: Event bus for publishing results
            storage_path: Directory for storing leaf images
        """
        self.camera_service = camera_service
        self.leaf_processor = leaf_processor
        self.event_bus = event_bus
        self.storage_path = Path(storage_path)
        
        # Create storage directory
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Track last capture per unit (prevent spam)
        self._last_capture: Dict[int, datetime] = {}
        
        logger.info(f"LeafCaptureService initialized (storage: {storage_path})")
    
    def capture_and_analyze(
        self,
        unit_id: int,
        plant_id: Optional[int] = None,
        environmental_context: Optional[Dict[str, float]] = None,
        min_interval_seconds: int = 3600  # 1 hour minimum between captures
    ) -> Optional[LeafHealthAnalysis]:
        """
        Capture leaf image and analyze health.
        
        Args:
            unit_id: Growth unit ID
            plant_id: Optional plant ID
            environmental_context: Current sensor readings
            min_interval_seconds: Minimum time between captures
            
        Returns:
            LeafHealthAnalysis or None if capture fails
        """
        try:
            # Check if camera is running
            if not self.camera_service.is_camera_running(unit_id):
                logger.warning(f"Camera not running for unit {unit_id}")
                return None
            
            # Check minimum interval
            last_capture = self._last_capture.get(unit_id)
            if last_capture:
                elapsed = (datetime.now() - last_capture).total_seconds()
                if elapsed < min_interval_seconds:
                    logger.debug(
                        f"Skipping capture for unit {unit_id} "
                        f"(last capture {elapsed:.0f}s ago)"
                    )
                    return None
            
            # Capture image
            image_bytes = self.camera_service.get_camera_frame(unit_id)
            if not image_bytes:
                logger.error(f"Failed to capture image for unit {unit_id}")
                return None
            
            # Save image
            image_path = self._save_image(unit_id, image_bytes)
            
            # Analyze leaf health
            analysis = self.leaf_processor.analyze_image(
                image_path=str(image_path),
                unit_id=unit_id,
                plant_id=plant_id,
                environmental_context=environmental_context
            )
            
            if analysis:
                # Update last capture time
                self._last_capture[unit_id] = datetime.now()
                
                # Publish event
                self._publish_health_update(analysis)
                
                logger.info(
                    f"Leaf health captured for unit {unit_id}: "
                    f"{analysis.health_status.value} (score: {analysis.health_score:.2f})"
                )
            
            return analysis
            
        except Exception as e:
            logger.error(
                f"Failed to capture and analyze for unit {unit_id}: {e}",
                exc_info=True
            )
            return None
    
    def _save_image(self, unit_id: int, image_bytes: bytes) -> Path:
        """
        Save captured image to storage.
        
        Returns:
            Path to saved image
        """
        # Create unit directory
        unit_dir = self.storage_path / f"unit_{unit_id}"
        unit_dir.mkdir(exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"leaf_{timestamp}.jpg"
        image_path = unit_dir / filename
        
        # Save image
        with open(image_path, 'wb') as f:
            f.write(image_bytes)
        
        # Clean up old images (keep last 100 per unit)
        self._cleanup_old_images(unit_dir, keep=100)
        
        return image_path
    
    def _cleanup_old_images(self, unit_dir: Path, keep: int = 100):
        """Remove old images, keeping most recent N"""
        images = sorted(unit_dir.glob("leaf_*.jpg"), key=os.path.getmtime, reverse=True)
        
        for image in images[keep:]:
            try:
                image.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete old image {image}: {e}")
    
    def _publish_health_update(self, analysis: LeafHealthAnalysis):
        """Publish leaf health update to event bus"""
        try:
            payload = {
                'unit_id': analysis.unit_id,
                'plant_id': analysis.plant_id,
                'health_status': analysis.health_status.value,
                'health_score': analysis.health_score,
                'issues': [issue.to_dict() for issue in analysis.issues],
                'color_metrics': analysis.color_metrics.to_dict(),
                'timestamp': analysis.timestamp.isoformat(),
                'image_path': analysis.image_path
            }
            
            self.event_bus.publish(
                SensorEvent.LEAF_HEALTH_UPDATE,
                payload
            )
            
        except Exception as e:
            logger.error(f"Failed to publish health update: {e}", exc_info=True)
    
    def get_latest_analysis(self, unit_id: int) -> Optional[Dict[str, Any]]:
        """Get most recent leaf health analysis for a unit"""
        try:
            unit_dir = self.storage_path / f"unit_{unit_id}"
            if not unit_dir.exists():
                return None
            
            # Find most recent image
            images = sorted(unit_dir.glob("leaf_*.jpg"), key=os.path.getmtime, reverse=True)
            if not images:
                return None
            
            latest_image = str(images[0])
            
            # Re-analyze if needed (cached results would be better)
            analysis = self.leaf_processor.analyze_image(
                image_path=latest_image,
                unit_id=unit_id
            )
            
            return analysis.to_dict() if analysis else None
            
        except Exception as e:
            logger.error(f"Failed to get latest analysis: {e}", exc_info=True)
            return None


def create_leaf_capture_task(
    camera_service: CameraService,
    sensor_manager: Any,
    leaf_capture_service: LeafCaptureService
):
    """
    Create scheduled task for periodic leaf capture.
    
    To be called from scheduled_tasks.py
    """
    def capture_all_units():
        """Capture and analyze all units with cameras"""
        try:
            # Get all active units
            # In production, get from growth_service.list_units()
            units = [1, 2, 3]  # Replace with actual unit discovery
            
            for unit_id in units:
                # Only capture if camera is running
                if not camera_service.is_camera_running(unit_id):
                    continue
                
                # Get current environmental context
                try:
                    latest_readings = sensor_manager.get_latest_readings(unit_id)
                    env_context = {
                        'temperature': latest_readings.get('temperature'),
                        'humidity': latest_readings.get('humidity'),
                        'vpd': latest_readings.get('vpd'),
                        'soil_moisture': latest_readings.get('soil_moisture')
                    }
                except Exception:
                    env_context = None
                
                # Capture and analyze
                leaf_capture_service.capture_and_analyze(
                    unit_id=unit_id,
                    environmental_context=env_context
                )
            
        except Exception as e:
            logger.error(f"Leaf capture task failed: {e}", exc_info=True)
    
    return capture_all_units
