"""
Environmental Health Scorer
============================
Infers leaf health from environmental sensor data.

Integrates with:
- disease_predictor.py (risk assessment)
- plant_health_monitor.py (health correlations)
- threshold_service.py (plant-specific optimal ranges)

This is a NON-INVASIVE addition that works with your existing data flow.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass
from datetime import datetime, timedelta

from app.enums import RiskLevel
from app.utils.time import utc_now

if TYPE_CHECKING:
    from app.services.application.threshold_service import ThresholdService
    from infrastructure.database.repositories.analytics import AnalyticsRepository

logger = logging.getLogger(__name__)


@dataclass
class LeafHealthScore:
    """Environmental-based leaf health assessment"""
    
    unit_id: int
    timestamp: datetime
    
    # Overall health (0.0-1.0, where 1.0 = perfect)
    overall_health: float
    
    # Component scores
    temperature_score: float
    humidity_score: float
    vpd_score: float
    moisture_score: float
    stress_score: float
    
    # Risk indicators
    disease_risk: RiskLevel
    stress_factors: List[str]
    
    # Predicted leaf issues
    predicted_issues: List[str]
    
    # Recommendations
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for WebSocket/API"""
        return {
            'unit_id': self.unit_id,
            'timestamp': self.timestamp.isoformat(),
            'overall_health': round(self.overall_health, 2),
            'component_scores': {
                'temperature': round(self.temperature_score, 2),
                'humidity': round(self.humidity_score, 2),
                'vpd': round(self.vpd_score, 2),
                'moisture': round(self.moisture_score, 2),
                'stress': round(self.stress_score, 2)
            },
            'disease_risk': self.disease_risk.value,
            'stress_factors': self.stress_factors,
            'predicted_issues': self.predicted_issues,
            'recommendations': self.recommendations
        }


