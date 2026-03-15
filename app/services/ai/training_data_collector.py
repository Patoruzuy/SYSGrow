"""
Automated Training Data Collection Pipeline
============================================
Continuously collects and prepares training data with proper labeling and quality control.

Features:
- Automated data collection from sensors and user feedback
- Intelligent labeling based on outcomes
- Data quality validation
- Feature engineering pipeline
- Balanced dataset management
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, TYPE_CHECKING
from dataclasses import dataclass
from pathlib import Path

# ML libraries lazy loaded in methods for faster startup
# import pandas as pd
# import numpy as np

if TYPE_CHECKING:
    from infrastructure.database.repositories.ai import AITrainingDataRepository
    from app.services.ai.feature_engineering import FeatureEngineer

logger = logging.getLogger(__name__)


@dataclass
class TrainingExample:
    """A single training example with features and labels."""
    
    example_id: str
    unit_id: int
    plant_type: str
    growth_stage: str
    timestamp: datetime
    
    # Features
    environmental_features: Dict[str, float]
    temporal_features: Dict[str, float]
    plant_features: Dict[str, Any]
    
    # Labels (targets)
    disease_occurred: bool
    disease_type: Optional[str]
    growth_success: Optional[bool]  # Did plant thrive?
    quality_rating: Optional[int]  # 1-5 scale
    yield_amount: Optional[float]  # For harvest predictions
    
    # Metadata
    data_quality_score: float  # 0-1
    verified: bool  # Human verified
    notes: Optional[str]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'example_id': self.example_id,
            'unit_id': self.unit_id,
            'plant_type': self.plant_type,
            'growth_stage': self.growth_stage,
            'timestamp': self.timestamp.isoformat(),
            'environmental_features': self.environmental_features,
            'temporal_features': self.temporal_features,
            'plant_features': self.plant_features,
            'disease_occurred': self.disease_occurred,
            'disease_type': self.disease_type,
            'growth_success': self.growth_success,
            'quality_rating': self.quality_rating,
            'yield_amount': self.yield_amount,
            'data_quality_score': self.data_quality_score,
            'verified': self.verified,
            'notes': self.notes
        }


class TrainingDataCollector:
    """
    Automated training data collection and preparation pipeline.
    
    Collects high-quality training data from sensor readings, user observations,
    and grow outcomes to enable supervised learning.
    """
    
    def __init__(
        self,
        training_data_repo: "AITrainingDataRepository",
        feature_engineer: "FeatureEngineer",
        storage_path: Optional[Path] = None
    ):
        """
        Initialize training data collector.
        
        Args:
            training_data_repo: Repository for accessing raw data
            feature_engineer: Feature engineering service
            storage_path: Path for storing prepared training data
        """
        self.training_data_repo = training_data_repo
        self.feature_engineer = feature_engineer
        self.storage_path = storage_path or Path("data/training")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Quality thresholds
        self.min_quality_score = 0.6
        self.min_sensor_readings = 24  # At least 24 hours of data
        
        logger.info("TrainingDataCollector initialized")
    
    def collect_disease_training_data(
        self,
        days_back: int = 30,
        min_examples_per_class: int = 50
    ):
        """
        Collect training data for disease prediction model.

        Args:
            days_back: Days of historical data to collect
            min_examples_per_class: Minimum examples needed per disease type

        Returns:
            DataFrame with balanced training data
        """
        import pandas as pd  # Lazy load

        logger.info(f"Collecting disease training data for last {days_back} days")
        
        examples = []
        
        # Get all health observations (these are our labels)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        observations = self.training_data_repo.get_health_observations(
            start_date.isoformat(),
            end_date.isoformat()
        )
        
        logger.info(f"Found {len(observations)} health observations")
        
        for obs in observations:
            try:
                # Get sensor data from 48 hours before observation
                obs_time = datetime.fromisoformat(obs['observation_date'])
                sensor_start = obs_time - timedelta(hours=48)
                
                sensor_df = self.training_data_repo.get_sensor_time_series(
                    obs['unit_id'],
                    sensor_start.isoformat(),
                    obs_time.isoformat(),
                    interval_hours=1
                )
                
                # Skip if insufficient sensor data
                if len(sensor_df) < self.min_sensor_readings:
                    logger.debug(f"Skipping observation: insufficient sensor data")
                    continue
                
                # Extract features
                features = self.feature_engineer.create_disease_features(
                    sensor_data=sensor_df,
                    growth_stage=obs.get('growth_stage', 'Vegetative'),
                    current_time=obs_time
                )
                
                # Create training example
                example = TrainingExample(
                    example_id=f"disease_{obs['unit_id']}_{obs_time.timestamp()}",
                    unit_id=obs['unit_id'],
                    plant_type=obs.get('plant_type', 'unknown'),
                    growth_stage=obs.get('growth_stage', 'Vegetative'),
                    timestamp=obs_time,
                    environmental_features=features.iloc[0].to_dict(),
                    temporal_features=self._extract_temporal_features(obs_time),
                    plant_features={'age_days': obs.get('plant_age_days', 0)},
                    disease_occurred=obs['health_status'] != 'healthy',
                    disease_type=obs.get('disease_type'),
                    growth_success=None,  # Not applicable for disease data
                    quality_rating=None,
                    yield_amount=None,
                    data_quality_score=self._calculate_quality_score(sensor_df),
                    verified=obs.get('verified', False),
                    notes=obs.get('notes')
                )
                
                # Only include high-quality examples
                if example.data_quality_score >= self.min_quality_score:
                    examples.append(example)
            
            except Exception as e:
                logger.error(f"Error processing observation: {e}")
                continue
        
        logger.info(f"Collected {len(examples)} high-quality disease examples")
        
        # Convert to DataFrame
        if not examples:
            return pd.DataFrame()
        
        df = pd.DataFrame([ex.to_dict() for ex in examples])
        
        # Balance dataset
        df_balanced = self._balance_dataset(
            df,
            label_column='disease_type',
            min_per_class=min_examples_per_class
        )
        
        # Save to disk
        self._save_training_data(df_balanced, 'disease_training_data.parquet')
        
        return df_balanced
    
    def collect_climate_training_data(
        self,
        days_back: int = 60
    ):
        """
        Collect training data for climate optimization model.

        Learns optimal conditions from successful grows and user adjustments.

        Args:
            days_back: Days of historical data to collect

        Returns:
            DataFrame with climate training data
        """
        import pandas as pd  # Lazy load

        logger.info(f"Collecting climate training data for last {days_back} days")
        
        examples = []
        
        # Get all manual user adjustments (these indicate desired conditions)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        adjustments = self.training_data_repo.get_user_adjustments(
            start_date.isoformat(),
            end_date.isoformat()
        )
        
        for adj in adjustments:
            try:
                adj_time = datetime.fromisoformat(adj['timestamp'])
                
                # Get sensor data before adjustment
                before_start = adj_time - timedelta(hours=6)
                sensor_df = self.training_data_repo.get_sensor_time_series(
                    adj['unit_id'],
                    before_start.isoformat(),
                    adj_time.isoformat(),
                    interval_hours=1
                )
                
                if sensor_df.empty:
                    continue
                
                # Extract features
                features = self.feature_engineer.create_climate_features(
                    sensor_data=sensor_df,
                    growth_stage=adj.get('growth_stage', 'Vegetative'),
                    plant_age_days=adj.get('plant_age_days', 0),
                    current_time=adj_time
                )
                
                # Target is the user's desired value
                example = {
                    'example_id': f"climate_{adj['unit_id']}_{adj_time.timestamp()}",
                    'unit_id': adj['unit_id'],
                    'plant_type': adj.get('plant_type', 'unknown'),
                    'growth_stage': adj.get('growth_stage', 'Vegetative'),
                    'timestamp': adj_time.isoformat(),
                    'features': features.iloc[0].to_dict(),
                    'target_temperature': adj.get('target_temperature'),
                    'target_humidity': adj.get('target_humidity'),
                    'target_soil_moisture': adj.get('target_soil_moisture'),
                    'data_quality_score': self._calculate_quality_score(sensor_df)
                }
                
                if example['data_quality_score'] >= self.min_quality_score:
                    examples.append(example)
            
            except Exception as e:
                logger.error(f"Error processing adjustment: {e}")
                continue
        
        logger.info(f"Collected {len(examples)} climate training examples")
        
        if not examples:
            return pd.DataFrame()
        
        df = pd.DataFrame(examples)
        self._save_training_data(df, 'climate_training_data.parquet')
        
        return df
    
    def collect_growth_outcome_data(
        self,
        days_back: int = 180
    ):
        """
        Collect training data for growth prediction model.

        Uses completed grow cycles with harvest data.

        Args:
            days_back: Days of historical data to collect

        Returns:
            DataFrame with growth outcome data
        """
        import pandas as pd  # Lazy load

        logger.info(f"Collecting growth outcome data for last {days_back} days")
        
        examples = []
        
        # Get completed grow cycles
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        grow_cycles = self.training_data_repo.get_completed_grows(
            start_date.isoformat(),
            end_date.isoformat()
        )
        
        for cycle in grow_cycles:
            try:
                # Get average conditions during each growth stage
                stages = ['Germination', 'Seedling', 'Vegetative', 'Flowering', 'Fruiting']
                
                cycle_data = {
                    'cycle_id': cycle['cycle_id'],
                    'unit_id': cycle['unit_id'],
                    'plant_type': cycle['plant_type'],
                    'start_date': cycle['start_date'],
                    'harvest_date': cycle['harvest_date'],
                    'days_to_harvest': cycle['days_to_harvest'],
                    'total_yield': cycle.get('total_yield'),
                    'quality_rating': cycle.get('quality_rating', 3),
                    'success': cycle.get('quality_rating', 3) >= 4
                }
                
                # Get conditions for each stage
                for stage in stages:
                    stage_start = cycle.get(f'{stage.lower()}_start')
                    stage_end = cycle.get(f'{stage.lower()}_end')
                    
                    if not stage_start or not stage_end:
                        continue
                    
                    sensor_df = self.training_data_repo.get_sensor_time_series(
                        cycle['unit_id'],
                        stage_start,
                        stage_end,
                        interval_hours=6
                    )
                    
                    if not sensor_df.empty:
                        # Calculate average conditions for this stage
                        cycle_data[f'{stage}_avg_temp'] = sensor_df['temperature'].mean()
                        cycle_data[f'{stage}_avg_humidity'] = sensor_df['humidity'].mean()
                        cycle_data[f'{stage}_avg_moisture'] = sensor_df['soil_moisture'].mean()
                        cycle_data[f'{stage}_temp_stability'] = sensor_df['temperature'].std()
                
                examples.append(cycle_data)
            
            except Exception as e:
                logger.error(f"Error processing grow cycle: {e}")
                continue
        
        logger.info(f"Collected {len(examples)} growth outcome examples")
        
        if not examples:
            return pd.DataFrame()
        
        df = pd.DataFrame(examples)
        self._save_training_data(df, 'growth_outcome_data.parquet')
        
        return df
    
    def validate_training_data(
        self,
        df,
        data_type: str
    ) -> Tuple[bool, List[str]]:
        """
        Validate training data quality and completeness.
        
        Args:
            df: DataFrame to validate
            data_type: Type of training data ('disease', 'climate', 'growth')
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []
        
        # Check basic requirements
        if df.empty:
            issues.append("Dataset is empty")
            return False, issues
        
        # Check for required columns based on data type
        required_columns = {
            'disease': ['unit_id', 'plant_type', 'disease_occurred', 'environmental_features'],
            'climate': ['unit_id', 'plant_type', 'features', 'target_temperature'],
            'growth': ['unit_id', 'plant_type', 'success', 'total_yield']
        }
        
        if data_type in required_columns:
            for col in required_columns[data_type]:
                if col not in df.columns:
                    issues.append(f"Missing required column: {col}")
        
        # Check for sufficient examples
        min_examples = 100
        if len(df) < min_examples:
            issues.append(f"Insufficient examples: {len(df)} < {min_examples}")
        
        # Check for class imbalance (for classification tasks)
        if data_type == 'disease' and 'disease_occurred' in df.columns:
            disease_counts = df['disease_occurred'].value_counts()
            imbalance_ratio = disease_counts.max() / disease_counts.min()
            if imbalance_ratio > 10:
                issues.append(f"Severe class imbalance: ratio {imbalance_ratio:.1f}")
        
        # Check data quality scores
        if 'data_quality_score' in df.columns:
            low_quality = (df['data_quality_score'] < self.min_quality_score).sum()
            if low_quality > len(df) * 0.3:
                issues.append(f"Too many low quality examples: {low_quality}/{len(df)}")
        
        # Check for missing values
        missing_pct = (df.isnull().sum() / len(df) * 100)
        high_missing = missing_pct[missing_pct > 20]
        if not high_missing.empty:
            issues.append(f"High missing values in columns: {high_missing.to_dict()}")
        
        is_valid = len(issues) == 0
        return is_valid, issues
    
    def _extract_temporal_features(self, timestamp: datetime) -> Dict[str, float]:
        """Extract temporal features from timestamp."""
        return {
            'hour': timestamp.hour,
            'day_of_week': timestamp.weekday(),
            'day_of_month': timestamp.day,
            'month': timestamp.month,
            'season': (timestamp.month % 12 + 3) // 3  # 1=Spring, 2=Summer, etc.
        }
    
    def _calculate_quality_score(self, sensor_df) -> float:
        """
        Calculate data quality score based on completeness and consistency.

        Args:
            sensor_df: Sensor data DataFrame

        Returns:
            Quality score between 0 and 1
        """
        import pandas as pd  # Lazy load
        import numpy as np  # Lazy load

        if sensor_df.empty:
            return 0.0

        score = 1.0

        # Penalize for missing data
        missing_pct = sensor_df.isnull().sum().sum() / (len(sensor_df) * len(sensor_df.columns))
        score -= missing_pct * 0.5

        # Penalize for outliers (likely sensor errors)
        for col in sensor_df.select_dtypes(include=[np.number]).columns:
            Q1 = sensor_df[col].quantile(0.25)
            Q3 = sensor_df[col].quantile(0.75)
            IQR = Q3 - Q1
            outliers = ((sensor_df[col] < (Q1 - 3 * IQR)) | (sensor_df[col] > (Q3 + 3 * IQR))).sum()
            outlier_pct = outliers / len(sensor_df)
            score -= outlier_pct * 0.3
        
        # Penalize for insufficient data points
        if len(sensor_df) < self.min_sensor_readings:
            score -= (self.min_sensor_readings - len(sensor_df)) / self.min_sensor_readings * 0.2
        
        return max(0.0, min(1.0, score))
    
    def _balance_dataset(
        self,
        df,
        label_column: str,
        min_per_class: int
    ):
        """
        Balance dataset by oversampling minority classes or undersampling majority.

        Args:
            df: DataFrame to balance
            label_column: Column name containing class labels
            min_per_class: Minimum examples per class

        Returns:
            Balanced DataFrame
        """
        import pandas as pd  # Lazy load

        try:
            class_counts = df[label_column].value_counts()
            logger.info(f"Class distribution before balancing: {class_counts.to_dict()}")
            
            # If any class has fewer than min, oversample
            if class_counts.min() < min_per_class:
                balanced_dfs = []
                
                for label in class_counts.index:
                    class_df = df[df[label_column] == label]
                    
                    if len(class_df) < min_per_class:
                        # Oversample with replacement
                        oversampled = class_df.sample(
                            n=min_per_class,
                            replace=True,
                            random_state=42
                        )
                        balanced_dfs.append(oversampled)
                    else:
                        balanced_dfs.append(class_df)
                
                df_balanced = pd.concat(balanced_dfs, ignore_index=True)
            else:
                df_balanced = df
            
            # Shuffle
            df_balanced = df_balanced.sample(frac=1, random_state=42).reset_index(drop=True)
            
            balanced_counts = df_balanced[label_column].value_counts()
            logger.info(f"Class distribution after balancing: {balanced_counts.to_dict()}")
            
            return df_balanced
        
        except Exception as e:
            logger.error(f"Error balancing dataset: {e}")
            return df
    
    def _save_training_data(self, df, filename: str):
        """Save training data to disk."""
        try:
            filepath = self.storage_path / filename
            df.to_parquet(filepath, index=False)
            logger.info(f"Saved training data to {filepath}")
        except Exception as e:
            logger.error(f"Error saving training data: {e}")
    
    def get_training_data_summary(self) -> Dict[str, Any]:
        """Get summary of available training data."""
        summary = {
            'disease_data': self._get_file_summary('disease_training_data.parquet'),
            'climate_data': self._get_file_summary('climate_training_data.parquet'),
            'growth_data': self._get_file_summary('growth_outcome_data.parquet'),
        }
        return summary
    
    def _get_file_summary(self, filename: str) -> Dict[str, Any]:
        """Get summary of a training data file."""
        import pandas as pd  # Lazy load

        filepath = self.storage_path / filename

        if not filepath.exists():
            return {'exists': False}

        try:
            df = pd.read_parquet(filepath)
            return {
                'exists': True,
                'examples': len(df),
                'created': datetime.fromtimestamp(filepath.stat().st_mtime).isoformat(),
                'size_mb': filepath.stat().st_size / (1024 * 1024)
            }
        except Exception as e:
            return {'exists': True, 'error': str(e)}
