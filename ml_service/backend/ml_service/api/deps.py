"""API dependencies"""
from fastapi import Depends
from ml_service.core.security import get_current_user

# Dependency for authenticated endpoints
AuthDep = Depends(get_current_user)

