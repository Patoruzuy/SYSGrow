"""
Model Registry Service
======================
Manages ML model versioning, loading, and lifecycle.

Provides:
- Model version management
- Safe model loading/saving
- Model metadata tracking
- Production deployment control
"""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, TYPE_CHECKING, Iterable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import joblib

from app.utils.time import iso_now

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ModelStatus(Enum):
    """Model deployment status."""

    TRAINING = "training"
    VALIDATING = "validating"
    PRODUCTION = "production"
    ARCHIVED = "archived"
    FAILED = "failed"


@dataclass
class ModelMetadata:
    """
    Metadata for a trained model version.
    
    Attributes:
        model_name: Name of the model (e.g., 'disease_predictor')
        version: Version identifier (e.g., 'v1', 'v2')
        created_at: ISO timestamp of creation
        status: Current deployment status
        metrics: Training/validation metrics
        features: List of feature names used
        training_data_points: Number of samples used
        parameters: Model hyperparameters
        notes: Additional notes
    """

    model_name: str
    version: str
    created_at: str
    status: ModelStatus
    metrics: Dict[str, float]
    features: List[str]
    training_data_points: int
    parameters: Dict[str, Any]
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelMetadata":
        """Create from dictionary."""
        data["status"] = ModelStatus(data["status"])
        return cls(**data)


