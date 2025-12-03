"""Скрипт для создания .env файла"""
from pathlib import Path

env_content = """# Server Configuration
ML_SERVICE_HOST=0.0.0.0
ML_SERVICE_PORT=8085
ML_LOG_LEVEL=INFO

# Database Configuration
ML_DB_PATH=./ml_store.db
ML_DB_TIMEOUT=10

# Artifacts Paths
ML_ARTIFACTS_ROOT=./ml_artifacts
ML_MODELS_PATH=./ml_artifacts/models
ML_FEATURES_PATH=./ml_artifacts/features

# GPU & Resources
ML_MIN_WORKERS=1
ML_MAX_WORKERS_LIMIT=8
ML_WORKER_CPU_PER_TASK=0.5

# ML Parameters
ML_HIDDEN_LAYER_SIZES=(512, 256, 128)
ML_LARGE_DATASET_HIDDEN_LAYERS=(1024, 512, 256, 128)
ML_LARGE_DATASET_THRESHOLD=500000
ML_ACTIVATION=relu
ML_SOLVER=adam
ML_MAX_ITER=5000
ML_BATCH_SIZE=auto
ML_LEARNING_RATE_INIT=0.001
ML_ALPHA=0.0001
ML_EARLY_STOPPING=True
ML_VALIDATION_FRACTION=0.1

# Drift Detection
ML_DRIFT_PSI_THRESHOLD=0.1
ML_DRIFT_JS_THRESHOLD=0.2
ML_DAILY_DRIFT_CHECK_TIME=23:00
ML_CLIENT_DATA_CONFIDENCE_THRESHOLD=0.8
ML_RETRAINING_ACCURACY_DROP_THRESHOLD=-0.05

# Security
# ВАЖНО: Измените этот токен на свой секретный (минимум 32 символа)
# Для генерации безопасного токена можно использовать:
# python -c "import secrets; print(secrets.token_urlsafe(32))"
ML_ADMIN_API_TOKEN=dev_token_change_this_to_secure_token_min_32_chars
ML_TOKEN_EXPIRY_DAYS=365

# System Admin credentials (главный админ, создается при первом запуске)
# Этот админ имеет полные права и может управлять другими админами
ML_ADMIN_USERNAME=admin
ML_ADMIN_PASSWORD=admin

# Session expiration (в днях)
ML_SESSION_EXPIRY_DAYS=30
"""

def create_env():
    """Создать .env файл если его нет"""
    env_file = Path(".env")
    
    if env_file.exists():
        print("✓ .env файл уже существует")
        return True
    
    try:
        env_file.write_text(env_content, encoding='utf-8')
        print("✓ .env файл создан успешно")
        print("  Расположение: ml_service/.env")
        print("  ВАЖНО: Отредактируйте ML_ADMIN_API_TOKEN перед production!")
        return True
    except Exception as e:
        print(f"❌ Ошибка при создании .env: {e}")
        return False

if __name__ == "__main__":
    print("=" * 50)
    print("Создание .env файла")
    print("=" * 50)
    create_env()
    print("=" * 50)

