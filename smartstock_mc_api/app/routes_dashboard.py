from typing import Any, Dict, Optional

import pymysql
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter()

# -----------------------------
# Helpers
# -----------------------------
def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        return int(float(x))
    except Exception:
        return default


# -----------------------------
# Modelos request
# -----------------------------
class ApproveBody(BaseModel):
    aprobado: int = Field(ge=0, le=1)
    qty_aprobada: Optional[float] = Field(default=None, ge=0)


# -----------------------------
# Endpoints esperados por BOLT
# -----------------------------

@router.get("/dashboard/sugerencias")
def dashboard_sugerencias():
    """
    Devuelve la grilla principal.
    Requiere vista: v_sugerencias_compra

    IMPORTANTE:
    - stock_actual = SOLO depósito libre (STOCK)
    - riesgo puede considerar oferta_total (stock + impo_libre) según tu vista
    - devolvemos campos extendidos para auditoría en frontend (no rompe si no se usan)
    - si la vista ya incluye estado_operativo/sku_activo, los devolvemos
    - si NO existen aún, devolvemos defaults sin romper el frontend
    """
    from app.main import cfg, get_conn  # import tardío para evitar circularidad

    # Traemos estado_operativo/sku_activo si están en la vista.
    # Si todavía no actualizaste la VIEW, estos campos se devuelven con defaults.
    sql = """
    SELECT
      sku,
      producto,
      proveedor,
      riesgo,

      stock_actual,              -- STOCK (depósito libre)
      impo_libre,                -- IMPO - STOCK

      reservado_deposito,        -- R
      impo_reservada,            -- IMPO - R
      stock_total_deposito,      -- STOCK + R
      impo_total,                -- IMPO - STOCK + IMPO - R
      oferta_total,              -- STOCK + IMPO libre (base del riesgo)

      stock_min,
      stock_objetivo,

      qty_recomendada,
      aprobado,
      qty_aprobada,
      qty_final,

      costo_unit,
      impacto_usd,

      modelo_recomendado,
      service_prob_usado,
      review_updated_at,

      /* NUEVO (si existe en la vista). Si no existe aún, la query fallará,
         por eso lo pedimos con fallback abajo (ver try/except). */
      estado_operativo,
      sku_activo
    FROM v_sugerencias_compra
    ORDER BY impacto_usd DESC;
    """

    sql_fallback = """
    SELECT
      sku,
      producto,
      proveedor,
      riesgo,

      stock_actual,
      impo_libre,

      reservado_deposito,
      impo_reservada,
      stock_total_deposito,
      impo_total,
      oferta_total,

      stock_min,
      stock_objetivo,

      qty_recomendada,
      aprobado,
      qty_aprobada,
      qty_final,

      costo_unit,
      impacto_usd,

      modelo_recomendado,
      service_prob_usado,
      review_updated_at,

      /* Defaults para no romper el frontend */
      'NORMAL' AS estado_operativo,
      1 AS sku_activo
    FROM v_sugerencias_compra
    ORDER BY impacto_usd DESC;
    """

    try:
        with get_conn(cfg) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                try:
                    cur.execute(sql)
                except pymysql.err.OperationalError as e:
                    # 1054 = Unknown column (por ejemplo, si la VIEW aún no tiene estado_operativo/sku_activo)
                    if getattr(e, "args", None) and len(e.args) > 0 and int(e.args[0]) == 1054:
                        cur.execute(sql_fallback)
                    else:
                        raise
                rows = cur.fetchall()

        # Normalizamos algunos campos numéricos para que el frontend no reciba DECIMAL como string
        # (no hace falta normalizar todos, pero estos suelen verse en UI/ordenamientos)
        for r in rows:
            r["stock_actual"] = safe_float(r.get("stock_actual"))
            r["impo_libre"] = safe_float(r.get("impo_libre"))
            r["reservado_deposito"] = safe_float(r.get("reservado_deposito"))
            r["impo_reservada"] = safe_float(r.get("impo_reservada"))
            r["stock_total_deposito"] = safe_float(r.get("stock_total_deposito"))
            r["impo_total"] = safe_float(r.get("impo_total"))
            r["oferta_total"] = safe_float(r.get("oferta_total"))
            r["stock_min"] = safe_float(r.get("stock_min"))
            r["stock_objetivo"] = safe_float(r.get("stock_objetivo"))
            r["qty_recomendada"] = safe_float(r.get("qty_recomendada"))
            r["qty_final"] = safe_float(r.get("qty_final"))
            r["costo_unit"] = safe_float(r.get("costo_unit"))
            r["impacto_usd"] = safe_float(r.get("impacto_usd"))
            r["sku_activo"] = safe_int(r.get("sku_activo"), default=1)

        return rows

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"dashboard/sugerencias error: {str(e)}")


