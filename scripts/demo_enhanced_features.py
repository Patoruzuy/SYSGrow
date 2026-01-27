"""
Example implementation showing how to integrate all enhanced features

⚠️ DEPRECATED: This script uses the old ZigBeeEnergyMonitor which has been replaced
by EnergyMonitoringService in ActuatorManager. This script is kept for reference only.

For current energy monitoring usage, see:
- infrastructure/hardware/actuators/services/energy_monitoring.py
- ActuatorManager.energy_monitoring property
- workers/USAGE_EXAMPLE.md for modern architecture patterns
"""

# This script is deprecated and will not run - imports are broken
import sys
sys.exit("This demo script is deprecated. See workers/USAGE_EXAMPLE.md for modern usage patterns.")

# Original imports (broken - kept for reference):
# import asyncio
# import logging
# from datetime import datetime, timedelta
# from infrastructure.database.sqlite_handler import SQLiteDatabaseHandler
# from app.workers.task_scheduler import TaskScheduler

# Import enhanced modules
try:
    from app.hardware.devices.zigbee_energy_monitor import ZigBeeEnergyMonitor
    from app.services.ai.plant_health_monitor import PlantHealthMonitor, HealthStatus
    from app.domain.plant_health import PlantHealthObservation
    from app.workers.environment_collector import EnvironmentInfoCollector, EnvironmentInfo
    from app.services.ai.ml_trainer import MLTrainerService
    from app.services.ai.model_registry import ModelRegistry
    from infrastructure.database.repositories.ai import AIHealthDataRepository, AITrainingDataRepository
    from infrastructure.database.schema_upgrade import upgrade_database_schema
    from pathlib import Path
    ENHANCED_FEATURES = True
except ImportError as e:
    print(f"Enhanced features not available: {e}")
    ENHANCED_FEATURES = False

