"""
NeoLab SmartStock - FastAPI Application
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import sys

# Asegurar que el directorio raíz esté en el path para resolver imports de 'backend.'
try:
    import backend.db.database
except ImportError:
    # Si falla, estamos probablemente dentro de la carpeta /backend/
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.db.database import init_db, close_db
from backend.jobs.scheduler import init_scheduler, shutdown_scheduler
from backend.utils.logger import get_logger, configure_logging
from backend.api.ml import router as ml_router
from backend.routers import health, dashboard, api

logger = get_logger(__name__)

# Configure logging level from environment
log_level = os.getenv("LOG_LEVEL", "INFO")
configure_logging(level=getattr(__import__("logging"), log_level))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting NeoLab SmartStock...")
    
    # Initialize database
    await init_db()
    
    # Initialize scheduler
    await init_scheduler()
    
    logger.info("NeoLab SmartStock started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down NeoLab SmartStock...")
    
    # Shutdown scheduler
    await shutdown_scheduler()
    
    # Close database connections
    await close_db()
    
    logger.info("NeoLab SmartStock shutdown complete")


# Create FastAPI application
app = FastAPI(
    title="NeoLab SmartStock API",
    description="Professional Purchase Replenishment Prediction System",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(dashboard.router)
app.include_router(api.router)
app.include_router(ml_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "NeoLab SmartStock API",
        "version": "2.0.0",
        "docs": "/docs",
        "health": "/health"
    }


@app.get("/api/v1/status")
async def api_status():
    """API status endpoint."""
    return {
        "status": "operational",
        "version": "2.0.0",
        "features": [
            "stock_management",
            "purchase_suggestions",
            "ml_pipeline",
            "scheduler",
            "observability"
        ]
    }
