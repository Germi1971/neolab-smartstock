# backend/routers/api.py

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.db.database import get_db

router = APIRouter(prefix="/api", tags=["api"])


# =========================================================
# Helpers
# =========================================================

def _norm_bool(v: str | None) -> bool | None:
    if v is None:
        return None
    s = str(v).strip().lower()
    if s in ("true", "1", "si", "sí", "yes", "y"):
        return True
    if s in ("false", "0", "no", "n"):
        return False
    return None


def _norm_todos(v: str | None) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    if not s:
        return None
    if s.upper() == "TODOS":
        return None
    return s


def _safe_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except Exception:
        return default


# =========================================================
# STOCK
# Frontend llama: /api/stock?page=1&page_size=25&sku=...
# =========================================================

@router.get("/stock")
async def api_stock(
    page: int = 1,
    page_size: int = 25,

    # filtros (según UI)
    sku: str | None = Query(default=None),
    descripcion: str | None = Query(default=None),
    estado: str | None = Query(default=None),        # "Todos" -> ignorar
    stock_bajo: str | None = Query(default=None),    # true/false/Todos

    # sorting
    sort_by: str | None = Query(default=None),
    sort_order: str | None = Query(default=None),

    db: AsyncSession = Depends(get_db),
):
    page = max(1, page)
    page_size = min(max(1, page_size), 500)
    offset = (page - 1) * page_size

    where = ["COALESCE(p.activo,1)=1"]
    params: dict[str, Any] = {"limit": page_size, "offset": offset}

    if sku:
        where.append("p.sku LIKE :sku")
        params["sku"] = f"%{sku}%"

    if descripcion:
        where.append("""
            COALESCE(NULLIF(tp.`Item Description`,''), NULLIF(tp.`Descripcion_Completa`,''), '') LIKE :descripcion
        """)
        params["descripcion"] = f"%{descripcion}%"

    est = _norm_todos(estado)
    if est:
        where.append("COALESCE(vs.estado,'OK') = :estado")
        params["estado"] = est

    sb = _norm_bool(stock_bajo)
    if sb is True:
        where.append("COALESCE(vs.estado,'OK') IN ('QUIEBRE','BAJO')")

    where_sql = " WHERE " + " AND ".join(where)

    # Whitelist sort_by (los keys que usa tu DataTable)
    sort_map = {
        "sku": "p.sku",
        "descripcion": "descripcion",
        "stock_posicion": "stock_posicion",
        "stock_objetivo": "stock_objetivo",
        "stock_seguridad": "stock_seguridad",
        "punto_reorden": "punto_reorden",
        "qty_sugerida": "qty_sugerida",
        "moq": "moq",
        "activo": "activo",
        "updated_at": "updated_at",
        "estado": "estado",

        # compat (por si alguna vista vieja usa estos nombres)
        "stock_pos": "stock_posicion",
        "stock_obj": "stock_objetivo",
        "stock_seg": "stock_seguridad",
        "pto_reorden": "punto_reorden",
        "actualizado": "updated_at",
    }
    sort_col = sort_map.get((sort_by or "").lower(), "p.sku")
    sort_dir = "DESC" if (sort_order or "").lower() == "desc" else "ASC"

    # TOTAL
    total_sql = text(f"""
        SELECT COUNT(*) AS total
        FROM parametros_sku p
        LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(p.sku)
        LEFT JOIN v_stock_semaforo_ui vs ON vs.sku = p.sku
        LEFT JOIN v_stock_estado se ON UPPER(TRIM(se.SKU)) = UPPER(TRIM(p.sku))
        {where_sql}
    """)

    # ITEMS
    # - devolvemos campos "nuevos" (frontend) + campos "compat"
    # - NO existe p.producto, lo removemos
    items_sql = text(f"""
        SELECT
          p.sku AS sku,

          COALESCE(
            NULLIF(tp.`Item Description`, ''),
            NULLIF(tp.`Descripcion_Completa`, ''),
            p.sku
          ) AS descripcion,

          /* STOCK base */
          CAST(COALESCE(se.Stock_Fisico_Libre, 0) AS DECIMAL(18,2)) AS stock_fisico,
          CAST(COALESCE(se.Impo_Libre, 0) AS DECIMAL(18,2))        AS impo_libre,
          CAST(COALESCE(se.Reservado_Total, 0) AS DECIMAL(18,2))   AS reservado,

          /* Campos que el frontend espera */
          CAST(COALESCE(se.Stock_Posicion_Libre, 0) AS DECIMAL(18,2)) AS stock_posicion,
          CAST(COALESCE(p.stock_objetivo, 0) AS DECIMAL(18,2))        AS stock_objetivo,
          CAST(COALESCE(p.stock_min, 0) AS DECIMAL(18,2))             AS stock_seguridad,

          /* Hoy no tenés una columna real de "punto_reorden" en parametros_sku.
             Dejo por defecto stock_min para que no quede NULL; más adelante lo calculamos bien
             (ej: ROP = SS + demanda_en_LT). */
          CAST(COALESCE(p.stock_min, 0) AS DECIMAL(18,2))             AS punto_reorden,

          CAST(COALESCE(p.moq, 0) AS DECIMAL(18,2))                   AS moq,
          COALESCE(p.multiplo_compra, 1)                              AS multiplo_compra,
          COALESCE(p.tipo_demanda, '')                                AS tipo_demanda,
          COALESCE(p.lead_time_dias, 0)                               AS lead_time_dias,
          COALESCE(p.z_servicio, 0)                                   AS z_servicio,
          COALESCE(p.activo, 1)                                       AS activo,

          COALESCE(vs.estado, 'OK')                                   AS estado,

          COALESCE(se.UltimoRegistro, DATE(p.review_updated_at))      AS updated_at,

          /* qty sugerida (si existe la vista de sugerencias) */
          CAST(COALESCE(sc.qty_recomendada, 0) AS DECIMAL(18,2))       AS qty_sugerida,

          /* compat (por si alguna parte vieja del front usa estos nombres) */
          CAST(COALESCE(se.Stock_Posicion_Libre, 0) AS DECIMAL(18,2))  AS stock_pos,
          CAST(COALESCE(p.stock_objetivo, 0) AS DECIMAL(18,2))         AS stock_obj,
          CAST(COALESCE(p.stock_min, 0) AS DECIMAL(18,2))              AS stock_seg,
          CAST(COALESCE(p.stock_min, 0) AS DECIMAL(18,2))              AS pto_reorden,
          COALESCE(se.UltimoRegistro, DATE(p.review_updated_at))       AS actualizado,

          /* extras */
          tp.`Marca`        AS marca,
          tp.`Category`     AS category,
          tp.`Sub-Category` AS sub_category

        FROM parametros_sku p
        LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(p.sku)
        LEFT JOIN v_stock_semaforo_ui vs ON vs.sku = p.sku
        LEFT JOIN v_stock_estado se ON UPPER(TRIM(se.SKU)) = UPPER(TRIM(p.sku))

        /* si existe v_sugerencias_compra, la usamos para qty_sugerida */
        LEFT JOIN v_sugerencias_compra sc ON sc.sku = p.sku

        {where_sql}
        ORDER BY {sort_col} {sort_dir}
        LIMIT :limit OFFSET :offset
    """)

    total_res = await db.execute(total_sql, params)
    total_row = total_res.mappings().first()
    total = _safe_int(total_row["total"] if total_row else 0, 0)

    items_res = await db.execute(items_sql, params)
    items = items_res.mappings().all()

    # STATS KPIs (Fixed)
    stats_sql = text(f"""
        SELECT 
            COUNT(*) as total_sugerencias,
            SUM(CASE WHEN COALESCE(ml.estado, CASE WHEN COALESCE(sc.aprobado,0)=1 THEN 'APROBADO' ELSE 'PENDIENTE' END) = 'PENDIENTE' THEN 1 ELSE 0 END) as pendientes,
            SUM(CASE WHEN COALESCE(ml.estado, CASE WHEN COALESCE(sc.aprobado,0)=1 THEN 'APROBADO' ELSE 'PENDIENTE' END) = 'APROBADO' THEN 1 ELSE 0 END) as aprobadas,
            SUM(CAST(ROUND(COALESCE(sc.qty_recomendada,0)) AS SIGNED)) as total_qty_sugerida
        FROM v_sugerencias_compra sc
        LEFT JOIN v_stock_estado se ON UPPER(TRIM(se.SKU)) = UPPER(TRIM(sc.sku))
        LEFT JOIN parametros_sku p ON p.sku = sc.sku
        LEFT JOIN (
            SELECT t1.sku, t1.policy_max, t1.modelo_seleccionado, t1.estado
            FROM ss_ml_suggestions t1
            INNER JOIN (
                SELECT sku, MAX(updated_at) as max_at
                FROM ss_ml_suggestions
                GROUP BY sku
            ) t2 ON t1.sku = t2.sku AND t1.updated_at = t2.max_at
        ) ml ON ml.sku = sc.sku
        {where_sql}
        AND (
          COALESCE(se.Stock_Posicion_Libre, 0) > 0
          OR (COALESCE(ml.policy_max, 0) > 0 AND COALESCE(ml.modelo_seleccionado, '') != 'SIN_DATOS')
        )
    """)
    stats_res = await db.execute(stats_sql, params)
    stats_row = stats_res.mappings().first()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "items": items,
        "stats": {
            "total_sugerencias": int(stats_row["total_sugerencias"] or 0),
            "pendientes": int(stats_row["pendientes"] or 0),
            "aprobadas": int(stats_row["aprobadas"] or 0),
            "total_qty_sugerida": int(stats_row["total_qty_sugerida"] or 0)
        }
    }


