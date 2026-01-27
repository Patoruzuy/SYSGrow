"""
Personalized Learning System
==============================
Adapts AI models to individual user's growing environment and patterns.

Features:
- User-specific model fine-tuning
- Environment fingerprinting (unique characteristics of each setup)
- Success pattern recognition
- Failure pattern learning
- Adaptive recommendations based on user's history
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path

# ML libraries lazy loaded in methods for faster startup
# import numpy as np
# import pandas as pd

if TYPE_CHECKING:
    from app.services.ai.model_registry import ModelRegistry
    from infrastructure.database.repositories.ai import AITrainingDataRepository

logger = logging.getLogger(__name__)


@dataclass
class EnvironmentProfile:
    """Profile of a user's unique growing environment."""
    
    user_id: int
    unit_id: int
    location_characteristics: Dict[str, Any]
    equipment_profile: Dict[str, Any]
    historical_patterns: Dict[str, Any]
    success_factors: List[str]
    challenge_areas: List[str]
    created_at: datetime
    updated_at: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'unit_id': self.unit_id,
            'location_characteristics': self.location_characteristics,
            'equipment_profile': self.equipment_profile,
            'historical_patterns': self.historical_patterns,
            'success_factors': self.success_factors,
            'challenge_areas': self.challenge_areas,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }


@dataclass
class GrowingSuccess:
    """Record of a successful grow cycle."""
    
    user_id: int
    unit_id: int
    plant_type: str
    plant_variety: Optional[str]
    start_date: datetime
    harvest_date: datetime
    total_yield: Optional[float]  # grams
    quality_rating: int  # 1-5
    growth_conditions: Dict[str, Any]
    lessons_learned: List[str]
    would_repeat: bool
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'user_id': self.user_id,
            'unit_id': self.unit_id,
            'plant_type': self.plant_type,
            'plant_variety': self.plant_variety,
            'start_date': self.start_date.isoformat(),
            'harvest_date': self.harvest_date.isoformat(),
            'days_to_harvest': (self.harvest_date - self.start_date).days,
            'total_yield': self.total_yield,
            'quality_rating': self.quality_rating,
            'growth_conditions': self.growth_conditions,
            'lessons_learned': self.lessons_learned,
            'would_repeat': self.would_repeat,
        }