class ModelRegistry:
    """
    ML model registry for version management and deployment.
    
    Directory structure:
        models/
        ├── registry.json          (model inventory)
        ├── disease_predictor/
        │   ├── v1/
        │   │   ├── model.pkl
        │   │   ├── scaler.pkl
        │   │   └── metadata.json
        │   ├── v2/
        │   │   ├── model.pkl
        │   │   ├── scaler.pkl
        │   │   └── metadata.json
        │   └── production -> v2  (symlink)
        └── climate_optimizer/
            └── v1/
                ├── model.pkl
                └── metadata.json
    """

    def __init__(self, base_path: Optional[Path] = None):
        """
        Initialize model registry.
        
        Args:
            base_path: Base directory for models (defaults to 'models/')
        """
        self.base_path = Path(base_path) if base_path else Path("models")
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        self.registry_file = self.base_path / "registry.json"
        # registry.json supports both legacy dict format and list-based entry format.
        # Keep it flexible to avoid breaking older training scripts.
        self._registry: Dict[str, Any] = self._load_registry()
        
        # Model cache to avoid reloading
        self._model_cache: Dict[str, Any] = {}

    def _parse_iso_ts(self, value: object) -> datetime:
        """Best-effort ISO timestamp parsing for registry sorting."""
        if value is None:
            return datetime.min
        text = str(value).strip()
        if not text:
            return datetime.min
        # Support "Z" suffix where present.
        if text.endswith("Z"):
            text = f"{text[:-1]}+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return datetime.min

    def _latest_entry(
        self,
        entries: List[Dict[str, Any]],
        *,
        version: Optional[str] = None,
        prefer_active: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if not entries:
            return None

        filtered = entries
        if version is not None:
            filtered = [e for e in entries if str(e.get("version")) == str(version)]
            if not filtered:
                return None

        if prefer_active:
            active = [
                e
                for e in filtered
                if str(e.get("status") or "").lower() in {"active", "production"}
            ]
            if active:
                filtered = active

        indexed: Iterable[Tuple[int, Dict[str, Any]]] = enumerate(filtered)
        idx, entry = max(
            indexed,
            key=lambda pair: (self._parse_iso_ts(pair[1].get("created_at")), pair[0]),
        )
        return entry

    def _map_status(self, raw_status: object) -> ModelStatus:
        """Map legacy registry status strings to ModelStatus enum."""
        text = str(raw_status or "").strip().lower()
        if text in {"active", "production"}:
            return ModelStatus.PRODUCTION
        if text in {"inactive", "archived"}:
            return ModelStatus.ARCHIVED
        try:
            return ModelStatus(text)
        except ValueError:
            return ModelStatus.ARCHIVED

    def _load_registry(self) -> Dict[str, Dict[str, Any]]:
        """Load registry from disk."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load registry: {e}", exc_info=True)
                return {}
        return {}

    def _save_registry(self) -> None:
        """Save registry to disk."""
        try:
            with open(self.registry_file, "w") as f:
                json.dump(self._registry, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry: {e}", exc_info=True)

    def _get_version_path(self, model_name: str, version: str) -> Path:
        """Get path to a model version directory."""
        return self.base_path / model_name / version

    def _get_production_path(self, model_name: str) -> Path:
        """Get path to production symlink."""
        return self.base_path / model_name / "production"

    def save_model(
        self,
        model_name: str,
        model: Any,
        metadata: ModelMetadata | Dict[str, Any],
        artifacts: Optional[Dict[str, Any]] = None,
        **legacy_artifacts: Any,
    ) -> str:
        """
        Save a trained model with metadata.
        
        Args:
            model_name: Name of the model
            model: Trained model object (will be pickled)
            metadata: Model metadata
            artifacts: Optional additional artifacts (e.g., scalers, encoders)
            
        Returns:
            Version ID of the saved model
        """
        # Merge legacy artifacts (e.g. scaler=...) into artifacts dict.
        merged_artifacts: Dict[str, Any] = {}
        if isinstance(artifacts, dict):
            merged_artifacts.update(artifacts)
        merged_artifacts.update({k: v for k, v in legacy_artifacts.items() if v is not None})

        if isinstance(metadata, ModelMetadata):
            version = metadata.version
            created_at = metadata.created_at
            metrics = metadata.metrics
            features_used = metadata.features
            hyperparameters = metadata.parameters
            training_samples = metadata.training_data_points
            status = "active" if metadata.status == ModelStatus.PRODUCTION else "inactive"
            notes = metadata.notes
        else:
            created_at = iso_now()
            version = str(metadata.get("version") or f"{datetime.now().strftime('%Y.%m.%d.%H%M%S')}")
            metrics = dict(metadata.get("metrics") or {})
            if not metrics:
                # Common trainer fields (kept for dashboard visibility).
                for key in ("accuracy", "precision", "recall", "f1_score", "train_score", "test_score", "cv_mean", "cv_std"):
                    if key in metadata:
                        metrics[key] = metadata[key]
                if "validation_score" in metadata:
                    metrics["validation_score"] = metadata["validation_score"]
            features_used = list(metadata.get("features") or metadata.get("features_used") or [])
            hyperparameters = dict(metadata.get("hyperparameters") or metadata.get("parameters") or {})
            training_samples = int(metadata.get("training_samples") or metadata.get("training_data_points") or 0)
            status = str(metadata.get("status") or "active")
            notes = str(metadata.get("notes") or "")

        return self.register_model(
            model=model,
            model_name=model_name,
            version=version,
            metrics=metrics,
            features_used=features_used,
            hyperparameters=hyperparameters,
            training_samples=training_samples,
            training_duration=float(metadata.get("training_time_seconds", 0.0))
            if isinstance(metadata, dict)
            else None,
            notes=notes,
            created_at=created_at,
            status=status,
            artifacts=merged_artifacts or None,
        )

    def register_model(
        self,
        *,
        model: Any,
        model_name: str,
        version: str,
        metrics: Optional[Dict[str, Any]] = None,
        features_used: Optional[List[str]] = None,
        hyperparameters: Optional[Dict[str, Any]] = None,
        training_samples: Optional[int] = None,
        training_duration: Optional[float] = None,
        notes: str = "",
        created_at: Optional[str] = None,
        status: str = "inactive",
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Register a model version using the list-based registry.json format.

        This matches the structure used by existing sample training scripts and the ML dashboard.
        """
        version_path = self._get_version_path(model_name, version)
        version_path.mkdir(parents=True, exist_ok=True)

        model_file = version_path / "model.joblib"
        joblib.dump(model, model_file)
        logger.info("Saved model to %s", model_file)

        if artifacts:
            for name, artifact in artifacts.items():
                artifact_file = version_path / f"{name}.joblib"
                joblib.dump(artifact, artifact_file)
                logger.info("Saved artifact %s to %s", name, artifact_file)

        entry = {
            "model_name": model_name,
            "version": version,
            "created_at": created_at or iso_now(),
            "training_samples": int(training_samples or 0),
            "validation_score": (metrics or {}).get("validation_score"),
            "metrics": metrics or {},
            "features_used": features_used or [],
            "hyperparameters": hyperparameters or {},
            "training_duration_seconds": training_duration,
            "status": status,
            "notes": notes,
        }

        existing = self._registry.get(model_name)
        if isinstance(existing, list):
            existing.append(entry)
        elif isinstance(existing, dict):
            # Preserve dict-based registry but also append list entries for metadata access.
            versions = existing.get("versions") if isinstance(existing.get("versions"), list) else []
            if version not in versions:
                versions.append(version)
            existing["versions"] = versions
            existing.setdefault("production_version", None)
            self._registry[model_name] = existing
            self._registry.setdefault(f"{model_name}__entries", []).append(entry)
        else:
            self._registry[model_name] = [entry]

        self._save_registry()
        self._clear_model_cache(model_name)
        return version

    def set_active_version(self, model_name: str, version: str) -> bool:
        """Legacy-friendly alias for promoting a version to production/active."""
        return self.promote_to_production(model_name, version)

    def load_model(
        self, model_name: str, version: Optional[str] = None, use_cache: bool = True
    ) -> Optional[Any]:
        """
        Load a model by name and version.
        
        Args:
            model_name: Name of the model
            version: Version to load (defaults to production version)
            use_cache: Whether to use cached model if available
            
        Returns:
            Loaded model object or None if not found
        """
        try:
            # Determine version to load
            if version is None:
                version = self.get_production_version(model_name)
                if version is None:
                    logger.warning(f"No production version set for {model_name}")
                    return None

            # Check cache
            cache_key = f"{model_name}:{version}"
            if use_cache and cache_key in self._model_cache:
                logger.debug(f"Using cached model {cache_key}")
                return self._model_cache[cache_key]

            version_path = self._get_version_path(model_name, version)
            model_file = None
            for candidate in ("model.joblib", "model.pkl"):
                path = version_path / candidate
                if path.exists():
                    model_file = path
                    break

            if model_file is None:
                logger.error("Model file not found for %s %s in %s", model_name, version, version_path)
                return None

            model = joblib.load(model_file)
            logger.info(f"Loaded model {model_name} version {version}")

            # Cache it
            if use_cache:
                self._model_cache[cache_key] = model

            return model

        except Exception as e:
            logger.error(f"Failed to load model: {e}", exc_info=True)
            return None

    def load_artifact(
        self, model_name: str, artifact_name: str, version: Optional[str] = None
    ) -> Optional[Any]:
        """
        Load a model artifact (e.g., scaler, encoder).
        
        Args:
            model_name: Name of the model
            artifact_name: Name of the artifact
            version: Version to load (defaults to production version)
            
        Returns:
            Loaded artifact or None if not found
        """
        try:
            if version is None:
                version = self.get_production_version(model_name)
                if version is None:
                    return None

            version_path = self._get_version_path(model_name, version)
            artifact_file = None
            for candidate in (f"{artifact_name}.joblib", f"{artifact_name}.pkl"):
                path = version_path / candidate
                if path.exists():
                    artifact_file = path
                    break

            if artifact_file is None:
                logger.warning("Artifact not found for %s (%s): %s", model_name, artifact_name, version_path)
                return None

            artifact = joblib.load(artifact_file)
            logger.debug(f"Loaded artifact {artifact_name} for {model_name}")
            return artifact

        except Exception as e:
            logger.error(f"Failed to load artifact: {e}", exc_info=True)
            return None

    def get_metadata(
        self, model_name: str, version: Optional[str] = None
    ) -> Optional[ModelMetadata]:
        """
        Get model metadata.
        
        Args:
            model_name: Name of the model
            version: Version to get metadata for (defaults to production)
            
        Returns:
            ModelMetadata or None if not found
        """
        try:
            if version is None:
                version = self.get_production_version(model_name)
                if version is None:
                    return None

            version_path = self._get_version_path(model_name, version)
            metadata_file = version_path / "metadata.json"

            if metadata_file.exists():
                with open(metadata_file, "r") as f:
                    data = json.load(f)
                    return ModelMetadata.from_dict(data)

            info = self._registry.get(model_name)
            if isinstance(info, list):
                entry = self._latest_entry(info, version=version)
                if not entry:
                    return None

                metrics = dict(entry.get("metrics") or {})
                if entry.get("validation_score") is not None and "validation_score" not in metrics:
                    metrics["validation_score"] = entry.get("validation_score")

                return ModelMetadata(
                    model_name=model_name,
                    version=str(entry.get("version") or version),
                    created_at=str(entry.get("created_at") or iso_now()),
                    status=self._map_status(entry.get("status")),
                    metrics=metrics,
                    features=list(entry.get("features_used") or entry.get("features") or []),
                    training_data_points=int(entry.get("training_samples") or entry.get("training_data_points") or 0),
                    parameters=dict(entry.get("hyperparameters") or entry.get("parameters") or {}),
                    notes=str(entry.get("notes") or ""),
                )

            # Fallback: legacy dict-based registry requires metadata.json for details.
            return None

        except Exception as e:
            logger.error(f"Failed to get metadata: {e}", exc_info=True)
            return None

    def list_versions(self, model_name: str) -> List[str]:
        """
        List all versions of a model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            List of version IDs
        """
        info = self._registry.get(model_name)
        if isinstance(info, list):
            # Return unique versions ordered by latest created_at.
            by_version: Dict[str, datetime] = {}
            for entry in info:
                v = str(entry.get("version") or "unknown")
                ts = self._parse_iso_ts(entry.get("created_at"))
                if v not in by_version or ts > by_version[v]:
                    by_version[v] = ts
            return [v for v, _ in sorted(by_version.items(), key=lambda kv: kv[1], reverse=True)]

        if isinstance(info, dict):
            return info.get("versions", [])
        return []

    def get_production_version(self, model_name: str) -> Optional[str]:
        """
        Get the current production version of a model.
        
        Args:
            model_name: Name of the model
            
        Returns:
            Production version ID or None
        """
        info = self._registry.get(model_name)
        if isinstance(info, list):
            active_entry = self._latest_entry(info, prefer_active=True)
            if not active_entry:
                active_entry = self._latest_entry(info)
            return str(active_entry.get("version")) if active_entry else None

        if isinstance(info, dict):
            return info.get("production_version")

        return None

    def promote_to_production(self, model_name: str, version: str) -> bool:
        """
        Promote a model version to production.
        
        Args:
            model_name: Name of the model
            version: Version to promote
            
        Returns:
            True if successful, False otherwise
        """
        try:
            info = self._registry.get(model_name)
            if info is None:
                logger.error("Model %s not found in registry", model_name)
                return False

            if isinstance(info, list):
                version_str = str(version)
                if not any(str(e.get("version")) == version_str for e in info):
                    logger.error("Version %s not found for %s", version, model_name)
                    return False

                for entry in info:
                    if str(entry.get("version")) == version_str:
                        entry["status"] = "active"
                    elif str(entry.get("status") or "").lower() == "active":
                        entry["status"] = "inactive"

                self._save_registry()
                self._clear_model_cache(model_name)
                logger.info("Promoted %s version %s to active", model_name, version)
                return True

            if isinstance(info, dict):
                versions = info.get("versions", [])
                if version not in versions:
                    logger.error("Version %s not found for %s", version, model_name)
                    return False

                old_version = info.get("production_version")
                info["production_version"] = version
                self._registry[model_name] = info
                self._save_registry()
                self._clear_model_cache(model_name)
                logger.info(
                    "Promoted %s from %s to %s in production",
                    model_name,
                    old_version,
                    version,
                )
                return True

            logger.error("Unsupported registry format for %s", model_name)
            return False

        except Exception as e:
            logger.error("Failed to promote model: %s", e, exc_info=True)
            return False

    def archive_version(self, model_name: str, version: str) -> bool:
        """
        Archive a model version (removes from active use but keeps files).
        
        Args:
            model_name: Name of the model
            version: Version to archive
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Update metadata status
            metadata = self.get_metadata(model_name, version)
            if metadata:
                metadata.status = ModelStatus.ARCHIVED
                
                metadata_file = self._get_version_path(model_name, version) / "metadata.json"
                with open(metadata_file, "w") as f:
                    json.dump(metadata.to_dict(), f, indent=2)

            logger.info(f"Archived {model_name} version {version}")
            return True

        except Exception as e:
            logger.error(f"Failed to archive version: {e}", exc_info=True)
            return False

    def delete_version(self, model_name: str, version: str) -> bool:
        """
        Permanently delete a model version.
        
        WARNING: This cannot be undone!
        
        Args:
            model_name: Name of the model
            version: Version to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Don't allow deleting production version
            if version == self.get_production_version(model_name):
                logger.error(f"Cannot delete production version {version}")
                return False

            version_path = self._get_version_path(model_name, version)
            if version_path.exists():
                shutil.rmtree(version_path)

            # Update registry
            if model_name in self._registry:
                if version in self._registry[model_name]["versions"]:
                    self._registry[model_name]["versions"].remove(version)
                    self._save_registry()

            logger.info(f"Deleted {model_name} version {version}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete version: {e}", exc_info=True)
            return False

    def list_models(self) -> List[Dict[str, Any]]:
        """
        List all registered models.
        
        Returns:
            List of model info dicts
        """
        models = []
        for model_name, info in self._registry.items():
            # Skip synthetic internal keys.
            if str(model_name).endswith("__entries"):
                continue
            # Handle list-based format (each model maps to a list of version entries)
            if isinstance(info, list):
                active_entry = self._latest_entry(info, prefer_active=True)
                if not active_entry:
                    active_entry = self._latest_entry(info)
                
                versions = self.list_versions(model_name)
                production_version = active_entry.get("version") if active_entry else None
                
                # Map status: "active" -> "production", "inactive" -> "archived"
                raw_status = active_entry.get("status", "unknown") if active_entry else "unknown"
                if raw_status == "active":
                    status = "production"
                elif raw_status == "inactive":
                    status = "archived"
                else:
                    status = raw_status
                
                # Extract metrics for frontend
                metrics = active_entry.get("metrics", {}) if active_entry else {}
                
                models.append({
                    "name": model_name,
                    "versions": versions,
                    "production_version": production_version,
                    "status": status,
                    "last_updated": active_entry.get("created_at") if active_entry else None,
                    # Frontend-expected fields
                    "active": raw_status == "active",
                    "latest_version": production_version,
                    "trained_at": active_entry.get("created_at") if active_entry else None,
                    "accuracy": metrics.get("accuracy") or metrics.get("validation_score"),
                    "mae": metrics.get("mae"),
                    "r2": metrics.get("r2_score"),
                })
            else:
                # Handle dict-based format (legacy)
                production_version = info.get("production_version")
                metadata = self.get_metadata(model_name, production_version) if production_version else None
                
                models.append({
                    "name": model_name,
                    "versions": info.get("versions", []),
                    "production_version": production_version,
                    "status": metadata.status.value if metadata else "unknown",
                    "last_updated": metadata.created_at if metadata else None,
                    "active": metadata.status == ModelStatus.PRODUCTION if metadata else False,
                    "latest_version": production_version,
                })
        
        return models

    def _clear_model_cache(self, model_name: Optional[str] = None) -> None:
        """Clear model cache for a specific model or all models."""
        if model_name:
            keys_to_remove = [k for k in self._model_cache.keys() if k.startswith(f"{model_name}:")]
            for key in keys_to_remove:
                del self._model_cache[key]
        else:
            self._model_cache.clear()
        logger.debug(f"Cleared model cache for {model_name or 'all models'}")