# =========================================================
# SKU DETAIL (Modal)
# Frontend llama: /api/sku/{sku}/detail
# =========================================================

@router.get("/sku/{sku}/detail")
async def api_sku_detail(
    sku: str,
    db: AsyncSession = Depends(get_db),
):
    # 1) stock (1 fila)
    stock_sql = text("""
      SELECT
        p.sku AS sku,
        COALESCE(
          NULLIF(tp.`Item Description`, ''),
          NULLIF(tp.`Descripcion_Completa`, ''),
          p.sku
        ) AS descripcion,
        CAST(COALESCE(se.Stock_Fisico_Libre, 0) AS DECIMAL(18,2)) AS stock_fisico,
        CAST(COALESCE(se.Impo_Libre, 0) AS DECIMAL(18,2))        AS impo_libre,
        CAST(COALESCE(se.Reservado_Total, 0) AS DECIMAL(18,2))   AS reservado,
        CAST(COALESCE(se.Stock_Posicion_Libre, 0) AS DECIMAL(18,2)) AS stock_posicion,
        COALESCE(vs.estado,'OK') AS estado,
        COALESCE(se.UltimoRegistro, DATE(p.review_updated_at)) AS updated_at,
        tp.`Marca` AS marca,
        tp.`Category` AS category,
        tp.`Sub-Category` AS sub_category
      FROM parametros_sku p
      LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(p.sku)
      LEFT JOIN v_stock_estado se ON UPPER(TRIM(se.SKU)) = UPPER(TRIM(p.sku))
      LEFT JOIN v_stock_semaforo_ui vs ON vs.sku = p.sku
      WHERE p.sku = :sku
      LIMIT 1
    """)
    stock_res = await db.execute(stock_sql, {"sku": sku})
    stock = stock_res.mappings().first()

    if not stock:
        raise HTTPException(status_code=404, detail=f"SKU no encontrado: {sku}")

    # 2) parametros
    params_sql = text("""
      SELECT
        sku,
        COALESCE(stock_objetivo,0) AS stock_objetivo,
        COALESCE(stock_min,0) AS stock_seguridad,
        COALESCE(stock_min,0) AS punto_reorden,
        COALESCE(moq,0) AS moq,
        COALESCE(multiplo_compra,1) AS multiplo_compra,
        COALESCE(tipo_demanda,'') AS tipo_demanda,
        COALESCE(lead_time_dias,0) AS lead_time_dias,
        COALESCE(z_servicio,0) AS z_servicio,
        COALESCE(activo,1) AS activo,
        DATE(review_updated_at) AS updated_at
      FROM parametros_sku
      WHERE sku = :sku
      LIMIT 1
    """)
    params_res = await db.execute(params_sql, {"sku": sku})
    parametros = params_res.mappings().first()

    # 3) sugerencia compra (si existe)
    sug_sql = text("""
      SELECT
        sku,
        producto,
        riesgo,
        qty_recomendada,
        costo_unit,
        impacto_usd,
        aprobado,
        fecha_aprobacion
      FROM v_sugerencias_compra
      WHERE sku = :sku
      LIMIT 1
    """)
    sug = None
    try:
        sug_res = await db.execute(sug_sql, {"sku": sku})
        sug = sug_res.mappings().first()
    except Exception:
        sug = None

    return {
        "sku": stock["sku"],
        "descripcion": stock["descripcion"],
        "stock": stock,
        "parametros": parametros,
        "sugerencia_compra": sug,
    }


