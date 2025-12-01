"""ML Model wrapper for MLPClassifier"""
import logging
import pickle
import joblib
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.neural_network import MLPClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score

from ml_service.core.config import settings
from ml_service.core.gpu_detector import GPUDetector
from ml_service.ml.feature_store import PerModelFeatureStore

logger = logging.getLogger(__name__)


class MLModel:
    """MLPClassifier wrapper with GPU support"""
    
    def __init__(self, model_key: str, version: str, features_config: Dict[str, Any]):
        self.model_key = model_key
        self.version = version
        self.features_config = features_config
        self.vectorizer: Optional[TfidfVectorizer] = None
        self.vectorizers: Dict[str, TfidfVectorizer] = {}  # Per-field vectorizers
        self.encoder: Optional[LabelEncoder] = None
        self.scaler: Optional[StandardScaler] = None
        self.classifier: Optional[MLPClassifier] = None
        self.feature_store = PerModelFeatureStore(model_key, version)
        self.feature_field_order: List[str] = []  # Store order of feature fields
        self.backend: str = "sklearn"
    
    def _prepare_features(self, items: List[Dict[str, Any]], fit: bool = False) -> np.ndarray:
        """Prepare features from items"""
        # Get feature fields first
        feature_fields = self.feature_field_order if self.feature_field_order else self.features_config.get("feature_fields", [])
        
        # Store feature field order on first fit
        if fit:
            self.feature_field_order = self.features_config.get("feature_fields", [])
            feature_fields = self.feature_field_order
        
        # Filter items to only include feature fields (remove any extra fields like _warnings, _metadata, etc.)
        filtered_items = []
        for item in items:
            # Explicitly keep only feature_fields - filter out any extra fields
            filtered_item = {k: v for k, v in item.items() if k in feature_fields}
            filtered_items.append(filtered_item)
        
        df = pd.DataFrame(filtered_items)
        
        # Ensure DataFrame only contains feature_fields columns
        # Drop any columns that are not in feature_fields (safety check)
        extra_columns = [col for col in df.columns if col not in feature_fields]
        if extra_columns:
            logger.warning(f"Dropping extra columns from DataFrame: {extra_columns}")
            df = df.drop(columns=extra_columns)
        
        # Log DataFrame info for debugging
        if not fit:
            logger.debug(f"DataFrame shape: {df.shape}, columns: {list(df.columns)}, feature_fields: {feature_fields}")
        
        # Check if this is an old model format (has vectorizer but no vectorizers dict)
        # Improved detection: check if vectorizers.pkl file exists
        vectorizers_file_exists = False
        if hasattr(self, 'feature_store'):
            vectorizers_file_exists = (self.feature_store.base_path / "vectorizers.pkl").exists()
        
        # Determine if old format: 
        # 1. No vectorizers dict or file exists but vectorizer exists (primary check)
        # 2. OR if both exist but scaler expects fewer features than new format would produce
        #    (this means model was trained with old format but vectorizers were added later)
        is_old_format = False
        if not fit:
            # Primary check: old format if vectorizer exists but no vectorizers
            if self.vectorizer is not None and (self.vectorizers is None or len(self.vectorizers) == 0) and not vectorizers_file_exists:
                is_old_format = True
            # Secondary check: if both exist, check scaler to determine format
            elif self.vectorizer is not None and self.vectorizers and len(self.vectorizers) > 0 and self.scaler:
                # Estimate features for new format: sum of vectorizer max_features + numeric fields
                text_fields_count = len(self.vectorizers)
                numeric_fields_count = len([f for f in feature_fields if f not in self.vectorizers])
                estimated_new_format_features = sum(
                    (v.max_features if hasattr(v, 'max_features') else 1000) 
                    for v in self.vectorizers.values()
                ) + numeric_fields_count
                
                expected_features = self.scaler.n_features_in_ if hasattr(self.scaler, 'n_features_in_') else None
                
                if expected_features:
                    # If expected features is much less than new format estimate, it's definitely old format
                    # Typical old format: 1000-2500 features, new format: 6000+ (6 fields * 1000)
                    # If expected is less than 50% of new format estimate, use old format
                    if expected_features < estimated_new_format_features * 0.5:
                        logger.info(
                            f"Detected old format model: scaler expects {expected_features} features, "
                            f"but new format would produce ~{estimated_new_format_features} (diff: {estimated_new_format_features - expected_features}). "
                            f"Using old format processing."
                        )
                        is_old_format = True
                    else:
                        # Estimate old format: single vectorizer + numeric fields
                        # Check actual vectorizer max_features if available
                        old_format_vectorizer_features = 1000  # Default
                        if hasattr(self.vectorizer, 'max_features'):
                            old_format_vectorizer_features = self.vectorizer.max_features
                        elif hasattr(self.vectorizer, 'vocabulary_') and self.vectorizer.vocabulary_:
                            # Estimate from vocabulary size
                            old_format_vectorizer_features = len(self.vectorizer.vocabulary_)
                        
                        estimated_old_format_features = old_format_vectorizer_features + numeric_fields_count
                        
                        # Check which format matches better
                        new_format_diff = abs(expected_features - estimated_new_format_features)
                        old_format_diff = abs(expected_features - estimated_old_format_features)
                        
                        # If old format is much closer (at least 2x better match), use it
                        if old_format_diff < new_format_diff * 0.5 and old_format_diff < 500:
                            logger.info(
                                f"Detected old format model: scaler expects {expected_features} features. "
                                f"Old format estimate: ~{estimated_old_format_features}, "
                                f"New format estimate: ~{estimated_new_format_features}. "
                                f"Using old format processing (diff: {old_format_diff} vs {new_format_diff})."
                            )
                            is_old_format = True
        
        # Log format detection for debugging
        if not fit:
            logger.info(
                f"Feature preparation: fit={fit}, "
                f"is_old_format={is_old_format}, "
                f"vectorizer={self.vectorizer is not None}, "
                f"vectorizers_count={len(self.vectorizers) if self.vectorizers else 0}, "
                f"vectorizers_file_exists={vectorizers_file_exists}, "
                f"feature_fields={feature_fields}, "
                f"data_columns={list(df.columns) if not df.empty else []}, "
                f"data_rows={len(df)}"
            )
        
        feature_arrays = []
        
        # For old format models, we need to handle text fields differently
        # Old models concatenated all text fields into one string before vectorization
        if is_old_format:
            logger.info("Detected old model format (single vectorizer). Using concatenated text fields approach.")
            text_fields = []
            numeric_fields = []
            
            # Separate text and numeric fields
            for field in feature_fields:
                if field not in df.columns:
                    # Missing field - try to determine type from metadata or default to numeric
                    if hasattr(self, 'feature_store'):
                        features = self.feature_store.load_features()
                        metadata = features.get("metadata", {})
                        stored_order = metadata.get("feature_field_order", [])
                        # If field was in stored order and we have vectorizer, it's likely text
                        # But we can't be sure, so we'll skip it and let the model handle it
                        logger.warning(f"Field {field} not found in data, skipping for old format model")
                    continue
                
                # Check if text field
                if df[field].dtype == "object":
                    non_null_values = df[field].dropna()
                    if len(non_null_values) > 0:
                        is_text = any(isinstance(v, str) for v in non_null_values.head(10))
                    else:
                        is_text = True  # Default to text for empty object fields
                    
                    if is_text:
                        text_fields.append(field)
                    else:
                        numeric_fields.append(field)
                else:
                    numeric_fields.append(field)
            
            # Concatenate all text fields into one (old format approach)
            if text_fields:
                # Normalize and concatenate text fields
                # Use placeholder for empty fields to maintain feature consistency
                text_data = []
                for idx in range(len(df)):
                    text_parts = []
                    for field in text_fields:
                        value = df.iloc[idx][field]
                        if pd.isna(value) or value is None or (isinstance(value, str) and value.strip() == ""):
                            # Use empty string (as old models were trained)
                            # Feature count will be adjusted via padding if needed
                            text_parts.append("")
                        else:
                            text_parts.append(str(value))
                    # Join with space (old format used space separator)
                    text_data.append(" ".join(text_parts))
                
                # Apply single vectorizer to concatenated text
                try:
                    vectorized = self.vectorizer.transform(text_data)
                    feature_arrays.append(vectorized.toarray())
                    logger.info(
                        f"Applied old format vectorizer to {len(text_fields)} concatenated text fields. "
                        f"Features shape: {vectorized.shape}"
                    )
                except Exception as e:
                    logger.error(f"Failed to apply old format vectorizer: {e}")
                    raise ValueError(
                        f"Failed to process text fields with old format vectorizer: {str(e)}. "
                        f"Please retrain the model with the new format."
                    )
            
            # Add numeric fields
            for field in numeric_fields:
                if field in df.columns:
                    # Fill NaN values with 0 for numeric fields
                    numeric_data = df[[field]].fillna(0).values
                    feature_arrays.append(numeric_data)
                else:
                    # Missing numeric field - add zeros
                    logger.debug(f"Missing numeric field {field} in old format, using zeros")
                    feature_arrays.append(np.zeros((len(df), 1)))
        else:
            # New format: process each field individually
            for field in feature_fields:
                if field not in df.columns:
                    # If field is missing during prediction, use zeros
                    if not fit:
                        # Try to determine if it was text or numeric from stored vectorizers
                        if field in self.vectorizers:
                            # It was a text field, use zeros with same shape as vectorizer expects
                            vectorizer = self.vectorizers[field]
                            n_features = vectorizer.max_features if hasattr(vectorizer, 'max_features') else 1000
                            feature_arrays.append(np.zeros((len(df), n_features)))
                            logger.debug(f"Missing text field {field} during prediction, using zeros")
                        else:
                            # It was a numeric field, use zero
                            feature_arrays.append(np.zeros((len(df), 1)))
                            logger.debug(f"Missing numeric field {field} during prediction, using zero")
                    else:
                        logger.warning(f"Field {field} not found in training data, skipping")
                    continue
                
                # Handle missing values in the field (NaN, None, empty strings)
                field_data = df[field]
                
                # Count missing values for logging
                missing_count = field_data.isna().sum() + (field_data == "").sum() if field_data.dtype == "object" else field_data.isna().sum()
                if missing_count > 0 and not fit:
                    logger.debug(f"Field {field} has {missing_count} missing values out of {len(df)}, filling with defaults")
                
                # Text features - use TF-IDF
                # Check if field is text type: object dtype or contains string values
                is_text_field = False
                if df[field].dtype == "object":
                    # Check if any non-null value is a string
                    non_null_values = df[field].dropna()
                    if len(non_null_values) > 0:
                        is_text_field = any(isinstance(v, str) for v in non_null_values.head(10))
                    else:
                        # All values are null/empty - treat as text field if it was text during training
                        if not fit:
                            # During prediction, if field is in vectorizers, it's a text field
                            is_text_field = field in self.vectorizers
                        else:
                            # During training, default to text if dtype is object
                            is_text_field = True
                
                if is_text_field:
                    # Normalize: convert None, NaN, empty strings to empty string
                    normalized_field = df[field].fillna("").astype(str).replace("nan", "").replace("None", "")
                    
                    if fit:
                        # Create or get vectorizer for this field
                        vectorizer = TfidfVectorizer(max_features=1000)
                        vectorized = vectorizer.fit_transform(normalized_field)
                        self.vectorizers[field] = vectorizer
                        # Keep backward compatibility
                        if not self.vectorizer:
                            self.vectorizer = vectorizer
                    else:
                        # Use stored vectorizer for this field
                        if field in self.vectorizers:
                            vectorizer = self.vectorizers[field]
                            vectorized = vectorizer.transform(normalized_field)
                        elif self.vectorizer:
                            # Fallback to single vectorizer for backward compatibility
                            # This should not happen in new format, but handle gracefully
                            try:
                                vectorized = self.vectorizer.transform(normalized_field)
                                logger.warning(
                                    f"Using fallback vectorizer for field {field}. "
                                    f"This model appears to be using an old format. "
                                    f"Consider retraining the model for better compatibility."
                                )
                            except Exception as e:
                                logger.error(
                                    f"Failed to use fallback vectorizer for field {field}: {e}. "
                                    f"This model was likely trained with a different feature configuration. "
                                    f"Please retrain the model."
                                )
                                raise ValueError(
                                    f"Vectorizer mismatch for field {field}. "
                                    f"The model was trained with a different feature configuration. "
                                    f"Please retrain the model with the current feature fields."
                                )
                        else:
                            logger.error(f"Vectorizer not fitted for field {field}")
                            raise ValueError(
                                f"Vectorizer not fitted for field {field}. "
                                f"Please ensure the model was properly trained and saved."
                            )
                    feature_arrays.append(vectorized.toarray())
                else:
                    # Numeric features
                    feature_arrays.append(df[[field]].values)
        
        if not feature_arrays:
            raise ValueError("No valid features found")
        
        # Concatenate all features
        X = np.hstack(feature_arrays)
        
        # Scale features
        if fit:
            self.scaler = StandardScaler()
            X = self.scaler.fit_transform(X)
            # Save baseline features for drift detection
            self.feature_store.save_baseline_features(X)
        else:
            if self.scaler:
                # Check if feature count matches
                expected_features = self.scaler.n_features_in_ if hasattr(self.scaler, 'n_features_in_') else None
                actual_features = X.shape[1]
                
                # If we got way more features than expected, and we haven't detected old format yet,
                # but we have vectorizer available, force old format processing
                if expected_features and actual_features != expected_features:
                    if not is_old_format and actual_features > expected_features * 1.3 and self.vectorizer is not None:
                        logger.warning(
                            f"Feature count mismatch detected during processing: got {actual_features}, expected {expected_features}. "
                            f"Model likely uses old format. Forcing old format reprocessing..."
                        )
                        # Reprocess with old format
                        is_old_format = True
                        # Re-process with old format approach
                        text_fields = []
                        numeric_fields = []
                        
                        for field in feature_fields:
                            if field not in df.columns:
                                continue
                            if df[field].dtype == "object":
                                non_null_values = df[field].dropna()
                                if len(non_null_values) > 0:
                                    is_text = any(isinstance(v, str) for v in non_null_values.head(10))
                                else:
                                    is_text = True
                                if is_text:
                                    text_fields.append(field)
                                else:
                                    numeric_fields.append(field)
                            else:
                                numeric_fields.append(field)
                        
                        # Concatenate all text fields
                        if text_fields:
                            text_data = []
                            for idx in range(len(df)):
                                text_parts = []
                                for field in text_fields:
                                    value = df.iloc[idx][field]
                                    if pd.isna(value) or value is None or (isinstance(value, str) and value.strip() == ""):
                                        text_parts.append("")
                                    else:
                                        text_parts.append(str(value))
                                text_data.append(" ".join(text_parts))
                            
                            vectorized = self.vectorizer.transform(text_data)
                            X = vectorized.toarray()
                            
                            # Add numeric fields
                            for field in numeric_fields:
                                if field in df.columns:
                                    numeric_data = df[[field]].fillna(0).values
                                    X = np.hstack([X, numeric_data])
                                else:
                                    X = np.hstack([X, np.zeros((len(df), 1))])
                            
                            logger.info(f"Reprocessed with old format: {X.shape[1]} features")
                
                if expected_features and actual_features != expected_features:
                    # For old format models, be more lenient with feature count
                    # Old format can have variable feature counts due to sparse TF-IDF
                    if is_old_format:
                        # Check if the difference is reasonable (within 10% or absolute difference < 100)
                        feature_diff = abs(expected_features - actual_features)
                        feature_diff_percent = (feature_diff / expected_features) * 100
                        
                        # For old format models, be more lenient - allow padding/truncation
                        # This handles cases where data has empty fields or different structure
                        logger.warning(
                            f"Feature count mismatch in old format model: expected {expected_features}, "
                            f"got {actual_features} (diff: {feature_diff}, {feature_diff_percent:.1f}%). "
                            f"Attempting to fix by padding/truncating features..."
                        )
                        
                        # Try to pad or truncate features to match expected size
                        if actual_features < expected_features:
                            # Pad with zeros (empty fields result in fewer features)
                            padding = np.zeros((X.shape[0], expected_features - actual_features))
                            X = np.hstack([X, padding])
                            logger.info(f"Padded features from {actual_features} to {expected_features}")
                        elif actual_features > expected_features:
                            # Truncate (shouldn't happen, but handle it)
                            X = X[:, :expected_features]
                            logger.warning(f"Truncated features from {actual_features} to {expected_features}")
                        else:
                            # Should not happen, but just in case
                            pass
                    # Try fallback: if we detected new format but got mismatch, try old format
                    elif not is_old_format and self.vectorizer is not None:
                        logger.warning(
                            f"Feature count mismatch (expected {expected_features}, got {actual_features}). "
                            f"Attempting fallback to old format processing..."
                        )
                        # Retry with old format approach
                        try:
                            # Re-process with old format
                            text_fields = []
                            numeric_fields = []
                            
                            for field in feature_fields:
                                if field not in df.columns:
                                    continue
                                if df[field].dtype == "object":
                                    non_null_values = df[field].dropna()
                                    if len(non_null_values) > 0:
                                        is_text = any(isinstance(v, str) for v in non_null_values.head(10))
                                    else:
                                        is_text = True
                                    if is_text:
                                        text_fields.append(field)
                                    else:
                                        numeric_fields.append(field)
                                else:
                                    numeric_fields.append(field)
                            
                            # Concatenate all text fields
                            if text_fields:
                                text_data = []
                                for idx in range(len(df)):
                                    text_parts = []
                                    for field in text_fields:
                                        value = df.iloc[idx][field]
                                        if pd.isna(value) or value is None or (isinstance(value, str) and value.strip() == ""):
                                            # Use empty string for old format (as they were trained)
                                            text_parts.append("")
                                        else:
                                            text_parts.append(str(value))
                                    text_data.append(" ".join(text_parts))
                                
                                vectorized = self.vectorizer.transform(text_data)
                                X_fallback = vectorized.toarray()
                                
                                logger.info(f"Old format text vectorization: {X_fallback.shape[1]} features from {len(text_fields)} text fields")
                                
                                # Add numeric fields
                                for field in numeric_fields:
                                    if field in df.columns:
                                        # Fill NaN with 0
                                        numeric_data = df[[field]].fillna(0).values
                                        X_fallback = np.hstack([X_fallback, numeric_data])
                                        logger.debug(f"Added numeric field {field}: {X_fallback.shape[1]} total features")
                                    else:
                                        # Missing numeric field - add zeros
                                        X_fallback = np.hstack([X_fallback, np.zeros((len(df), 1))])
                                        logger.debug(f"Added missing numeric field {field} (zeros): {X_fallback.shape[1]} total features")
                                
                                logger.info(f"Fallback old format total features: {X_fallback.shape[1]}, expected: {expected_features}")
                                
                                # Check if fallback worked (allow small differences for old format)
                                feature_diff = abs(X_fallback.shape[1] - expected_features)
                                if X_fallback.shape[1] == expected_features:
                                    logger.info(f"Fallback to old format successful! Features: {X_fallback.shape[1]}")
                                    X = X_fallback
                                elif feature_diff <= 10:  # Allow small differences (padding/truncation)
                                    logger.warning(f"Fallback feature count close but not exact: {X_fallback.shape[1]} vs {expected_features}, adjusting...")
                                    if X_fallback.shape[1] < expected_features:
                                        padding = np.zeros((X_fallback.shape[0], expected_features - X_fallback.shape[1]))
                                        X = np.hstack([X_fallback, padding])
                                    else:
                                        X = X_fallback[:, :expected_features]
                                    logger.info(f"Adjusted features to {X.shape[1]}")
                                else:
                                    raise ValueError(f"Fallback failed: got {X_fallback.shape[1]} features, expected {expected_features} (diff: {feature_diff})")
                            else:
                                raise ValueError("No text fields found for fallback")
                        except Exception as fallback_error:
                            logger.error(f"Fallback to old format failed: {fallback_error}")
                            # Continue with original error
                            error_msg = (
                                f"Feature count mismatch: model expects {expected_features} features, "
                                f"but got {actual_features}. This usually happens when:\n"
                                f"1. The model was trained with different feature fields\n"
                                f"2. The model is using an old format (single vectorizer for all text fields)\n"
                                f"3. Some feature fields are missing or have different types\n"
                                f"4. Data contains only a subset of expected fields\n"
                                f"Debug info: feature_fields={feature_fields}, "
                                f"data_columns={list(df.columns)}, "
                                f"is_old_format={is_old_format}, "
                                f"vectorizer_exists={self.vectorizer is not None}, "
                                f"vectorizers_count={len(self.vectorizers) if self.vectorizers else 0}\n"
                                f"Please retrain the model with the current feature configuration or ensure all required fields are present."
                            )
                            logger.error(error_msg)
                            raise ValueError(error_msg)
                    else:
                        # Original error handling
                        error_msg = (
                            f"Feature count mismatch: model expects {expected_features} features, "
                            f"but got {actual_features}. This usually happens when:\n"
                            f"1. The model was trained with different feature fields\n"
                            f"2. The model is using an old format (single vectorizer for all text fields)\n"
                            f"3. Some feature fields are missing or have different types\n"
                            f"4. Data contains only a subset of expected fields\n"
                            f"Debug info: feature_fields={feature_fields}, "
                            f"data_columns={list(df.columns)}, "
                            f"is_old_format={is_old_format}, "
                            f"vectorizer_exists={self.vectorizer is not None}, "
                            f"vectorizers_count={len(self.vectorizers) if self.vectorizers else 0}\n"
                            f"Please retrain the model with the current feature configuration or ensure all required fields are present."
                        )
                        logger.error(error_msg)
                        raise ValueError(error_msg)
                
                X = self.scaler.transform(X)
            else:
                logger.warning("Scaler not fitted")
        
        return X
    
    def _prepare_target(self, items: List[Dict[str, Any]], target_field: str, fit: bool = False) -> np.ndarray:
        """Prepare target labels"""
        df = pd.DataFrame(items)
        
        if target_field not in df.columns:
            raise ValueError(f"Target field {target_field} not found")
        
        y = df[target_field].values
        
        # Encode labels
        if fit:
            self.encoder = LabelEncoder()
            y = self.encoder.fit_transform(y)
        else:
            if self.encoder:
                # Map to known classes, use -1 for unknown
                y_encoded = []
                for label in y:
                    try:
                        y_encoded.append(self.encoder.transform([label])[0])
                    except ValueError:
                        y_encoded.append(-1)  # Unknown class
                y = np.array(y_encoded)
            else:
                raise ValueError("Encoder not fitted")
        
        return y
    
    def train(
        self,
        items: List[Dict[str, Any]],
        target_field: str,
        feature_fields: List[str],
        validation_split: float = 0.1,
        use_gpu: bool = False
    ) -> Dict[str, Any]:
        """
        Train MLPClassifier model
        
        Args:
            items: Training data
            target_field: Target column name
            feature_fields: Feature column names
            validation_split: Validation split ratio
            use_gpu: Whether to use GPU (cuML)
        
        Returns:
            Training metrics
        """
        logger.info(f"Starting training for {self.model_key} v{self.version}")
        
        dataset_size = len(items)
        
        # Detect backend
        if use_gpu:
            self.backend = GPUDetector.get_backend(dataset_size)
        else:
            self.backend = "sklearn"
        
        logger.info(f"Using backend: {self.backend}")
        
        # Prepare features
        X = self._prepare_features(items, fit=True)
        y = self._prepare_target(items, target_field, fit=True)
        
        # Split data
        if validation_split > 0:
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=validation_split, random_state=42, stratify=y
            )
        else:
            X_train, X_val, y_train, y_val = X, X, y, y
        
        # Get architecture based on dataset size
        hidden_layer_sizes = settings.get_hidden_layer_sizes(dataset_size)
        logger.info(f"Using architecture: {hidden_layer_sizes}")
        
        # Create and train classifier
        if self.backend == "cuml":
            try:
                from cuml.neural_network import MLPClassifier as cuMLPClassifier
                self.classifier = cuMLPClassifier(
                    hidden_layer_sizes=hidden_layer_sizes,
                    activation=settings.ML_ACTIVATION,
                    solver=settings.ML_SOLVER,
                    max_iter=settings.ML_MAX_ITER,
                    learning_rate_init=settings.ML_LEARNING_RATE_INIT,
                    alpha=settings.ML_ALPHA,
                    early_stopping=settings.ML_EARLY_STOPPING,
                    validation_fraction=settings.ML_VALIDATION_FRACTION
                )
            except ImportError:
                logger.warning("cuML not available, falling back to sklearn")
                self.backend = "sklearn"
        
        if self.backend == "sklearn" or self.classifier is None:
            self.classifier = MLPClassifier(
                hidden_layer_sizes=hidden_layer_sizes,
                activation=settings.ML_ACTIVATION,
                solver=settings.ML_SOLVER,
                max_iter=settings.ML_MAX_ITER,
                learning_rate_init=settings.ML_LEARNING_RATE_INIT,
                alpha=settings.ML_ALPHA,
                early_stopping=settings.ML_EARLY_STOPPING,
                validation_fraction=settings.ML_VALIDATION_FRACTION,
                batch_size=settings.ML_BATCH_SIZE if settings.ML_BATCH_SIZE != "auto" else "auto"
            )
        
        # Train
        logger.info("Training classifier...")
        self.classifier.fit(X_train, y_train)
        
        # Evaluate
        train_pred = self.classifier.predict(X_train)
        train_accuracy = accuracy_score(y_train, train_pred)
        
        val_pred = self.classifier.predict(X_val)
        val_accuracy = accuracy_score(y_val, val_pred)
        val_precision = precision_score(y_val, val_pred, average="weighted", zero_division=0)
        val_recall = recall_score(y_val, val_pred, average="weighted", zero_division=0)
        val_f1 = f1_score(y_val, val_pred, average="weighted", zero_division=0)
        
        metrics = {
            "train_accuracy": float(train_accuracy),
            "validation_accuracy": float(val_accuracy),
            "precision": float(val_precision),
            "recall": float(val_recall),
            "f1": float(val_f1),
            "dataset_size": dataset_size,
            "architecture": str(hidden_layer_sizes),
            "backend": self.backend
        }
        
        # Save model and features
        self._save_model()
        self.feature_store.save_features(
            vectorizer=self.vectorizer,
            vectorizers=self.vectorizers,
            encoder=self.encoder,
            scaler=self.scaler,
            metadata={
                "feature_fields": feature_fields,
                "target_field": target_field,
                "metrics": metrics
            },
            feature_field_order=self.feature_field_order
        )
        
        logger.info(f"Training completed. Accuracy: {val_accuracy:.4f}")
        
        return metrics
    
    def predict(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Make predictions with confidence scores"""
        if not self.classifier:
            # Try to load model
            self._load_model()
        
        if not self.classifier:
            raise ValueError("Model not trained or loaded")
        
        # Load features if not loaded
        if not self.scaler or (not self.vectorizer and not self.vectorizers):
            features = self.feature_store.load_features()
            self.vectorizer = features.get("vectorizer")
            self.vectorizers = features.get("vectorizers", {})
            # Ensure vectorizers is a dict (not None)
            if self.vectorizers is None:
                self.vectorizers = {}
            self.encoder = features.get("encoder")
            self.scaler = features.get("scaler")
            # Load feature field order from metadata
            metadata = features.get("metadata", {})
            self.feature_field_order = metadata.get("feature_field_order", self.features_config.get("feature_fields", []))
            
            # Log model format information for debugging
            vectorizers_file_exists = (self.feature_store.base_path / "vectorizers.pkl").exists()
            vectorizer_file_exists = (self.feature_store.base_path / "vectorizer.pkl").exists()
            logger.info(
                f"Model format info: vectorizer={self.vectorizer is not None}, "
                f"vectorizers_count={len(self.vectorizers)}, "
                f"vectorizer.pkl exists={vectorizer_file_exists}, "
                f"vectorizers.pkl exists={vectorizers_file_exists}, "
                f"feature_fields={len(self.feature_field_order)}"
            )
        
        # Prepare features
        X = self._prepare_features(items, fit=False)
        
        # Predict
        predictions = self.classifier.predict(X)
        probabilities = self.classifier.predict_proba(X)
        
        # Decode labels
        if self.encoder:
            predicted_labels = self.encoder.inverse_transform(predictions)
        else:
            predicted_labels = predictions
        
        # Format results
        results = []
        class_names = self.encoder.classes_ if self.encoder else [str(i) for i in range(probabilities.shape[1])]
        
        for i, (pred, probs) in enumerate(zip(predicted_labels, probabilities)):
            # Get top predictions
            top_indices = np.argsort(probs)[::-1]
            
            all_scores = {
                class_names[idx]: float(probs[idx])
                for idx in top_indices
            }
            
            results.append({
                "input": items[i],
                "prediction": str(pred),
                "confidence": float(probs[top_indices[0]]),
                "all_scores": all_scores
            })
        
        return results
    
    def evaluate(self, items: List[Dict[str, Any]], target_field: str) -> Dict[str, float]:
        """Calculate metrics on test data"""
        X = self._prepare_features(items, fit=False)
        y = self._prepare_target(items, target_field, fit=False)
        
        predictions = self.classifier.predict(X)
        
        accuracy = accuracy_score(y, predictions)
        precision = precision_score(y, predictions, average="weighted", zero_division=0)
        recall = recall_score(y, predictions, average="weighted", zero_division=0)
        f1 = f1_score(y, predictions, average="weighted", zero_division=0)
        
        return {
            "accuracy": float(accuracy),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1)
        }
    
    def _save_model(self):
        """Save trained model to disk"""
        model_path = Path(settings.ML_MODELS_PATH) / self.model_key / self.version
        model_path.mkdir(parents=True, exist_ok=True)
        
        model_file = model_path / "model.joblib"
        joblib.dump(self.classifier, model_file)
        
        logger.info(f"Model saved to {model_file}")
    
    def _load_model(self):
        """Load trained model from disk"""
        model_path = Path(settings.ML_MODELS_PATH) / self.model_key / self.version
        model_file = model_path / "model.joblib"
        
        if model_file.exists():
            self.classifier = joblib.load(model_file)
            logger.info(f"Model loaded from {model_file}")
        else:
            logger.warning(f"Model file not found: {model_file}")

