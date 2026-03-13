from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.db.database import get_db

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/stock")
async def dashboard_stock(
    q: str | None = Query(default=None, description="search sku or producto"),
    estado: str | None = Query(default=None, description="OK|QUIEBRE|SOBRESTOCK"),
    page: int = 1,
    per_page: int = 200,
    db: AsyncSession = Depends(get_db),
):
    page = max(1, page)
    per_page = min(max(1, per_page), 2000)
    offset = (page - 1) * per_page

    where = []
    params = {"limit": per_page, "offset": offset}

    if q:
        where.append("(sku LIKE :q OR producto LIKE :q)")
        params["q"] = f"%{q}%"

    if estado:
        where.append("estado = :estado")
        params["estado"] = estado

    where_sql = (" WHERE " + " AND ".join(where)) if where else ""

    total_sql = text(f"SELECT COUNT(*) AS total FROM v_stock_semaforo {where_sql}")
    items_sql = text(f"""
        SELECT
          sku,
          producto,
          stock_actual,
          stock_min,
          stock_objetivo,
          estado,
          stock_fisico,
          impo_libre,
          reservado,
          ultimo_registro
        FROM v_stock_semaforo_ui
        {where_sql}
        ORDER BY
          FIELD(estado,'QUIEBRE','OK','SOBRESTOCK'),
          (stock_objetivo - stock_actual) DESC,
          sku
        LIMIT :limit OFFSET :offset
    """)

    total_res = await db.execute(total_sql, params)
    total = int(total_res.mappings().first()["total"])

    items_res = await db.execute(items_sql, params)
    items = items_res.mappings().all()

    return {"page": page, "per_page": per_page, "total": total, "items": items}
