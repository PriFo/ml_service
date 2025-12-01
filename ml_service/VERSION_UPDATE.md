# Version Update: 3.2.0 -> 0.9.1

## Changes Made

### Version Updated
- **Old version**: 3.2.0
- **New version**: 0.9.1

### Port Configuration Verified
- **Backend port**: 8085 (matches old version)
- **Frontend port**: 6565 (changed from 3000)

## Updated Files

### Backend
- `backend/ml_service/__init__.py` - `__version__ = "0.9.1"`
- `backend/ml_service/api/app.py` - version and title updated

### Frontend
- `frontend/package.json` - `"version": "0.9.1"`

### Scripts
- `START.bat` - version references updated
- `run_all.bat` - version references updated
- `run_backend.bat` - version references updated
- `run_frontend.bat` - version references updated
- `check_status.bat` - version references updated
- `run_all.sh` - version references updated
- `run_backend.sh` - version references updated
- `run_frontend.sh` - version references updated

### Documentation
- `README.md` - version updated
- `QUICK_START.md` - version updated
- `TROUBLESHOOTING.md` - version updated

## Port Configuration

### Backend
- **Port**: 8085 (verified from old version)
- **Config**: `backend/ml_service/core/config.py` - `ML_SERVICE_PORT: int = 8085`

### Frontend
- **Port**: 6565 (changed from 3000 to avoid conflicts)
- **Config**: `frontend/package.json` - `"dev": "next dev -p 6565"`

## Verification

All version references have been updated from 3.2.0 to 0.9.1.
Backend port matches the old version (8085).
Frontend port changed to 6565 to avoid conflicts with other services.

