"""Configuration management"""
from pathlib import Path
from pydantic_settings import BaseSettings
from typing import Tuple


def find_env_file() -> str:
    """Найти .env файл относительно корня проекта"""
    import logging
    logger = logging.getLogger(__name__)
    
    # Определяем корень проекта (где находится ml_service/)
    # config.py находится в: ml_service/backend/ml_service/core/config.py
    # Корень проекта: ml_service/ (где должен быть .env)
    current_file = Path(__file__).resolve()
    # Поднимаемся на 4 уровня вверх: core -> ml_service -> backend -> ml_service (корень)
    project_root = current_file.parent.parent.parent.parent
    env_file = project_root / ".env"
    
    # Логируем для отладки
    logger.debug(f"Looking for .env file. Current file: {current_file}")
    logger.debug(f"Project root: {project_root}")
    logger.debug(f"Env file path: {env_file}")
    logger.debug(f"Env file exists: {env_file.exists()}")
    
    # Если не нашли, пробуем относительно текущей директории
    if not env_file.exists():
        env_file = Path(".env")
        logger.debug(f"Trying current directory: {env_file.absolute()}")
        logger.debug(f"Current directory env exists: {env_file.exists()}")
    
    result = str(env_file) if env_file.exists() else ".env"
    logger.info(f"Using .env file: {result}")
    return result


class Settings(BaseSettings):
    """Application settings"""
    
    # Server
    ML_SERVICE_HOST: str = "0.0.0.0"
    ML_SERVICE_PORT: int = 8085
    ML_LOG_LEVEL: str = "INFO"
    
    # SSL/HTTPS Configuration
    ML_USE_HTTPS: bool = False  # Enable HTTPS support
    ML_SSL_CERT_FILE: str = "./ssl/cert.pem"  # Path to SSL certificate
    ML_SSL_KEY_FILE: str = "./ssl/key.pem"  # Path to SSL private key
    ML_TRUST_PROXY: bool = True  # Trust proxy headers (X-Forwarded-*)
    
    # Database
    ML_DB_PATH: str = "./ml_store.db"
    ML_DB_TIMEOUT: int = 60  # Increased timeout to handle concurrent writes and locks
    
    # Artifacts
    ML_ARTIFACTS_ROOT: str = "./ml_artifacts"
    ML_MODELS_PATH: str = "./ml_artifacts/models"
    ML_FEATURES_PATH: str = "./ml_artifacts/features"
    ML_BASELINES_PATH: str = "./ml_artifacts/baselines"
    
    # GPU & Resources
    ML_MIN_WORKERS: int = 1
    ML_MAX_WORKERS_LIMIT: int = 8
    ML_WORKER_CPU_PER_TASK: float = 0.5
    
    # ML Parameters
    ML_HIDDEN_LAYER_SIZES: str = "(512, 256, 128)"
    ML_LARGE_DATASET_HIDDEN_LAYERS: str = "(1024, 512, 256, 128)"
    ML_LARGE_DATASET_THRESHOLD: int = 500000
    ML_ACTIVATION: str = "relu"
    ML_SOLVER: str = "adam"
    ML_MAX_ITER: int = 5000
    ML_BATCH_SIZE: str = "auto"
    ML_LEARNING_RATE_INIT: float = 0.001
    ML_ALPHA: float = 0.0001
    ML_EARLY_STOPPING: bool = True
    ML_VALIDATION_FRACTION: float = 0.1
    
    # Drift Detection
    ML_DRIFT_PSI_THRESHOLD: float = 0.1
    ML_DRIFT_JS_THRESHOLD: float = 0.2
    ML_DAILY_DRIFT_CHECK_TIME: str = "23:00"
    ML_CLIENT_DATA_CONFIDENCE_THRESHOLD: float = 0.8
    ML_RETRAINING_ACCURACY_DROP_THRESHOLD: float = -0.05
    
    # Security
    ML_ADMIN_API_TOKEN: str = ""
    ML_TOKEN_EXPIRY_DAYS: int = 365
    
    # System admin credentials (для создания главного админа при первом запуске)
    ML_ADMIN_USERNAME: str = "admin"
    ML_ADMIN_PASSWORD: str = "admin"
    
    # Session settings
    ML_SESSION_EXPIRY_DAYS: int = 30
    
    class Config:
        env_file = find_env_file()
        env_file_encoding = 'utf-8'
        case_sensitive = True
    
    def get_hidden_layer_sizes(self, dataset_size: int) -> Tuple[int, ...]:
        """Get hidden layer sizes based on dataset size"""
        if dataset_size < 10000:
            return (128, 64)
        elif dataset_size < 100000:
            return (256, 128)
        elif dataset_size < 500000:
            return tuple(map(int, self.ML_HIDDEN_LAYER_SIZES.strip("()").split(", ")))
        else:
            return tuple(map(int, self.ML_LARGE_DATASET_HIDDEN_LAYERS.strip("()").split(", ")))


settings = Settings()