# =========================================================
# PARAMETERS (list)
# Frontend: /api/parameters?page=1&page_size=25
# =========================================================

@router.get("/parameters")
async def api_parameters(
    page: int = 1,
    page_size: int = 25,
    sku: str | None = Query(default=None),
    descripcion: str | None = Query(default=None),
    activo: str | None = Query(default=None),  # Todos/Activos/Inactivos
    sort_by: str | None = Query(default=None),
    sort_order: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    page = max(1, page)
    page_size = min(max(1, page_size), 500)
    offset = (page - 1) * page_size

    where = ["1=1"]
    params: dict[str, Any] = {"limit": page_size, "offset": offset}

    if sku:
        where.append("p.sku LIKE :sku")
        params["sku"] = f"%{sku}%"

    if descripcion:
        where.append("""
          COALESCE(NULLIF(tp.`Item Description`,''), NULLIF(tp.`Descripcion_Completa`,''), '') LIKE :descripcion
        """)
        params["descripcion"] = f"%{descripcion}%"

    act = _norm_todos(activo)
    if act:
        if act.strip().lower() in ("activos", "activo", "1", "true"):
            where.append("COALESCE(p.activo,1)=1")
        elif act.strip().lower() in ("inactivos", "inactivo", "0", "false"):
            where.append("COALESCE(p.activo,1)=0")

    where_sql = " WHERE " + " AND ".join(where)

    sort_map = {
        "sku": "p.sku",
        "descripcion": "descripcion",
        "stock_objetivo": "stock_objetivo",
        "stock_seguridad": "stock_seguridad",
        "punto_reorden": "punto_reorden",
        "moq": "moq",
        "multiplo_compra": "multiplo_compra",
        "activo": "activo",
        "updated_at": "updated_at",
    }
    sort_col = sort_map.get((sort_by or "").lower(), "p.sku")
    sort_dir = "DESC" if (sort_order or "").lower() == "desc" else "ASC"

    total_sql = text(f"""
      SELECT COUNT(*) AS total
      FROM parametros_sku p
      LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(p.sku)
      {where_sql}
    """)

    items_sql = text(f"""
      SELECT
        p.sku AS sku,
        COALESCE(NULLIF(tp.`Item Description`,''), NULLIF(tp.`Descripcion_Completa`,''), p.sku) AS descripcion,

        CAST(COALESCE(p.stock_objetivo,0) AS DECIMAL(18,2)) AS stock_objetivo,
        CAST(COALESCE(p.stock_min,0) AS DECIMAL(18,2))      AS stock_seguridad,
        CAST(COALESCE(p.stock_min,0) AS DECIMAL(18,2))      AS punto_reorden,

        CAST(COALESCE(p.moq,0) AS DECIMAL(18,2))            AS moq,
        COALESCE(p.multiplo_compra,1)                      AS multiplo_compra,
        COALESCE(p.activo,1)                               AS activo,
        COALESCE(DATE(p.review_updated_at), NULL)          AS updated_at
      FROM parametros_sku p
      LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(p.sku)
      {where_sql}
      ORDER BY {sort_col} {sort_dir}
      LIMIT :limit OFFSET :offset
    """)

    total_res = await db.execute(total_sql, params)
    total_row = total_res.mappings().first()
    total = _safe_int(total_row["total"] if total_row else 0, 0)

    items_res = await db.execute(items_sql, params)
    items = items_res.mappings().all()

    # STATS KPIs (Fixed)
    stats_sql = text(f"""
        SELECT 
            COUNT(*) as total_sugerencias,
            SUM(CASE WHEN COALESCE(ml.estado, CASE WHEN COALESCE(sc.aprobado,0)=1 THEN 'APROBADO' ELSE 'PENDIENTE' END) = 'PENDIENTE' THEN 1 ELSE 0 END) as pendientes,
            SUM(CASE WHEN COALESCE(ml.estado, CASE WHEN COALESCE(sc.aprobado,0)=1 THEN 'APROBADO' ELSE 'PENDIENTE' END) = 'APROBADO' THEN 1 ELSE 0 END) as aprobadas,
            SUM(CAST(ROUND(COALESCE(sc.qty_recomendada,0)) AS SIGNED)) as total_qty_sugerida
        FROM v_sugerencias_compra sc
        LEFT JOIN v_stock_estado se ON UPPER(TRIM(se.SKU)) = UPPER(TRIM(sc.sku))
        LEFT JOIN parametros_sku p ON p.sku = sc.sku
        LEFT JOIN (
            SELECT t1.sku, t1.policy_max, t1.modelo_seleccionado, t1.estado
            FROM ss_ml_suggestions t1
            INNER JOIN (
                SELECT sku, MAX(updated_at) as max_at
                FROM ss_ml_suggestions
                GROUP BY sku
            ) t2 ON t1.sku = t2.sku AND t1.updated_at = t2.max_at
        ) ml ON ml.sku = sc.sku
        {where_sql}
        AND (
          COALESCE(se.Stock_Posicion_Libre, 0) > 0
          OR (COALESCE(ml.policy_max, 0) > 0 AND COALESCE(ml.modelo_seleccionado, '') != 'SIN_DATOS')
        )
    """)
    stats_res = await db.execute(stats_sql, params)
    stats_row = stats_res.mappings().first()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "items": items,
        "stats": {
            "total_sugerencias": int(stats_row["total_sugerencias"] or 0),
            "pendientes": int(stats_row["pendientes"] or 0),
            "aprobadas": int(stats_row["aprobadas"] or 0),
            "total_qty_sugerida": int(stats_row["total_qty_sugerida"] or 0)
        }
    }


