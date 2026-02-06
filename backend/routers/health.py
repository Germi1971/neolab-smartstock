"""
Health and Observability Endpoints
"""
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func

from backend.db.database import get_db
from backend.models.ml_models import SystemMetric, SchedulerLock, MLRun
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", response_model=Dict[str, Any])
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Basic health check endpoint.
    Returns overall system status.
    """
    checks = {
        "database": "unknown",
        "ml_pipeline": "unknown",
        "scheduler": "unknown"
    }
    
    # Database check
    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "healthy"
    except Exception as e:
        checks["database"] = f"unhealthy: {str(e)}"
        logger.error(f"Database health check failed: {e}")
    
    # ML Pipeline check - last run within 24 hours
    try:
        result = await db.execute(
            text("""
                SELECT finished_at, skus_fallidos, skus_procesados
                FROM ml_run
                WHERE finished_at IS NOT NULL
                ORDER BY finished_at DESC
                LIMIT 1
            """)
        )
        row = result.fetchone()
        if row:
            last_run = row[0]
            hours_ago = (datetime.utcnow() - last_run).total_seconds() / 3600
            
            if hours_ago < 24:
                if row[1] == 0:  # No failures
                    checks["ml_pipeline"] = "healthy"
                elif row[1] < row[2] * 0.1:  # Less than 10% failures
                    checks["ml_pipeline"] = "degraded"
                else:
                    checks["ml_pipeline"] = "unhealthy"
            else:
                checks["ml_pipeline"] = f"stale (last run {hours_ago:.1f}h ago)"
        else:
            checks["ml_pipeline"] = "no runs yet"
    except Exception as e:
        checks["ml_pipeline"] = f"error: {str(e)}"
    
    # Scheduler check - active locks
    try:
        result = await db.execute(
            text("SELECT COUNT(*) FROM scheduler_locks WHERE expires_at > NOW()")
        )
        active_locks = result.scalar()
        checks["scheduler"] = f"active ({active_locks} locks)" if active_locks > 0 else "idle"
    except Exception as e:
        checks["scheduler"] = f"error: {str(e)}"
    
    # Overall status
    overall = "healthy"
    if any("unhealthy" in str(v) or "error" in str(v) for v in checks.values()):
        overall = "unhealthy"
    elif any("degraded" in str(v) or "stale" in str(v) for v in checks.values()):
        overall = "degraded"
    
    return {
        "status": overall,
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": checks
    }


@router.get("/ready", response_model=Dict[str, bool])
async def readiness_check(db: AsyncSession = Depends(get_db)):
    """
    Kubernetes-style readiness probe.
    Returns 200 only when ready to serve traffic.
    """
    try:
        await db.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        raise HTTPException(status_code=503, detail="Not ready")


@router.get("/live", response_model=Dict[str, bool])
async def liveness_check():
    """
    Kubernetes-style liveness probe.
    Returns 200 if the application is running.
    """
    return {"alive": True}


@router.get("/metrics", response_model=Dict[str, Any])
async def get_metrics(
    metric_name: Optional[str] = None,
    hours: int = 24,
    db: AsyncSession = Depends(get_db)
):
    """
    Get system metrics.
    """
    since = datetime.utcnow() - timedelta(hours=hours)
    
    query = select(SystemMetric).where(SystemMetric.recorded_at >= since)
    
    if metric_name:
        query = query.where(SystemMetric.metric_name == metric_name)
    
    query = query.order_by(SystemMetric.recorded_at.desc())
    
    result = await db.execute(query)
    metrics = result.scalars().all()
    
    # Aggregate by metric name
    aggregated: Dict[str, Dict[str, Any]] = {}
    for m in metrics:
        if m.metric_name not in aggregated:
            aggregated[m.metric_name] = {
                "current": m.metric_value,
                "min": m.metric_value,
                "max": m.metric_value,
                "avg": m.metric_value,
                "count": 1,
                "type": m.metric_type
            }
        else:
            agg = aggregated[m.metric_name]
            agg["min"] = min(agg["min"], m.metric_value)
            agg["max"] = max(agg["max"], m.metric_value)
            agg["avg"] = (agg["avg"] * agg["count"] + m.metric_value) / (agg["count"] + 1)
            agg["count"] += 1
    
    return {
        "period_hours": hours,
        "metrics_recorded": len(metrics),
        "aggregated": aggregated
    }


@router.get("/runs", response_model=Dict[str, Any])
async def get_run_status(
    limit: int = 10,
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent ML run status.
    """
    result = await db.execute(
        text("""
            SELECT 
                run_id,
                started_at,
                finished_at,
                skus_procesados,
                skus_exitosos,
                skus_fallidos,
                duracion_segundos,
                triggered_by,
                CASE 
                    WHEN skus_fallidos = 0 THEN 'SUCCESS'
                    WHEN skus_exitosos = 0 THEN 'FAILED'
                    ELSE 'PARTIAL'
                END as status
            FROM ml_run
            ORDER BY started_at DESC
            LIMIT :limit
        """),
        {"limit": limit}
    )
    
    runs = []
    for row in result.fetchall():
        runs.append({
            "run_id": row[0],
            "started_at": row[1].isoformat() if row[1] else None,
            "finished_at": row[2].isoformat() if row[2] else None,
            "skus_procesados": row[3],
            "skus_exitosos": row[4],
            "skus_fallidos": row[5],
            "duracion_segundos": row[6],
            "triggered_by": row[7],
            "status": row[8]
        })
    
    # Calculate success rate
    if runs:
        success_count = sum(1 for r in runs if r["status"] == "SUCCESS")
        success_rate = success_count / len(runs)
    else:
        success_rate = 0
    
    return {
        "runs": runs,
        "success_rate_24h": success_rate,
        "total_runs": len(runs)
    }


