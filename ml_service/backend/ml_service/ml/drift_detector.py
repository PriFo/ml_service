"""Drift detection using PSI and Jensen-Shannon divergence"""
import numpy as np
from typing import Dict, Any, Optional, List
import logging
import pickle

from ml_service.core.config import settings
from ml_service.ml.feature_store import PerModelFeatureStore
from ml_service.db.repositories import PredictionLogRepository

logger = logging.getLogger(__name__)


class DriftDetector:
    """Detect data drift using statistical methods"""
    
    def calculate_psi(self, expected: np.ndarray, actual: np.ndarray, bins: int = 10) -> float:
        """
        Calculate Population Stability Index (PSI)
        PSI > 0.1 indicates drift
        """
        try:
            # Create bins based on expected distribution
            _, bin_edges = np.histogram(expected, bins=bins)
            
            # Calculate expected distribution
            expected_counts, _ = np.histogram(expected, bins=bin_edges)
            expected_probs = expected_counts / len(expected)
            expected_probs = np.where(expected_probs == 0, 0.0001, expected_probs)  # Avoid log(0)
            
            # Calculate actual distribution
            actual_counts, _ = np.histogram(actual, bins=bin_edges)
            actual_probs = actual_counts / len(actual)
            actual_probs = np.where(actual_probs == 0, 0.0001, actual_probs)  # Avoid log(0)
            
            # Calculate PSI
            psi = np.sum((actual_probs - expected_probs) * np.log(actual_probs / expected_probs))
            
            return float(psi)
        except Exception as e:
            logger.error(f"Error calculating PSI: {e}")
            return 0.0
    
    def calculate_js_divergence(self, p: np.ndarray, q: np.ndarray) -> float:
        """
        Calculate Jensen-Shannon divergence
        JS divergence > 0.2 indicates drift
        """
        try:
            # Normalize distributions
            p = p / np.sum(p) if np.sum(p) > 0 else p
            q = q / np.sum(q) if np.sum(q) > 0 else q
            
            # Avoid zeros
            p = np.where(p == 0, 0.0001, p)
            q = np.where(q == 0, 0.0001, q)
            
            # Calculate JS divergence
            m = (p + q) / 2
            js = 0.5 * np.sum(p * np.log(p / m)) + 0.5 * np.sum(q * np.log(q / m))
            
            return float(js)
        except Exception as e:
            logger.error(f"Error calculating JS divergence: {e}")
            return 0.0
    
    def load_baseline_features(self, model_key: str, version: str) -> Optional[np.ndarray]:
        """Load baseline features from feature store"""
        try:
            feature_store = PerModelFeatureStore(model_key, version)
            baseline_features = feature_store.load_baseline_features()
            return baseline_features
        except Exception as e:
            logger.error(f"Failed to load baseline features for {model_key}/{version}: {e}")
            return None
    
    def load_current_features(
        self, 
        model_key: str, 
        version: str, 
        hours: int = 24
    ) -> Optional[np.ndarray]:
        """Load current features from recent predictions"""
        try:
            log_repo = PredictionLogRepository()
            feature_bytes_list = log_repo.get_recent_features(model_key, version, hours=hours)
            
            if not feature_bytes_list:
                logger.warning(f"No recent prediction features found for {model_key}/{version}")
                return None
            
            # Deserialize features
            features_list = []
            for feature_bytes in feature_bytes_list:
                try:
                    features = pickle.loads(feature_bytes)
                    if isinstance(features, np.ndarray):
                        features_list.append(features)
                    elif isinstance(features, (list, tuple)):
                        features_list.extend(features)
                except Exception as e:
                    logger.warning(f"Failed to deserialize feature: {e}")
                    continue
            
            if not features_list:
                return None
            
            # Stack all features into single array
            current_features = np.vstack(features_list)
            logger.info(f"Loaded {len(features_list)} prediction feature arrays for {model_key}/{version}")
            return current_features
            
        except Exception as e:
            logger.error(f"Failed to load current features for {model_key}/{version}: {e}")
            return None
    
    async def check_drift(
        self,
        model_key: str,
        version: str,
        baseline_data: Optional[np.ndarray] = None,
        current_data: Optional[np.ndarray] = None
    ) -> Dict[str, Any]:
        """
        Check for drift between baseline and current data.
        Loads baseline from training data and current data from recent predictions.
        """
        # Load baseline if not provided
        if baseline_data is None:
            baseline_data = self.load_baseline_features(model_key, version)
        
        # Load current data if not provided
        if current_data is None:
            current_data = self.load_current_features(model_key, version, hours=24)
        
        # If still no data, return warning
        if baseline_data is None or current_data is None:
            if baseline_data is None:
                logger.warning(f"Baseline data not available for {model_key}/{version}")
            if current_data is None:
                logger.warning(f"Current data not available for {model_key}/{version}")
            
            return {
                "psi": None,
                "js_divergence": None,
                "drift_detected": False,
                "items_analyzed": 0,
                "warning": "Insufficient data for drift detection"
            }
        
        # Ensure both arrays are 1D for PSI/JS calculation
        # Use mean of features across samples for distribution comparison
        if len(baseline_data.shape) > 1:
            baseline_dist = np.mean(baseline_data, axis=0)
        else:
            baseline_dist = baseline_data
        
        if len(current_data.shape) > 1:
            current_dist = np.mean(current_data, axis=0)
        else:
            current_dist = current_data
        
        # Calculate PSI
        psi = self.calculate_psi(baseline_dist, current_dist)
        
        # Calculate JS divergence
        js_div = self.calculate_js_divergence(baseline_dist, current_dist)
        
        # Determine if drift detected
        drift_detected = (
            psi > settings.ML_DRIFT_PSI_THRESHOLD or
            js_div > settings.ML_DRIFT_JS_THRESHOLD
        )
        
        logger.info(
            f"Drift check for {model_key}/{version}: "
            f"PSI={psi:.4f}, JS={js_div:.4f}, detected={drift_detected}"
        )
        
        return {
            "psi": psi,
            "js_divergence": js_div,
            "drift_detected": drift_detected,
            "items_analyzed": len(current_data)
        }

