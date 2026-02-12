"""Training parameter optimizer based on dataset analysis"""
import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple, Optional

from ml_service.core.config import settings

logger = logging.getLogger(__name__)


class TrainingOptimizer:
    """Analyze dataset and recommend optimal training parameters"""
    
    @staticmethod
    def analyze_dataset(items: List[Dict[str, Any]], target_field: str) -> Dict[str, Any]:
        """
        Analyze dataset and return statistics.
        
        Args:
            items: Training data items
            target_field: Target field name
        
        Returns:
            Dictionary with dataset statistics
        """
        if not items:
            raise ValueError("Dataset is empty")
        
        df = pd.DataFrame(items)
        
        # Basic statistics
        dataset_size = len(df)
        
        # Target field analysis
        if target_field not in df.columns:
            raise ValueError(f"Target field '{target_field}' not found in dataset")
        
        target_values = df[target_field].dropna()
        num_classes = target_values.nunique()
        class_distribution = target_values.value_counts().to_dict()
        
        # Feature analysis
        feature_fields = [col for col in df.columns if col != target_field]
        num_features = len(feature_fields)
        
        # Analyze feature types
        numeric_features = []
        text_features = []
        
        for field in feature_fields:
            if field in df.columns:
                if df[field].dtype in ['int64', 'float64']:
                    numeric_features.append(field)
                elif df[field].dtype == 'object':
                    # Check if it's text or categorical
                    sample_values = df[field].dropna().head(10)
                    if len(sample_values) > 0:
                        is_text = any(isinstance(v, str) and len(str(v)) > 20 for v in sample_values)
                        if is_text:
                            text_features.append(field)
                        else:
                            numeric_features.append(field)  # Treat short strings as categorical
        
        # Calculate feature dimensions (estimate)
        # Text features will be vectorized (typically 1000 features each)
        # Numeric features are 1 feature each
        estimated_feature_dim = len(numeric_features) + len(text_features) * 1000
        
        return {
            "dataset_size": dataset_size,
            "num_classes": num_classes,
            "class_distribution": class_distribution,
            "num_features": num_features,
            "numeric_features_count": len(numeric_features),
            "text_features_count": len(text_features),
            "estimated_feature_dim": estimated_feature_dim,
            "feature_fields": feature_fields
        }
    
    @staticmethod
    def get_recommended_params(
        items: List[Dict[str, Any]], 
        target_field: str,
        feature_fields: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Get recommended training parameters based on dataset analysis.
        
        Args:
            items: Training data items
            target_field: Target field name
            feature_fields: Optional list of feature fields (auto-detected if not provided)
        
        Returns:
            Dictionary with recommended parameters
        """
        # Analyze dataset
        stats = TrainingOptimizer.analyze_dataset(items, target_field)
        
        dataset_size = stats["dataset_size"]
        num_classes = stats["num_classes"]
        estimated_feature_dim = stats["estimated_feature_dim"]
        
        # Recommend hidden_layers based on dataset size and feature dimension
        hidden_layers = TrainingOptimizer._recommend_hidden_layers(
            dataset_size, estimated_feature_dim, num_classes
        )
        
        # Recommend batch_size
        batch_size = TrainingOptimizer._recommend_batch_size(dataset_size, estimated_feature_dim)
        
        # Recommend validation_split
        validation_split = TrainingOptimizer._recommend_validation_split(dataset_size)
        
        # Recommend max_iter
        max_iter = TrainingOptimizer._recommend_max_iter(dataset_size, num_classes)
        
        # Recommend learning_rate
        learning_rate = TrainingOptimizer._recommend_learning_rate(dataset_size, num_classes)
        
        # Recommend alpha (regularization)
        alpha = TrainingOptimizer._recommend_alpha(dataset_size, estimated_feature_dim)
        
        # Recommend early_stopping
        early_stopping = dataset_size > 1000  # Use early stopping for larger datasets
        
        return {
            "hidden_layers": hidden_layers,
            "batch_size": batch_size,
            "validation_split": validation_split,
            "max_iter": max_iter,
            "learning_rate_init": learning_rate,
            "alpha": alpha,
            "early_stopping": early_stopping,
            "dataset_stats": stats
        }
    
    @staticmethod
    def _recommend_hidden_layers(
        dataset_size: int, 
        feature_dim: int, 
        num_classes: int
    ) -> Tuple[int, ...]:
        """Recommend hidden layer architecture"""
        # Base architecture on dataset size and feature dimension
        if dataset_size < 1000:
            # Small dataset - simple architecture
            return (64, 32)
        elif dataset_size < 10000:
            # Medium dataset
            return (128, 64)
        elif dataset_size < 100000:
            # Large dataset - use settings default
            return settings.get_hidden_layer_sizes(dataset_size)
        else:
            # Very large dataset
            return settings.get_hidden_layer_sizes(dataset_size)
    
    @staticmethod
    def _recommend_batch_size(dataset_size: int, feature_dim: int) -> str:
        """Recommend batch size"""
        if dataset_size < 1000:
            return "32"
        elif dataset_size < 10000:
            return "64"
        elif dataset_size < 100000:
            return "128"
        else:
            return "256"
    
    @staticmethod
    def _recommend_validation_split(dataset_size: int) -> float:
        """Recommend validation split"""
        if dataset_size < 1000:
            return 0.2  # More validation data for small datasets
        elif dataset_size < 10000:
            return 0.15
        else:
            return 0.1  # Standard 10% for larger datasets
    
    @staticmethod
    def _recommend_max_iter(dataset_size: int, num_classes: int) -> int:
        """Recommend maximum iterations"""
        # More iterations for larger datasets or more classes
        base_iter = 1000
        
        if dataset_size > 100000:
            base_iter = 5000
        elif dataset_size > 10000:
            base_iter = 3000
        elif dataset_size > 1000:
            base_iter = 2000
        
        # Increase for more classes
        if num_classes > 10:
            base_iter = int(base_iter * 1.5)
        
        return min(base_iter, settings.ML_MAX_ITER)
    
    @staticmethod
    def _recommend_learning_rate(dataset_size: int, num_classes: int) -> float:
        """Recommend learning rate"""
        # Smaller learning rate for larger datasets
        if dataset_size > 100000:
            return 0.0005
        elif dataset_size > 10000:
            return 0.001
        else:
            return 0.001
    
    @staticmethod
    def _recommend_alpha(dataset_size: int, feature_dim: int) -> float:
        """Recommend regularization alpha"""
        # More regularization for larger feature dimensions
        base_alpha = 0.0001
        
        if feature_dim > 5000:
            base_alpha = 0.001
        elif feature_dim > 2000:
            base_alpha = 0.0005
        
        return base_alpha

