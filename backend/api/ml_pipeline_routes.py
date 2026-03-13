from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from datetime import datetime
import uuid

from backend.db.database import get_db
from backend.ml_engine.pipeline import MLPipeline
from backend.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/ml", tags=["ml"])


@router.post("/pipeline/run")
async def run_ml_pipeline(
    payload: dict = {},
    db: AsyncSession = Depends(get_db),
):
    """
    Ejecuta el pipeline ML.

    Payload opcional:
      { "sku": "M524-100L" }
      { "skus": ["A111", "B222"] }
    """

    started_at = datetime.utcnow()

    run_id = f"RUN-{started_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    pipeline = MLPipeline(session=db, run_id=run_id)

    # -------------------------------------------------
    # Resolver SKUs a procesar
    # -------------------------------------------------
    if "sku" in payload:
        skus = [payload["sku"]]
    elif "skus" in payload:
        skus = payload["skus"]
    else:
        res = await db.execute(
            text("SELECT sku FROM sku_parameters WHERE activo = 1")
        )
        skus = [r[0] for r in res.fetchall()]

    ok = 0
    errors = []

    logger.info(f"ML pipeline start | run_id={run_id} | skus={len(skus)}")

    # -------------------------------------------------
    # Ejecutar pipeline
    # -------------------------------------------------
    for sku in skus:
        try:
            await pipeline.process_single_sku(sku)
            ok += 1
        except Exception as e:
            logger.error(f"Pipeline error | {sku} | {e}")
            errors.append({"sku": sku, "error": str(e)})

    finished_at = datetime.utcnow()
    duration = int((finished_at - started_at).total_seconds())

    total = len(skus)
    failed = len(errors)

    if ok == total and failed == 0:
        status = "SUCCESS"
    elif ok > 0 and failed > 0:
        status = "PARTIAL"
    else:
        status = "FAILED"

    logger.info(
        f"ML pipeline end | run_id={run_id} | ok={ok} | fail={failed} | status={status}"
    )

    # -------------------------------------------------
    # 🔥 Persistir ejecución (esto destraba KPIs / runs)
    # -------------------------------------------------
    await db.execute(
        text("""
            INSERT INTO ml_runs (
                run_id,
                started_at,
                finished_at,
                skus_procesados,
                skus_exitosos,
                skus_fallidos,
                duracion_segundos,
                triggered_by,
                status
            )
            VALUES (
                :run_id,
                :started_at,
                :finished_at,
                :total,
                :ok,
                :failed,
                :duration,
                'MANUAL',
                :status
            )
        """),
        {
            "run_id": run_id,
            "started_at": started_at,
            "finished_at": finished_at,
            "total": total,
            "ok": ok,
            "failed": failed,
            "duration": duration,
            "status": status,
        }
    )

    await db.commit()

    # -------------------------------------------------
    # Response
    # -------------------------------------------------
    return {
        "ok": True,
        "run_id": run_id,
        "total": total,
        "success": ok,
        "failed": failed,
        "status": status,
        "duration_seconds": duration,
        "errors": errors[:10],
    }
