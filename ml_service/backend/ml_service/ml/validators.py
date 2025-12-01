"""Data validation for ML models"""
from typing import List, Dict, Any, Optional
import logging
import math

logger = logging.getLogger(__name__)


class DataValidator:
    """Validate input data for training and prediction"""
    
    def __init__(self, feature_fields: List[str], target_field: Optional[str] = None):
        self.feature_fields = feature_fields
        self.target_field = target_field
    
    def validate_training_data(self, items: List[Dict[str, Any]]) -> tuple[List[Dict], List[Dict]]:
        """
        Validate training data.
        Returns: (valid_items, invalid_items)
        """
        valid_items = []
        invalid_items = []
        
        for idx, item in enumerate(items):
            errors = []
            
            # Check required feature fields
            for field in self.feature_fields:
                if field not in item:
                    errors.append(f"Missing required field: {field}")
            
            # Check target field if provided
            if self.target_field and self.target_field not in item:
                errors.append(f"Missing target field: {self.target_field}")
            
            if errors:
                invalid_items.append({
                    "item_index": idx,
                    "item": item,
                    "errors": errors
                })
            else:
                valid_items.append(item)
        
        return valid_items, invalid_items
    
    def validate_prediction_data(self, items: List[Dict[str, Any]], strict: bool = False) -> tuple[List[Dict], List[Dict]]:
        """
        Validate prediction data.
        
        Args:
            items: Input data items
            strict: If True, reject items with missing fields. If False, fill missing fields with defaults.
        
        Returns: (valid_items, invalid_items)
        """
        valid_items = []
        invalid_items = []
        
        for idx, item in enumerate(items):
            errors = []
            warnings = []
            
            # Remove label field if present (it's not used for prediction)
            if "label" in item:
                item = {k: v for k, v in item.items() if k != "label"}
            
            # Normalize and validate item
            normalized_item = {}
            
            for field in self.feature_fields:
                if field not in item:
                    if strict:
                        errors.append(f"Missing required field: {field}")
                    else:
                        # Fill missing field with default value
                        warnings.append(f"Missing field {field}, using default value")
                        normalized_item[field] = ""  # Default: empty string
                else:
                    value = item[field]
                    # Normalize and validate value
                    try:
                        normalized_value = self._normalize_value(value, field)
                        normalized_item[field] = normalized_value
                    except Exception as e:
                        if strict:
                            errors.append(f"Invalid value for field {field}: {str(e)}")
                        else:
                            # Use default value for invalid data
                            warnings.append(f"Invalid value for field {field}: {str(e)}, using default")
                            normalized_item[field] = ""
            
            # Handle extra fields (not in feature_fields) - ignore them
            for key, value in item.items():
                if key not in self.feature_fields:
                    # Extra fields are ignored, but we can log them
                    pass
            
            if errors and strict:
                invalid_items.append({
                    "item_index": idx,
                    "item": item,
                    "errors": errors,
                    "error_code": "SCHEMA_VALIDATION_ERROR",
                    "expected_fields": {f: {"required": True} for f in self.feature_fields},
                    "provided_fields": list(item.keys())
                })
            else:
                # Item is valid (or was fixed with defaults)
                # Don't add _warnings to normalized_item - it would be treated as a feature field
                # Warnings are logged but not included in the data
                if warnings:
                    logger.debug(f"Item {idx} warnings: {warnings}")
                valid_items.append(normalized_item)
        
        return valid_items, invalid_items
    
    def _normalize_value(self, value: Any, field: str) -> Any:
        """
        Normalize a single value for a field.
        Handles various edge cases and data types.
        """
        # Handle None
        if value is None:
            return ""
        
        # Handle NaN and Inf
        if isinstance(value, float):
            if math.isnan(value) or math.isinf(value):
                return ""
            return value
        
        # Handle strings
        if isinstance(value, str):
            # Trim whitespace
            value = value.strip()
            # Handle empty strings
            if value == "":
                return ""
            # Truncate extremely long strings (prevent memory issues)
            max_length = 10000  # Reasonable limit
            if len(value) > max_length:
                logger.warning(f"Field {field} value truncated from {len(value)} to {max_length} characters")
                return value[:max_length]
            return value
        
        # Handle numeric types
        if isinstance(value, (int, float)):
            return float(value)
        
        # Handle boolean
        if isinstance(value, bool):
            return int(value)
        
        # Handle lists/arrays - convert to string
        if isinstance(value, (list, tuple)):
            # Join list items with space
            return " ".join(str(v) for v in value)
        
        # Handle dict - convert to string representation
        if isinstance(value, dict):
            # Try to extract meaningful string representation
            if "name" in value:
                return str(value["name"])
            elif "value" in value:
                return str(value["value"])
            else:
                return str(value)
        
        # For any other type, convert to string
        try:
            return str(value)
        except Exception as e:
            logger.warning(f"Failed to convert value for field {field}: {e}")
            return ""

