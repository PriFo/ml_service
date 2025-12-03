"""Entry point for ML Service"""
import uvicorn
from pathlib import Path
from ml_service.core.config import settings

if __name__ == "__main__":
    ssl_keyfile = None
    ssl_certfile = None
    
    # Configure SSL if enabled
    if settings.ML_USE_HTTPS:
        cert_path = Path(settings.ML_SSL_CERT_FILE)
        key_path = Path(settings.ML_SSL_KEY_FILE)
        
        if cert_path.exists() and key_path.exists():
            ssl_certfile = str(cert_path)
            ssl_keyfile = str(key_path)
            print(f"SSL enabled: Using certificate from {ssl_certfile}")
        else:
            print(f"Warning: SSL enabled but certificate files not found!")
            print(f"  Certificate: {cert_path} (exists: {cert_path.exists()})")
            print(f"  Private key: {key_path} (exists: {key_path.exists()})")
            print(f"  Run 'python -m ml_service.core.generate_ssl_cert' to generate certificates")
    
    uvicorn.run(
        "ml_service.api.app:app",
        host=settings.ML_SERVICE_HOST,
        port=settings.ML_SERVICE_PORT,
        reload=False,
        log_level=settings.ML_LOG_LEVEL.lower(),
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
    )