# =========================================================
# PARAMETERS (get one)
# Frontend: /api/parameters/{sku}
# =========================================================

@router.get("/parameters/{sku}")
async def api_get_parameter(
    sku: str,
    db: AsyncSession = Depends(get_db),
):
    sql = text("""
      SELECT
        p.sku AS sku,
        COALESCE(NULLIF(tp.`Item Description`,''), NULLIF(tp.`Descripcion_Completa`,''), p.sku) AS descripcion,
        CAST(COALESCE(p.stock_objetivo,0) AS DECIMAL(18,2)) AS stock_objetivo,
        CAST(COALESCE(p.stock_min,0) AS DECIMAL(18,2))      AS stock_seguridad,
        CAST(COALESCE(p.stock_min,0) AS DECIMAL(18,2))      AS punto_reorden,
        CAST(COALESCE(p.moq,0) AS DECIMAL(18,2))            AS moq,
        COALESCE(p.multiplo_compra,1)                      AS multiplo_compra,
        COALESCE(p.tipo_demanda,'')                        AS tipo_demanda,
        COALESCE(p.lead_time_dias,0)                       AS lead_time_dias,
        COALESCE(p.z_servicio,0)                           AS z_servicio,
        COALESCE(p.activo,1)                               AS activo,
        DATE(p.review_updated_at)                          AS updated_at
      FROM parametros_sku p
      LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(p.sku)
      WHERE p.sku = :sku
      LIMIT 1
    """)
    res = await db.execute(sql, {"sku": sku})
    row = res.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"SKU no encontrado: {sku}")
    return row