class PersonalizedLearningService:
    """
    Service for personalizing AI recommendations to individual users.
    
    Learns from each user's unique environment, equipment, and growing history
    to provide increasingly accurate and personalized recommendations.
    """
    
    def __init__(
        self,
        model_registry: "ModelRegistry",
        training_data_repo: "AITrainingDataRepository",
        profiles_dir: Optional[Path] = None
    ):
        """
        Initialize personalized learning service.
        
        Args:
            model_registry: Model registry for accessing base models
            training_data_repo: Repository for training data
            profiles_dir: Directory for storing user profiles
        """
        self.model_registry = model_registry
        self.training_data_repo = training_data_repo
        self.profiles_dir = profiles_dir or Path("data/user_profiles")
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        # Cache of loaded profiles
        self._profile_cache: Dict[int, EnvironmentProfile] = {}
        
        # Success/failure tracking
        self.successes_dir = self.profiles_dir / "successes"
        self.successes_dir.mkdir(exist_ok=True)
        
        logger.info("PersonalizedLearningService initialized")
    
    def create_environment_profile(
        self,
        user_id: int,
        unit_id: int,
        location_info: Optional[Dict[str, Any]] = None,
        equipment_info: Optional[Dict[str, Any]] = None
    ) -> EnvironmentProfile:
        """
        Create initial environment profile for a user's grow unit.
        
        Args:
            user_id: User ID
            unit_id: Unit ID
            location_info: Optional location characteristics (climate zone, etc.)
            equipment_info: Optional equipment specifications
            
        Returns:
            Created EnvironmentProfile
        """
        # Analyze historical data to build profile
        historical_patterns = self._analyze_historical_patterns(unit_id)
        
        # Detect unique environmental characteristics
        location_chars = location_info or self._detect_location_characteristics(unit_id)
        equipment_profile = equipment_info or self._profile_equipment(unit_id)
        
        profile = EnvironmentProfile(
            user_id=user_id,
            unit_id=unit_id,
            location_characteristics=location_chars,
            equipment_profile=equipment_profile,
            historical_patterns=historical_patterns,
            success_factors=[],  # Will be populated as grows complete
            challenge_areas=[],  # Will be populated from issues
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        
        # Save profile
        self._save_profile(profile)
        self._profile_cache[unit_id] = profile
        
        logger.info(f"Created environment profile for user {user_id}, unit {unit_id}")
        return profile
    
    def get_profile(self, unit_id: int) -> Optional[EnvironmentProfile]:
        """Get environment profile for a unit."""
        # Check cache
        if unit_id in self._profile_cache:
            return self._profile_cache[unit_id]
        
        # Load from disk
        profile_file = self.profiles_dir / f"unit_{unit_id}_profile.json"
        if profile_file.exists():
            try:
                with open(profile_file, 'r') as f:
                    data = json.load(f)
                    profile = EnvironmentProfile(
                        user_id=data['user_id'],
                        unit_id=data['unit_id'],
                        location_characteristics=data['location_characteristics'],
                        equipment_profile=data['equipment_profile'],
                        historical_patterns=data['historical_patterns'],
                        success_factors=data['success_factors'],
                        challenge_areas=data['challenge_areas'],
                        created_at=datetime.fromisoformat(data['created_at']),
                        updated_at=datetime.fromisoformat(data['updated_at'])
                    )
                    self._profile_cache[unit_id] = profile
                    return profile
            except Exception as e:
                logger.error(f"Error loading profile: {e}")
        
        return None
    
    def update_profile(self, unit_id: int, updates: Dict[str, Any]):
        """Update environment profile with new learnings."""
        profile = self.get_profile(unit_id)
        if not profile:
            logger.warning(f"No profile found for unit {unit_id}")
            return
        
        # Update fields
        for key, value in updates.items():
            if hasattr(profile, key):
                setattr(profile, key, value)
        
        profile.updated_at = datetime.now()
        
        # Save updated profile
        self._save_profile(profile)
        self._profile_cache[unit_id] = profile
    
    def record_success(self, success: GrowingSuccess):
        """
        Record a successful grow cycle for learning.
        
        Args:
            success: GrowingSuccess record
        """
        try:
            # Save success record
            success_file = self.successes_dir / f"success_{success.unit_id}_{datetime.now().timestamp()}.json"
            with open(success_file, 'w') as f:
                json.dump(success.to_dict(), f, indent=2)
            
            # Update environment profile with success factors
            profile = self.get_profile(success.unit_id)
            if profile:
                # Extract key factors that led to success
                success_factors = self._extract_success_factors(success)
                
                # Add unique factors to profile
                for factor in success_factors:
                    if factor not in profile.success_factors:
                        profile.success_factors.append(factor)
                
                profile.updated_at = datetime.now()
                self._save_profile(profile)
            
            logger.info(f"Recorded successful grow for unit {success.unit_id}")
            
        except Exception as e:
            logger.error(f"Error recording success: {e}", exc_info=True)
    
    def get_personalized_recommendations(
        self,
        unit_id: int,
        plant_type: str,
        growth_stage: str,
        current_conditions: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Get personalized recommendations based on user's profile and history.
        
        Args:
            unit_id: Unit ID
            plant_type: Plant type
            growth_stage: Current growth stage
            current_conditions: Current environmental readings
            
        Returns:
            Personalized recommendations with explanations
        """
        profile = self.get_profile(unit_id)
        
        # Start with base recommendations
        recommendations = {
            'temperature': self._get_base_recommendation('temperature', plant_type, growth_stage),
            'humidity': self._get_base_recommendation('humidity', plant_type, growth_stage),
            'soil_moisture': self._get_base_recommendation('soil_moisture', plant_type, growth_stage),
            'personalization_notes': []
        }
        
        if not profile:
            recommendations['personalization_notes'].append(
                "Using general recommendations. Create profile for personalized advice."
            )
            return recommendations
        
        # Adjust based on environment profile
        adjustments = self._calculate_personalized_adjustments(
            profile, plant_type, growth_stage, current_conditions
        )
        
        for metric, adjustment in adjustments.items():
            if metric in recommendations:
                recommendations[metric] += adjustment
                if adjustment != 0:
                    recommendations['personalization_notes'].append(
                        f"Adjusted {metric} by {adjustment:+.1f} based on your environment"
                    )
        
        # Add success-based insights
        past_successes = self._get_past_successes(unit_id, plant_type)
        if past_successes:
            best_success = max(past_successes, key=lambda x: x.quality_rating)
            recommendations['personalization_notes'].append(
                f"Previously grew {plant_type} with {best_success.quality_rating}/5 rating. "
                f"Consider similar conditions."
            )
        
        # Add challenge-aware notes
        if profile.challenge_areas:
            for challenge in profile.challenge_areas:
                recommendations['personalization_notes'].append(
                    f"⚠️ Watch for {challenge} - this has been challenging in your environment"
                )
        
        return recommendations
    
    def get_similar_growers(
        self,
        unit_id: int,
        plant_type: str,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Find growers with similar environments who succeeded with this plant type.
        
        Args:
            unit_id: User's unit ID
            plant_type: Plant type being grown
            limit: Maximum number of similar growers to return
            
        Returns:
            List of similar grower profiles and their success strategies
        """
        profile = self.get_profile(unit_id)
        if not profile:
            return []
        
        similar_growers = []
        
        # Scan all success records
        for success_file in self.successes_dir.glob("success_*.json"):
            try:
                with open(success_file, 'r') as f:
                    success_data = json.load(f)
                
                # Skip if different plant type
                if success_data['plant_type'] != plant_type:
                    continue
                
                # Skip if same unit (that's us!)
                if success_data['unit_id'] == unit_id:
                    continue
                
                # Calculate similarity score
                similarity = self._calculate_environment_similarity(
                    profile, success_data['growth_conditions']
                )
                
                if similarity > 0.6:  # 60% similarity threshold
                    similar_growers.append({
                        'similarity_score': similarity,
                        'success_data': success_data,
                        'key_conditions': self._extract_key_conditions(success_data)
                    })
            
            except Exception as e:
                logger.error(f"Error reading success file: {e}")
                continue
        
        # Sort by similarity and return top matches
        similar_growers.sort(key=lambda x: x['similarity_score'], reverse=True)
        return similar_growers[:limit]
    
    def _analyze_historical_patterns(self, unit_id: int) -> Dict[str, Any]:
        """Analyze historical data to find patterns."""
        import pandas as pd  # Lazy load

        try:
            # Get 90 days of data
            end_date = datetime.now()
            start_date = end_date - timedelta(days=90)

            df = self.training_data_repo.get_sensor_data_range(
                unit_id,
                start_date.isoformat(),
                end_date.isoformat()
            )

            if df.empty:
                return {}

            patterns = {}

            # Identify daily cycles
            if 'temperature' in df.columns:
                df['hour'] = pd.to_datetime(df['timestamp']).dt.hour
                hourly_avg = df.groupby('hour')['temperature'].mean()
                patterns['daily_temp_cycle'] = {
                    'min_hour': int(hourly_avg.idxmin()),
                    'max_hour': int(hourly_avg.idxmax()),
                    'range': float(hourly_avg.max() - hourly_avg.min())
                }
            
            # Identify stability characteristics
            for col in ['temperature', 'humidity', 'soil_moisture']:
                if col in df.columns:
                    patterns[f'{col}_stability'] = {
                        'mean': float(df[col].mean()),
                        'std': float(df[col].std()),
                        'coefficient_of_variation': float(df[col].std() / df[col].mean())
                    }
            
            return patterns
            
        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")
            return {}
    
    def _detect_location_characteristics(self, unit_id: int) -> Dict[str, Any]:
        """Detect unique location characteristics."""
        # This would integrate with external APIs or user input
        # For now, return placeholder
        return {
            'climate_zone': 'temperate',
            'indoor_outdoor': 'indoor',
            'natural_light_available': False,
            'ambient_temp_stable': True
        }
    
    def _profile_equipment(self, unit_id: int) -> Dict[str, Any]:
        """Profile the equipment setup."""
        # Would query device inventory and capabilities
        return {
            'has_automated_watering': True,
            'has_climate_control': True,
            'has_co2_injection': False,
            'lighting_type': 'LED',
            'sensor_accuracy': 'high'
        }
    
    def _save_profile(self, profile: EnvironmentProfile):
        """Save profile to disk."""
        profile_file = self.profiles_dir / f"unit_{profile.unit_id}_profile.json"
        with open(profile_file, 'w') as f:
            json.dump(profile.to_dict(), f, indent=2)
    
    def _extract_success_factors(self, success: GrowingSuccess) -> List[str]:
        """Extract key factors that contributed to success."""
        factors = []
        
        # Analyze conditions
        conditions = success.growth_conditions
        
        # Check for optimal ranges
        if conditions.get('temperature_stability', 0) < 2.0:
            factors.append('stable_temperature')
        
        if conditions.get('consistent_watering', False):
            factors.append('consistent_watering')
        
        if success.quality_rating >= 4:
            factors.append('high_quality_outcome')
        
        # Add user-provided lessons
        factors.extend(success.lessons_learned)
        
        return factors
    
    def _get_past_successes(
        self,
        unit_id: int,
        plant_type: str
    ) -> List[GrowingSuccess]:
        """Get past successful grows for this unit and plant type."""
        successes = []
        
        for success_file in self.successes_dir.glob(f"success_{unit_id}_*.json"):
            try:
                with open(success_file, 'r') as f:
                    data = json.load(f)
                    if data['plant_type'] == plant_type:
                        success = GrowingSuccess(
                            user_id=data['user_id'],
                            unit_id=data['unit_id'],
                            plant_type=data['plant_type'],
                            plant_variety=data.get('plant_variety'),
                            start_date=datetime.fromisoformat(data['start_date']),
                            harvest_date=datetime.fromisoformat(data['harvest_date']),
                            total_yield=data.get('total_yield'),
                            quality_rating=data['quality_rating'],
                            growth_conditions=data['growth_conditions'],
                            lessons_learned=data['lessons_learned'],
                            would_repeat=data['would_repeat']
                        )
                        successes.append(success)
            except Exception as e:
                logger.error(f"Error loading success: {e}")
        
        return successes
    
    def _calculate_personalized_adjustments(
        self,
        profile: EnvironmentProfile,
        plant_type: str,
        growth_stage: str,
        current_conditions: Dict[str, float]
    ) -> Dict[str, float]:
        """Calculate adjustments based on user's environment."""
        adjustments = {
            'temperature': 0.0,
            'humidity': 0.0,
            'soil_moisture': 0.0
        }
        
        # Adjust for historical patterns
        if 'temperature_stability' in profile.historical_patterns:
            stability = profile.historical_patterns['temperature_stability']
            if stability['std'] > 3.0:
                # Unstable temps - aim slightly higher to accommodate fluctuations
                adjustments['temperature'] = 1.0
        
        # Adjust for equipment capabilities
        if not profile.equipment_profile.get('has_climate_control'):
            # Without climate control, be more conservative
            adjustments['humidity'] = -5.0
        
        return adjustments
    
    def _get_base_recommendation(
        self,
        metric: str,
        plant_type: str,
        growth_stage: str
    ) -> float:
        """Get base recommendation from general knowledge."""
        # This would query the growth predictor or climate optimizer
        defaults = {
            'temperature': {'Germination': 22, 'Vegetative': 24, 'Flowering': 23},
            'humidity': {'Germination': 75, 'Vegetative': 65, 'Flowering': 60},
            'soil_moisture': {'Germination': 85, 'Vegetative': 75, 'Flowering': 70}
        }
        
        return defaults.get(metric, {}).get(growth_stage, 0)
    
    def _calculate_environment_similarity(
        self,
        profile: EnvironmentProfile,
        conditions: Dict[str, Any]
    ) -> float:
        """Calculate similarity between two environments."""
        # Simple similarity based on key characteristics
        similarity_score = 0.0
        comparison_points = 0
        
        # Compare equipment
        if profile.equipment_profile.get('lighting_type') == conditions.get('lighting_type'):
            similarity_score += 0.3
        comparison_points += 1
        
        # Compare climate control capability
        if profile.equipment_profile.get('has_climate_control') == conditions.get('has_climate_control'):
            similarity_score += 0.2
        comparison_points += 1
        
        # Compare location characteristics
        if profile.location_characteristics.get('climate_zone') == conditions.get('climate_zone'):
            similarity_score += 0.3
        comparison_points += 1
        
        return similarity_score
    
    def _extract_key_conditions(self, success_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract key conditions from success data."""
        conditions = success_data.get('growth_conditions', {})
        return {
            'avg_temperature': conditions.get('avg_temperature'),
            'avg_humidity': conditions.get('avg_humidity'),
            'lighting_hours': conditions.get('lighting_hours'),
            'watering_frequency': conditions.get('watering_frequency')
        }