class EnvironmentalLeafHealthScorer:
    """
    Infer leaf health from environmental conditions.
    
    Uses existing sensors + your threshold_service for plant-specific ranges.
    Integrates with your disease_predictor for risk assessment.
    """
    
    # VPD ranges (kPa) - from psychrometrics
    VPD_OPTIMAL_VEG = (0.8, 1.2)
    VPD_OPTIMAL_FLOWER = (1.0, 1.5)
    VPD_STRESS_LOW = 0.4
    VPD_STRESS_HIGH = 1.8
    
    # Stress accumulation thresholds (hours)
    STRESS_THRESHOLD_MINOR = 6
    STRESS_THRESHOLD_MODERATE = 12
    STRESS_THRESHOLD_SEVERE = 24
    
    def __init__(
        self,
        threshold_service: Optional[ThresholdService] = None,
        analytics_repo: Optional[AnalyticsRepository] = None
    ):
        """
        Initialize environmental health scorer.
        
        Args:
            threshold_service: For plant-specific optimal ranges
            analytics_repo: For historical sensor data
        """
        self.threshold_service = threshold_service
        self.analytics_repo = analytics_repo
    
    def score_current_health(
        self,
        unit_id: int,
        current_conditions: Dict[str, float],
        plant_type: Optional[str] = None,
        growth_stage: Optional[str] = None
    ) -> LeafHealthScore:
        """
        Score leaf health from current environmental readings.
        
        Args:
            unit_id: Growth unit ID
            current_conditions: Dict with temperature, humidity, vpd, soil_moisture, etc.
            plant_type: Plant type for threshold lookup
            growth_stage: Growth stage for stage-specific ranges
            
        Returns:
            LeafHealthScore with assessment
        """
        try:
            # Get plant-specific thresholds
            thresholds = self._get_thresholds(plant_type, growth_stage)
            
            # Score individual components
            temp_score = self._score_temperature(
                current_conditions.get('temperature', 22.0),
                thresholds
            )
            
            humidity_score = self._score_humidity(
                current_conditions.get('humidity', 60.0),
                thresholds
            )
            
            vpd_score = self._score_vpd(
                current_conditions.get('vpd', 1.0),
                growth_stage
            )
            
            moisture_score = self._score_soil_moisture(
                current_conditions.get('soil_moisture', 60.0),
                thresholds
            )
            
            # Get historical stress
            stress_score, stress_factors = self._calculate_stress_score(
                unit_id, current_conditions
            )
            
            # Calculate overall health (weighted average)
            overall = (
                temp_score * 0.25 +
                humidity_score * 0.20 +
                vpd_score * 0.25 +
                moisture_score * 0.20 +
                stress_score * 0.10
            )
            
            # Determine disease risk
            disease_risk = self._assess_disease_risk(
                current_conditions, overall
            )
            
            # Predict issues
            predicted_issues = self._predict_leaf_issues(
                current_conditions, stress_factors, disease_risk
            )
            
            # Generate recommendations
            recommendations = self._generate_recommendations(
                current_conditions, thresholds, stress_factors, predicted_issues
            )
            
            return LeafHealthScore(
                unit_id=unit_id,
                timestamp=utc_now(),
                overall_health=overall,
                temperature_score=temp_score,
                humidity_score=humidity_score,
                vpd_score=vpd_score,
                moisture_score=moisture_score,
                stress_score=stress_score,
                disease_risk=disease_risk,
                stress_factors=stress_factors,
                predicted_issues=predicted_issues,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Failed to score leaf health: {e}", exc_info=True)
            return self._get_default_score(unit_id)
    
    def _get_thresholds(
        self, plant_type: Optional[str], growth_stage: Optional[str]
    ) -> Dict[str, Any]:
        """Get thresholds from threshold_service or defaults"""
        if self.threshold_service and plant_type:
            try:
                thresholds_obj = self.threshold_service.get_thresholds(
                    plant_type, growth_stage
                )
                return {
                    'temperature': thresholds_obj.temperature,
                    'humidity': thresholds_obj.humidity,
                    'soil_moisture': thresholds_obj.soil_moisture,
                    'temp_tolerance': 3.0,
                    'humidity_tolerance': 10.0,
                    'moisture_tolerance': 10.0
                }
            except Exception as e:
                logger.warning(f"Failed to get thresholds: {e}")
        
        # Generic defaults
        return {
            'temperature': 24.0,
            'humidity': 60.0,
            'soil_moisture': 65.0,
            'temp_tolerance': 3.0,
            'humidity_tolerance': 10.0,
            'moisture_tolerance': 10.0
        }
    
    def _score_temperature(
        self, temp: float, thresholds: Dict[str, Any]
    ) -> float:
        """Score temperature (1.0 = optimal)"""
        optimal = thresholds['temperature']
        tolerance = thresholds['temp_tolerance']
        
        deviation = abs(temp - optimal)
        
        if deviation <= tolerance:
            return 1.0
        elif deviation <= tolerance * 2:
            return 0.7
        elif deviation <= tolerance * 3:
            return 0.4
        else:
            return 0.2
    
    def _score_humidity(
        self, humidity: float, thresholds: Dict[str, Any]
    ) -> float:
        """Score humidity (1.0 = optimal)"""
        optimal = thresholds['humidity']
        tolerance = thresholds['humidity_tolerance']
        
        deviation = abs(humidity - optimal)
        
        if deviation <= tolerance:
            return 1.0
        elif deviation <= tolerance * 2:
            return 0.6
        elif deviation <= tolerance * 3:
            return 0.3
        else:
            return 0.1
    
    def _score_vpd(self, vpd: float, growth_stage: Optional[str]) -> float:
        """Score VPD (1.0 = optimal)"""
        # Use stage-specific optimal range
        if growth_stage and growth_stage.lower() in ['flowering', 'fruiting']:
            optimal_range = self.VPD_OPTIMAL_FLOWER
        else:
            optimal_range = self.VPD_OPTIMAL_VEG
        
        if optimal_range[0] <= vpd <= optimal_range[1]:
            return 1.0
        elif vpd < self.VPD_STRESS_LOW or vpd > self.VPD_STRESS_HIGH:
            return 0.2  # Severe stress
        elif vpd < optimal_range[0]:
            # Too low (fungal risk)
            deviation = optimal_range[0] - vpd
            return max(0.4, 1.0 - deviation * 2)
        else:
            # Too high (transpiration stress)
            deviation = vpd - optimal_range[1]
            return max(0.3, 1.0 - deviation * 1.5)
    
    def _score_soil_moisture(
        self, moisture: float, thresholds: Dict[str, Any]
    ) -> float:
        """Score soil moisture (1.0 = optimal)"""
        optimal = thresholds['soil_moisture']
        tolerance = thresholds['moisture_tolerance']
        
        deviation = abs(moisture - optimal)
        
        if deviation <= tolerance:
            return 1.0
        elif deviation <= tolerance * 2:
            return 0.6
        elif deviation <= tolerance * 3:
            return 0.3
        else:
            return 0.1
    
    def _calculate_stress_score(
        self, unit_id: int, current: Dict[str, float]
    ) -> tuple[float, List[str]]:
        """Calculate accumulated stress from historical data"""
        stress_factors = []
        
        if not self.analytics_repo:
            return 1.0, stress_factors
        
        try:
            # Get last 24 hours of data
            end_time = utc_now()
            start_time = end_time - timedelta(hours=24)
            
            sensor_df = self.analytics_repo.get_sensor_time_series(
                unit_id,
                start_time.isoformat(),
                end_time.isoformat(),
                interval_hours=1
            )
            
            if sensor_df.empty:
                return 1.0, stress_factors
            
            # Count stress hours
            temp_stress_hours = 0
            humidity_stress_hours = 0
            moisture_stress_hours = 0
            
            if 'temperature' in sensor_df.columns:
                # Cold stress (<15°C) or heat stress (>32°C)
                temp_stress_hours = (
                    (sensor_df['temperature'] < 15) | 
                    (sensor_df['temperature'] > 32)
                ).sum()
            
            if 'humidity' in sensor_df.columns:
                # Very high humidity (>85%) or very low (<30%)
                humidity_stress_hours = (
                    (sensor_df['humidity'] > 85) | 
                    (sensor_df['humidity'] < 30)
                ).sum()
            
            if 'soil_moisture' in sensor_df.columns:
                # Drought stress (<30%) or waterlogged (>90%)
                moisture_stress_hours = (
                    (sensor_df['soil_moisture'] < 30) | 
                    (sensor_df['soil_moisture'] > 90)
                ).sum()
            
            # Track stress factors
            if temp_stress_hours >= self.STRESS_THRESHOLD_MINOR:
                stress_factors.append('temperature_stress')
            if humidity_stress_hours >= self.STRESS_THRESHOLD_MINOR:
                stress_factors.append('humidity_stress')
            if moisture_stress_hours >= self.STRESS_THRESHOLD_MINOR:
                stress_factors.append('water_stress')
            
            # Calculate stress score
            total_stress_hours = (
                temp_stress_hours + humidity_stress_hours + moisture_stress_hours
            )
            
            if total_stress_hours == 0:
                return 1.0, stress_factors
            elif total_stress_hours < self.STRESS_THRESHOLD_MODERATE:
                return 0.8, stress_factors
            elif total_stress_hours < self.STRESS_THRESHOLD_SEVERE:
                return 0.5, stress_factors
            else:
                return 0.2, stress_factors
            
        except Exception as e:
            logger.warning(f"Failed to calculate stress score: {e}")
            return 1.0, stress_factors
    
    def _assess_disease_risk(
        self, current: Dict[str, float], health_score: float
    ) -> RiskLevel:
        """Assess disease risk from conditions"""
        humidity = current.get('humidity', 60.0)
        vpd = current.get('vpd', 1.0)
        
        # High humidity + low VPD = high fungal risk
        if humidity > 80 and vpd < 0.6:
            return RiskLevel.HIGH
        elif humidity > 75 and vpd < 0.8:
            return RiskLevel.MODERATE
        elif health_score < 0.5:
            return RiskLevel.MODERATE
        elif health_score < 0.7:
            return RiskLevel.LOW
        else:
            return RiskLevel.MINIMAL
    
    def _predict_leaf_issues(
        self,
        current: Dict[str, float],
        stress_factors: List[str],
        disease_risk: RiskLevel
    ) -> List[str]:
        """Predict likely leaf issues from conditions"""
        issues = []
        
        # Temperature-related
        temp = current.get('temperature', 22.0)
        if temp < 15:
            issues.append('chlorosis_risk')  # Cold-induced yellowing
        elif temp > 32:
            issues.append('leaf_burn_risk')
        
        # Humidity/VPD related
        humidity = current.get('humidity', 60.0)
        vpd = current.get('vpd', 1.0)
        
        if humidity > 85 or vpd < 0.5:
            issues.append('fungal_disease_risk')
        
        if vpd > 1.8:
            issues.append('wilting_risk')  # Excessive transpiration
        
        # Moisture-related
        moisture = current.get('soil_moisture', 60.0)
        if moisture < 35:
            issues.append('drought_stress')
            issues.append('wilting_risk')
        elif moisture > 85:
            issues.append('overwatering_risk')
            issues.append('root_rot_risk')
        
        # Stress accumulation
        if 'water_stress' in stress_factors:
            issues.append('nutrient_deficiency_risk')
        
        return list(set(issues))  # Remove duplicates
    
    def _generate_recommendations(
        self,
        current: Dict[str, float],
        thresholds: Dict[str, Any],
        stress_factors: List[str],
        predicted_issues: List[str]
    ) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []
        
        # Temperature
        temp = current.get('temperature', 22.0)
        optimal_temp = thresholds['temperature']
        if abs(temp - optimal_temp) > 3:
            if temp < optimal_temp:
                recommendations.append(
                    f"Increase temperature to {optimal_temp}°C (currently {temp:.1f}°C)"
                )
            else:
                recommendations.append(
                    f"Decrease temperature to {optimal_temp}°C (currently {temp:.1f}°C)"
                )
        
        # Humidity
        humidity = current.get('humidity', 60.0)
        optimal_humidity = thresholds['humidity']
        if abs(humidity - optimal_humidity) > 10:
            if humidity < optimal_humidity:
                recommendations.append(
                    f"Increase humidity to {optimal_humidity}% (currently {humidity:.1f}%)"
                )
            else:
                recommendations.append(
                    f"Decrease humidity to {optimal_humidity}% (currently {humidity:.1f}%)"
                )
        
        # VPD
        vpd = current.get('vpd', 1.0)
        if vpd < 0.5:
            recommendations.append("Increase VPD (improve air circulation, reduce humidity)")
        elif vpd > 1.6:
            recommendations.append("Decrease VPD (increase humidity or lower temperature)")
        
        # Specific issues
        if 'fungal_disease_risk' in predicted_issues:
            recommendations.append("⚠️ High fungal risk - improve air circulation, reduce humidity")
        
        if 'wilting_risk' in predicted_issues:
            recommendations.append("⚠️ Wilting risk - check soil moisture and reduce VPD")
        
        if 'drought_stress' in predicted_issues:
            recommendations.append("💧 Water plants - soil moisture is low")
        
        return recommendations
    
    def _get_default_score(self, unit_id: int) -> LeafHealthScore:
        """Return default score when calculation fails"""
        return LeafHealthScore(
            unit_id=unit_id,
            timestamp=utc_now(),
            overall_health=0.5,
            temperature_score=0.5,
            humidity_score=0.5,
            vpd_score=0.5,
            moisture_score=0.5,
            stress_score=0.5,
            disease_risk=RiskLevel.MODERATE,
            stress_factors=[],
            predicted_issues=[],
            recommendations=["Insufficient data for health assessment"]
        )
