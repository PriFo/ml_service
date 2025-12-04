"""Security and authentication"""
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import HTTPException, Security, Header, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from ml_service.core.config import settings
from ml_service.db.repositories import ApiTokenRepository
from ml_service.db.connection import db_manager

# Try to import bcrypt, fallback to None if not installed
try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False
    bcrypt = None

security = HTTPBearer(auto_error=False)


def generate_token() -> str:
    """Generate a secure random token"""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash token using SHA256"""
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    """Hash password using bcrypt with salt"""
    if not BCRYPT_AVAILABLE:
        raise ImportError(
            "bcrypt is not installed. Please install it with: pip install bcrypt>=4.0.0\n"
            "Or install all dependencies: pip install -r requirements.txt"
        )
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash"""
    if not BCRYPT_AVAILABLE:
        # Fallback to SHA256 if bcrypt is not available (for backward compatibility)
        sha256_hash = hashlib.sha256(password.encode()).hexdigest()
        return sha256_hash == password_hash
    
    try:
        # Try bcrypt first (new format)
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
    except (ValueError, TypeError):
        # Fallback to SHA256 for backward compatibility (legacy passwords)
        # This allows existing passwords to still work during migration
        sha256_hash = hashlib.sha256(password.encode()).hexdigest()
        return sha256_hash == password_hash


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security),
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
) -> dict:
    """
    Dependency for authenticated endpoints.
    Always validates tokens through database (no dev mode).
    """
    # Get token from X-Admin-Token header or Authorization Bearer
    token = x_admin_token
    if not token and credentials:
        token = credentials.credentials
    
    if not token:
        raise HTTPException(
            status_code=401,
            detail="Missing authentication token"
        )
    
    # Check admin token from env (for backward compatibility)
    if settings.ML_ADMIN_API_TOKEN and token == settings.ML_ADMIN_API_TOKEN:
        return {
            "authenticated": True,
            "user_id": "system_admin",
            "username": "system_admin",
            "tier": "system_admin"
        }
    
    # Validate token through database
    token_hash = hash_token(token)
    token_repo = ApiTokenRepository()
    api_token = token_repo.get_by_hash(token_hash)
    
    if not api_token:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )
    
    # Get user information from database
    with db_manager.users_db.get_connection() as conn:
        user_row = conn.execute("""
            SELECT user_id, username, tier, is_active
            FROM users
            WHERE user_id = ? AND is_active = 1
        """, (api_token.user_id,)).fetchone()
        
        if not user_row:
            raise HTTPException(
                status_code=401,
                detail="User not found or inactive"
            )
        
        # Update last_used_at for the token
        token_repo.update_last_used(api_token.token_id)
        
        return {
            "authenticated": True,
            "user_id": user_row['user_id'],
            "username": user_row['username'],
            "tier": user_row['tier'] or 'user'
        }


# Dependency for authenticated endpoints
AuthDep = Depends(get_current_user)


def require_tier(allowed_tiers: List[str]):
    """Dependency для проверки tier пользователя"""
    def check(user: dict = AuthDep):
        if user.get("tier") not in allowed_tiers:
            raise HTTPException(403, "Access denied")
        return user
    return Depends(check)


def require_system_admin():
    """Dependency для проверки system_admin"""
    return require_tier(["system_admin"])


def require_admin():
    """Dependency для проверки admin или system_admin"""
    return require_tier(["system_admin", "admin"])


def can_manage_user(current_user: dict, target_user_tier: str) -> bool:
    """
    Проверка, может ли текущий пользователь управлять целевым пользователем
    
    Args:
        current_user: информация о текущем пользователе
        target_user_tier: tier целевого пользователя
        
    Returns:
        True если может управлять, False если нет
    """
    current_tier = current_user.get("tier")
    
    if current_tier == "system_admin":
        return True  # system_admin может управлять всеми
    
    if current_tier == "admin":
        # admin может управлять только user, но не admin и system_admin
        return target_user_tier == "user"
    
    return False  # user не может управлять никем


def can_create_tier(current_user: dict, new_tier: str) -> bool:
    """Проверка, может ли текущий пользователь создать пользователя с указанным tier"""
    current_tier = current_user.get("tier")
    
    if current_tier == "system_admin":
        # system_admin может создать user или admin, но не system_admin
        return new_tier in ["user", "admin"]
    
    if current_tier == "admin":
        # admin может создать только user
        return new_tier == "user"
    
    return False

