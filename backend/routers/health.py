from datetime import datetime, timedelta

from fastapi import APIRouter
from sqlalchemy import text

from backend.db.database import async_session_maker
from backend.models.models import SystemMetric, SchedulerLock  # <-- sin MLRun

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
async def health():
    return {"ok": True, "service": "NeoLab SmartStock"}


@router.get("/ready")
async def ready():
    # Readiness = DB reachable
    try:
        async with async_session_maker() as session:
            await session.execute(text("SELECT 1"))
        return {"ready": True}
    except Exception as e:
        return {"ready": False, "error": str(e)}


@router.get("/live")
async def live():
    return {"live": True}


@router.get("/runs")
async def runs(limit: int = 20):
    # Devuelve las últimas ejecuciones de ml_run sin depender de ORM
    async with async_session_maker() as session:
        res = await session.execute(
            text(
                """
                SELECT
                    run_id, started_at, finished_at,
                    skus_procesados, skus_exitosos, skus_fallidos,
                    duracion_segundos, triggered_by
                FROM ml_run
                ORDER BY started_at DESC
                LIMIT :limit
                """
            ),
            {"limit": int(limit)},
        )
        rows = res.mappings().all()
        return {"count": len(rows), "items": [dict(r) for r in rows]}


@router.get("/errors")
async def errors(limit: int = 50):
    async with async_session_maker() as session:
        res = await session.execute(
            text(
                """
                SELECT
                    id, run_id, sku, error_code, error_message,
                    retry_count, max_retries, created_at, resolved_at
                FROM ml_run_errors
                ORDER BY created_at DESC
                LIMIT :limit
                """
            ),
            {"limit": int(limit)},
        )
        rows = res.mappings().all()
        return {"count": len(rows), "items": [dict(r) for r in rows]}


@router.get("/cache")
async def cache(status: str | None = None, limit: int = 50):
    where = ""
    params = {"limit": int(limit)}
    if status:
        where = "WHERE estado = :status"
        params["status"] = status

    async with async_session_maker() as session:
        res = await session.execute(
            text(
                f"""
                SELECT
                    sku, run_id, stock_posicion, stock_objetivo, stock_seguridad,
                    qty_sugerida, qty_final, estado, modelo_seleccionado,
                    drift_detected, computed_at, expires_at
                FROM sku_cache_latest
                {where}
                ORDER BY computed_at DESC
                LIMIT :limit
                """
            ),
            params,
        )
        rows = res.mappings().all()
        return {"count": len(rows), "items": [dict(r) for r in rows]}


@router.get("/locks")
async def locks():
    async with async_session_maker() as session:
        res = await session.execute(
            text(
                """
                SELECT lock_name, locked_by, locked_at, expires_at
                FROM scheduler_locks
                ORDER BY locked_at DESC
                """
            )
        )
        rows = res.mappings().all()
        return {"count": len(rows), "items": [dict(r) for r in rows]}


@router.get("/metrics")
async def metrics(name: str | None = None, minutes: int = 60, limit: int = 200):
    since = datetime.utcnow() - timedelta(minutes=int(minutes))

    where = "WHERE recorded_at >= :since"
    params = {"since": since, "limit": int(limit)}
    if name:
        where += " AND metric_name = :name"
        params["name"] = name

    async with async_session_maker() as session:
        res = await session.execute(
            text(
                f"""
                SELECT id, metric_name, metric_value, metric_type, recorded_at
                FROM system_metrics
                {where}
                ORDER BY recorded_at DESC
                LIMIT :limit
                """
            ),
            params,
        )
        rows = res.mappings().all()
        return {"count": len(rows), "items": [dict(r) for r in rows]}
