import csv
import io
from typing import Any, Dict, Optional

import pymysql
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
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
# Endpoints dashboard (compatibles con frontend neolab_smartstock)
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


# Columnas CSV: todos los parámetros de la vista que existen y aparecen en el HUD.
# Incluye: identificación, stock, objetivos, sugerencia, costos, clasificación, prioridad, auditoría.
CSV_FIELDNAMES_HUD = [
    "sku", "producto", "proveedor", "riesgo",
    "stock_actual", "impo_libre", "reservado_deposito", "impo_reservada",
    "stock_total_deposito", "impo_total", "oferta_total",
    "meses_con_venta_12m", "demanda_prom_mensual_12m", "sku_activo", "estado_operativo",
    "stock_min", "stock_objetivo_parametrico", "stock_objetivo", "stock_objetivo_modelo", "stock_objetivo_capeado",
    "cap_objetivo", "aprobado", "fecha_aprobacion", "qty_aprobada",
    "qty_recomendada_sin_cap", "qty_recomendada", "qty_final", "qty_recomendada_final",
    "costo_unit", "inventario_usd", "impacto_usd",
    "demand_target_source", "selected_service_level", "applied_caps",
    "policy_reason", "explanation", "criticidad_policy", "policy_updated_at",
    "priority_score", "priority_band", "priority_reason",
    "demand_class", "lifecycle_state", "classification_reason",
    "modelo_recomendado", "service_prob_usado", "review_updated_at",
]


@router.get("/dashboard/sugerencias/export")
def dashboard_sugerencias_export():
    """
    Exporta todas las sugerencias como CSV descargable.
    Columnas alineadas con el HUD (modal SmartStock).
    Intenta: ss2_v_purchase_suggestions_v2 (completo), luego v_sugerencias_compra.
    """
    import os
    import pymysql

    from app.main import cfg, get_conn

    # ss2_v: todos los parámetros de la vista (alineados con HUD)
    sql_ss2 = """
    SELECT sku, producto, proveedor, riesgo,
           stock_actual, impo_libre, reservado_deposito, impo_reservada,
           stock_total_deposito, impo_total, oferta_total,
           meses_con_venta_12m, demanda_prom_mensual_12m, sku_activo, estado_operativo,
           stock_min, stock_objetivo_parametrico,
           stock_objetivo_final AS stock_objetivo, stock_objetivo_modelo, stock_objetivo_capeado,
           cap_objetivo, aprobado, fecha_aprobacion, qty_aprobada,
           qty_recomendada_sin_cap, qty_recomendada, qty_final, qty_recomendada_final,
           costo_unit, impacto_usd,
           demand_target_source, selected_service_level, applied_caps,
           policy_reason, explanation, criticidad_policy, policy_updated_at,
           priority_score, priority_band, priority_reason,
           demand_class, lifecycle_state, classification_reason,
           modelo_recomendado, service_prob_usado, review_updated_at
    FROM ss2_v_purchase_suggestions_v2
    ORDER BY impacto_usd DESC;
    """
    # ss2 fallback si faltan columnas (demand_class, reservado_deposito, etc)
    sql_ss2_min = """
    SELECT sku, producto, proveedor, riesgo, stock_actual, impo_libre,
           stock_min, stock_objetivo_final AS stock_objetivo,
           qty_recomendada, qty_final,
           costo_unit, impacto_usd, modelo_recomendado, service_prob_usado, review_updated_at
    FROM ss2_v_purchase_suggestions_v2
    ORDER BY impacto_usd DESC;
    """
    sql_vista = """
    SELECT sku, producto, proveedor, riesgo, stock_actual, impo_libre,
           stock_min, stock_objetivo, qty_recomendada, qty_final,
           costo_unit, impacto_usd, modelo_recomendado, service_prob_usado, review_updated_at
    FROM v_sugerencias_compra
    ORDER BY impacto_usd DESC;
    """

    dbs_to_try = [cfg.database]
    ss2_db = os.getenv("SS2_DB", "").strip() or os.getenv("MYSQL_DB_SS2", "").strip()
    if ss2_db and ss2_db not in dbs_to_try:
        dbs_to_try.append(ss2_db)
    if cfg.database == "neobd" and "ss2_staging" not in dbs_to_try:
        dbs_to_try.append("ss2_staging")

    rows = []
    for db_name in dbs_to_try:
        try:
            conn = pymysql.connect(
                host=cfg.host,
                port=cfg.port,
                user=cfg.user,
                password=cfg.password,
                database=db_name,
                charset="utf8mb4",
                cursorclass=pymysql.cursors.DictCursor,
            )
            for sql in (sql_ss2, sql_ss2_min, sql_vista):
                try:
                    with conn.cursor() as cur:
                        cur.execute(sql)
                        rows = cur.fetchall()
                    conn.close()
                    if rows:
                        break
                except pymysql.err.OperationalError:
                    continue
            if rows:
                break
        except Exception:
            pass

    if not rows:
        rows = [{"sku": "Sin datos", "producto": "", "qty_final": 0}]

    # Agregar inventario_usd y normalizar columnas para alinear con HUD
    for r in rows:
        stock = safe_float(r.get("stock_actual"))
        costo = safe_float(r.get("costo_unit"))
        r["inventario_usd"] = round(stock * costo, 2)
        # Asegurar stock_objetivo si viene como stock_objetivo_final
        if "stock_objetivo" not in r and r.get("stock_objetivo_final") is not None:
            r["stock_objetivo"] = r["stock_objetivo_final"]
        # Rellenar columnas faltantes para CSV consistente
        str_cols = ("demand_class", "lifecycle_state", "classification_reason", "policy_reason",
                    "producto", "proveedor", "explanation", "criticidad_policy", "priority_reason",
                    "demand_target_source", "applied_caps", "priority_band")
        for k in CSV_FIELDNAMES_HUD:
            if k not in r:
                r[k] = "" if k in str_cols else 0

    fieldnames = CSV_FIELDNAMES_HUD

    output = io.StringIO()
    writer = csv.DictWriter(
        output,
        fieldnames=fieldnames,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)

    content = ("\ufeff" + output.getvalue()).encode("utf-8")
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=sugerencias_smartstock.csv"},
    )


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