# =========================================================
# PARAMETERS (update one)
# Frontend: PUT /api/parameters/{sku}
# =========================================================

@router.put("/parameters/{sku}")
async def api_update_parameter(
    sku: str,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    # Permitimos actualizar solo algunos campos
    allowed = {
        "stock_objetivo",
        "stock_seguridad",
        "punto_reorden",
        "moq",
        "multiplo_compra",
        "activo",
        "tipo_demanda",
        "lead_time_dias",
        "z_servicio",
    }
    data = {k: v for k, v in payload.items() if k in allowed}

    # Map: frontend -> columnas reales
    # (en DB hoy: stock_min; no existe stock_seguridad ni punto_reorden)
    if "stock_seguridad" in data:
        data["stock_min"] = data.pop("stock_seguridad")

    # punto_reorden hoy no existe como columna: lo ignoramos por ahora
    if "punto_reorden" in data:
        data.pop("punto_reorden", None)

    if not data:
        raise HTTPException(status_code=400, detail="No hay campos válidos para actualizar")

    set_sql = ", ".join([f"{k} = :{k}" for k in data.keys()])
    data["sku"] = sku

    sql = text(f"""
      UPDATE parametros_sku
      SET {set_sql},
          review_updated_at = NOW()
      WHERE sku = :sku
    """)
    await db.execute(sql, data)

    # devolvemos el registro actualizado
    return await api_get_parameter(sku, db)


# =========================================================
# PARAMETERS (bulk update)
# Frontend: PUT /api/parameters/bulk
# =========================================================

@router.put("/parameters/bulk")
async def api_bulk_update_parameters(
    payload: list[dict[str, Any]],
    db: AsyncSession = Depends(get_db),
):
    updated = 0
    for row in payload:
        sku = row.get("sku")
        if not sku:
            continue
        try:
            await api_update_parameter(sku, row, db)
            updated += 1
        except Exception:
            continue

    # STATS para KPIs del frontend (Compras)
    stats_sql = text("""
        SELECT 
            COUNT(*) as total_sugerencias,
            SUM(CASE WHEN COALESCE(sc.aprobado, 0) = 0 THEN 1 ELSE 0 END) as pendientes,
            SUM(CASE WHEN COALESCE(sc.aprobado, 0) = 1 THEN 1 ELSE 0 END) as aprobadas,
            SUM(COALESCE(sc.qty_recomendada, 0)) as total_qty_sugerida
        FROM v_sugerencias_compra sc
    """)
    stats_res = await db.execute(stats_sql)
    stats_row = stats_res.mappings().first()

    return {
        "ok": True,
        "updated_count": updated,
        "message": f"Se actualizaron {updated} registros correctamente"
    }

@router.get("/purchases/suggestions")
async def api_purchase_suggestions(
    page: int = 1,
    page_size: int = 25,
    sku: str | None = Query(default=None),
    estado: str | None = Query(default=None),   # PENDIENTE/APROBADO/...
    modelo: str | None = Query(default=None),   # opcional
    sort_by: str | None = Query(default=None),
    sort_order: str | None = Query(default='asc'),
    order: str | None = Query(default=None), # Compatibilidad
    db: AsyncSession = Depends(get_db),
):
    # Unificar sort_order
    final_sort_order = sort_order
    if order and order.lower() == 'desc':
        final_sort_order = 'desc'
    
    page = max(1, page)
    page_size = min(max(1, page_size), 500)
    offset = (page - 1) * page_size
    offset = (page - 1) * page_size

    where = ["1=1"]
    params: dict[str, Any] = {"limit": page_size, "offset": offset}

    if sku:
        where.append("sc.sku LIKE :sku")
        params["sku"] = f"%{sku}%"

    # v_sugerencias_compra usa "aprobado" (int) y "riesgo"
    # Mapeamos "estado" UI:
    # - APROBADO => aprobado=1
    # - PENDIENTE => aprobado=0
    est = _norm_todos(estado)
    if est:
        est_l = est.strip().upper()
        if est_l == "APROBADO":
            where.append("COALESCE(sc.aprobado,0)=1")
        elif est_l == "PENDIENTE":
            where.append("COALESCE(sc.aprobado,0)=0")

    if modelo and modelo.strip():
        # Filtramos por el modelo que se muestra (ml o p)
        # Como usamos un COALESCE en el SELECT, lo ideal seria filtrar sobre eso,
        # pero para WHERE simple, asumimos que ml.modelo_seleccionado es el principal si existe.
        # Si filtramos por 'MONTE_CARLO', buscamos en ml.
        m_val = modelo.strip()
        where.append(f"COALESCE(ml.modelo_seleccionado, p.modelo_recomendado, '') = '{m_val}'")

    where_sql = " WHERE " + " AND ".join(where)

    # Sorting logic
    order_clause = "sc.impacto_usd DESC, sc.qty_recomendada DESC, sc.sku"
    if sort_by:
        sort_map = {
            "sku": "sc.sku",
            "descripcion": "descripcion", # Alias
            "stock_posicion": "stock_posicion", # Alias
            "stock_objetivo": "stock_objetivo", # Alias
            "stock_objetivo_calculado": "stock_objetivo_calculado", # Alias
            "qty_sugerida": "qty_sugerida", # Alias
            "estado": "estado", # Alias
            "modelo_seleccionado": "modelo_seleccionado", # Alias
            "updated_at": "updated_at" # Alias
        }
        col = sort_map.get(sort_by)
        if col:
            direction = "DESC" if final_sort_order and final_sort_order.lower() == "desc" else "ASC"
            order_clause = f"{col} {direction}"

    total_sql = text(f"""
        SELECT COUNT(*) AS total 
        FROM v_sugerencias_compra sc
        LEFT JOIN v_stock_estado se ON UPPER(TRIM(se.SKU)) = UPPER(TRIM(sc.sku))
        LEFT JOIN parametros_sku p ON p.sku = sc.sku
        LEFT JOIN (
            SELECT t1.sku, t1.policy_max, t1.modelo_seleccionado, t1.estado
            FROM ss_ml_suggestions t1
            INNER JOIN (
                SELECT sku, MAX(updated_at) as max_at
                FROM ss_ml_suggestions
                GROUP BY sku
            ) t2 ON t1.sku = t2.sku AND t1.updated_at = t2.max_at
        ) ml ON ml.sku = sc.sku
        {where_sql}
        AND (
          COALESCE(se.Stock_Posicion_Libre, 0) > 0
          OR (COALESCE(ml.policy_max, 0) > 0 AND COALESCE(ml.modelo_seleccionado, '') != 'SIN_DATOS')
        )
    """)


    items_sql = text(f"""
      SELECT
        sc.sku AS sku,
        COALESCE(NULLIF(tp.`Item Description`,''), NULLIF(tp.`Descripcion_Completa`,''), sc.producto, sc.sku) AS descripcion,

        CAST(COALESCE(se.Stock_Posicion_Libre,0) AS SIGNED) AS stock_posicion,
        CAST(COALESCE(p.stock_objetivo,0) AS SIGNED)        AS stock_objetivo,
        CAST(ROUND(COALESCE(sc.stock_objetivo_capeado,0)) AS SIGNED) AS stock_objetivo_calculado,

        CAST(ROUND(COALESCE(sc.qty_recomendada,0)) AS SIGNED)       AS qty_sugerida,

        COALESCE(ml.estado, CASE WHEN COALESCE(sc.aprobado,0)=1 THEN 'APROBADO' ELSE 'PENDIENTE' END) AS estado,

        /* Priorizamos modelo ML */
        COALESCE(ml.modelo_seleccionado, p.modelo_recomendado, '') AS modelo_seleccionado,

        COALESCE(DATE(sc.fecha_aprobacion), DATE(p.review_updated_at)) AS updated_at
      FROM v_sugerencias_compra sc
      LEFT JOIN parametros_sku p ON p.sku = sc.sku
      LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(sc.sku)
      LEFT JOIN v_stock_estado se ON UPPER(TRIM(se.SKU)) = UPPER(TRIM(sc.sku))
      /* JOIN con la última sugerencia ML para filtrar */
      LEFT JOIN (
          SELECT t1.sku, t1.policy_max, t1.modelo_seleccionado, t1.estado
          FROM ss_ml_suggestions t1
          INNER JOIN (
              SELECT sku, MAX(updated_at) as max_at
              FROM ss_ml_suggestions
              GROUP BY sku
          ) t2 ON t1.sku = t2.sku AND t1.updated_at = t2.max_at
      ) ml ON ml.sku = sc.sku

      {where_sql}
      AND (
        COALESCE(se.Stock_Posicion_Libre, 0) > 0
        OR (COALESCE(ml.policy_max, 0) > 0 AND COALESCE(ml.modelo_seleccionado, '') != 'SIN_DATOS')
      )
      ORDER BY {order_clause}
      LIMIT :limit OFFSET :offset
    """)

    total_res = await db.execute(total_sql, params)
    total_row = total_res.mappings().first()
    total = _safe_int(total_row["total"] if total_row else 0, 0)

    items_res = await db.execute(items_sql, params)
    items = items_res.mappings().all()

    # STATS KPIs (Fixed)
    stats_sql = text(f"""
        SELECT 
            COUNT(*) as total_sugerencias,
            SUM(CASE WHEN COALESCE(ml.estado, CASE WHEN COALESCE(sc.aprobado,0)=1 THEN 'APROBADO' ELSE 'PENDIENTE' END) = 'PENDIENTE' THEN 1 ELSE 0 END) as pendientes,
            SUM(CASE WHEN COALESCE(ml.estado, CASE WHEN COALESCE(sc.aprobado,0)=1 THEN 'APROBADO' ELSE 'PENDIENTE' END) = 'APROBADO' THEN 1 ELSE 0 END) as aprobadas,
            SUM(CAST(ROUND(COALESCE(sc.qty_recomendada,0)) AS SIGNED)) as total_qty_sugerida
        FROM v_sugerencias_compra sc
        LEFT JOIN v_stock_estado se ON UPPER(TRIM(se.SKU)) = UPPER(TRIM(sc.sku))
        LEFT JOIN parametros_sku p ON p.sku = sc.sku
        LEFT JOIN (
            SELECT t1.sku, t1.policy_max, t1.modelo_seleccionado, t1.estado
            FROM ss_ml_suggestions t1
            INNER JOIN (
                SELECT sku, MAX(updated_at) as max_at
                FROM ss_ml_suggestions
                GROUP BY sku
            ) t2 ON t1.sku = t2.sku AND t1.updated_at = t2.max_at
        ) ml ON ml.sku = sc.sku
        {where_sql}
        AND (
          COALESCE(se.Stock_Posicion_Libre, 0) > 0
          OR (COALESCE(ml.policy_max, 0) > 0 AND COALESCE(ml.modelo_seleccionado, '') != 'SIN_DATOS')
        )
    """)
    stats_res = await db.execute(stats_sql, params)
    stats_row = stats_res.mappings().first()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "items": items,
        "stats": {
            "total_sugerencias": int(stats_row["total_sugerencias"] or 0),
            "pendientes": int(stats_row["pendientes"] or 0),
            "aprobadas": int(stats_row["aprobadas"] or 0),
            "total_qty_sugerida": int(stats_row["total_qty_sugerida"] or 0)
        }
    }


