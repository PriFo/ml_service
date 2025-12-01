"""Security and authentication"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException, Security, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ml_service.core.config import settings

security = HTTPBearer(auto_error=False)


def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash token using SHA256"""
    return hashlib.sha256(token.encode()).hexdigest()


def validate_token(token: Optional[str] = None) -> bool:
    """Validate admin token"""
    if not settings.ML_ADMIN_API_TOKEN:
        # If no token configured, allow access (development mode)
        return True
    
    if not token:
        return False
    
    # Compare with configured token
    if token == settings.ML_ADMIN_API_TOKEN:
        return True
    
    # Also check hashed version (for stored tokens)
    token_hash = hash_token(token)
    # In production, check against database
    return False


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
) -> dict:
    """Dependency for authenticated endpoints"""
    # Get token from X-Admin-Token header or Authorization Bearer
    token = x_admin_token
    if not token and credentials:
        token = credentials.credentials
    
    # If no token configured, allow access (development mode)
    if not settings.ML_ADMIN_API_TOKEN:
        return {"authenticated": True, "token": None, "mode": "development"}
    
    # Validate token
    if not validate_token(token):
        raise HTTPException(
            status_code=403,
            detail="Invalid or missing authentication token"
        )
    
    return {"authenticated": True, "token": token, "mode": "production"}