@router.get("/ml/sku/{sku}")
def sku_detail_for_drawer(sku: str):
    """
    Devuelve un detalle 'plano' para el drawer del frontend:
    - datos de la vista v_sugerencias_compra (producto/proveedor/riesgo/stock/qty/impacto)
    - features 12m desde v_sku_review_input_v3 (demanda/sigma/p_event/eventos)
    - opcional: cache MC desde sku_mc_cache (p_stockout, qty_recomendada_mc, stock_objetivo_mc)

    Nota:
    - Aquí también intentamos leer estado_operativo/sku_activo desde la VIEW si existen.
    """
    from app.main import cfg, get_conn  # import tardío para evitar circularidad

    try:
        with get_conn(cfg) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                # Base (lo que ve el dashboard) + campos extendidos (si existen)
                cur.execute(
                    """
                    SELECT *
                    FROM v_sugerencias_compra
                    WHERE sku=%s
                    LIMIT 1;
                    """,
                    (sku,),
                )
                base = cur.fetchone()

                if not base:
                    raise HTTPException(status_code=404, detail=f"SKU not found in v_sugerencias_compra: {sku}")

                # Features 12m (para KPIs del drawer)
                cur.execute(
                    """
                    SELECT
                      demanda_prom_mensual_12m,
                      sigma_mensual_12m,
                      p_evento_mensual_12m,
                      eventos_12m
                    FROM v_sku_review_input_v3
                    WHERE sku=%s
                    LIMIT 1;
                    """,
                    (sku,),
                )
                feat = cur.fetchone() or {}

                # Cache Monte Carlo (si existe)
                cur.execute(
                    """
                    SELECT
                      mc_enabled,
                      p_stockout,
                      exp_lost_units,
                      stock_objetivo_mc,
                      qty_recomendada_mc,
                      mc_reason,
                      updated_at
                    FROM sku_mc_cache
                    WHERE sku=%s
                    LIMIT 1;
                    """,
                    (sku,),
                )
                mc = cur.fetchone() or {}

        # Normalizamos campos esperados por la UI (evita DECIMAL como string)
        out: Dict[str, Any] = dict(base)

        out["demanda_promedio_mensual"] = safe_float(feat.get("demanda_prom_mensual_12m"))
        out["sigma"] = safe_float(feat.get("sigma_mensual_12m"))
        out["p_evento"] = safe_float(feat.get("p_evento_mensual_12m"))
        out["eventos_12m"] = safe_int(feat.get("eventos_12m"))

        # Asegurar defaults si no están
        if "estado_operativo" not in out or out["estado_operativo"] is None:
            out["estado_operativo"] = "NORMAL"
        if "sku_activo" not in out or out["sku_activo"] is None:
            out["sku_activo"] = 1

        out["mc"] = {
            "mc_enabled": safe_int(mc.get("mc_enabled")),
            "p_stockout": safe_float(mc.get("p_stockout")),
            "exp_lost_units": safe_float(mc.get("exp_lost_units")),
            "stock_objetivo_mc": safe_float(mc.get("stock_objetivo_mc")),
            "qty_recomendada_mc": safe_float(mc.get("qty_recomendada_mc")),
            "mc_reason": mc.get("mc_reason"),
            "updated_at": mc.get("updated_at"),
        }

        return out

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ml/sku/{sku} error: {str(e)}")


@router.post("/sku/{sku}/approve")
def approve_sku(sku: str, body: ApproveBody):
    """
    Guarda aprobación manual en parametros_sku:
      - sugerencia_aprobada
      - qty_aprobada
      - fecha_sugerencia
    """
    from app.main import cfg, get_conn  # import tardío para evitar circularidad

    try:
        with get_conn(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE parametros_sku
                    SET sugerencia_aprobada=%s,
                        qty_aprobada=%s,
                        fecha_sugerencia=NOW()
                    WHERE sku=%s
                    """,
                    (int(body.aprobado), body.qty_aprobada, sku),
                )

        return {"ok": True, "sku": sku, "aprobado": int(body.aprobado), "qty_aprobada": body.qty_aprobada}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"approve error: {str(e)}")
