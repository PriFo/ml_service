# Port Change: Frontend 3000 -> 6565

## Changes Made

Frontend port has been changed from **3000** to **6565** to avoid conflicts with other services.

## Updated Files

### Configuration
- `frontend/package.json` - Added `-p 6565` to dev and start scripts
- `frontend/Dockerfile` - Changed EXPOSE and PORT to 6565
- `docker-compose.yml` - Changed port mapping to 6565:6565

### Scripts
- `START.bat` - Updated frontend URL
- `run_all.bat` - Updated frontend URL
- `run_frontend.bat` - Updated frontend URL
- `run_frontend.sh` - Updated frontend URL
- `run_all.sh` - Updated frontend URL
- `check_status.bat` - Updated port check to 6565

### Documentation
- `README.md` - Updated references
- `TROUBLESHOOTING.md` - Updated port references
- `QUICK_START.md` - Updated port references
- `CHECKLIST.md` - Updated port references
- `FINAL_CHECK.md` - Updated port references

## New URLs

- **Backend**: http://localhost:8085
- **Frontend**: http://localhost:6565

## Testing

After changes, test the frontend:
```bash
cd frontend
npm run dev
# Should start on http://localhost:6565
```

Or use the startup scripts:
```bash
# Windows
.\START.bat

# Linux/Mac
./run_all.sh
```

Both services will start on their respective ports.

