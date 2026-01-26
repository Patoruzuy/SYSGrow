"""
ML Model Training Service
==========================
Service for training and retraining AI/ML models with automated data collection.

This service provides:
- Model training with cross-validation
- Training data collection and preprocessing
- Model evaluation and metrics tracking
- Integration with ModelRegistry for versioning
"""

from __future__ import annotations

import logging
import statistics
import threading
from typing import Dict, List, Optional, Any, TYPE_CHECKING
from datetime import datetime, timedelta
from dataclasses import dataclass
from pathlib import Path

from app.utils.time import iso_now

# ML libraries lazy loaded in methods for faster startup
# import numpy as np
# import pandas as pd
# from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
# from sklearn.model_selection import train_test_split, cross_val_score
# from sklearn.preprocessing import StandardScaler
# from sklearn.metrics import mean_squared_error, accuracy_score, classification_report

if TYPE_CHECKING:
    from infrastructure.database.repositories.ai import AITrainingDataRepository
    from app.services.ai.model_registry import ModelRegistry

logger = logging.getLogger(__name__)


@dataclass
class TrainingMetrics:
    """Model training metrics."""
    
    model_name: str
    model_type: str
    training_samples: int
    test_samples: int
    train_score: float
    test_score: float
    cv_scores: List[float]
    feature_importance: Dict[str, float]
    training_time: float
    timestamp: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "model_name": self.model_name,
            "model_type": self.model_type,
            "training_samples": self.training_samples,
            "test_samples": self.test_samples,
            "train_score": round(self.train_score, 4),
            "test_score": round(self.test_score, 4),
            "cv_mean": round(statistics.mean(self.cv_scores), 4) if self.cv_scores else 0.0,
            "cv_std": round(statistics.stdev(self.cv_scores), 4) if len(self.cv_scores) > 1 else 0.0,
            "feature_importance": self.feature_importance,
            "training_time_seconds": round(self.training_time, 2),
            "timestamp": self.timestamp.isoformat()
        }