@router.get("/purchases/suggestions/{sku}")
async def api_purchase_suggestion_by_sku(
    sku: str,
    db: AsyncSession = Depends(get_db),
):
    sql = text("""
      SELECT
        sc.sku AS sku,
        COALESCE(NULLIF(tp.`Item Description`,''), NULLIF(tp.`Descripcion_Completa`,''), sc.producto, sc.sku) AS descripcion,
        CAST(ROUND(COALESCE(sc.qty_recomendada,0)) AS SIGNED) AS qty_sugerida,
        CAST(ROUND(COALESCE(sc.stock_actual,0)) AS SIGNED)    AS stock_actual,
        CAST(ROUND(COALESCE(sc.stock_objetivo,0)) AS SIGNED)  AS stock_objetivo,
        CAST(ROUND(COALESCE(sc.stock_min,0)) AS SIGNED)       AS stock_min,
        CAST(COALESCE(sc.costo_unit,0) AS DECIMAL(18,2))      AS costo_unit,
        CAST(COALESCE(sc.impacto_usd,0) AS DECIMAL(18,2))     AS impacto_usd,
        CASE WHEN COALESCE(sc.aprobado,0)=1 THEN 'APROBADO' ELSE 'PENDIENTE' END AS estado,
        sc.fecha_aprobacion AS fecha_aprobacion
      FROM v_sugerencias_compra sc
      LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(sc.sku)
      WHERE sc.sku = :sku
      LIMIT 1
    """)
    res = await db.execute(sql, {"sku": sku})
    row = res.mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail=f"Sugerencia no encontrada para: {sku}")
    return row


