"""
Cache Refresh Job - Materialize cache for frequently accessed data.
"""
from datetime import datetime, timedelta
from typing import Dict, Any, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from backend.db.database import async_session_maker
from backend.jobs.scheduler import SchedulerLockManager
from backend.utils.logger import get_logger
from backend.models.ml_models import SKULatestCache, SchedulerConfig

logger = get_logger(__name__)


class CacheRefreshJob:
    """Job to refresh materialized cache."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
        self.cache_ttl_minutes = 60
        self.batch_size = 500
    
    async def load_config(self):
        """Load cache configuration."""
        result = await self.session.execute(
            select(SchedulerConfig).where(
                SchedulerConfig.config_key == "cache.ttl_minutes"
            )
        )
        config = result.scalar_one_or_none()
        if config:
            self.cache_ttl_minutes = int(config.config_value)
    
    async def get_latest_run_id(self) -> str:
        """Get the latest successful ML run ID."""
        result = await self.session.execute(
            text("""
                SELECT run_id FROM ml_run 
                WHERE finished_at IS NOT NULL 
                AND skus_fallidos = 0
                ORDER BY finished_at DESC 
                LIMIT 1
            """)
        )
        row = result.fetchone()
        if row:
            return row[0]
        
        # Fallback to any finished run
        result = await self.session.execute(
            text("""
                SELECT run_id FROM ml_run 
                WHERE finished_at IS NOT NULL 
                ORDER BY finished_at DESC 
                LIMIT 1
            """)
        )
        row = result.fetchone()
        if row:
            return row[0]
        
        raise RuntimeError("No ML runs found")
    
    async def refresh_cache(self) -> Dict[str, Any]:
        """Refresh the materialized cache."""
        await self.load_config()
        
        run_id = await self.get_latest_run_id()
        expires_at = datetime.utcnow() + timedelta(minutes=self.cache_ttl_minutes)
        
        logger.info(f"Refreshing cache from run {run_id}, expires at {expires_at}")
        
        # Clear old cache
        await self.session.execute(text("DELETE FROM sku_cache_latest"))
        await self.session.commit()
        
        # Build cache from latest data
        await self.session.execute(
            text("""
                INSERT INTO sku_cache_latest (
                    sku, run_id,
                    stock_posicion, stock_objetivo, stock_seguridad,
                    qty_sugerida, estado, qty_final,
                    modelo_seleccionado, s_policy, S_policy, score_composite,
                    cv_12m, lambda_eventos_mes_12m, eventos_12m, unidades_12m,
                    drift_detected,
                    computed_at, expires_at
                )
                SELECT 
                    s.sku,
                    :run_id,
                    COALESCE(st.stock_posicion, 0),
                    p.stock_objetivo,
                    p.stock_seguridad,
                    COALESCE(sug.qty_sugerida, 0),
                    COALESCE(sug.estado, 'PENDIENTE'),
                    sug.qty_final,
                    sug.modelo_seleccionado,
                    sug.s_policy,
                    sug.S_policy,
                    mr.score_composite,
                    f.cv_12m,
                    f.lambda_eventos_mes_12m,
                    f.eventos_12m,
                    f.unidades_12m,
                    COALESCE(dd.drift_detected, FALSE),
                    NOW(),
                    :expires_at
                FROM sku_master s
                JOIN sku_parameters p ON s.sku = p.sku
                LEFT JOIN stock st ON s.sku = st.sku
                LEFT JOIN ml_suggestions sug ON s.sku = sug.sku AND sug.run_id = :run_id
                LEFT JOIN ml_model_registry mr ON s.sku = mr.sku
                LEFT JOIN ml_sku_features f ON s.sku = f.sku AND f.run_id = :run_id
                LEFT JOIN ml_drift_log dd ON s.sku = dd.sku AND dd.run_id = :run_id
                WHERE s.activo = TRUE
            """),
            {"run_id": run_id, "expires_at": expires_at}
        )
        await self.session.commit()
        
        # Count cached records
        result = await self.session.execute(
            text("SELECT COUNT(*) FROM sku_cache_latest")
        )
        count = result.scalar()
        
        logger.info(f"Cache refreshed: {count} SKUs cached")
        
        return {
            "cached_count": count,
            "run_id": run_id,
            "expires_at": expires_at.isoformat()
        }
    
    async def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        result = await self.session.execute(
            text("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN expires_at < NOW() THEN 1 ELSE 0 END) as expired,
                    SUM(CASE WHEN estado = 'PENDIENTE' THEN 1 ELSE 0 END) as pendientes,
                    SUM(CASE WHEN estado = 'APROBADO' THEN 1 ELSE 0 END) as aprobadas,
                    SUM(CASE WHEN drift_detected = TRUE THEN 1 ELSE 0 END) as drift_detected
                FROM sku_cache_latest
            """)
        )
        row = result.fetchone()
        
        return {
            "total_cached": row[0] or 0,
            "expired": row[1] or 0,
            "pendientes": row[2] or 0,
            "aprobadas": row[3] or 0,
            "drift_detected": row[4] or 0
        }


async def refresh_materialized_cache() -> Dict[str, Any]:
    """Entry point for cache refresh job."""
    instance_id = f"cache-refresh-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    async with async_session_maker() as session:
        lock_manager = SchedulerLockManager(session)
        
        lock_acquired = await lock_manager.acquire_lock(
            "cache_refresh",
            instance_id,
            timeout_seconds=300  # 5 minutes
        )
        
        if not lock_acquired:
            logger.warning("Another cache refresh is running. Skipping.")
            return {"status": "skipped", "reason": "lock_not_acquired"}
        
        try:
            job = CacheRefreshJob(session)
            result = await job.refresh_cache()
            stats = await job.get_cache_stats()
            
            return {
                "status": "success",
                **result,
                "stats": stats
            }
            
        finally:
            await lock_manager.release_lock("cache_refresh", instance_id)


async def get_cached_sku_list(
    estado: str = None,
    modelo: str = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get cached SKU list with filtering."""
    async with async_session_maker() as session:
        query = """
            SELECT 
                sku, stock_posicion, stock_objetivo, qty_sugerida,
                estado, modelo_seleccionado, cv_12m, drift_detected,
                expires_at
            FROM sku_cache_latest
            WHERE 1=1
        """
        params = {}
        
        if estado:
            query += " AND estado = :estado"
            params["estado"] = estado
        
        if modelo:
            query += " AND modelo_seleccionado = :modelo"
            params["modelo"] = modelo
        
        query += " ORDER BY sku LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        result = await session.execute(text(query), params)
        
        rows = []
        for row in result.fetchall():
            rows.append({
                "sku": row[0],
                "stock_posicion": row[1],
                "stock_objetivo": row[2],
                "qty_sugerida": row[3],
                "estado": row[4],
                "modelo_seleccionado": row[5],
                "cv_12m": row[6],
                "drift_detected": row[7],
                "cache_expired": row[8] < datetime.utcnow() if row[8] else True
            })
        
        return rows


async def invalidate_cache(sku: str = None):
    """Invalidate cache for a specific SKU or all."""
    async with async_session_maker() as session:
        if sku:
            await session.execute(
                text("DELETE FROM sku_cache_latest WHERE sku = :sku"),
                {"sku": sku}
            )
        else:
            await session.execute(text("DELETE FROM sku_cache_latest"))
        
        await session.commit()
        logger.info(f"Cache invalidated{' for SKU ' + sku if sku else ''}")
