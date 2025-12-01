"""FastAPI application"""
import logging
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from ml_service.api.routes import router
from ml_service.api.deps import AuthDep
from ml_service.core.config import settings
from ml_service.db.migrations import run_migrations
from ml_service.core.daily_scheduler import scheduler

logger = logging.getLogger(__name__)

# Initialize database
run_migrations()

# Create FastAPI app
app = FastAPI(
    title="ML Service 0.9.1",
    description="Production-grade ML Platform",
    version="0.9.1"
)

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
    # Start daily scheduler
    scheduler.start()
    print("ML Service 0.9.1 started")
    print(f"API available at http://{settings.ML_SERVICE_HOST}:{settings.ML_SERVICE_PORT}")


@app.on_event("shutdown")
async def shutdown_event():
    """Shutdown tasks"""
    scheduler.stop()
    print("ML Service 0.9.1 stopped")

