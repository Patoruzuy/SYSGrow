"""
Plant Harvest Service

Generates comprehensive harvest reports including energy consumption,
health history, and lifecycle analytics.
"""
from typing import Dict, List, Optional, TYPE_CHECKING
from datetime import datetime, timedelta
import json
import logging

if TYPE_CHECKING:
    from infrastructure.database.repositories.analytics import AnalyticsRepository

logger = logging.getLogger(__name__)


class PlantHarvestService:
    """
    Service for generating comprehensive plant harvest reports.
    
    Tracks full plant lifecycle from planting to harvest including:
    - Energy consumption by growth stage
    - Device usage breakdown
    - Light exposure hours
    - Health incidents
    - Environmental conditions
    - Yield and efficiency metrics
    """
    
    def __init__(self, analytics_repo: 'AnalyticsRepository'):
        """
        Initialize harvest service.
        
        Args:
            analytics_repo: AnalyticsRepository for database access
        """
        self.analytics_repo = analytics_repo
    
    def generate_harvest_report(
        self, 
        plant_id: int,
        harvest_weight_grams: float = 0.0,
        quality_rating: int = 3,
        notes: str = ""
    ) -> Dict:
        """
        Generate comprehensive harvest report for a plant.
        
        Args:
            plant_id: Plant ID
            harvest_weight_grams: Harvest weight in grams
            quality_rating: Quality rating (1-5 scale)
            notes: Optional harvest notes
            
        Returns:
            Complete harvest report dictionary
        """
        try:
            # Get plant info
            plant_info = self.analytics_repo.get_plant_info(plant_id)
            if not plant_info:
                raise ValueError(f"Plant {plant_id} not found")
            
            # Convert Row to dict for easier access
            plant_dict = dict(plant_info) if hasattr(plant_info, 'keys') else plant_info
            
            # Calculate lifecycle dates
            planted_date = plant_dict.get('planted_date') or plant_dict.get('created_at')
            if not planted_date:
                # Fallback to current date minus days_in_stage if no date available
                planted_date = (datetime.now() - timedelta(days=plant_dict.get('days_in_stage', 0))).isoformat()
            
            harvested_date = datetime.now()
            
            # Parse planted_date if it's a string
            if isinstance(planted_date, str):
                try:
                    planted_dt = datetime.fromisoformat(planted_date)
                except ValueError:
                    # Try parsing as datetime string
                    planted_dt = datetime.strptime(planted_date, '%Y-%m-%d %H:%M:%S')
            else:
                planted_dt = planted_date
                
            total_days = (harvested_date - planted_dt).days
            
            # Get energy summary
            energy_summary = self._get_energy_summary(plant_id, planted_dt, harvested_date)
            
            # Get health history
            health_summary = self._get_health_summary(plant_id)
            
            # Get environmental averages
            env_averages = self._get_environmental_averages(plant_id)
            
            # Get light exposure
            light_summary = self._get_light_summary(plant_id)
            
            # Calculate efficiency metrics
            efficiency = self._calculate_efficiency(
                energy_summary['total_kwh'],
                energy_summary['total_cost'],
                harvest_weight_grams
            )
            
            # Build comprehensive report
            report = {
                'harvest_id': None,  # Will be set after DB insert
                'plant_id': plant_id,
                'plant_name': plant_dict.get('name', 'Unknown'),
                'unit_id': plant_dict.get('unit_id'),
                
                'lifecycle': {
                    'planted_date': planted_date if isinstance(planted_date, str) else planted_date.isoformat(),
                    'harvested_date': harvested_date.isoformat(),
                    'total_days': total_days,
                    'stages': self._get_stage_durations(plant_dict)
                },
                
                'energy_consumption': energy_summary,
                'light_exposure': light_summary,
                'environmental_conditions': env_averages,
                'health_summary': health_summary,
                
                'yield': {
                    'weight_grams': harvest_weight_grams,
                    'quality_rating': quality_rating,
                    'notes': notes
                },
                
                'efficiency_metrics': efficiency,
                
                'recommendations': self._generate_recommendations(
                    energy_summary, health_summary, env_averages, total_days
                )
            }
            
            # Save to database
            summary_data = self._prepare_db_summary(report)
            harvest_id = self.analytics_repo.save_harvest_summary(plant_id, summary_data)
            report['harvest_id'] = harvest_id
            
            logger.info(f"Generated harvest report for plant {plant_id} (harvest_id: {harvest_id})")
            return report
            
        except Exception as e:
            logger.error(f"Failed to generate harvest report for plant {plant_id}: {e}")
            raise
    
    def _get_energy_summary(self, plant_id: int, planted_date: datetime, harvested_date: datetime) -> Dict:
        """Get energy consumption summary"""
        try:
            # Get total energy for plant
            with self.analytics_repo._backend.connection() as conn:
                result = conn.execute("""
                    SELECT 
                        SUM(er.energy_kwh) as total_kwh,
                        AVG(er.power_watts) as avg_power
                    FROM EnergyReadings er
                    JOIN Plants p ON p.unit_id = er.unit_id
                    WHERE p.plant_id = ?
                """, (plant_id,)).fetchone()
                
                total_kwh = result['total_kwh'] or 0.0
                avg_power = result['avg_power'] or 0.0
                
                # Get by stage
                by_stage_results = conn.execute("""
                    SELECT 
                        er.growth_stage as growth_stage,
                        SUM(er.energy_kwh) as stage_kwh,
                        AVG(er.power_watts) as stage_power
                    FROM EnergyReadings er
                    JOIN Plants p ON p.unit_id = er.unit_id
                    WHERE p.plant_id = ?
                    GROUP BY er.growth_stage
                """, (plant_id,)).fetchall()
                
                by_stage = {row['growth_stage']: row['stage_kwh'] for row in by_stage_results if row['growth_stage']}
                
                # Estimate cost (assume $0.20/kWh as default)
                cost_per_kwh = 0.20
                total_cost = total_kwh * cost_per_kwh
                cost_by_stage = {stage: kwh * cost_per_kwh for stage, kwh in by_stage.items()}
            
            return {
                'total_kwh': round(total_kwh, 2),
                'total_cost': round(total_cost, 2),
                'avg_daily_power_watts': round(avg_power, 2),
                'by_stage': by_stage,
                'cost_by_stage': cost_by_stage,
                'by_device': {}  # TODO: Implement device breakdown
            }
        except Exception as e:
            logger.error(f"Failed to get energy summary: {e}")
            return {'total_kwh': 0.0, 'total_cost': 0.0, 'avg_daily_power_watts': 0.0, 'by_stage': {}, 'cost_by_stage': {}, 'by_device': {}}
    
    def _get_health_summary(self, plant_id: int) -> Dict:
        """Get health incident summary"""
        try:
            # This would query PlantHealthLogs table
            # Simplified for now
            return {
                'total_incidents': 0,
                'incidents': [],
                'disease_free_days': 0,
                'pest_free_days': 0,
                'avg_health_score': 95
            }
        except Exception as e:
            logger.warning(f"Failed to get health summary: {e}")
            return {
                'total_incidents': 0,
                'incidents': [],
                'disease_free_days': 0,
                'pest_free_days': 0,
                'avg_health_score': 0
            }
    
    def _get_environmental_averages(self, plant_id: int) -> Dict:
        """Get environmental condition averages"""
        try:
            avg_temp = self.analytics_repo.get_average_temperature(plant_id)
            avg_humidity = self.analytics_repo.get_average_humidity(plant_id)
            
            return {
                'temperature': {
                    'avg': round(avg_temp, 1),
                    'min': 0.0,  # Would query from sensor history
                    'max': 0.0,
                    'optimal_range': '22-26°C',
                    'within_range_percent': 90
                },
                'humidity': {
                    'avg': round(avg_humidity, 1),
                    'min': 0.0,
                    'max': 0.0,
                    'optimal_range': '60-70%',
                    'within_range_percent': 85
                },
                'co2': {
                    'avg': 0,
                    'optimal': '400-1000 ppm'
                }
            }
        except Exception as e:
            logger.warning(f"Failed to get environmental averages: {e}")
            return {
                'temperature': {'avg': 0, 'min': 0, 'max': 0},
                'humidity': {'avg': 0, 'min': 0, 'max': 0},
                'co2': {'avg': 0}
            }
    
    def _get_light_summary(self, plant_id: int) -> Dict:
        """Get light exposure summary"""
        try:
            total_hours = self.analytics_repo.get_total_light_hours(plant_id)
            
            return {
                'total_hours': round(total_hours, 1),
                'by_stage': {},  # Would calculate per stage
                'total_dli': 0  # Daily Light Integral
            }
        except Exception as e:
            logger.warning(f"Failed to get light summary: {e}")
            return {
                'total_hours': 0.0,
                'by_stage': {},
                'total_dli': 0
            }
    
    def _get_stage_durations(self, plant_info: Dict) -> Dict:
        """Get duration in each growth stage"""
        # This would parse the plant's growth stage history
        # Simplified for now
        return {
            'seedling': {'days': 7, 'dates': 'N/A'},
            'vegetative': {'days': 21, 'dates': 'N/A'},
            'flowering': {'days': 18, 'dates': 'N/A'}
        }
    
    def _calculate_efficiency(self, total_kwh: float, total_cost: float, 
                             harvest_weight_grams: float) -> Dict:
        """Calculate efficiency metrics"""
        if harvest_weight_grams > 0 and total_kwh > 0:
            grams_per_kwh = harvest_weight_grams / total_kwh
            cost_per_gram = total_cost / harvest_weight_grams
            cost_per_pound = cost_per_gram * 453.592  # grams in a pound
            
            return {
                'grams_per_kwh': round(grams_per_kwh, 2),
                'cost_per_gram': round(cost_per_gram, 3),
                'cost_per_pound': round(cost_per_pound, 2),
                'energy_efficiency_rating': self._get_efficiency_rating(grams_per_kwh)
            }
        
        return {
            'grams_per_kwh': 0.0,
            'cost_per_gram': 0.0,
            'cost_per_pound': 0.0,
            'energy_efficiency_rating': 'N/A'
        }
    
    def _get_efficiency_rating(self, grams_per_kwh: float) -> str:
        """Rate energy efficiency"""
        if grams_per_kwh >= 5.0:
            return 'Excellent'
        elif grams_per_kwh >= 3.0:
            return 'Good'
        elif grams_per_kwh >= 1.5:
            return 'Average'
        else:
            return 'Poor'
    
    def _generate_recommendations(self, energy_summary: Dict, health_summary: Dict,
                                  env_averages: Dict, total_days: int) -> Dict:
        """Generate recommendations for next grow"""
        recommendations = {
            'next_grow': [],
            'cost_optimization': []
        }
        
        # Health-based recommendations
        if health_summary['avg_health_score'] >= 90:
            recommendations['next_grow'].append(
                "Excellent health score! Maintain current practices."
            )
        elif health_summary['avg_health_score'] < 70:
            recommendations['next_grow'].append(
                "Consider improving environmental controls to boost plant health."
            )
        
        # Energy optimization
        total_kwh = energy_summary.get('total_kwh', 0)
        if total_kwh > 0:
            recommendations['cost_optimization'].append(
                f"Total energy used: {total_kwh} kWh. Consider LED efficiency upgrades."
            )
        
        # Duration recommendations
        if total_days > 60:
            recommendations['next_grow'].append(
                "Long growing cycle. Consider faster-growing varieties."
            )
        
        return recommendations
    
    def _prepare_db_summary(self, report: Dict) -> Dict:
        """Prepare summary data for database storage"""
        # Helper to parse cost values (handles both string "$X.XX" and float X.XX)
        def parse_cost(value):
            if isinstance(value, str):
                return float(value.replace('$', '').replace(',', ''))
            return float(value) if value else 0.0
        
        return {
            'unit_id': report.get('unit_id'),
            'planted_date': report['lifecycle']['planted_date'],
            'harvested_date': report['lifecycle']['harvested_date'],
            'total_days': report['lifecycle']['total_days'],
            'seedling_days': report['lifecycle']['stages']['seedling']['days'],
            'vegetative_days': report['lifecycle']['stages']['vegetative']['days'],
            'flowering_days': report['lifecycle']['stages']['flowering']['days'],
            'total_energy_kwh': report['energy_consumption']['total_kwh'],
            'energy_by_stage': json.dumps(report['energy_consumption']['by_stage']),
            'total_cost': parse_cost(report['energy_consumption']['total_cost']),
            'cost_by_stage': json.dumps(report['energy_consumption'].get('cost_by_stage', {})),
            'device_usage': json.dumps(report['energy_consumption']['by_device']),
            'avg_daily_power_watts': report['energy_consumption'].get('avg_daily_power_watts', 0.0),
            'total_light_hours': report['light_exposure']['total_hours'],
            'light_hours_by_stage': json.dumps(report['light_exposure']['by_stage']),
            'avg_ppfd': 0.0,
            'health_incidents': json.dumps(report['health_summary']['incidents']),
            'disease_days': 0,
            'pest_days': 0,
            'avg_health_score': report['health_summary']['avg_health_score'],
            'avg_temperature': report['environmental_conditions']['temperature']['avg'],
            'avg_humidity': report['environmental_conditions']['humidity']['avg'],
            'avg_co2': report['environmental_conditions']['co2']['avg'],
            'harvest_weight_grams': report['yield']['weight_grams'],
            'quality_rating': report['yield']['quality_rating'],
            'notes': report['yield']['notes'],
            'grams_per_kwh': report['efficiency_metrics']['grams_per_kwh'],
            'cost_per_gram': parse_cost(report['efficiency_metrics']['cost_per_gram']),
        }
    
    def get_harvest_reports(self, unit_id: Optional[int] = None) -> List[Dict]:
        """
        Get all harvest reports, optionally filtered by unit.
        
        Args:
            unit_id: Optional unit ID filter
            
        Returns:
            List of harvest summaries
        """
        try:
            return self.analytics_repo.get_all_harvest_reports(unit_id)
        except Exception as e:
            logger.error(f"Failed to get harvest reports: {e}")
            return []
    
    def compare_harvests(self, unit_id: int, limit: int = 10) -> List[Dict]:
        """
        Get harvest efficiency trends for comparison.
        
        Args:
            unit_id: Unit ID
            limit: Number of harvests to compare
            
        Returns:
            List of harvest efficiency metrics
        """
        try:
            return self.analytics_repo.get_harvest_efficiency_trends(unit_id, limit)
        except Exception as e:
            logger.error(f"Failed to compare harvests: {e}")
            return []
    
    def cleanup_after_harvest(
        self,
        plant_id: int,
        delete_plant_data: bool = True
    ) -> Dict[str, int]:
        """
        Clean up plant-specific data after harvest.
        
        IMPORTANT: This only deletes PLANT-SPECIFIC data. Shared data is preserved:
        - Energy readings are KEPT (needed for other plants' reports)
        - Sensor readings are KEPT (shared across unit)
        - Environmental data is KEPT (shared across unit)
        - Device history is KEPT (affects multiple plants)
        
        Only deleted if delete_plant_data=True:
        - Plant record (from Plants table)
        - Plant health logs (PlantHealth, PlantHealthLogs)
        - Plant-sensor associations (PlantSensors)
        - Plant-unit associations (GrowthUnitPlants)
        - AI decisions specific to this plant
        
        Args:
            plant_id: Plant ID to clean up
            delete_plant_data: If True, delete plant-specific records
            
        Returns:
            Dictionary with counts of deleted records by type
        """
        deleted_counts = {
            'plant_health_logs': 0,
            'plant_sensors': 0,
            'plant_unit_associations': 0,
            'ai_decision_logs': 0,
            'plant_record': 0
        }
        
        if not delete_plant_data:
            logger.info(f"Skipping plant data deletion for plant {plant_id} (delete_plant_data=False)")
            return deleted_counts
        
        try:
            with self.analytics_repo._backend.connection() as conn:
                # 1. Delete plant health logs (plant-specific)
                deleted_counts['plant_health_logs'] = 0
                for table_name in ("PlantHealthLogs", "PlantHealth"):
                    try:
                        cursor = conn.execute(
                            f"DELETE FROM {table_name} WHERE plant_id = ?",
                            (plant_id,),
                        )
                        deleted_counts['plant_health_logs'] += cursor.rowcount
                    except Exception as exc:
                        if "no such table" in str(exc).lower():
                            continue
                        raise
                
                # 2. Delete plant-sensor associations (plant-specific)
                cursor = conn.execute(
                    "DELETE FROM PlantSensors WHERE plant_id = ?",
                    (plant_id,)
                )
                deleted_counts['plant_sensors'] = cursor.rowcount
                
                # 3. Delete plant-unit associations (plant-specific)
                cursor = conn.execute(
                    "DELETE FROM GrowthUnitPlants WHERE plant_id = ?",
                    (plant_id,)
                )
                deleted_counts['plant_unit_associations'] = cursor.rowcount
                
                # 4. Delete AI decision logs for this plant (optional - may want to keep for learning)
                # Uncomment if you want to delete AI decisions:
                # cursor = conn.execute(
                #     "DELETE FROM AI_DecisionLogs WHERE plant_id = ?",
                #     (plant_id,)
                # )
                # deleted_counts['ai_decision_logs'] = cursor.rowcount
                
                # 5. Clear active_plant_id from GrowthUnits (don't delete the unit!)
                conn.execute(
                    """
                    UPDATE GrowthUnits 
                    SET active_plant_id = NULL 
                    WHERE active_plant_id = ?
                    """,
                    (plant_id,)
                )
                
                # 6. Delete the plant record itself (LAST!)
                cursor = conn.execute(
                    "DELETE FROM Plants WHERE plant_id = ?",
                    (plant_id,)
                )
                deleted_counts['plant_record'] = cursor.rowcount
                
            logger.info(
                f"Cleaned up plant {plant_id}: "
                f"Health logs: {deleted_counts['plant_health_logs']}, "
                f"Sensor associations: {deleted_counts['plant_sensors']}, "
                f"Unit associations: {deleted_counts['plant_unit_associations']}, "
                f"Plant record: {deleted_counts['plant_record']}"
            )
            
            return deleted_counts
            
        except Exception as e:
            logger.error(f"Failed to cleanup plant {plant_id}: {e}")
            raise
    
    def harvest_and_cleanup(
        self,
        plant_id: int,
        harvest_weight_grams: float = 0.0,
        quality_rating: int = 3,
        notes: str = "",
        delete_plant_data: bool = True
    ) -> Dict:
        """
        Generate harvest report AND optionally clean up plant data.
        
        This is a convenience method that:
        1. Generates the comprehensive harvest report
        2. Saves it to PlantHarvestSummary table
        3. Optionally deletes plant-specific data (preserves shared data)
        
        Args:
            plant_id: Plant ID
            harvest_weight_grams: Harvest weight in grams
            quality_rating: Quality rating (1-5 scale)
            notes: Optional harvest notes
            delete_plant_data: If True, delete plant-specific records after harvest
            
        Returns:
            Dictionary with harvest report and cleanup results
        """
        try:
            # Generate harvest report first
            report = self.generate_harvest_report(
                plant_id=plant_id,
                harvest_weight_grams=harvest_weight_grams,
                quality_rating=quality_rating,
                notes=notes
            )
            
            # Clean up plant data if requested
            cleanup_results = None
            if delete_plant_data:
                cleanup_results = self.cleanup_after_harvest(
                    plant_id=plant_id,
                    delete_plant_data=True
                )
            
            return {
                'harvest_report': report,
                'cleanup_results': cleanup_results,
                'plant_data_deleted': delete_plant_data
            }
            
        except Exception as e:
            logger.error(f"Failed to harvest and cleanup plant {plant_id}: {e}")
            raise
