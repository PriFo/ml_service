"""FastAPI application"""
import logging
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ml_service.api.routes import router, scheduler as job_scheduler
from ml_service.api.deps import AuthDep
from ml_service.core.config import settings
from ml_service.db.migrations import migrate_to_separated_databases, create_schemas_for_separated_databases
from ml_service.core.daily_scheduler import scheduler as daily_scheduler
from ml_service.core.proxy_middleware import ProxyHeadersMiddleware
from ml_service.db.connection import db_manager
from ml_service.db.queue_manager import WriteQueueManager

logger = logging.getLogger(__name__)

# Global queue manager instance (will be initialized at module level)
queue_manager: WriteQueueManager = None

# Initialize database manager and queue manager
logger.info("Initializing database manager...")
# DatabaseManager is already initialized as db_manager singleton

# Check health of all databases
try:
    health_status = db_manager.check_all_databases()
    logger.info(f"Database health check: {health_status}")
except Exception as e:
    logger.warning(f"Error checking database health: {e}")

# Initialize write queue manager
try:
    queue_manager = WriteQueueManager(db_manager)
    queue_manager.start()
    # Set global instance for access from other modules
    import ml_service.db
    ml_service.db.queue_manager_instance = queue_manager
    logger.info("Write queue manager started successfully")
except Exception as e:
    logger.error(f"Failed to start write queue manager: {e}", exc_info=True)
    queue_manager = None

# Check if migration is needed
from pathlib import Path
legacy_db_path = Path(settings.ML_DB_PATH)
if legacy_db_path.exists():
    logger.info("Legacy database found, checking if migration is needed...")
    # Check if separated databases exist
    models_db_path = Path(settings.ML_DB_MODELS_PATH)
    users_db_path = Path(settings.ML_DB_USERS_PATH)
    logs_db_path = Path(settings.ML_DB_LOGS_PATH)
    
    if not (models_db_path.exists() and users_db_path.exists() and logs_db_path.exists()):
        logger.info("Separated databases not found, running migration...")
        try:
            create_schemas_for_separated_databases()
            migration_result = migrate_to_separated_databases()
            if migration_result.get("status") == "success":
                logger.info(f"Migration completed successfully. Backup: {migration_result.get('backup_path')}")
                logger.info(f"Migration statistics: {migration_result.get('statistics', {})}")
            else:
                logger.error(f"Migration failed: {migration_result.get('error')}")
                # Continue anyway - schemas are created
        except Exception as e:
            logger.error(f"Error during migration: {e}", exc_info=True)
            # Try to create schemas anyway
            try:
                create_schemas_for_separated_databases()
                logger.info("Created separated database schemas despite migration error")
            except Exception as schema_error:
                logger.error(f"Failed to create schemas: {schema_error}", exc_info=True)
    else:
        logger.info("Separated databases already exist, skipping migration")
        # Ensure schemas are up to date
        try:
            create_schemas_for_separated_databases()
            logger.info("Separated database schemas verified/updated")
            
            # Check if users table is empty and legacy DB has users (one-time migration)
            try:
                with db_manager.users_db.get_connection() as conn:
                    user_count = conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
                    if user_count and user_count['count'] == 0:
                        logger.info("Users table is empty, checking legacy database for users...")
                        # Try to migrate users from legacy DB if it exists (one-time only)
                        if legacy_db_path.exists():
                            try:
                                import sqlite3
                                legacy_conn = sqlite3.connect(
                                    str(legacy_db_path),
                                    timeout=settings.ML_DB_TIMEOUT,
                                    check_same_thread=False
                                )
                                legacy_conn.row_factory = sqlite3.Row
                                try:
                                    legacy_users = legacy_conn.execute("SELECT COUNT(*) as count FROM users").fetchone()
                                    if legacy_users and legacy_users['count'] > 0:
                                        logger.info("Found users in legacy database, migrating...")
                                        migration_result = migrate_to_separated_databases()
                                        if migration_result.get("status") == "success":
                                            logger.info(f"Users migrated successfully: {migration_result.get('statistics', {})}")
                                finally:
                                    legacy_conn.close()
                            except Exception as migrate_error:
                                logger.warning(f"Could not migrate users from legacy DB: {migrate_error}")
            except Exception as check_error:
                logger.warning(f"Could not check users table: {check_error}")
        except Exception as e:
            logger.warning(f"Could not verify schemas: {e}")
