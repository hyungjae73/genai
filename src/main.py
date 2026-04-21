"""
FastAPI application for Payment Compliance Monitor.

This module provides REST API for managing monitoring sites, contracts, and viewing results.
"""

import logging
import os
import secrets

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
from sqlalchemy.exc import IntegrityError

from src.auth.password import hash_password
from src.database import SessionLocal
from src.models import AuditLog, User

logger = logging.getLogger(__name__)


def _create_initial_admin():
    """Create the initial admin user if no users exist in the database."""
    db = SessionLocal()
    try:
        user_count = db.query(User).count()
        if user_count == 0:
            username = os.getenv("ADMIN_USERNAME", "hjkim93")
            password = os.getenv("ADMIN_PASSWORD")
            if not password:
                password = secrets.token_urlsafe(16)
                logger.warning(f"ADMIN_PASSWORD not set. Generated password: {password}")

            admin = User(
                username=username,
                email=f"{username}@localhost",
                hashed_password=hash_password(password),
                role="admin",
                must_change_password=True,
            )
            db.add(admin)
            db.flush()

            log = AuditLog(
                user="system",
                action="create",
                resource_type="user",
                resource_id=admin.id,
                details={"username": username, "role": "admin", "reason": "initial_setup"},
            )
            db.add(log)
            db.commit()
            logger.info(f"Initial admin user '{username}' created.")
    except IntegrityError:
        db.rollback()
        logger.info("Initial admin user already exists (created by another worker).")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("Starting Payment Compliance Monitor API...")
    _create_initial_admin()

    from src.core.telemetry import init_telemetry, instrument_fastapi
    init_telemetry()
    instrument_fastapi(app)

    yield
    # Shutdown
    print("Shutting down Payment Compliance Monitor API...")


# Create FastAPI app
app = FastAPI(
    title="Payment Compliance Monitor API",
    description="API for monitoring payment compliance and detecting violations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Payment Compliance Monitor API",
        "version": "1.0.0",
        "status": "running"
    }



@app.get("/health")
async def health_check():
    """Extended health check endpoint (Requirements 8.1, 8.4)."""
    import os
    from datetime import datetime, timezone
    from sqlalchemy import text
    from fastapi.responses import JSONResponse

    health = {
        "status": "healthy",
        "version": os.getenv("IMAGE_TAG", "dev"),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "services": {
            "database": "unknown",
            "redis": "unknown"
        }
    }

    # PostgreSQL connection check (sync session — matches existing database.py)
    try:
        from src.database import SessionLocal
        session = SessionLocal()
        try:
            session.execute(text("SELECT 1"))
            health["services"]["database"] = "healthy"
        finally:
            session.close()
    except Exception as e:
        health["status"] = "unhealthy"
        health["services"]["database"] = {
            "status": f"unhealthy: {str(e)}",
            "error_code": "PCM-E201",
        }

    # Redis connection check
    try:
        import redis as redis_lib
        redis_client = redis_lib.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        redis_client.ping()
        health["services"]["redis"] = "healthy"
        redis_client.close()
    except Exception as e:
        health["status"] = "unhealthy"
        health["services"]["redis"] = {
            "status": f"unhealthy: {str(e)}",
            "error_code": "PCM-E301",
        }

    status_code = 200 if health["status"] == "healthy" else 503
    return JSONResponse(content=health, status_code=status_code)



# Import and include routers
from src.api.auth import router as auth_router
from src.api.users import router as users_router
from src.api.sites import router as sites_router
from src.api.customers import router as customers_router
from src.api.contracts import router as contracts_router
from src.api.monitoring import router as monitoring_router
from src.api.alerts import router as alerts_router
from src.api.screenshots import router as screenshots_router
from src.api.verification import router as verification_router
from src.api.categories import router as categories_router
from src.api.field_schemas import router as field_schemas_router
from src.api.extraction import router as extraction_router
from src.api.crawl import router as crawl_router
from src.api.extracted_data import router as extracted_data_router
from src.api.extracted_data import price_history_router
from src.api.audit_logs import router as audit_logs_router
from src.api.schedules import router as schedules_router
from src.api.notifications import router as notifications_router
from src.api.dark_patterns import router as dark_patterns_router
from src.api.reviews import router as reviews_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(users_router, prefix="/api/users", tags=["users"])
app.include_router(customers_router, prefix="/api/customers", tags=["customers"])
app.include_router(sites_router, prefix="/api/sites", tags=["sites"])
app.include_router(contracts_router, prefix="/api/contracts", tags=["contracts"])
app.include_router(monitoring_router, prefix="/api/monitoring", tags=["monitoring"])
app.include_router(alerts_router, prefix="/api/alerts", tags=["alerts"])
app.include_router(screenshots_router, prefix="/api/screenshots", tags=["screenshots"])
app.include_router(verification_router, prefix="/api/verification", tags=["verification"])
app.include_router(categories_router, prefix="/api/categories", tags=["categories"])
app.include_router(field_schemas_router, prefix="/api/field-schemas", tags=["field-schemas"])
app.include_router(extraction_router, prefix="/api/extraction", tags=["extraction"])
app.include_router(crawl_router, prefix="/api/crawl", tags=["crawl"])
app.include_router(extracted_data_router, prefix="/api/extracted-data", tags=["extracted-data"])
app.include_router(price_history_router, prefix="/api/price-history", tags=["price-history"])
app.include_router(audit_logs_router, prefix="/api/audit-logs", tags=["audit-logs"])
app.include_router(schedules_router, prefix="/api", tags=["schedules"])
app.include_router(notifications_router, prefix="/api", tags=["notifications"])
app.include_router(dark_patterns_router, prefix="/api", tags=["dark-patterns"])
app.include_router(reviews_router, prefix="/api/reviews", tags=["reviews"])

# Serve screenshot files as static assets so the frontend can load them
# via their filesystem path (e.g. /screenshots/2024/03/42/xxx.png).
_screenshot_dir = os.getenv("SCREENSHOT_DIR", "screenshots")
if os.path.isdir(_screenshot_dir):
    app.mount("/screenshots", StaticFiles(directory=_screenshot_dir), name="screenshots")