@router.post("/purchases/approve/{sku}")
async def api_approve_suggestion(
    sku: str,
    payload: dict[str, Any],
    db: AsyncSession = Depends(get_db),
):
    """
    Aprueba la ÚLTIMA sugerencia generada para el SKU.
    """
    # 1. Encontrar la última sugerencia (run_id más reciente)
    find_sql = text("""
        SELECT run_id 
        FROM ss_ml_suggestions 
        WHERE sku = :sku 
        ORDER BY updated_at DESC 
        LIMIT 1
    """)
    res = await db.execute(find_sql, {"sku": sku})
    row = res.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="No hay sugerencias para aprobar")
    
    run_id = row[0]

    # 2. Actualizar estado
    update_sql = text("""
        UPDATE ss_ml_suggestions
        SET estado = 'APROBADO',
            fecha_aprobacion = NOW(),
            qty_final = :qty,
            notas = :notas
        WHERE sku = :sku AND run_id = :run_id
    """)
    
    qty_final = _safe_int(payload.get("qty_final"), 0)
    notas = str(payload.get("notas", ""))

    await db.execute(update_sql, {
        "sku": sku, 
        "run_id": run_id,
        "qty": qty_final,
        "notas": notas
    })
    
    return {"ok": True, "sku": sku, "status": "APROBADO"}


