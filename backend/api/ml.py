from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import uuid
import json

from backend.db.database import get_db
from backend.ml_engine.pipeline import MLPipeline
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/ml", tags=["ml"])

@router.post("/run")
async def run_ml_pipeline(
    payload: dict = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Ejecuta el pipeline ML.
    Payload opcional: { "sku": "..." } o { "skus": ["...", "..."] }
    """
    payload = payload or {}
    started_at = datetime.utcnow()
    run_id = f"RUN-{started_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    
    # 1. Resolver SKUs
    if "sku" in payload:
        skus = [payload["sku"]]
    elif "skus" in payload:
        skus = payload["skus"]
    else:
        res = await db.execute(text("SELECT sku FROM parametros_sku WHERE activo = 1"))
        skus = [r[0] for r in res.fetchall()]

    logger.info(f"ML pipeline start | run_id={run_id} | skus={len(skus)}")

    # 2. Registrar inicio del run
    await db.execute(
        text("""
            INSERT INTO ss_ml_run (run_id, started_at, status, triggered_by, skus_procesados)
            VALUES (:run_id, :started_at, 'RUNNING', 'MANUAL', :total)
        """),
        {"run_id": run_id, "started_at": started_at, "total": len(skus)}
    )
    await db.flush()

    pipeline = MLPipeline(session=db, run_id=run_id)
    ok = 0
    errors = []

    # 3. Ejecutar pipeline
    for sku in skus:
        try:
            await pipeline.process_single_sku(sku)
            ok += 1
        except Exception as e:
            logger.error(f"Pipeline error | {sku} | {e}")
            errors.append({"sku": sku, "error": str(e)})
            await db.rollback()

    # 4. Finalizar run
    finished_at = datetime.utcnow()
    duration = int((finished_at - started_at).total_seconds())
    failed = len(errors)
    
    if ok == len(skus) and failed == 0:
        status = "SUCCESS"
    elif ok > 0:
        status = "PARTIAL"
    else:
        status = "FAILED"

    await db.execute(
        text("""
            UPDATE ss_ml_run 
            SET finished_at = :finished_at,
                skus_exitosos = :ok,
                skus_fallidos = :failed,
                duracion_segundos = :duration,
                status = :status,
                error_log = :error_log
            WHERE run_id = :run_id
        """),
        {
            "run_id": run_id,
            "finished_at": finished_at,
            "ok": ok,
            "failed": failed,
            "duration": duration,
            "status": status,
            "error_log": json.dumps(errors[:20]) if errors else None
        }
    )
    await db.commit()

    return {
        "ok": True,
        "run_id": run_id,
        "total": len(skus),
        "success": ok,
        "failed": failed,
        "status": status,
        "duration_seconds": duration,
        "errors": errors[:10],
    }

@router.get("/runs")
async def get_ml_runs(
    page: int = 1,
    page_size: int = 10,
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    """Lista de ejecuciones con stats para KPIs."""
    offset = (page - 1) * page_size
    
    where_parts = ["1=1"]
    params = {"limit": page_size, "offset": offset}
    
    if status and status.upper() != "TODOS":
        where_parts.append("status = :status")
        params["status"] = status.upper()
        
    where_sql = " AND ".join(where_parts)

    # 1. Items
    items_sql = text(f"""
        SELECT run_id, started_at, finished_at, skus_procesados, 
               skus_exitosos, skus_fallidos, duracion_segundos, status, triggered_by
        FROM ss_ml_run
        WHERE {where_sql}
        ORDER BY started_at DESC
        LIMIT :limit OFFSET :offset
    """)
    res = await db.execute(items_sql, params)
    items = res.mappings().all()

    # 2. Total para paginación
    total_sql = text(f"SELECT COUNT(*) FROM ss_ml_run WHERE {where_sql}")
    total_res = await db.execute(total_sql, params)
    total = total_res.scalar() or 0

    # 3. Stats para KPIs
    stats_sql = text("""
        SELECT 
            COUNT(*) as total_runs,
            SUM(CASE WHEN status='SUCCESS' THEN 1 ELSE 0 END) as successful_runs,
            SUM(skus_procesados) as total_skus,
            AVG(duracion_segundos) as avg_duration
        FROM ss_ml_run
    """)
    stats_res = await db.execute(stats_sql)
    stats = stats_res.mappings().first()

    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": {
            "total_runs": int(stats["total_runs"] or 0),
            "successful_runs": int(stats["successful_runs"] or 0),
            "total_skus": int(stats["total_skus"] or 0),
            "avg_duration": round(float(stats["avg_duration"] or 0), 2)
        }
    }

@router.get("/models")
async def get_ml_models(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Lista de modelos registrados por SKU."""
    sql = text("""
        SELECT sku, modelo_actual, modelo_anterior, fecha_seleccion, 
               run_id_seleccion, rmse, mae, score_composite
        FROM ss_ml_model_registry
        ORDER BY fecha_seleccion DESC
        LIMIT :limit
    """)
    res = await db.execute(sql, {"limit": limit})
    return {"items": res.mappings().all()}

@router.get("/sku/{sku}")
async def get_ml_sku_detail(
    sku: str,
    db: AsyncSession = Depends(get_db),
):
    """Detalle ML por SKU: snapshot + eventos."""
    # Features (v_ml_sku_snapshot)
    snap_res = await db.execute(
        text("SELECT * FROM v_ml_sku_snapshot WHERE sku = :sku"),
        {"sku": sku}
    )
    snap = snap_res.mappings().first()

    if not snap:
        raise HTTPException(status_code=404, detail="SKU no encontrado en vistas ML")

    # Eventos (v_ml_eventos_50)
    eventos_res = await db.execute(
        text("""
            SELECT SKU, Fecha, FAC, ClienteNombre, Qty, UnitPrice_USD, Revenue_USD
            FROM v_ml_eventos_50
            WHERE SKU = :sku
            ORDER BY Fecha DESC
            LIMIT 50
        """),
        {"sku": sku}
    )
    eventos = eventos_res.mappings().all()

    return {
        "sku": sku,
        "features": snap,
        "eventos": eventos
    }

@router.post("/suggestions/sync")
async def sync_ml_suggestions(
    payload: dict = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Sincroniza las sugerencias de la última corrida de ML con los parámetros de producción.
    Payload: { "run_id": "...", "sku": "..." }
    Si no se envía run_id, toma la última corrida exitosa.
    """
    payload = payload or {}
    run_id = payload.get("run_id")
    sku = payload.get("sku")

    if not run_id:
        # Buscar la última corrida exitosa o parcial
        res = await db.execute(
            text("SELECT run_id FROM ss_ml_run WHERE status IN ('SUCCESS', 'PARTIAL') ORDER BY started_at DESC LIMIT 1")
        )
        row = res.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="No se encontró ninguna corrida ML válida para sincronizar")
        run_id = row[0]

    where_parts = ["s.run_id = :run_id"]
    params = {"run_id": run_id}
    
    if sku:
        where_parts.append("s.sku = :sku")
        params["sku"] = sku

    where_sql = " AND ".join(where_parts)

    # Actualizar parametros_sku con los valores de policy_max (S) de ss_ml_suggestions
    # Solo actualizamos si el estado es PENDIENTE (o si el usuario lo decide, por ahora todos los del run)
    sql = text(f"""
        UPDATE parametros_sku p
        JOIN ss_ml_suggestions s ON s.sku = p.sku
        SET p.stock_min = s.policy_min,
            p.stock_objetivo = s.policy_max,
            p.review_updated_at = NOW(),
            p.modelo_recomendado = s.modelo_seleccionado
        WHERE {where_sql}
    """)
    
    res = await db.execute(sql, params)
    await db.commit()

    return {
        "ok": True,
        "run_id": run_id,
        "updated_count": res.rowcount,
        "message": f"Se sincronizaron {res.rowcount} sugerencias de la corrida {run_id}"
    }
