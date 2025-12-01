"""Per-model feature store"""
import pickle
import json
from pathlib import Path
from typing import Dict, Any, Optional, List
import logging
import numpy as np

from ml_service.core.config import settings

logger = logging.getLogger(__name__)


class PerModelFeatureStore:
    """Each model has independent feature store"""
    
    def __init__(self, model_key: str, version: str):
        self.model_key = model_key
        self.version = version
        self.base_path = Path(settings.ML_FEATURES_PATH) / model_key / version
        self.base_path.mkdir(parents=True, exist_ok=True)
    
    def save_features(
        self,
        vectorizer: Any = None,
        vectorizers: Optional[Dict[str, Any]] = None,
        encoder: Any = None,
        scaler: Any = None,
        metadata: Optional[Dict[str, Any]] = None,
        feature_field_order: Optional[List[str]] = None
    ):
        """Save vectorizer(s), encoder, scaler as .pkl files"""
        if vectorizer:
            with open(self.base_path / "vectorizer.pkl", "wb") as f:
                pickle.dump(vectorizer, f)
        
        if vectorizers:
            with open(self.base_path / "vectorizers.pkl", "wb") as f:
                pickle.dump(vectorizers, f)
        
        if encoder:
            with open(self.base_path / "encoder.pkl", "wb") as f:
                pickle.dump(encoder, f)
        
        if scaler:
            with open(self.base_path / "scaler.pkl", "wb") as f:
                pickle.dump(scaler, f)
        
        if metadata or feature_field_order:
            if metadata is None:
                metadata = {}
            if feature_field_order:
                metadata["feature_field_order"] = feature_field_order
            with open(self.base_path / "metadata.json", "w") as f:
                json.dump(metadata, f, indent=2)
        
        logger.info(f"Features saved for {self.model_key}/{self.version}")
    
    def load_features(self) -> Dict[str, Any]:
        """Load features from disk"""
        features = {}
        
        vectorizer_path = self.base_path / "vectorizer.pkl"
        if vectorizer_path.exists():
            with open(vectorizer_path, "rb") as f:
                features["vectorizer"] = pickle.load(f)
        
        vectorizers_path = self.base_path / "vectorizers.pkl"
        if vectorizers_path.exists():
            with open(vectorizers_path, "rb") as f:
                features["vectorizers"] = pickle.load(f)
        
        encoder_path = self.base_path / "encoder.pkl"
        if encoder_path.exists():
            with open(encoder_path, "rb") as f:
                features["encoder"] = pickle.load(f)
        
        scaler_path = self.base_path / "scaler.pkl"
        if scaler_path.exists():
            with open(scaler_path, "rb") as f:
                features["scaler"] = pickle.load(f)
        
        metadata_path = self.base_path / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                features["metadata"] = json.load(f)
        
        return features
    
    def get_metadata(self) -> Optional[Dict[str, Any]]:
        """Return feature config for frontend"""
        metadata_path = self.base_path / "metadata.json"
        if metadata_path.exists():
            with open(metadata_path, "r") as f:
                return json.load(f)
        return None
    
    def exists(self) -> bool:
        """Check if feature store exists"""
        return (self.base_path / "metadata.json").exists()
    
    def save_baseline_features(self, baseline_features: np.ndarray):
        """Save baseline features for drift detection"""
        baseline_path = Path(settings.ML_BASELINES_PATH) / self.model_key / self.version
        baseline_path.mkdir(parents=True, exist_ok=True)
        
        baseline_file = baseline_path / "baseline_features.npy"
        np.save(baseline_file, baseline_features)
        logger.info(f"Baseline features saved for {self.model_key}/{self.version}: {baseline_features.shape}")
    
    def load_baseline_features(self) -> Optional[np.ndarray]:
        """Load baseline features for drift detection"""
        baseline_path = Path(settings.ML_BASELINES_PATH) / self.model_key / self.version
        baseline_file = baseline_path / "baseline_features.npy"
        
        if baseline_file.exists():
            baseline_features = np.load(baseline_file)
            logger.info(f"Baseline features loaded for {self.model_key}/{self.version}: {baseline_features.shape}")
            return baseline_features
        else:
            logger.warning(f"Baseline features not found for {self.model_key}/{self.version}")
            return None

