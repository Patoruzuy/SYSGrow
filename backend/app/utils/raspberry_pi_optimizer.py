"""
Raspberry Pi Performance Optimization Utilities
================================================
Automatic detection and optimization for Raspberry Pi hardware.

Features:
- Hardware detection (Pi 3, 4, 5)
- Automatic performance profile selection
- Memory and CPU optimization
- Model quantization helpers
"""

import logging
import os
import platform
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class HardwareProfile:
    """Hardware capabilities profile."""
    model: str
    ram_mb: int
    cpu_cores: int
    has_gpu: bool
    recommended_monitoring_interval: int
    recommended_max_predictions: int
    use_quantization: bool
    enable_gpu_acceleration: bool


class RaspberryPiOptimizer:
    """Optimize SYSGrow for Raspberry Pi hardware."""
    
    # Predefined profiles for different Pi models
    PROFILES = {
        "pi3": HardwareProfile(
            model="Raspberry Pi 3",
            ram_mb=1024,
            cpu_cores=4,
            has_gpu=False,
            recommended_monitoring_interval=600,  # 10 minutes
            recommended_max_predictions=1,
            use_quantization=True,
            enable_gpu_acceleration=False
        ),
        "pi4": HardwareProfile(
            model="Raspberry Pi 4",
            ram_mb=4096,
            cpu_cores=4,
            has_gpu=False,
            recommended_monitoring_interval=300,  # 5 minutes
            recommended_max_predictions=2,
            use_quantization=True,
            enable_gpu_acceleration=False
        ),
        "pi5": HardwareProfile(
            model="Raspberry Pi 5",
            ram_mb=8192,
            cpu_cores=4,
            has_gpu=True,
            recommended_monitoring_interval=180,  # 3 minutes
            recommended_max_predictions=3,
            use_quantization=False,
            enable_gpu_acceleration=True
        ),
        "default": HardwareProfile(
            model="Development/Desktop",
            ram_mb=16384,
            cpu_cores=8,
            has_gpu=True,
            recommended_monitoring_interval=60,  # 1 minute
            recommended_max_predictions=5,
            use_quantization=False,
            enable_gpu_acceleration=False  # Typically not using TensorFlow on dev
        )
    }
    
    def __init__(self):
        """Initialize optimizer and detect hardware."""
        self.profile = self._detect_hardware()
        logger.info(f"Hardware profile: {self.profile.model}")
    
    def _detect_hardware(self) -> HardwareProfile:
        """
        Detect Raspberry Pi model and return appropriate profile.
        
        Returns:
            HardwareProfile for the detected hardware
        """
        try:
            # Check if running on Raspberry Pi
            if not self._is_raspberry_pi():
                logger.info("Not running on Raspberry Pi - using default profile")
                return self.PROFILES["default"]
            
            # Read model information
            model_file = Path("/proc/device-tree/model")
            if not model_file.exists():
                return self.PROFILES["default"]
            
            model_str = model_file.read_text().lower()
            
            # Detect specific Pi model
            if "raspberry pi 5" in model_str:
                logger.info("Detected Raspberry Pi 5")
                return self.PROFILES["pi5"]
            elif "raspberry pi 4" in model_str:
                logger.info("Detected Raspberry Pi 4")
                # Check actual RAM
                ram_mb = self._get_total_ram_mb()
                profile = self.PROFILES["pi4"]
                profile.ram_mb = ram_mb
                return profile
            elif "raspberry pi 3" in model_str:
                logger.info("Detected Raspberry Pi 3")
                return self.PROFILES["pi3"]
            else:
                logger.warning(f"Unknown Raspberry Pi model: {model_str}")
                return self.PROFILES["pi4"]  # Conservative default
        
        except Exception as e:
            logger.error(f"Error detecting hardware: {e}")
            return self.PROFILES["default"]
    
    def _is_raspberry_pi(self) -> bool:
        """Check if running on Raspberry Pi."""
        try:
            # Check for Raspberry Pi specific file
            return Path("/proc/device-tree/model").exists()
        except:
            return False
    
    def _get_total_ram_mb(self) -> int:
        """Get total system RAM in MB."""
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb // 1024
        except:
            pass
        return 4096  # Default assumption
    
    def get_optimized_config(self, base_config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get optimized configuration based on hardware profile.
        
        Args:
            base_config: Base configuration dictionary
            
        Returns:
            Optimized configuration dictionary
        """
        config = base_config.copy()
        
        # Apply hardware-specific optimizations
        config["continuous_monitoring_interval"] = self.profile.recommended_monitoring_interval
        config["max_concurrent_predictions"] = self.profile.recommended_max_predictions
        config["use_model_quantization"] = self.profile.use_quantization
        config["enable_gpu_acceleration"] = self.profile.enable_gpu_acceleration
        
        # Additional optimizations for low-memory systems
        if self.profile.ram_mb < 2048:
            logger.warning("Low RAM detected - applying aggressive memory optimizations")
            config["model_cache_predictions"] = False
            config["monitoring_max_insights_per_unit"] = 20  # Reduced from 50
            config["retraining_check_interval"] = 7200  # 2 hours instead of 1
        
        # Optimize for CPU-limited systems
        if self.profile.cpu_cores <= 4:
            config["retraining_max_concurrent_jobs"] = 1
            # Reduce parallelism in scikit-learn
            os.environ["OMP_NUM_THREADS"] = "2"
            os.environ["OPENBLAS_NUM_THREADS"] = "2"
            os.environ["MKL_NUM_THREADS"] = "2"
        
        logger.info(f"Applied optimizations for {self.profile.model}")
        logger.info(f"  Monitoring interval: {config['continuous_monitoring_interval']}s")
        logger.info(f"  Max predictions: {config['max_concurrent_predictions']}")
        logger.info(f"  Model quantization: {config['use_model_quantization']}")
        
        return config
    
    def optimize_for_training(self) -> Dict[str, Any]:
        """
        Get optimization settings for model training.
        
        Returns:
            Dictionary of training-specific optimizations
        """
        optimizations = {
            "n_estimators": 50 if self.profile.ram_mb < 4096 else 100,
            "max_depth": 10 if self.profile.cpu_cores <= 4 else 15,
            "n_jobs": min(2, self.profile.cpu_cores - 1),
            "batch_size": 32 if self.profile.ram_mb < 2048 else 64,
        }
        
        return optimizations
    
    def should_enable_feature(self, feature_name: str) -> bool:
        """
        Determine if a feature should be enabled based on hardware.
        
        Args:
            feature_name: Name of the feature to check
            
        Returns:
            True if feature should be enabled
        """
        resource_intensive_features = {
            "enable_computer_vision": self.profile.ram_mb >= 4096 and self.profile.cpu_cores >= 4,
            "enable_continuous_monitoring": self.profile.ram_mb >= 1024,
            "enable_automated_retraining": self.profile.ram_mb >= 2048,
            "enable_personalized_learning": self.profile.ram_mb >= 2048,
            "enable_training_data_collection": True,  # Lightweight
            "enable_ab_testing": self.profile.ram_mb >= 2048,
            "enable_drift_detection": True,  # Lightweight
        }
        
        return resource_intensive_features.get(feature_name, True)
    
    def get_memory_usage_mb(self) -> float:
        """Get current process memory usage in MB."""
        try:
            import psutil
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / 1024 / 1024
        except ImportError:
            return 0.0
    
    def check_system_health(self) -> Dict[str, Any]:
        """
        Check system health metrics.
        
        Returns:
            Dictionary with system health information
        """
        health = {
            "model": self.profile.model,
            "ram_mb": self.profile.ram_mb,
            "cpu_cores": self.profile.cpu_cores,
        }
        
        try:
            import psutil
            
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            health["cpu_usage_percent"] = cpu_percent
            health["cpu_warning"] = cpu_percent > 80
            
            # Memory usage
            memory = psutil.virtual_memory()
            health["memory_used_mb"] = memory.used / 1024 / 1024
            health["memory_available_mb"] = memory.available / 1024 / 1024
            health["memory_percent"] = memory.percent
            health["memory_warning"] = memory.percent > 85
            
            # Disk usage
            disk = psutil.disk_usage("/")
            health["disk_percent"] = disk.percent
            health["disk_warning"] = disk.percent > 90
            
            # Temperature (Raspberry Pi specific)
            if self._is_raspberry_pi():
                temp = self._get_cpu_temperature()
                if temp:
                    health["cpu_temperature_c"] = temp
                    health["temperature_warning"] = temp > 75
            
        except ImportError:
            logger.warning("psutil not available - install for system health monitoring")
        except Exception as e:
            logger.error(f"Error checking system health: {e}")
        
        return health
    
    def _get_cpu_temperature(self) -> Optional[float]:
        """Get CPU temperature on Raspberry Pi."""
        try:
            temp_file = Path("/sys/class/thermal/thermal_zone0/temp")
            if temp_file.exists():
                temp = int(temp_file.read_text()) / 1000.0
                return temp
        except:
            pass
        return None


# Global instance
_optimizer_instance = None


def get_optimizer() -> RaspberryPiOptimizer:
    """Get global optimizer instance (singleton)."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = RaspberryPiOptimizer()
    return _optimizer_instance


def is_raspberry_pi() -> bool:
    """Quick check if running on Raspberry Pi."""
    try:
        return Path("/proc/device-tree/model").exists()
    except:
        return False


def apply_optimizations(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply Raspberry Pi optimizations to configuration.
    
    Args:
        config: Base configuration dictionary
        
    Returns:
        Optimized configuration
    """
    optimizer = get_optimizer()
    return optimizer.get_optimized_config(config)
