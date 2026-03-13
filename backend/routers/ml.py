from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.db.database import get_db

router = APIRouter(prefix="/ml", tags=["ml"])


@router.get("/sku/{sku}")
async def ml_sku_detail(
    sku: str,
    db: AsyncSession = Depends(get_db),
):
    snap_sql = text("SELECT * FROM v_ml_sku_snapshot WHERE sku = :sku")
    snap_res = await db.execute(snap_sql, {"sku": sku})
    snap = snap_res.mappings().first()

    if not snap:
        raise HTTPException(status_code=404, detail="SKU not found")

    eventos_sql = text("""
        SELECT SKU, Fecha, FAC, ClienteN, ClienteNombre, Qty,
               UnitPrice_USD, UnitCost_USD, Revenue_USD, Margin_USD
        FROM v_ml_eventos_50
        WHERE SKU = :sku
        ORDER BY Fecha DESC, FAC DESC
        LIMIT 50
    """)
    eventos_res = await db.execute(eventos_sql, {"sku": sku})
    eventos = eventos_res.mappings().all()

    return {"sku": sku, "features": snap, "eventos": eventos}