else:
    # No legacy database, just create schemas for separated databases
    logger.info("No legacy database found, creating separated database schemas...")
    try:
        create_schemas_for_separated_databases()
        logger.info("Separated database schemas created successfully")
    except Exception as e:
        logger.error(f"Failed to create separated database schemas: {e}", exc_info=True)

# Run migrations for separated databases (if needed)
# run_migrations()  # Legacy - not needed for separated databases

# Create FastAPI app
app = FastAPI(
    title="ML Service 0.9.1",
    description="Production-grade ML Platform",
    version="0.9.1"
)

# Proxy headers middleware (must be first to process X-Forwarded-* headers)
if settings.ML_TRUST_PROXY:
    app.add_middleware(ProxyHeadersMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify allowed origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(router, prefix="", tags=["ml"])


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


# Global exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors"""
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all other exceptions to prevent server crashes"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error. Please check logs for details.",
            "error_type": type(exc).__name__
        }
    )


# Protected documentation endpoints (only for authenticated users)
@app.get("/docs", include_in_schema=False)
async def get_documentation(user: dict = AuthDep):
    """Swagger UI documentation (admin only)"""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
    )


@app.get("/redoc", include_in_schema=False)
async def get_redoc_documentation(user: dict = AuthDep):
    """ReDoc documentation (admin only)"""
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@next/bundles/redoc.standalone.js",
    )


@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_json(user: dict = AuthDep):
    """OpenAPI JSON schema (admin only)"""
    return app.openapi()


@app.on_event("startup")
async def startup_event():
    """Startup tasks"""
    # Verify database manager is initialized
    try:
        db_status = db_manager.get_database_status()
        logger.info(f"Database status at startup: {db_status}")
        
        # Final health check
        health_status = db_manager.check_all_databases()
        logger.info(f"Final database health check: {health_status}")
        
        # Verify queue manager is running
        if queue_manager and queue_manager.running:
            queue_sizes = queue_manager.get_queue_sizes()
            logger.info(f"Write queue sizes: {queue_sizes}")
        else:
            logger.warning("Write queue manager is not running")
    except Exception as e:
        logger.error(f"Error during startup verification: {e}", exc_info=True)
    
    # Start daily scheduler
    daily_scheduler.start()
    
    # Start job scheduler
    if job_scheduler:
        await job_scheduler.start()
        print("Job scheduler started")
    
    protocol = "https" if settings.ML_USE_HTTPS else "http"
    print("ML Service 0.9.1 started")
    print(f"API available at {protocol}://{settings.ML_SERVICE_HOST}:{settings.ML_SERVICE_PORT}")
    if settings.ML_USE_HTTPS:
        print(f"HTTPS enabled with certificate: {settings.ML_SSL_CERT_FILE}")
    
    # Print database paths
    print(f"Models DB: {settings.ML_DB_MODELS_PATH}")
    print(f"Users DB: {settings.ML_DB_USERS_PATH}")
    print(f"Logs DB: {settings.ML_DB_LOGS_PATH}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown tasks"""
    daily_scheduler.stop()
    
    # Stop job scheduler
    if job_scheduler:
        await job_scheduler.stop()
        print("Job scheduler stopped")
    
    # Stop write queue manager
    if queue_manager:
        try:
            queue_manager.stop()
            logger.info("Write queue manager stopped")
        except Exception as e:
            logger.error(f"Error stopping write queue manager: {e}")
    
    print("ML Service 0.9.1 stopped")

