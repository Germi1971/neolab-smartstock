"""
NeoLab SmartStock - FastAPI Application
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.db.database import init_db, close_db
from backend.jobs.scheduler import init_scheduler, shutdown_scheduler
from backend.utils.logger import get_logger, configure_logging

# Import routers
from backend.routers import health

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
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)


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