@router.get("/errors", response_model=Dict[str, Any])
async def get_errors(
    run_id: Optional[str] = None,
    sku: Optional[str] = None,
    unresolved_only: bool = True,
    limit: int = 50,
    db: AsyncSession = Depends(get_db)
):
    """
    Get ML run errors.
    """
    query = """
        SELECT 
            e.id,
            e.run_id,
            e.sku,
            e.error_code,
            e.error_message,
            e.retry_count,
            e.max_retries,
            e.created_at,
            e.resolved_at
        FROM ml_run_errors e
        WHERE 1=1
    """
    params: Dict[str, Any] = {"limit": limit}
    
    if run_id:
        query += " AND e.run_id = :run_id"
        params["run_id"] = run_id
    
    if sku:
        query += " AND e.sku = :sku"
        params["sku"] = sku
    
    if unresolved_only:
        query += " AND e.resolved_at IS NULL"
    
    query += " ORDER BY e.created_at DESC LIMIT :limit"
    
    result = await db.execute(text(query), params)
    
    errors = []
    for row in result.fetchall():
        errors.append({
            "id": row[0],
            "run_id": row[1],
            "sku": row[2],
            "error_code": row[3],
            "error_message": row[4],
            "retry_count": row[5],
            "max_retries": row[6],
            "created_at": row[7].isoformat() if row[7] else None,
            "resolved_at": row[8].isoformat() if row[8] else None
        })
    
    # Get error summary
    summary_result = await db.execute(
        text("""
            SELECT 
                error_code,
                COUNT(*) as count
            FROM ml_run_errors
            WHERE resolved_at IS NULL
            GROUP BY error_code
            ORDER BY count DESC
        """)
    )
    
    summary = {row[0]: row[1] for row in summary_result.fetchall()}
    
    return {
        "errors": errors,
        "summary": summary,
        "total_unresolved": sum(summary.values())
    }


@router.post("/errors/{error_id}/resolve")
async def resolve_error(
    error_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Mark an error as resolved.
    """
    result = await db.execute(
        text("""
            UPDATE ml_run_errors
            SET resolved_at = NOW()
            WHERE id = :error_id
        """),
        {"error_id": error_id}
    )
    await db.commit()
    
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="Error not found")
    
    return {"status": "resolved", "error_id": error_id}


@router.get("/cache", response_model=Dict[str, Any])
async def get_cache_status(db: AsyncSession = Depends(get_db)):
    """
    Get materialized cache status.
    """
    result = await db.execute(
        text("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN expires_at < NOW() THEN 1 ELSE 0 END) as expired,
                SUM(CASE WHEN estado = 'PENDIENTE' THEN 1 ELSE 0 END) as pendientes,
                SUM(CASE WHEN estado = 'APROBADO' THEN 1 ELSE 0 END) as aprobadas,
                SUM(CASE WHEN drift_detected = TRUE THEN 1 ELSE 0 END) as drift_detected,
                MAX(computed_at) as last_computed,
                MIN(expires_at) as first_expiry
            FROM sku_cache_latest
        """)
    )
    
    row = result.fetchone()
    
    return {
        "total_cached": row[0] or 0,
        "expired": row[1] or 0,
        "pendientes": row[2] or 0,
        "aprobadas": row[3] or 0,
        "drift_detected": row[4] or 0,
        "last_computed": row[5].isoformat() if row[5] else None,
        "first_expiry": row[6].isoformat() if row[6] else None,
        "healthy": row[1] == 0 if row else False
    }