class MLTrainerService:
    """
    Machine Learning training service.
    
    Handles model training, evaluation, and deployment.
    """
    
    def __init__(
        self,
        training_data_repo: AITrainingDataRepository,
        model_registry: ModelRegistry
    ):
        """
        Initialize ML trainer service.
        
        Args:
            training_data_repo: Repository for training data access
            model_registry: Model registry for saving trained models
        """
        self.training_data_repo = training_data_repo
        self.model_registry = model_registry
        self.logger = logging.getLogger(__name__)
        
        # Training configuration
        self.min_training_samples = 100
        self.validation_split = 0.2
        self.cross_validation_folds = 5
        self.random_state = 42
        
        # Feature configurations
        self.environmental_features = [
            "temperature",
            "humidity",
            "soil_moisture",
            "co2",
            "lux",
        ]
        
        self.climate_targets = ["temperature", "humidity", "soil_moisture"]
    
    def collect_training_data(
        self,
        model_type: str,
        unit_id: Optional[int] = None,
        days: int = 30
    ):
        """
        Collect and prepare training data.

        Args:
            model_type: Type of model to train ('climate', 'disease', 'growth')
            unit_id: Optional unit filter
            days: Number of days of historical data

        Returns:
            DataFrame with training data
        """
        import pandas as pd  # Lazy load

        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            end_date = iso_now()
            
            # Collect training data from repository
            data_records = self.training_data_repo.get_training_data(
                model_type=model_type,
                start_date=start_date,
                end_date=end_date,
                unit_id=unit_id
            )
            
            if not data_records:
                self.logger.warning(f"No training data collected for {model_type}")
                return pd.DataFrame()
            
            # Convert to DataFrame
            df = pd.DataFrame(data_records)
            
            # Clean and preprocess
            df = self._clean_data(df)
            df = self._engineer_features(df)
            
            self.logger.info(f"Collected {len(df)} training samples for {model_type}")
            return df
            
        except Exception as e:
            self.logger.error(f"Failed to collect training data: {e}", exc_info=True)
            return pd.DataFrame()
    
    def _clean_data(self, df):
        """Clean and preprocess data."""
        import numpy as np  # Lazy load
        import pandas as pd  # Lazy load

        try:
            # Remove rows with too many missing values (>30%)
            df = df.dropna(thresh=len(df.columns) * 0.7)

            # Fill missing numeric values with mean
            numeric_columns = df.select_dtypes(include=[np.number]).columns
            for col in numeric_columns:
                if df[col].isnull().any():
                    df[col] = df[col].fillna(df[col].mean())
            
            # Remove outliers using IQR method
            for col in self.environmental_features:
                if col in df.columns:
                    Q1 = df[col].quantile(0.25)
                    Q3 = df[col].quantile(0.75)
                    IQR = Q3 - Q1
                    lower = Q1 - 1.5 * IQR
                    upper = Q3 + 1.5 * IQR
                    df = df[(df[col] >= lower) & (df[col] <= upper)]
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Error cleaning data: {e}")
            return df
    
    def _engineer_features(self, df):
        """Create engineered features."""
        import pandas as pd  # Lazy load

        try:
            # Timestamp features
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df['hour'] = df['timestamp'].dt.hour
                df['day_of_week'] = df['timestamp'].dt.dayofweek
                df['month'] = df['timestamp'].dt.month
            
            # Interaction features
            if 'temperature' in df.columns and 'humidity' in df.columns:
                df['temp_humidity_interaction'] = df['temperature'] * df['humidity']
            
            return df
            
        except Exception as e:
            self.logger.warning(f"Error engineering features: {e}")
            return df
    
    def train_climate_model(
        self,
        unit_id: Optional[int] = None,
        days: int = 30,
        save_model: bool = True,
        *,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Train climate prediction model.

        Args:
            unit_id: Optional unit filter
            days: Days of training data
            save_model: Whether to save the trained model

        Returns:
            Training results with metrics
        """
        # Lazy load ML libraries
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.metrics import mean_absolute_error
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import mean_absolute_error
        from sklearn.metrics import mean_absolute_error

        start_time = datetime.now()

        class TrainingCancelled(Exception):
            pass

        def check_cancel() -> None:
            if cancel_event is not None and cancel_event.is_set():
                raise TrainingCancelled("Training cancelled")

        def report_progress(progress: float, message: Optional[str] = None) -> None:
            if progress_callback:
                progress_callback(float(progress), message)
        
        try:
            check_cancel()
            report_progress(10, "Collecting training data...")
            # Collect training data
            df = self.collect_training_data('climate', unit_id, days)
            check_cancel()
            
            if len(df) < self.min_training_samples:
                return {
                    "success": False,
                    "error": f"Insufficient training data ({len(df)} < {self.min_training_samples})"
                }

            report_progress(15, "Preparing features...")
            
            # Prepare features
            feature_columns = [
                col for col in self.environmental_features + ['hour', 'day_of_week', 'month']
                if col in df.columns
            ]
            
            results = {}
            models_trained = 0
            
            # Train a model for each climate target
            targets = [t for t in self.climate_targets if t in df.columns]
            total_targets = max(1, len(targets))

            for idx, target in enumerate(targets):
                if target not in df.columns:
                    continue

                check_cancel()
                progress_base = 15 + ((idx / total_targets) * 70)
                report_progress(progress_base, f"Training target: {target}")
                
                try:
                    # Prepare data
                    X = df[feature_columns]
                    y = df[target]
                    
                    # Split data
                    X_train, X_test, y_train, y_test = train_test_split(
                        X, y,
                        test_size=self.validation_split,
                        random_state=self.random_state
                    )
                    
                    # Scale features
                    scaler = StandardScaler()
                    X_train_scaled = scaler.fit_transform(X_train)
                    X_test_scaled = scaler.transform(X_test)
                    
                    # Train model
                    model = RandomForestRegressor(
                        n_estimators=100,
                        max_depth=10,
                        random_state=self.random_state,
                        n_jobs=-1
                    )
                    check_cancel()
                    model.fit(X_train_scaled, y_train)
                    
                    # Evaluate
                    train_score = model.score(X_train_scaled, y_train)
                    test_score = model.score(X_test_scaled, y_test)
                    
                    # Cross-validation
                    check_cancel()
                    cv_scores = cross_val_score(
                        model, X_train_scaled, y_train,
                        cv=self.cross_validation_folds,
                        scoring='r2'
                    )
                    check_cancel()
                    
                    # Feature importance
                    feature_importance = dict(zip(
                        feature_columns,
                        model.feature_importances_
                    ))
                    
                    # Save model if requested
                    model_name = f"climate_{target}"
                    if save_model:
                        check_cancel()
                        metadata = {
                            "model_type": "climate_prediction",
                            "target": target,
                            "features": feature_columns,
                            "train_score": train_score,
                            "test_score": test_score,
                            "cv_mean": float(np.mean(cv_scores)),
                            "cv_std": float(np.std(cv_scores)),
                            "training_samples": len(X_train),
                            "feature_importance": {k: float(v) for k, v in feature_importance.items()}
                        }
                        
                        self.model_registry.save_model(
                            model_name=model_name,
                            model=model,
                            metadata=metadata,
                            scaler=scaler
                        )
                    
                    # Store results
                    results[target] = {
                        "train_score": round(train_score, 4),
                        "test_score": round(test_score, 4),
                        "cv_mean": round(float(np.mean(cv_scores)), 4),
                        "cv_std": round(float(np.std(cv_scores)), 4),
                        "feature_importance": {k: round(float(v), 4) for k, v in feature_importance.items()}
                    }
                    
                    models_trained += 1
                    progress_end = 15 + (((idx + 1) / total_targets) * 70)
                    report_progress(progress_end, f"Completed target: {target}")
                    
                except Exception as e:
                    self.logger.error(f"Failed to train {target} model: {e}")
                    results[target] = {"error": str(e)}
            
            training_time = (datetime.now() - start_time).total_seconds()
            report_progress(90, "Training run finished")
            
            return {
                "success": models_trained > 0,
                "models_trained": models_trained,
                "training_samples": len(df),
                "features_used": feature_columns,
                "results": results,
                "training_time_seconds": round(training_time, 2)
            }
            
        except Exception as e:
            if str(e) == "Training cancelled":
                return {"success": False, "error": "cancelled"}
            self.logger.error(f"Failed to train climate model: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def train_disease_model(
        self,
        unit_id: Optional[int] = None,
        days: int = 365,
        save_model: bool = True,
        *,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Train disease prediction model using historical disease occurrences.

        This trains a classifier that predicts disease risk based on environmental
        conditions. It uses the DiseaseOccurrence table for positive examples
        and generates synthetic negative examples from healthy periods.

        Args:
            unit_id: Optional unit filter
            days: Days of training data (default 365 for disease patterns)
            save_model: Whether to save the trained model

        Returns:
            Training results with metrics
        """
        # Lazy load ML libraries
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler
        from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

        start_time = datetime.now()

        def cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        def report_progress(progress: float, message: Optional[str] = None) -> None:
            if progress_callback:
                progress_callback(float(progress), message)
        
        try:
            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(10, "Collecting disease occurrence data...")
            
            # Get disease occurrence training data
            disease_df = self.training_data_repo.get_disease_occurrence_training_data(
                unit_id=unit_id,
                days_limit=days,
                confirmed_only=True,
            )
            
            if cancelled():
                return {"success": False, "error": "cancelled"}
            
            # Check if we have enough disease occurrences
            if len(disease_df) < 10:
                self.logger.warning(
                    f"Insufficient confirmed disease occurrences ({len(disease_df)} < 10)"
                )
                return {
                    "success": False,
                    "error": f"Insufficient disease data ({len(disease_df)} < 10 confirmed occurrences)",
                    "message": "Train model after recording more disease incidents",
                }
            
            report_progress(20, "Generating training features...")
            
            # Prepare positive examples (disease occurred)
            positive_features = []
            positive_labels = []
            disease_types = disease_df["disease_type"].unique().tolist()
            
            for _, row in disease_df.iterrows():
                features = self._extract_disease_features(row)
                if features:
                    positive_features.append(features)
                    positive_labels.append(row["disease_type"])
            
            if len(positive_features) < 10:
                return {
                    "success": False,
                    "error": "Insufficient valid feature vectors for training",
                }
            
            if cancelled():
                return {"success": False, "error": "cancelled"}
            
            report_progress(30, "Generating negative examples...")
            
            # Generate negative examples from healthy periods
            negative_features = self._generate_healthy_samples(
                unit_id=unit_id,
                days=days,
                num_samples=len(positive_features) * 2,  # 2:1 ratio
            )
            
            if len(negative_features) < len(positive_features):
                self.logger.warning("Could not generate enough negative samples")
            
            negative_labels = ["healthy"] * len(negative_features)
            
            if cancelled():
                return {"success": False, "error": "cancelled"}
            
            report_progress(40, "Building training dataset...")
            
            # Combine positive and negative examples
            all_features = positive_features + negative_features
            all_labels = positive_labels + negative_labels
            
            # Convert to DataFrame for easier handling
            feature_columns = [
                "temperature", "humidity", "soil_moisture", "vpd",
                "avg_temperature_72h", "avg_humidity_72h", "avg_soil_moisture_72h",
                "humidity_variance_72h", "growth_stage_num", "days_in_stage",
            ]
            
            X = np.array([[f.get(col, 0) for col in feature_columns] for f in all_features])
            y = np.array(all_labels)
            
            # Remove any rows with NaN values
            valid_mask = ~np.any(np.isnan(X), axis=1)
            X = X[valid_mask]
            y = y[valid_mask]
            
            if len(X) < self.min_training_samples:
                return {
                    "success": False,
                    "error": f"Insufficient training samples after cleanup ({len(X)} < {self.min_training_samples})",
                }
            
            report_progress(50, "Splitting and scaling data...")
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)
            
            if cancelled():
                return {"success": False, "error": "cancelled"}
            
            report_progress(60, "Training disease classifier...")
            
            # Train model - use GradientBoosting for better imbalanced data handling
            model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                min_samples_split=5,
                min_samples_leaf=2,
                learning_rate=0.1,
                random_state=42,
            )
            
            model.fit(X_train_scaled, y_train)
            
            if cancelled():
                return {"success": False, "error": "cancelled"}
            
            report_progress(80, "Evaluating model...")
            
            # Evaluate
            y_pred = model.predict(X_test_scaled)
            
            # Calculate metrics
            accuracy = accuracy_score(y_test, y_pred)
            
            # Calculate per-class metrics
            unique_classes = np.unique(y_test)
            class_metrics = {}
            for cls in unique_classes:
                cls_mask = y_test == cls
                if cls_mask.sum() > 0:
                    cls_pred = y_pred[cls_mask]
                    cls_true = y_test[cls_mask]
                    class_metrics[cls] = {
                        "samples": int(cls_mask.sum()),
                        "correct": int((cls_pred == cls_true).sum()),
                    }
            
            # Cross-validation for robustness check
            cv_scores = cross_val_score(model, X_train_scaled, y_train, cv=min(5, len(y_train) // 5))
            
            if cancelled():
                return {"success": False, "error": "cancelled"}
            
            report_progress(90, "Saving model...")
            
            # Save model and scaler
            if save_model:
                model_data = {
                    "model": model,
                    "scaler": scaler,
                    "feature_columns": feature_columns,
                    "disease_types": disease_types,
                    "trained_at": datetime.now().isoformat(),
                    "training_samples": len(X_train),
                    "accuracy": accuracy,
                }
                
                model_name = f"disease_classifier_unit_{unit_id}" if unit_id else "disease_classifier"
                self._save_model(model_data, model_name)
            
            training_time = (datetime.now() - start_time).total_seconds()
            report_progress(100, "Disease model training complete")
            
            self.logger.info(
                f"Trained disease classifier: {len(X_train)} samples, "
                f"{len(disease_types)} disease types, accuracy={accuracy:.3f}"
            )
            
            return {
                "success": True,
                "model_type": "disease_classifier",
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "positive_samples": len(positive_features),
                "negative_samples": len(negative_features),
                "disease_types": disease_types,
                "accuracy": round(accuracy, 4),
                "cv_mean_accuracy": round(cv_scores.mean(), 4),
                "cv_std": round(cv_scores.std(), 4),
                "class_metrics": class_metrics,
                "training_time_seconds": round(training_time, 2),
            }
            
        except Exception as e:
            self.logger.error(f"Failed to train disease model: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def _extract_disease_features(self, row) -> Optional[Dict[str, float]]:
        """Extract feature vector from disease occurrence row."""
        try:
            growth_stage_map = {
                "seedling": 1, "vegetative": 2, "flowering": 3,
                "fruiting": 4, "harvest": 5, "dormant": 0,
            }
            
            return {
                "temperature": row.get("temperature_at_detection", 0) or 0,
                "humidity": row.get("humidity_at_detection", 0) or 0,
                "soil_moisture": row.get("soil_moisture_at_detection", 0) or 0,
                "vpd": row.get("vpd_at_detection", 0) or 0,
                "avg_temperature_72h": row.get("avg_temperature_72h", 0) or 0,
                "avg_humidity_72h": row.get("avg_humidity_72h", 0) or 0,
                "avg_soil_moisture_72h": row.get("avg_soil_moisture_72h", 0) or 0,
                "humidity_variance_72h": row.get("humidity_variance_72h", 0) or 0,
                "growth_stage_num": growth_stage_map.get(row.get("growth_stage", ""), 2),
                "days_in_stage": row.get("days_in_stage", 0) or 0,
            }
        except Exception as e:
            self.logger.warning(f"Failed to extract disease features: {e}")
            return None

    def _generate_healthy_samples(
        self,
        unit_id: Optional[int],
        days: int,
        num_samples: int,
    ) -> List[Dict[str, float]]:
        """
        Generate synthetic negative samples from healthy periods.
        
        Samples environmental conditions from times when no disease was detected.
        """
        import numpy as np
        
        try:
            # Get environmental data
            env_df = self.collect_training_data("climate", unit_id, days)
            
            if len(env_df) < num_samples:
                num_samples = len(env_df)
            
            if num_samples == 0:
                return []
            
            # Sample random healthy periods
            samples = []
            indices = np.random.choice(len(env_df), size=num_samples, replace=False)
            
            for idx in indices:
                row = env_df.iloc[idx]
                sample = {
                    "temperature": row.get("temperature", 22) or 22,
                    "humidity": row.get("humidity", 60) or 60,
                    "soil_moisture": row.get("soil_moisture", 50) or 50,
                    "vpd": row.get("vpd", 1.0) or 1.0,
                    "avg_temperature_72h": row.get("temperature", 22) or 22,
                    "avg_humidity_72h": row.get("humidity", 60) or 60,
                    "avg_soil_moisture_72h": row.get("soil_moisture", 50) or 50,
                    "humidity_variance_72h": np.random.uniform(2, 8),  # Typical healthy variance
                    "growth_stage_num": 2,  # Assume vegetative
                    "days_in_stage": np.random.randint(5, 30),
                }
                samples.append(sample)
            
            return samples
            
        except Exception as e:
            self.logger.warning(f"Failed to generate healthy samples: {e}")
            return []
    
    def retrain_all_models(
        self,
        days: int = 30,
        include_irrigation: bool = True,
    ) -> Dict[str, Any]:
        """
        Retrain all models with latest data.
        
        Args:
            days: Days of training data to use
            include_irrigation: Whether to include irrigation models (default True)
            
        Returns:
            Summary of retraining results
        """
        results = {}
        
        # Train climate models
        climate_result = self.train_climate_model(days=days, save_model=True)
        results['climate'] = climate_result
        
        # Train irrigation models
        if include_irrigation:
            # Irrigation threshold model
            threshold_result = self.train_irrigation_threshold_model(days=90, save_model=True)
            results['irrigation_threshold'] = threshold_result
            
            # Irrigation response model
            response_result = self.train_irrigation_response_model(days=90, save_model=True)
            results['irrigation_response'] = response_result
            
            # Irrigation duration model
            duration_result = self.train_irrigation_duration_model(days=90, save_model=True)
            results['irrigation_duration'] = duration_result

            # Irrigation timing model
            timing_result = self.train_irrigation_timing_model(days=120, save_model=True)
            results['irrigation_timing'] = timing_result
        
        return {
            "success": any(r.get('success', False) for r in results.values()),
            "models": results,
            "timestamp": iso_now()
        }
    
    def get_training_status(self) -> Dict[str, Any]:
        """Get status of training system."""
        try:
            # Get all models from registry
            models = self.model_registry.list_models()
            
            return {
                "available": True,
                "total_models": len(models),
                "models": models,
                "min_training_samples": self.min_training_samples
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get training status: {e}")
            return {
                "available": False,
                "error": str(e)
            }

    # ==================== Irrigation ML Training Methods ====================

    def train_irrigation_threshold_model(
        self,
        unit_id: Optional[int] = None,
        days: int = 90,
        save_model: bool = True,
        *,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Train model to predict optimal soil moisture threshold.
        
        This model learns from user feedback (too_little/just_right/too_much)
        to predict the optimal threshold for specific plant/growth stage combinations.
        
        Features:
        - Plant type/variety
        - Growth stage
        - Environmental conditions at feedback time
        - Historical threshold adjustments
        - User consistency score
        
        Target:
        - Optimal threshold (derived from feedback patterns)
        
        Args:
            unit_id: Optional unit filter
            days: Days of training data to use
            save_model: Whether to save the trained model
            cancel_event: Optional threading event for cancellation
            progress_callback: Optional callback for progress updates
            
        Returns:
            Training results with metrics
        """
        # Lazy load ML libraries
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.metrics import mean_absolute_error
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler

        start_time = datetime.now()

        def cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        def report_progress(progress: float, message: Optional[str] = None) -> None:
            if progress_callback:
                progress_callback(float(progress), message)

        try:
            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(10, "Collecting irrigation threshold training data...")

            # Collect training data from irrigation feedback
            df = self._collect_irrigation_threshold_data(unit_id, days)
            if cancelled():
                return {"success": False, "error": "cancelled"}

            min_samples = 30  # Lower threshold for irrigation models
            if len(df) < min_samples:
                return {
                    "success": False,
                    "error": f"Insufficient training data ({len(df)} < {min_samples})"
                }

            report_progress(20, f"Processing {len(df)} samples...")

            from app.services.ai.feature_engineering import FeatureEngineer

            # Prepare features (single source of truth)
            feature_columns = FeatureEngineer.get_irrigation_model_features("threshold_optimizer")
            df = FeatureEngineer.align_features(df, feature_columns)

            # Target: optimal threshold derived from feedback
            if "optimal_threshold" not in df.columns:
                return {"success": False, "error": "Missing target column 'optimal_threshold'"}

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(30, "Preparing features and target...")

            X = df[feature_columns].fillna(0)
            y = df["optimal_threshold"]

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=self.validation_split,
                random_state=self.random_state
            )

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(50, "Training threshold model...")

            # Train model - GradientBoosting works well for threshold prediction
            model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=self.random_state,
            )
            model.fit(X_train_scaled, y_train)

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(70, "Evaluating model...")

            # Evaluate
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)
            y_pred = model.predict(X_test_scaled)
            mae = mean_absolute_error(y_test, y_pred)

            # Cross-validation
            cv_scores = cross_val_score(
                model, X_train_scaled, y_train,
                cv=min(self.cross_validation_folds, len(X_train)),
                scoring="r2"
            )

            # Feature importance
            feature_importance = dict(zip(feature_columns, model.feature_importances_))

            if cancelled():
                return {"success": False, "error": "cancelled"}

            # Save model if requested
            model_name = "irrigation_threshold"
            if save_model:
                report_progress(85, "Saving model...")
                metrics = {
                    "train_score": float(train_score),
                    "test_score": float(test_score),
                    "cv_mean": float(np.mean(cv_scores)),
                    "cv_std": float(np.std(cv_scores)),
                    "mae": float(mae),
                }
                metadata = {
                    "model_type": "irrigation_threshold_prediction",
                    "features": feature_columns,
                    "metrics": metrics,
                    "training_samples": len(X_train),
                    "feature_importance": {k: float(v) for k, v in feature_importance.items()},
                }
                self.model_registry.save_model(
                    model_name=model_name,
                    model=model,
                    metadata=metadata,
                    scaler=scaler
                )

            training_time = (datetime.now() - start_time).total_seconds()
            report_progress(95, "Training complete")

            return {
                "success": True,
                "model_name": model_name,
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "train_score": round(train_score, 4),
                "test_score": round(test_score, 4),
                "cv_mean": round(float(np.mean(cv_scores)), 4),
                "cv_std": round(float(np.std(cv_scores)), 4),
                "mae": round(float(mae), 4),
                "feature_importance": {k: round(float(v), 4) for k, v in feature_importance.items()},
                "training_time_seconds": round(training_time, 2),
            }

        except Exception as e:
            if str(e) == "cancelled":
                return {"success": False, "error": "cancelled"}
            self.logger.error(f"Failed to train irrigation threshold model: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def train_irrigation_response_model(
        self,
        unit_id: Optional[int] = None,
        days: int = 90,
        save_model: bool = True,
        *,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Train model to predict user response to irrigation requests.
        
        Predicts whether user will approve, delay, or cancel irrigation requests
        based on timing, conditions, and historical patterns.
        
        Features:
        - Time of day, day of week
        - Current soil moisture
        - Environmental conditions
        - User historical patterns
        
        Target:
        - Response class (approve/delay/cancel)
        
        Args:
            unit_id: Optional unit filter
            days: Days of training data to use
            save_model: Whether to save the trained model
            cancel_event: Optional threading event for cancellation
            progress_callback: Optional callback for progress updates
            
        Returns:
            Training results with metrics
        """
        # Lazy load ML libraries
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler, LabelEncoder
        from sklearn.metrics import classification_report, f1_score, balanced_accuracy_score, accuracy_score

        start_time = datetime.now()

        def cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        def report_progress(progress: float, message: Optional[str] = None) -> None:
            if progress_callback:
                progress_callback(float(progress), message)

        try:
            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(10, "Collecting response training data...")

            # Collect training data
            df = self._collect_irrigation_response_data(unit_id, days)
            if cancelled():
                return {"success": False, "error": "cancelled"}

            min_samples = 20
            if len(df) < min_samples:
                return {
                    "success": False,
                    "error": f"Insufficient training data ({len(df)} < {min_samples})"
                }

            report_progress(20, f"Processing {len(df)} samples...")

            from app.services.ai.feature_engineering import FeatureEngineer

            # Prepare features (single source of truth)
            feature_columns = FeatureEngineer.get_irrigation_model_features("response_predictor")
            df = FeatureEngineer.align_features(df, feature_columns)

            if "user_response" not in df.columns:
                return {"success": False, "error": "Missing required columns"}

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(30, "Encoding labels...")

            X = df[feature_columns].fillna(0)

            # Encode target labels
            label_encoder = LabelEncoder()
            y = label_encoder.fit_transform(df["user_response"])
            class_names = list(label_encoder.classes_)

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=self.validation_split,
                random_state=self.random_state,
                stratify=y if len(np.unique(y)) > 1 else None
            )

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(50, "Training response model...")

            # Train classifier
            model = RandomForestClassifier(
                n_estimators=100,
                max_depth=8,
                random_state=self.random_state,
                class_weight="balanced",
                n_jobs=-1
            )
            model.fit(X_train_scaled, y_train)

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(70, "Evaluating model...")

            # Evaluate
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)
            y_pred = model.predict(X_test_scaled)
            mae = mean_absolute_error(y_test, y_pred)
            mape = float(np.mean(np.abs((y_test - y_pred) / np.maximum(y_test, 1.0))))

            # Cross-validation
            cv_scores = cross_val_score(
                model, X_train_scaled, y_train,
                cv=min(self.cross_validation_folds, len(X_train)),
                scoring="accuracy"
            )

            # Feature importance
            feature_importance = dict(zip(feature_columns, model.feature_importances_))

            # Classification report + additional metrics
            y_pred = model.predict(X_test_scaled)
            report = classification_report(y_test, y_pred, target_names=class_names, output_dict=True)
            macro_f1 = f1_score(y_test, y_pred, average="macro") if len(np.unique(y_test)) > 1 else 0.0
            balanced_acc = (
                balanced_accuracy_score(y_test, y_pred)
                if len(np.unique(y_test)) > 1
                else accuracy_score(y_test, y_pred)
            )

            if cancelled():
                return {"success": False, "error": "cancelled"}

            # Save model if requested
            model_name = "irrigation_response"
            if save_model:
                report_progress(85, "Saving model...")
                metrics = {
                    "train_score": float(train_score),
                    "test_score": float(test_score),
                    "cv_mean": float(np.mean(cv_scores)),
                    "cv_std": float(np.std(cv_scores)),
                    "macro_f1": float(macro_f1),
                    "balanced_accuracy": float(balanced_acc),
                }
                metadata = {
                    "model_type": "irrigation_response_prediction",
                    "features": feature_columns,
                    "metrics": metrics,
                    "parameters": {"class_names": class_names},
                    "training_samples": len(X_train),
                    "feature_importance": {k: float(v) for k, v in feature_importance.items()},
                }
                self.model_registry.save_model(
                    model_name=model_name,
                    model=model,
                    metadata=metadata,
                    scaler=scaler,
                    label_encoder=label_encoder
                )

            training_time = (datetime.now() - start_time).total_seconds()
            report_progress(95, "Training complete")

            return {
                "success": True,
                "model_name": model_name,
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "train_score": round(train_score, 4),
                "test_score": round(test_score, 4),
                "cv_mean": round(float(np.mean(cv_scores)), 4),
                "cv_std": round(float(np.std(cv_scores)), 4),
                "macro_f1": round(float(macro_f1), 4),
                "balanced_accuracy": round(float(balanced_acc), 4),
                "class_names": class_names,
                "classification_report": report,
                "feature_importance": {k: round(float(v), 4) for k, v in feature_importance.items()},
                "training_time_seconds": round(training_time, 2),
            }

        except Exception as e:
            if str(e) == "cancelled":
                return {"success": False, "error": "cancelled"}
            self.logger.error(f"Failed to train irrigation response model: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def train_irrigation_timing_model(
        self,
        unit_id: Optional[int] = None,
        days: int = 120,
        save_model: bool = True,
        *,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Train model to predict preferred irrigation hour (classification).

        Learns timing preferences from delayed irrigation responses.

        Features:
        - Time of detection (hour, day of week, weekend)
        - Current soil moisture and environment
        - Hours since last irrigation

        Target:
        - Preferred hour bucket (0-23)
        """
        import numpy as np
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler, LabelEncoder
        from sklearn.metrics import accuracy_score

        start_time = datetime.now()

        def cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        def report_progress(progress: float, message: Optional[str] = None) -> None:
            if progress_callback:
                progress_callback(float(progress), message)

        try:
            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(10, "Collecting timing training data...")

            df = self._collect_irrigation_timing_data(unit_id, days)
            if cancelled():
                return {"success": False, "error": "cancelled"}

            min_samples = 25
            if len(df) < min_samples:
                return {
                    "success": False,
                    "error": f"Insufficient training data ({len(df)} < {min_samples})"
                }

            report_progress(20, f"Processing {len(df)} samples...")

            from app.services.ai.feature_engineering import FeatureEngineer

            feature_columns = FeatureEngineer.get_irrigation_model_features("timing_predictor")
            df = FeatureEngineer.align_features(df, feature_columns)

            if "preferred_hour" not in df.columns:
                return {"success": False, "error": "Missing required columns"}

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(30, "Encoding labels...")

            X = df[feature_columns].fillna(0)
            label_encoder = LabelEncoder()
            y = label_encoder.fit_transform(df["preferred_hour"].astype(int))
            class_names = list(label_encoder.classes_)

            X_train, X_test, y_train, y_test = train_test_split(
                X,
                y,
                test_size=self.validation_split,
                random_state=self.random_state,
                stratify=y if len(np.unique(y)) > 1 else None,
            )

            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(50, "Training timing model...")

            model = RandomForestClassifier(
                n_estimators=120,
                max_depth=10,
                random_state=self.random_state,
                class_weight="balanced",
                n_jobs=-1,
            )
            model.fit(X_train_scaled, y_train)

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(70, "Evaluating model...")

            y_pred = model.predict(X_test_scaled)
            proba = model.predict_proba(X_test_scaled)

            top1_accuracy = float(accuracy_score(y_test, y_pred))

            top3_hits = []
            reciprocal_ranks = []
            for idx, probs in enumerate(proba):
                order = np.argsort(probs)[::-1]
                top3 = order[:3]
                top3_hits.append(1.0 if y_test[idx] in top3 else 0.0)
                rank = int(np.where(order == y_test[idx])[0][0]) + 1
                reciprocal_ranks.append(1.0 / rank)

            top3_accuracy = float(np.mean(top3_hits))
            mrr = float(np.mean(reciprocal_ranks))

            cv_scores = cross_val_score(
                model,
                X_train_scaled,
                y_train,
                cv=min(self.cross_validation_folds, len(X_train)),
                scoring="accuracy",
            )

            feature_importance = dict(zip(feature_columns, model.feature_importances_))

            if cancelled():
                return {"success": False, "error": "cancelled"}

            model_name = "irrigation_timing"
            if save_model:
                report_progress(85, "Saving model...")
                metrics = {
                    "top1_accuracy": float(top1_accuracy),
                    "top3_accuracy": float(top3_accuracy),
                    "mrr": float(mrr),
                    "cv_mean": float(np.mean(cv_scores)),
                    "cv_std": float(np.std(cv_scores)),
                }
                metadata = {
                    "model_type": "irrigation_timing_prediction",
                    "features": feature_columns,
                    "metrics": metrics,
                    "parameters": {"class_names": class_names},
                    "training_samples": len(X_train),
                    "feature_importance": {k: float(v) for k, v in feature_importance.items()},
                }
                self.model_registry.save_model(
                    model_name=model_name,
                    model=model,
                    metadata=metadata,
                    scaler=scaler,
                    label_encoder=label_encoder,
                )

            training_time = (datetime.now() - start_time).total_seconds()
            report_progress(95, "Training complete")

            return {
                "success": True,
                "model_name": model_name,
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "top1_accuracy": round(top1_accuracy, 4),
                "top3_accuracy": round(top3_accuracy, 4),
                "mrr": round(mrr, 4),
                "cv_mean": round(float(np.mean(cv_scores)), 4),
                "cv_std": round(float(np.std(cv_scores)), 4),
                "feature_importance": {k: round(float(v), 4) for k, v in feature_importance.items()},
                "training_time_seconds": round(training_time, 2),
            }

        except Exception as e:
            if str(e) == "cancelled":
                return {"success": False, "error": "cancelled"}
            self.logger.error(f"Failed to train irrigation timing model: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def train_irrigation_duration_model(
        self,
        unit_id: Optional[int] = None,
        days: int = 90,
        save_model: bool = True,
        *,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Train model to predict optimal irrigation duration.
        
        Learns the relationship between duration and moisture increase
        to recommend optimal watering time.
        
        Features:
        - Soil moisture before irrigation
        - Target moisture level
        - Temperature, humidity
        - Historical duration outcomes
        
        Target:
        - Optimal duration in seconds
        
        Args:
            unit_id: Optional unit filter
            days: Days of training data to use
            save_model: Whether to save the trained model
            cancel_event: Optional threading event for cancellation
            progress_callback: Optional callback for progress updates
            
        Returns:
            Training results with metrics
        """
        # Lazy load ML libraries
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import train_test_split, cross_val_score
        from sklearn.preprocessing import StandardScaler

        start_time = datetime.now()

        def cancelled() -> bool:
            return cancel_event is not None and cancel_event.is_set()

        def report_progress(progress: float, message: Optional[str] = None) -> None:
            if progress_callback:
                progress_callback(float(progress), message)

        try:
            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(10, "Collecting duration training data...")

            # Collect training data
            df = self._collect_irrigation_duration_data(unit_id, days)
            if cancelled():
                return {"success": False, "error": "cancelled"}

            min_samples = 15
            if len(df) < min_samples:
                return {
                    "success": False,
                    "error": f"Insufficient training data ({len(df)} < {min_samples})"
                }

            report_progress(20, f"Processing {len(df)} samples...")

            from app.services.ai.feature_engineering import FeatureEngineer

            # Prepare features (single source of truth)
            feature_columns = FeatureEngineer.get_irrigation_model_features("duration_optimizer")
            df = FeatureEngineer.align_features(df, feature_columns)

            if "execution_duration_seconds" not in df.columns:
                return {"success": False, "error": "Missing required columns"}

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(30, "Preparing features...")

            X = df[feature_columns].fillna(0)
            y = df["execution_duration_seconds"]

            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y,
                test_size=self.validation_split,
                random_state=self.random_state
            )

            # Scale features
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(50, "Training duration model...")

            # Train model
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=8,
                random_state=self.random_state,
                n_jobs=-1
            )
            model.fit(X_train_scaled, y_train)

            if cancelled():
                return {"success": False, "error": "cancelled"}

            report_progress(70, "Evaluating model...")

            # Evaluate
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)

            # Cross-validation
            cv_scores = cross_val_score(
                model, X_train_scaled, y_train,
                cv=min(self.cross_validation_folds, len(X_train)),
                scoring="r2"
            )

            # Feature importance
            feature_importance = dict(zip(feature_columns, model.feature_importances_))

            if cancelled():
                return {"success": False, "error": "cancelled"}

            # Save model if requested
            model_name = "irrigation_duration"
            if save_model:
                report_progress(85, "Saving model...")
                metrics = {
                    "train_score": float(train_score),
                    "test_score": float(test_score),
                    "cv_mean": float(np.mean(cv_scores)),
                    "cv_std": float(np.std(cv_scores)),
                    "mae": float(mae),
                    "mape": float(mape),
                }
                metadata = {
                    "model_type": "irrigation_duration_prediction",
                    "features": feature_columns,
                    "metrics": metrics,
                    "training_samples": len(X_train),
                    "feature_importance": {k: float(v) for k, v in feature_importance.items()},
                }
                self.model_registry.save_model(
                    model_name=model_name,
                    model=model,
                    metadata=metadata,
                    scaler=scaler
                )

            training_time = (datetime.now() - start_time).total_seconds()
            report_progress(95, "Training complete")

            return {
                "success": True,
                "model_name": model_name,
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "train_score": round(train_score, 4),
                "test_score": round(test_score, 4),
                "cv_mean": round(float(np.mean(cv_scores)), 4),
                "cv_std": round(float(np.std(cv_scores)), 4),
                "mae": round(float(mae), 4),
                "mape": round(float(mape), 4),
                "feature_importance": {k: round(float(v), 4) for k, v in feature_importance.items()},
                "training_time_seconds": round(training_time, 2),
            }

        except Exception as e:
            if str(e) == "cancelled":
                return {"success": False, "error": "cancelled"}
            self.logger.error(f"Failed to train irrigation duration model: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ==================== Irrigation Data Collection Helpers ====================

    def _collect_irrigation_threshold_data(
        self,
        unit_id: Optional[int] = None,
        days: int = 90,
    ):
        """
        Collect training data for threshold prediction model.
        
        Derives optimal threshold from feedback patterns.
        """
        import pandas as pd

        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()
            
            # Get feedback data with environmental context
            data = self.training_data_repo.get_irrigation_threshold_training_data(
                unit_id=unit_id,
                start_date=start_date,
            )

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)

            # Engineer optimal threshold from timing feedback
            # "triggered_too_late" -> optimal higher than current
            # "triggered_too_early" -> optimal lower than current
            # "just_right" -> optimal equals current
            df["optimal_threshold"] = df.apply(
                lambda row: self._calculate_optimal_threshold_from_feedback(
                    current=row.get("current_threshold", 50.0),
                    feedback=row.get("feedback_response", "just_right"),
                ),
                axis=1
            )

            # Add growth stage encoding
            df["plant_stage_vegetative"] = (df.get("growth_stage", "Vegetative") == "Vegetative").astype(int)
            df["plant_stage_flowering"] = (df.get("growth_stage", "") == "Flowering").astype(int)
            df["plant_stage_fruiting"] = (df.get("growth_stage", "") == "Fruiting").astype(int)

            # Default user consistency if not present
            if "user_consistency_score" not in df.columns:
                df["user_consistency_score"] = 0.7

            return df

        except Exception as e:
            self.logger.error(f"Failed to collect threshold training data: {e}", exc_info=True)
            return pd.DataFrame()

    def _collect_irrigation_response_data(
        self,
        unit_id: Optional[int] = None,
        days: int = 90,
    ):
        """Collect training data for response prediction model."""
        import pandas as pd

        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()

            data = self.training_data_repo.get_irrigation_response_training_data(
                unit_id=unit_id,
                start_date=start_date,
            )

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)

            # Add temporal features
            if "detected_at" in df.columns:
                df["detected_at"] = pd.to_datetime(df["detected_at"])
                df["hour_of_day"] = df["detected_at"].dt.hour
                df["day_of_week"] = df["detected_at"].dt.dayofweek
                df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

            return df

        except Exception as e:
            self.logger.error(f"Failed to collect response training data: {e}", exc_info=True)
            return pd.DataFrame()

    def _collect_irrigation_duration_data(
        self,
        unit_id: Optional[int] = None,
        days: int = 90,
    ):
        """Collect training data for duration prediction model."""
        import pandas as pd

        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()

            data = self.training_data_repo.get_irrigation_duration_training_data(
                unit_id=unit_id,
                start_date=start_date,
            )

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)

            # Calculate target moisture (threshold + buffer)
            if "soil_moisture_threshold" in df.columns:
                df["target_moisture"] = df["soil_moisture_threshold"] + 15.0
            else:
                df["target_moisture"] = 65.0  # Default target

            # Calculate average previous duration for each unit
            if "execution_duration_seconds" in df.columns:
                df["avg_previous_duration"] = df["execution_duration_seconds"].expanding().mean().shift(1).fillna(120)

            return df

        except Exception as e:
            self.logger.error(f"Failed to collect duration training data: {e}", exc_info=True)
            return pd.DataFrame()

    @staticmethod
    def _calculate_optimal_threshold_from_feedback(
        current: float,
        feedback: str,
    ) -> float:
        """
        Calculate optimal threshold from user feedback.
        
        Args:
            current: Current threshold setting
            feedback: User feedback (triggered_too_early, triggered_too_late, just_right)
            
        Returns:
            Estimated optimal threshold
        """
        # Adjustment based on feedback type
        adjustments = {
            "triggered_too_late": 5.0,   # Trigger earlier -> higher threshold
            "just_right": 0.0,          # Current is optimal
            "triggered_too_early": -5.0,  # Trigger later -> lower threshold
        }
        adjustment = adjustments.get(feedback, 0.0)
        return max(20.0, min(80.0, current + adjustment))

    def _collect_irrigation_timing_data(
        self,
        unit_id: Optional[int] = None,
        days: int = 120,
    ):
        """Collect training data for irrigation timing prediction model."""
        import pandas as pd

        try:
            start_date = (datetime.now() - timedelta(days=days)).isoformat()

            data = self.training_data_repo.get_irrigation_timing_training_data(
                unit_id=unit_id,
                start_date=start_date,
            )

            if not data:
                return pd.DataFrame()

            df = pd.DataFrame(data)

            # Temporal features from detected_at
            if "detected_at" in df.columns:
                df["detected_at"] = pd.to_datetime(df["detected_at"])
                df["hour_of_day"] = df["detected_at"].dt.hour
                df["day_of_week"] = df["detected_at"].dt.dayofweek
                df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)

            # Preferred hour label from delayed_until
            if "delayed_until" in df.columns:
                df["delayed_until"] = pd.to_datetime(df["delayed_until"])
                df["preferred_hour"] = df["delayed_until"].dt.hour

            # Drop rows without target
            df = df.dropna(subset=["preferred_hour"])
            if df.empty:
                return pd.DataFrame()

            return df

        except Exception as e:
            self.logger.error(f"Failed to collect timing training data: {e}", exc_info=True)
            return pd.DataFrame()

    # ==================== Plant-Specific Fine-Tuning ====================

    def fine_tune_for_plant_type(
        self,
        base_model_name: str,
        plant_type: str,
        min_samples: int = 10,
        save_model: bool = True,
    ) -> Dict[str, Any]:
        """
        Fine-tune a base model for a specific plant type using harvest outcomes.
        
        Creates specialized models like:
        - climate_optimizer_tomato
        - climate_optimizer_pepper
        - growth_predictor_lettuce
        
        Args:
            base_model_name: Base model to fine-tune (e.g., 'climate_optimizer')
            plant_type: Plant type to specialize for
            min_samples: Minimum harvest records needed for fine-tuning
            save_model: Whether to save the fine-tuned model
            
        Returns:
            Fine-tuning results with metrics
        """
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, r2_score

        start_time = datetime.now()
        specialized_name = f"{base_model_name}_{plant_type.lower().replace(' ', '_')}"

        try:
            # Get harvest data for this plant type
            harvest_data = self.training_data_repo.get_harvest_training_data(
                plant_type=plant_type,
                min_quality=3,  # Only learn from decent+ grows
                days_limit=730,  # 2 years of data
            )

            if len(harvest_data) < min_samples:
                self.logger.info(
                    f"Insufficient harvest data for {plant_type} fine-tuning: "
                    f"{len(harvest_data)}/{min_samples}"
                )
                return {
                    "success": False,
                    "error": f"Insufficient data ({len(harvest_data)}/{min_samples})",
                    "plant_type": plant_type,
                }

            self.logger.info(
                f"Fine-tuning {base_model_name} for {plant_type} with {len(harvest_data)} records"
            )

            # Prepare features based on model type
            if base_model_name == "climate_optimizer":
                return self._fine_tune_climate_model(
                    harvest_data, plant_type, specialized_name, save_model
                )
            elif base_model_name == "growth_predictor":
                return self._fine_tune_growth_model(
                    harvest_data, plant_type, specialized_name, save_model
                )
            else:
                return {
                    "success": False,
                    "error": f"Fine-tuning not implemented for {base_model_name}",
                    "plant_type": plant_type,
                }

        except Exception as e:
            self.logger.error(f"Failed to fine-tune {base_model_name} for {plant_type}: {e}", exc_info=True)
            return {"success": False, "error": str(e), "plant_type": plant_type}

    def _fine_tune_climate_model(
        self,
        harvest_data,
        plant_type: str,
        model_name: str,
        save_model: bool,
    ) -> Dict[str, Any]:
        """Fine-tune climate model for a specific plant type."""
        import numpy as np
        from sklearn.ensemble import GradientBoostingRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, r2_score

        try:
            # Filter to records with required fields
            required_cols = ["avg_temperature", "avg_humidity", "quality_rating"]
            df = harvest_data.dropna(subset=required_cols)

            if len(df) < 5:
                return {
                    "success": False,
                    "error": "Insufficient complete records after filtering",
                    "plant_type": plant_type,
                }

            # Features: growth stage indicators (approximated from duration ratios)
            # Target: quality rating (we learn what conditions led to high quality)
            X = df[["avg_temperature", "avg_humidity"]].values
            y_quality = df["quality_rating"].values

            # Train model to predict quality from conditions
            # This lets us find conditions that maximize quality
            X_train, X_test, y_train, y_test = train_test_split(
                X, y_quality, test_size=0.2, random_state=42
            )

            model = GradientBoostingRegressor(
                n_estimators=50,
                max_depth=3,
                random_state=42
            )
            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)

            # Extract optimal conditions (conditions from top quality grows)
            top_df = df.nlargest(min(10, len(df)), "quality_rating")
            optimal_conditions = {
                "temperature": round(top_df["avg_temperature"].mean(), 1),
                "humidity": round(top_df["avg_humidity"].mean(), 1),
            }

            # Save model
            if save_model:
                self.model_registry.save_model(model_name, model)
                
                # Also save optimal conditions as metadata
                metadata = {
                    "plant_type": plant_type,
                    "optimal_conditions": optimal_conditions,
                    "training_samples": len(df),
                    "mae": round(mae, 3),
                    "r2": round(r2, 3),
                }
                self.model_registry.save_model(f"{model_name}_meta", metadata)

            self.logger.info(
                f"✅ Fine-tuned climate model for {plant_type}: MAE={mae:.3f}, R²={r2:.3f}"
            )

            return {
                "success": True,
                "model_name": model_name,
                "plant_type": plant_type,
                "training_samples": len(df),
                "metrics": {"mae": round(mae, 3), "r2": round(r2, 3)},
                "optimal_conditions": optimal_conditions,
            }

        except Exception as e:
            self.logger.error(f"Climate fine-tuning error: {e}", exc_info=True)
            return {"success": False, "error": str(e), "plant_type": plant_type}

    def _fine_tune_growth_model(
        self,
        harvest_data,
        plant_type: str,
        model_name: str,
        save_model: bool,
    ) -> Dict[str, Any]:
        """Fine-tune growth predictor for a specific plant type."""
        import numpy as np
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import mean_absolute_error, r2_score

        try:
            # Filter to records with duration data
            required_cols = ["total_days", "avg_temperature", "avg_humidity"]
            df = harvest_data.dropna(subset=required_cols)

            if len(df) < 5:
                return {
                    "success": False,
                    "error": "Insufficient complete records after filtering",
                    "plant_type": plant_type,
                }

            # Features: environmental conditions
            # Target: total days to harvest
            X = df[["avg_temperature", "avg_humidity"]].values
            y_days = df["total_days"].values

            X_train, X_test, y_train, y_test = train_test_split(
                X, y_days, test_size=0.2, random_state=42
            )

            model = RandomForestRegressor(
                n_estimators=50,
                max_depth=5,
                random_state=42
            )
            model.fit(X_train, y_train)

            # Evaluate
            y_pred = model.predict(X_test)
            mae = mean_absolute_error(y_test, y_pred)
            r2 = r2_score(y_test, y_pred)

            # Calculate average growth duration
            avg_duration = {
                "total_days": int(df["total_days"].mean()),
                "std_days": int(df["total_days"].std()),
            }
            
            if "vegetative_days" in df.columns and df["vegetative_days"].notna().any():
                avg_duration["vegetative_days"] = int(df["vegetative_days"].mean())
            if "flowering_days" in df.columns and df["flowering_days"].notna().any():
                avg_duration["flowering_days"] = int(df["flowering_days"].mean())

            # Save model
            if save_model:
                self.model_registry.save_model(model_name, model)
                
                metadata = {
                    "plant_type": plant_type,
                    "avg_duration": avg_duration,
                    "training_samples": len(df),
                    "mae_days": round(mae, 1),
                    "r2": round(r2, 3),
                }
                self.model_registry.save_model(f"{model_name}_meta", metadata)

            self.logger.info(
                f"✅ Fine-tuned growth model for {plant_type}: MAE={mae:.1f} days, R²={r2:.3f}"
            )

            return {
                "success": True,
                "model_name": model_name,
                "plant_type": plant_type,
                "training_samples": len(df),
                "metrics": {"mae_days": round(mae, 1), "r2": round(r2, 3)},
                "avg_duration": avg_duration,
            }

        except Exception as e:
            self.logger.error(f"Growth fine-tuning error: {e}", exc_info=True)
            return {"success": False, "error": str(e), "plant_type": plant_type}

    def fine_tune_all_plant_types(
        self,
        base_model_name: str = "climate_optimizer",
        min_samples: int = 10,
    ) -> Dict[str, Any]:
        """
        Fine-tune models for all plant types with sufficient harvest data.
        
        Args:
            base_model_name: Base model to fine-tune
            min_samples: Minimum samples required per plant type
            
        Returns:
            Summary of all fine-tuning results
        """
        try:
            # Get all unique plant types from harvest data
            all_harvest_data = self.training_data_repo.get_harvest_training_data(
                min_quality=1,
                days_limit=730,
            )

            if all_harvest_data.empty:
                return {"success": False, "error": "No harvest data available"}

            # Group by plant type and count
            plant_counts = all_harvest_data.groupby("plant_type").size()
            eligible_plants = plant_counts[plant_counts >= min_samples].index.tolist()

            if not eligible_plants:
                return {
                    "success": False,
                    "error": f"No plant types with >={min_samples} harvests",
                    "plant_counts": plant_counts.to_dict(),
                }

            results = {}
            for plant_type in eligible_plants:
                result = self.fine_tune_for_plant_type(
                    base_model_name=base_model_name,
                    plant_type=plant_type,
                    min_samples=min_samples,
                    save_model=True,
                )
                results[plant_type] = result

            successful = sum(1 for r in results.values() if r.get("success", False))

            return {
                "success": successful > 0,
                "total_plant_types": len(eligible_plants),
                "successful_fine_tunings": successful,
                "results": results,
            }

        except Exception as e:
            self.logger.error(f"Failed to fine-tune all plant types: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    # ========================================================================
    # Plant Health Score ML Training
    # ========================================================================

    def train_health_score_model(
        self,
        unit_id: Optional[int] = None,
        plant_type: Optional[str] = None,
        days: int = 365,
        save_model: bool = True,
        *,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Train plant health score regressor.

        Target: Harvest quality rating × 20 (maps 1-5 to 20-100)
        Features: PLANT_HEALTH_FEATURES_V1
        Algorithm: GradientBoostingRegressor

        Args:
            unit_id: Optional filter by unit
            plant_type: Optional filter by plant type
            days: Training data window (default 365)
            save_model: Whether to save the trained model
            cancel_event: Optional event to signal cancellation
            progress_callback: Optional progress update callback

        Returns:
            Training result dictionary with metrics
        """
        import time
        start_time = time.time()

        try:
            # Lazy load ML libraries
            import numpy as np
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.model_selection import train_test_split, cross_val_score
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

            from app.services.ai.feature_engineering import (
                FeatureEngineer,
                PlantHealthFeatureExtractor,
            )

            MIN_SAMPLES = 50

            if progress_callback:
                progress_callback(0.1, "Collecting training data...")

            # 1. Collect training data from harvests
            harvest_data = self.training_data_repo.get_health_score_training_data(
                unit_id=unit_id,
                plant_type=plant_type,
                days_limit=days,
                min_quality=1,
            )

            if cancel_event and cancel_event.is_set():
                return {"success": False, "error": "Training cancelled"}

            if len(harvest_data) < MIN_SAMPLES:
                self.logger.warning(
                    f"Insufficient training data: {len(harvest_data)} < {MIN_SAMPLES}"
                )
                return {
                    "success": False,
                    "error": f"Insufficient training data: {len(harvest_data)} samples (need {MIN_SAMPLES})",
                    "samples_available": len(harvest_data),
                    "samples_required": MIN_SAMPLES,
                }

            if progress_callback:
                progress_callback(0.3, "Extracting features...")

            # 2. Extract features
            feature_extractor = PlantHealthFeatureExtractor()
            X_df = feature_extractor.extract_training_features(harvest_data)

            # Target: quality_rating × 20 (maps 1-5 to 20-100)
            y = np.array([sample.get("quality_rating", 3) * 20 for sample in harvest_data])

            if cancel_event and cancel_event.is_set():
                return {"success": False, "error": "Training cancelled"}

            if progress_callback:
                progress_callback(0.5, "Training model...")

            # 3. Split and scale
            X_train, X_test, y_train, y_test = train_test_split(
                X_df, y, test_size=0.2, random_state=self.random_state
            )
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # 4. Train model
            model = GradientBoostingRegressor(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=self.random_state,
            )
            model.fit(X_train_scaled, y_train)

            if cancel_event and cancel_event.is_set():
                return {"success": False, "error": "Training cancelled"}

            if progress_callback:
                progress_callback(0.7, "Evaluating model...")

            # 5. Evaluate
            train_score = model.score(X_train_scaled, y_train)
            test_score = model.score(X_test_scaled, y_test)
            y_pred = model.predict(X_test_scaled)
            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)

            # Cross-validation
            cv_scores = cross_val_score(
                model, X_train_scaled, y_train, cv=min(5, len(X_train) // 10)
            )

            # Feature importance
            feature_importance = dict(
                zip(X_df.columns, model.feature_importances_)
            )
            sorted_importance = dict(
                sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
            )

            if progress_callback:
                progress_callback(0.9, "Saving model...")

            # 6. Save model
            model_name = "plant_health_regressor"
            if save_model:
                self.model_registry.save_model(
                    model_name,
                    model,
                    metadata={
                        "r2_score": float(test_score),
                        "mae": float(mae),
                        "rmse": float(rmse),
                        "features": list(X_df.columns),
                        "training_samples": len(X_train),
                        "test_samples": len(X_test),
                        "plant_type": plant_type,
                        "unit_id": unit_id,
                    },
                    artifacts={"scaler": scaler},
                )

            training_time = time.time() - start_time

            self.logger.info(
                f"✅ Trained plant health regressor: R²={test_score:.3f}, MAE={mae:.1f}, "
                f"samples={len(harvest_data)}"
            )

            if progress_callback:
                progress_callback(1.0, "Training complete")

            return {
                "success": True,
                "model_name": model_name,
                "metrics": {
                    "r2_score": round(test_score, 4),
                    "train_r2": round(train_score, 4),
                    "mae": round(mae, 2),
                    "rmse": round(rmse, 2),
                    "cv_mean": round(float(np.mean(cv_scores)), 4),
                    "cv_std": round(float(np.std(cv_scores)), 4),
                },
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "feature_importance": sorted_importance,
                "training_time_seconds": round(training_time, 2),
                "plant_type": plant_type,
                "unit_id": unit_id,
            }

        except Exception as e:
            self.logger.error(f"Health score model training error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}

    def train_health_status_classifier(
        self,
        unit_id: Optional[int] = None,
        days: int = 365,
        save_model: bool = True,
        *,
        cancel_event: Optional[threading.Event] = None,
        progress_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Train plant health status classifier (ensemble component 2).

        Target: User-reported health status (healthy/stressed/critical)
        Features: PLANT_HEALTH_FEATURES_V1
        Algorithm: GradientBoostingClassifier

        Args:
            unit_id: Optional filter by unit
            days: Training data window (default 365)
            save_model: Whether to save the trained model
            cancel_event: Optional event to signal cancellation
            progress_callback: Optional progress update callback

        Returns:
            Training result dictionary with metrics
        """
        import time
        start_time = time.time()

        try:
            # Lazy load ML libraries
            import numpy as np
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.model_selection import train_test_split, cross_val_score
            from sklearn.preprocessing import StandardScaler, LabelEncoder
            from sklearn.metrics import accuracy_score, classification_report

            from app.services.ai.feature_engineering import PlantHealthFeatureExtractor

            MIN_SAMPLES = 50

            if progress_callback:
                progress_callback(0.1, "Collecting training data...")

            # 1. Collect training data from health observations
            observation_data = self.training_data_repo.get_health_status_training_data(
                unit_id=unit_id,
                days_limit=days,
                confirmed_only=True,
            )

            if cancel_event and cancel_event.is_set():
                return {"success": False, "error": "Training cancelled"}

            # 2. Generate synthetic healthy samples from periods without issues
            healthy_samples = self.training_data_repo.generate_health_baseline_samples(
                unit_id=unit_id,
                num_samples=max(len(observation_data), MIN_SAMPLES // 2),
            )

            all_samples = observation_data + healthy_samples

            if len(all_samples) < MIN_SAMPLES:
                self.logger.warning(
                    f"Insufficient training data: {len(all_samples)} < {MIN_SAMPLES}"
                )
                return {
                    "success": False,
                    "error": f"Insufficient training data: {len(all_samples)} samples (need {MIN_SAMPLES})",
                    "samples_available": len(all_samples),
                    "observation_samples": len(observation_data),
                    "synthetic_samples": len(healthy_samples),
                    "samples_required": MIN_SAMPLES,
                }

            if progress_callback:
                progress_callback(0.3, "Extracting features...")

            # 3. Extract features and labels
            feature_extractor = PlantHealthFeatureExtractor()
            X_df = feature_extractor.extract_training_features(all_samples)

            # Encode labels
            label_encoder = LabelEncoder()
            labels = [s.get("health_status", "healthy") for s in all_samples]
            y = label_encoder.fit_transform(labels)

            if cancel_event and cancel_event.is_set():
                return {"success": False, "error": "Training cancelled"}

            if progress_callback:
                progress_callback(0.5, "Training classifier...")

            # 4. Split and scale
            X_train, X_test, y_train, y_test = train_test_split(
                X_df, y, test_size=0.2, random_state=self.random_state, stratify=y
            )
            scaler = StandardScaler()
            X_train_scaled = scaler.fit_transform(X_train)
            X_test_scaled = scaler.transform(X_test)

            # 5. Train classifier
            model = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=self.random_state,
            )
            model.fit(X_train_scaled, y_train)

            if cancel_event and cancel_event.is_set():
                return {"success": False, "error": "Training cancelled"}

            if progress_callback:
                progress_callback(0.7, "Evaluating classifier...")

            # 6. Evaluate
            train_accuracy = model.score(X_train_scaled, y_train)
            test_accuracy = model.score(X_test_scaled, y_test)
            y_pred = model.predict(X_test_scaled)

            # Classification report
            class_names = label_encoder.classes_.tolist()
            report = classification_report(
                y_test, y_pred, target_names=class_names, output_dict=True
            )

            # Cross-validation
            cv_scores = cross_val_score(
                model, X_train_scaled, y_train, cv=min(5, len(X_train) // 10)
            )

            # Feature importance
            feature_importance = dict(
                zip(X_df.columns, model.feature_importances_)
            )
            sorted_importance = dict(
                sorted(feature_importance.items(), key=lambda x: x[1], reverse=True)[:10]
            )

            if progress_callback:
                progress_callback(0.9, "Saving classifier...")

            # 7. Save model
            model_name = "plant_health_classifier"
            if save_model:
                self.model_registry.save_model(
                    model_name,
                    model,
                    metadata={
                        "accuracy": float(test_accuracy),
                        "features": list(X_df.columns),
                        "classes": class_names,
                        "training_samples": len(X_train),
                        "test_samples": len(X_test),
                        "unit_id": unit_id,
                    },
                    artifacts={
                        "scaler": scaler,
                        "label_encoder": label_encoder,
                    },
                )

            training_time = time.time() - start_time

            self.logger.info(
                f"✅ Trained plant health classifier: accuracy={test_accuracy:.3f}, "
                f"samples={len(all_samples)}, classes={class_names}"
            )

            if progress_callback:
                progress_callback(1.0, "Training complete")

            return {
                "success": True,
                "model_name": model_name,
                "metrics": {
                    "accuracy": round(test_accuracy, 4),
                    "train_accuracy": round(train_accuracy, 4),
                    "cv_mean": round(float(np.mean(cv_scores)), 4),
                    "cv_std": round(float(np.std(cv_scores)), 4),
                    "per_class": {
                        cls: {
                            "precision": round(report[cls]["precision"], 3),
                            "recall": round(report[cls]["recall"], 3),
                            "f1-score": round(report[cls]["f1-score"], 3),
                        }
                        for cls in class_names
                        if cls in report
                    },
                },
                "training_samples": len(X_train),
                "test_samples": len(X_test),
                "classes": class_names,
                "feature_importance": sorted_importance,
                "training_time_seconds": round(training_time, 2),
                "unit_id": unit_id,
            }

        except Exception as e:
            self.logger.error(f"Health status classifier training error: {e}", exc_info=True)
            return {"success": False, "error": str(e)}