@router.post("/purchases/unapprove/{sku}")
async def api_unapprove_suggestion(
    sku: str,
    db: AsyncSession = Depends(get_db),
):
    """
    Revierte la aprobación de la ÚLTIMA sugerencia.
    """
    # 1. Encontrar la última sugerencia
    find_sql = text("""
        SELECT run_id 
        FROM ss_ml_suggestions 
        WHERE sku = :sku 
        ORDER BY updated_at DESC 
        LIMIT 1
    """)
    res = await db.execute(find_sql, {"sku": sku})
    row = res.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="No hay sugerencias para revertir")
    
    run_id = row[0]

    # 2. Actualizar estado
    update_sql = text("""
        UPDATE ss_ml_suggestions
        SET estado = 'PENDIENTE',
            fecha_aprobacion = NULL,
            qty_final = NULL
        WHERE sku = :sku AND run_id = :run_id
    """)
    await db.execute(update_sql, {"sku": sku, "run_id": run_id})
    
    return {"ok": True, "sku": sku, "status": "PENDIENTE"}


@router.get("/purchases/export")
async def api_export_purchases(
    response: Response,
    sku: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    # CSV simple desde v_sugerencias_compra
    where = ["1=1"]
    params: dict[str, Any] = {}
    if sku:
        where.append("sku LIKE :sku")
        params["sku"] = f"%{sku}%"
    where_sql = " WHERE " + " AND ".join(where)

    sql = text(f"""
      SELECT
        sku,
        producto,
        riesgo,
        qty_recomendada,
        stock_actual,
        stock_min,
        stock_objetivo,
        costo_unit,
        impacto_usd,
        aprobado,
        fecha_aprobacion
      FROM v_sugerencias_compra
      {where_sql}
      ORDER BY impacto_usd DESC
      LIMIT 10000
    """)
    res = await db.execute(sql, params)
    rows = res.mappings().all()

    # build csv
    headers = [
        "sku","producto","riesgo","qty_recomendada","stock_actual","stock_min","stock_objetivo",
        "costo_unit","impacto_usd","aprobado","fecha_aprobacion"
    ]
    lines = [",".join(headers)]
    for r in rows:
        line = []
        for h in headers:
            v = r.get(h, "")
            if v is None:
                v = ""
            s = str(v).replace('"', '""')
            if "," in s or "\n" in s:
                s = f'"{s}"'
            line.append(s)
        lines.append(",".join(line))

    csv_data = "\n".join(lines)
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return csv_data


# =========================================================
# =========================================================
# END OF API
# =========================================================