class SYSGrowEnhancedDemo:
    """
    Demo class showing complete integration of enhanced SYSGrow features
    """
    
    def __init__(self, db_path="database/sysgrow.db"):
        self.db_path = db_path
        self.database_handler = SQLiteDatabaseHandler(db_path)
        
        if ENHANCED_FEATURES:
            self.setup_enhanced_features()
        else:
            print("Enhanced features not available - demo will be limited")
    
    def setup_enhanced_features(self):
        """Initialize all enhanced components"""
        # Upgrade database schema
        upgrade_database_schema(self.db_path)
        
        # Initialize components
        self.energy_monitor = ZigBeeEnergyMonitor(self.database_handler)
        repo_health = AIHealthDataRepository(self.database_handler)
        self.plant_health_monitor = PlantHealthMonitor(repo_health=repo_health)
        self.environment_collector = EnvironmentInfoCollector(self.database_handler)
        training_repo = AITrainingDataRepository(self.database_handler)
        model_registry = ModelRegistry(base_path=Path("models"))
        self.ml_trainer = MLTrainerService(
            training_data_repo=training_repo,
            model_registry=model_registry,
        )
        
        # Initialize enhanced scheduler
        self.scheduler = TaskScheduler(self.database_handler)
        
        print("✅ Enhanced features initialized successfully")
    
    async def demo_energy_monitoring(self):
        """Demonstrate energy monitoring capabilities"""
        print("\n🔌 Energy Monitoring Demo")
        print("=" * 50)
        
        try:
            # Initialize ZigBee network
            await self.energy_monitor.initialize_zigbee_network()
            
            # Discover energy monitors
            devices = await self.energy_monitor.discover_energy_monitors()
            print(f"📡 Discovered {len(devices)} energy monitoring devices")
            
            # Simulate energy readings
            for device in devices:
                reading = await self.energy_monitor.read_energy_data(device['ieee_address'])
                if reading:
                    print(f"⚡ Device {device['ieee_address']}: {reading.power}W")
            
            # Get consumption estimates for unit 1
            device_states = {
                'lights': True,
                'fan': True,
                'extractor': True,
                'heater': False,
                'humidifier': False,
                'water_pump': False
            }
            
            estimates = self.energy_monitor.estimate_device_consumption(1, device_states)
            print(f"\n💡 Device Power Estimates for Unit 1:")
            for device, estimate in estimates.items():
                print(f"  {device}: {estimate.estimated_power:.1f}W (confidence: {estimate.confidence:.2f})")
            
            # Calculate cost estimates
            costs = self.energy_monitor.calculate_cost_estimate(1)
            print(f"\n💰 Cost Estimates:")
            print(f"  Daily: ${costs['daily_cost']}")
            print(f"  Monthly: ${costs['monthly_cost']}")
            print(f"  Yearly: ${costs['yearly_cost']}")
            
        except Exception as e:
            print(f"❌ Energy monitoring demo failed: {e}")
    
    def demo_environment_setup(self):
        """Demonstrate environment information collection"""
        print("\n🌍 Environment Setup Demo")
        print("=" * 50)
        
        try:
            # Create sample environment info
            env_info = EnvironmentInfo(
                unit_id=1,
                room_width=3.0,
                room_length=4.0,
                room_height=2.5,
                room_volume=0,  # Will be calculated
                insulation_type='good',
                ventilation_type='forced',
                window_area=2.0,
                light_source_type='led',
                ambient_light_hours=8.0,
                location_climate='temperate',
                outdoor_temperature_avg=20.0,
                outdoor_humidity_avg=60.0,
                electricity_cost_per_kwh=0.12
            )
            
            # Save environment info
            success = self.environment_collector.save_environment_info(env_info)
            if success:
                print(f"✅ Environment info saved for unit 1")
                print(f"📐 Room volume: {env_info.room_volume} m³")
            
            # Calculate metrics
            metrics = self.environment_collector.calculate_climate_metrics(1)
            if metrics:
                print(f"\n📊 Climate Metrics:")
                print(f"  Air changes per hour: {metrics.air_changes_per_hour}")
                print(f"  Heat loss coefficient: {metrics.heat_loss_coefficient}")
                print(f"  Lighting efficiency: {metrics.lighting_efficiency}")
                print(f"  Ventilation efficiency: {metrics.ventilation_efficiency}")
            
            # Get recommendations
            recommendations = self.environment_collector.get_climate_recommendations(1)
            print(f"\n💡 Recommendations:")
            for rec in recommendations['recommendations']:
                print(f"  {rec['category']}: {rec['recommended']} (Priority: {rec['priority']})")
            
            # Energy estimates
            energy_est = self.environment_collector.estimate_energy_requirements(1)
            print(f"\n⚡ Energy Requirements:")
            print(f"  Total power: {energy_est['total_watts']}W")
            print(f"  Daily consumption: {energy_est['daily_kwh']} kWh")
            print(f"  Monthly cost: ${energy_est['monthly_cost']}")
            
        except Exception as e:
            print(f"❌ Environment demo failed: {e}")
    
    def demo_plant_health_monitoring(self):
        """Demonstrate plant health monitoring"""
        print("\n🌱 Plant Health Monitoring Demo")
        print("=" * 50)
        
        try:
            # Record a health observation
            observation = PlantHealthObservation(
                unit_id=1,
                plant_id=1,
                health_status=HealthStatus.STRESSED,
                symptoms=['yellowing_leaves', 'brown_spots'],
                disease_type=None,
                severity_level=3,
                affected_parts=['leaves'],
                environmental_factors={
                    'high_humidity': True,
                    'poor_air_circulation': True
                },
                treatment_applied=None,
                notes="Lower leaves showing yellowing with small brown spots"
            )
            
            health_id = self.plant_health_monitor.record_health_observation(observation)
            print(f"✅ Health observation recorded: {health_id}")
            
            # Get health recommendations
            recommendations = self.plant_health_monitor.get_health_recommendations(1)
            print(f"\n🏥 Health Analysis:")
            print(f"  Status: {recommendations['status']}")
            print(f"  Trend: {recommendations['trend']}")
            
            if recommendations['symptom_recommendations']:
                print(f"\n💊 Treatment Recommendations:")
                for rec in recommendations['symptom_recommendations']:
                    print(f"  Issue: {rec['issue']}")
                    print(f"  Likely causes: {', '.join(rec['likely_causes'])}")
                    print(f"  Actions: {', '.join(rec['recommended_actions'])}")
            
            if recommendations['environmental_recommendations']:
                print(f"\n🌡️ Environmental Issues:")
                for env_rec in recommendations['environmental_recommendations']:
                    print(f"  {env_rec['factor']}: {env_rec['issue']} (Action: {env_rec['action']})")
            
        except Exception as e:
            print(f"❌ Plant health demo failed: {e}")
    
    def demo_ml_training(self):
        """Demonstrate ML training system"""
        print("\n🤖 ML Training Demo")
        print("=" * 50)
        
        try:
            # Check if we have enough data for training
            df = self.ml_trainer.collect_training_data("climate", unit_id=1, days=7)
            print(f"📊 Available training data: {len(df)} samples")
            
            if len(df) < 10:  # Reduced for demo
                print("⚠️ Not enough data for full training demo")
                print("   Generating sample data...")
                
                # This would normally be collected over time
                # For demo, we'll just show the structure
                print("📈 Training data structure:")
                print("  Environmental features: temperature, humidity, soil_moisture, etc.")
                print("  Energy features: power consumption by device")
                print("  Context features: room volume, insulation, climate")
                print("  Plant health features: health score, growth rate")
                
            else:
                # Run actual training
                print("🚀 Starting ML training...")
                results = self.ml_trainer.train_climate_model(unit_id=1, days=7)
                
                if results.get('success'):
                    print(f"✅ Training completed successfully!")
                    print(f"   Data points used: {results.get('training_samples')}")
                    print(f"   Training duration: {results.get('training_time_seconds')}s")
                    
                    # Show model performance
                    print(f"\n📈 Climate Control Model Results:")
                    for target, metrics in (results.get("results") or {}).items():
                        print(f"   {target}: test_score = {metrics.get('test_score')}")
                else:
                    print(f"❌ Training failed: {results.get('error', 'Unknown error')}")
            
            # Automated retraining handled by AutomatedRetrainingService in the main app.
            print("\n⏰ Automated retraining is managed by the runtime scheduler.")
            
        except Exception as e:
            print(f"❌ ML training demo failed: {e}")
    
    def demo_scheduler_features(self):
        """Demonstrate enhanced scheduler capabilities"""
        print("\n📅 Enhanced Scheduler Demo")
        print("=" * 50)
        
        try:
            # Show system status
            status = self.scheduler.get_system_status()
            print(f"🔧 System Status:")
            print(f"  Scheduler active: {status['scheduler_active']}")
            print(f"  ML training available: {status['features']['ml_training']}")
            print(f"  Energy monitoring available: {status['features']['energy_monitoring']}")
            print(f"  Plant health monitoring available: {status['features']['plant_health_monitoring']}")
            
            if 'last_ml_training' in status:
                last_training = status['last_ml_training']
                print(f"\n🤖 Last ML Training:")
                print(f"  Session: {last_training['session_id']}")
                print(f"  Status: {last_training['status']}")
                print(f"  Accuracy: {last_training['accuracy']:.3f}")
                print(f"  Data points: {last_training['data_points']}")
            
            # Schedule additional tasks
            print(f"\n⏱️ Scheduling enhanced tasks:")
            print("  ✅ ML training: Daily at 3:00 AM")
            print("  ✅ Data collection: Every hour")
            print("  ✅ Energy monitoring: Every 15 minutes")
            print("  ✅ Plant health check: Daily at 9:00 AM")
            
        except Exception as e:
            print(f"❌ Scheduler demo failed: {e}")
    
    async def run_complete_demo(self):
        """Run the complete demo of all enhanced features"""
        print("🚀 SYSGrow Enhanced Features Demo")
        print("=" * 60)
        print("This demo showcases the new capabilities:")
        print("• ZigBee Energy Monitoring")
        print("• Plant Health Tracking")
        print("• Environment Information Collection")
        print("• Automated ML Training")
        print("• Enhanced Task Scheduling")
        print("=" * 60)
        
        if not ENHANCED_FEATURES:
            print("❌ Enhanced features not available")
            print("Please install required dependencies:")
            print("  pip install scikit-learn pandas numpy schedule zigpy")
            return
        
        try:
            # Run all demos
            await self.demo_energy_monitoring()
            self.demo_environment_setup()
            self.demo_plant_health_monitoring()
            self.demo_ml_training()
            self.demo_scheduler_features()
            
            print("\n🎉 Demo completed successfully!")
            print("\nNext steps:")
            print("1. Set up actual ZigBee coordinator and energy monitors")
            print("2. Configure environment information for your grow units")
            print("3. Start recording plant health observations")
            print("4. Let the system collect data for a few days")
            print("5. Review ML training results and predictions")
            
        except Exception as e:
            print(f"❌ Demo failed: {e}")
            import traceback
            traceback.print_exc()


async def main():
    """Main demo function"""
    demo = SYSGrowEnhancedDemo()
    await demo.run_complete_demo()


if __name__ == "__main__":
    # Run the demo
    asyncio.run(main())
