"""Entry point for ML Service"""
import uvicorn
from ml_service.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "ml_service.api.app:app",
        host=settings.ML_SERVICE_HOST,
        port=settings.ML_SERVICE_PORT,
        reload=False,
        log_level=settings.ML_LOG_LEVEL.lower(),
    )

