"""
FastAPI application for Payment Compliance Monitor.

This module provides REST API for managing monitoring sites, contracts, and viewing results.
"""

import os

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup
    print("Starting Payment Compliance Monitor API...")
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
    """Health check endpoint."""
    return {"status": "healthy"}


# Import and include routers
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
