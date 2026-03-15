"""
Smart Replenishment Score (SRS) - Priorización de SKUs para reposición.

NO decide cantidad (eso es Policy Engine). Decide QUÉ comprar primero.

Fórmula:
  SRS = 0.30*stockout + 0.20*criticidad + 0.15*LT + 0.10*acceleration
        + 0.10*margen + 0.10*backlog - 0.10*overstock - 0.05*cliente
  Luego reescalado a 0-100.

Bandas: URGENTE (85-100), ALTA (70-84), MEDIA (55-69), BAJA (40-54), MUY_BAJA (<40)
"""

from __future__ import annotations

from typing import Any, Optional

# Pesos de la fórmula SRS
WEIGHT_STOCKOUT = 0.30
WEIGHT_CRITICIDAD = 0.20
WEIGHT_LEAD_TIME = 0.15
WEIGHT_ACCELERATION = 0.10
WEIGHT_MARGEN = 0.10
WEIGHT_BACKLOG = 0.10
WEIGHT_OVERSTOCK = 0.10
WEIGHT_CLIENTE = 0.05

# Bandas de prioridad
PRIORITY_BANDS = [
    (85, 100, "URGENTE"),
    (70, 84, "ALTA"),
    (55, 69, "MEDIA"),
    (40, 54, "BAJA"),
    (0, 39, "MUY_BAJA"),
]


def score_stockout(row: dict) -> float:
    """
    Riesgo de stockout. 0-100.
    Usa p_stockout_at_current_stock si existe (ss2_demand_cache).
    Fallback analítico: stock bajo vs objetivo/min.
    """
    p = row.get("p_stockout_at_current_stock") or row.get("p_stockout")
    if p is not None:
        return min(100.0, max(0.0, float(p) * 100))

    # Fallback analítico
    stock = float(row.get("stock_posicion") or row.get("oferta_total") or 0)
    stock_min = float(row.get("stock_min") or 0)
    stock_objetivo = float(row.get("stock_objetivo_final") or row.get("stock_objetivo") or 0)

    if stock <= 0:
        return 95.0
    if stock_min > 0 and stock < stock_min:
        return 85.0
    if stock_objetivo > 0 and stock < stock_objetivo * 0.5:
        return 70.0
    if stock_objetivo > 0 and stock < stock_objetivo:
        return 50.0
    return 20.0


def score_criticidad(row: dict) -> float:
    """
    Criticidad del producto. 0-100.
    CRITICO=100, ALTO=80, MEDIO=50, BAJO=20.
    """
    c = (row.get("criticidad") or "BAJO").upper().strip()
    return {
        "CRITICO": 100.0,
        "ALTO": 80.0,
        "MEDIO": 50.0,
        "BAJO": 20.0,
    }.get(c, 20.0)


def score_lead_time(row: dict) -> float:
    """
    Lead time en días. LT más largo = mayor score.
    >120=100, 91-120=85, 61-90=70, 31-60=45, <=30=20.
    """
    lt = float(row.get("lt_days") or row.get("Mu_LT") or row.get("lt_days_operativo") or 0)
    if lt > 120:
        return 100.0
    if lt >= 91:
        return 85.0
    if lt >= 61:
        return 70.0
    if lt >= 31:
        return 45.0
    return 20.0


def score_acceleration(row: dict) -> float:
    """
    Aceleración de demanda: demand_6m / demand_24m.
    >=1.8=100, 1.4-1.79=80, 1.1-1.39=60, 0.8-1.09=40, <0.8=20.
    Si no hay datos, retorna 40 (neutral).
    """
    d6 = row.get("demand_6m") or row.get("demanda_6m") or row.get("mu_6m")
    d24 = row.get("demand_24m") or row.get("demanda_24m") or row.get("mu_24m")

    if d6 is None or d24 is None:
        # Fallback: demanda_prom_mensual_12m vs forecast histórico
        d12 = float(row.get("demanda_prom_mensual_12m") or row.get("Forecast_m") or 0)
        if d12 > 0:
            # Aproximación: si hay demanda reciente vs 0 histórico, acelerando
            return 60.0
        return 40.0

    d6f = float(d6)
    d24f = float(d24)
    if d24f <= 0:
        return 40.0

    ratio = d6f / d24f
    if ratio >= 1.8:
        return 100.0
    if ratio >= 1.4:
        return 80.0
    if ratio >= 1.1:
        return 60.0
    if ratio >= 0.8:
        return 40.0
    return 20.0


def score_margen(row: dict) -> float:
    """
    Margen o valor comercial. 0-100.
    Si existe margen_bruto_pct o similar, normalizar.
    Fallback: margen_nivel (MUY_ALTO, ALTO, MEDIO, BAJO) o 50.
    """
    nivel = (row.get("margen_nivel") or row.get("valor_nivel") or "").upper()
    if nivel:
        return {"MUY_ALTO": 100.0, "ALTO": 80.0, "MEDIO": 50.0, "BAJO": 20.0}.get(nivel, 50.0)

    pct = row.get("margen_bruto_pct") or row.get("margen_pct")
    if pct is not None:
        p = float(pct)
        if p >= 0.4:
            return 100.0
        if p >= 0.25:
            return 80.0
        if p >= 0.15:
            return 50.0
        return 20.0

    return 50.0


def score_backlog(row: dict) -> float:
    """
    Backlog o demanda insatisfecha. 0-100.
    100 si backlog >= stock_actual, 80 si >0.5*stock, 60 si >0, 0 si 0.
    """
    backlog = int(row.get("backlog_qty") or row.get("backlog_qty_at_calc") or 0)
    stock = float(row.get("stock_posicion") or row.get("oferta_total") or 0)

    if backlog <= 0:
        return 0.0
    if stock <= 0:
        return 100.0
    if backlog >= stock:
        return 100.0
    if backlog >= 0.5 * stock:
        return 80.0
    return 60.0


def penalty_overstock(row: dict) -> float:
    """
    Riesgo de sobrestock. Penalidad 0-100 (resta del score).
    Prioridad: days_of_supply (días de stock) si existe; si no, ratio stock/objetivo.
    """
    days = row.get("days_of_supply")
    if days is not None:
        try:
            d = float(days)
            if d > 365:
                return 100.0
            if d > 180:
                return 70.0
            if d > 120:
                return 40.0
            if d > 90:
                return 10.0
            return 0.0
        except (TypeError, ValueError):
            pass

    stock = float(row.get("stock_posicion") or row.get("oferta_total") or 0)
    objetivo = float(row.get("stock_objetivo_final") or row.get("stock_objetivo") or 0)

    if objetivo <= 0:
        return 0.0

    ratio = stock / objetivo
    if ratio >= 2.0:
        return 100.0
    if ratio >= 1.5:
        return 70.0
    if ratio >= 1.2:
        return 40.0
    if ratio >= 1.0:
        return 10.0
    return 0.0


def penalty_cliente(row: dict) -> float:
    """
    Dominancia de cliente (top1_share). Penalidad 0-50.
    >=0.85=-50, 0.70-0.84=-35, 0.60-0.69=-20, <0.60=0.
    """
    share = row.get("top1_share_12m") or row.get("top1_share") or row.get("share_cliente_dominante")
    if share is None:
        return 0.0

    s = float(share)
    if s >= 0.85:
        return 50.0
    if s >= 0.70:
        return 35.0
    if s >= 0.60:
        return 20.0
    return 0.0


def _band_for_score(score: float) -> str:
    """Devuelve la banda de prioridad para un score 0-100."""
    for lo, hi, band in PRIORITY_BANDS:
        if lo <= score <= hi:
            return band
    return "MUY_BAJA" if score < 40 else "URGENTE"


def _build_priority_reason(
    stockout: float,
    criticidad: float,
    lt: float,
    accel: float,
    margen: float,
    backlog: float,
    overstock: float,
    cliente: float,
) -> str:
    """Construye explicación breve de la prioridad."""
    parts = []
    if stockout >= 70:
        parts.append("riesgo de stockout elevado")
    if criticidad >= 80:
        parts.append("criticidad alta")
    if lt >= 70:
        parts.append("lead time largo")
    if accel >= 70:
        parts.append("aceleración de demanda")
    if backlog >= 60:
        parts.append("backlog pendiente")
    if overstock >= 50:
        parts.append("riesgo de sobrestock")
    if cliente >= 30:
        parts.append("cliente dominante")

    if not parts:
        return "Prioridad estándar."
    return "Prioridad por: " + ", ".join(parts[:4]) + "."


def calculate_priority_score(row: dict) -> dict:
    """
    Calcula el Smart Replenishment Score completo para un SKU.
    row debe tener los campos de ss2_demand_cache, ss2_policy_results, stock, etc.
    """
    sku = row.get("sku", "")

    stockout = score_stockout(row)
    criticidad = score_criticidad(row)
    lt = score_lead_time(row)
    accel = score_acceleration(row)
    margen = score_margen(row)
    backlog = score_backlog(row)
    overstock = penalty_overstock(row)
    cliente = penalty_cliente(row)

    # Fórmula ponderada (componentes 0-100, penalidades restan)
    raw = (
        WEIGHT_STOCKOUT * stockout
        + WEIGHT_CRITICIDAD * criticidad
        + WEIGHT_LEAD_TIME * lt
        + WEIGHT_ACCELERATION * accel
        + WEIGHT_MARGEN * margen
        + WEIGHT_BACKLOG * backlog
        - WEIGHT_OVERSTOCK * overstock
        - WEIGHT_CLIENTE * cliente
    )

    # La fórmula ya produce ~0-100. Clamp para garantizar rango.
    priority_score = max(0.0, min(100.0, raw))

    priority_band = _band_for_score(priority_score)
    priority_reason = _build_priority_reason(
        stockout, criticidad, lt, accel, margen, backlog, overstock, cliente
    )

    return {
        "sku": sku,
        "priority_score": round(priority_score, 2),
        "stockout_score": round(stockout, 2),
        "criticidad_score": round(criticidad, 2),
        "lead_time_score": round(lt, 2),
        "acceleration_score": round(accel, 2),
        "margen_score": round(margen, 2),
        "backlog_score": round(backlog, 2),
        "overstock_penalty": round(overstock, 2),
        "cliente_penalty": round(cliente, 2),
        "priority_band": priority_band,
        "priority_reason": priority_reason,
    }


def run_purchase_scoring(rows: list[dict]) -> list[dict]:
    """
    Ejecuta el scoring sobre una lista de filas.
    Cada row debe tener la estructura esperada por calculate_priority_score.
    """
    return [calculate_priority_score(r) for r in rows]


# -----------------------------
# Integración con DB
# -----------------------------

FETCH_SCORING_INPUTS_SQL = """
SELECT
  p.sku,
  COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0) AS stock_posicion,
  COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0) AS oferta_total,
  COALESCE(pr.stock_min, p.stock_min) AS stock_min,
  COALESCE(pr.stock_objetivo_final, p.stock_objetivo) AS stock_objetivo_final,
  p.stock_objetivo,
  COALESCE(pr.criticidad, d.criticidad, p.criticidad, 'BAJO') AS criticidad,
  COALESCE(d.lt_days, p.lead_time_dias, 60) AS lt_days,
  COALESCE(d.p_stockout_at_current_stock, 0) AS p_stockout_at_current_stock,
  COALESCE(pr.backlog_qty_at_calc, 0) AS backlog_qty,
  pr.backlog_qty_at_calc AS backlog_qty_at_calc,
  f.demanda_prom_mensual_12m,
  f.demanda_prom_mensual_12m AS Forecast_m,
  f.meses_con_venta_12m,
  -- Margen: margen_total / revenue_total (0-1). score_margen usa umbrales 0.4, 0.25, 0.15
  (CASE
    WHEN COALESCE(ef.eventos_12m, 0) > 0
     AND COALESCE(ef.revenue_prom_evento_12m, 0) > 0
    THEN ef.margen_total_12m / (ef.revenue_prom_evento_12m * ef.eventos_12m)
    ELSE NULL
  END) AS margen_pct,
  -- top1_share_12m: share del cliente dominante (0-1). Si existe v_sku_top_client_share, unir aquí.
  NULL AS top1_share_12m,
  -- demanda_6m, demanda_24m: para score_acceleration. Si v_sku_features_12m las tiene, reemplazar NULL.
  NULL AS demanda_6m,
  NULL AS demanda_24m,
  -- days_of_supply: stock / demanda_anual_diaria. Para penalty_overstock alternativo.
  (CASE
    WHEN COALESCE(f.demanda_prom_mensual_12m, 0) > 0
    THEN (COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0))
         / (f.demanda_prom_mensual_12m * 12 / 365.0)
    ELSE NULL
  END) AS days_of_supply
FROM parametros_sku p
LEFT JOIN v_stock_estado_unidades se ON se.sku = p.sku
LEFT JOIN ss2_policy_results pr ON pr.sku = p.sku
LEFT JOIN ss2_demand_cache d ON d.sku = p.sku
LEFT JOIN v_sku_features_12m f ON f.SKU = p.sku
LEFT JOIN v_sku_event_features_12m ef ON ef.SKU = p.sku
WHERE p.activo = 1 AND p.discontinuado = 0
"""

# Fallback si v_sku_event_features_12m no existe o faltan columnas
FETCH_SCORING_INPUTS_SQL_LEGACY = """
SELECT
  p.sku,
  COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0) AS stock_posicion,
  COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0) AS oferta_total,
  COALESCE(pr.stock_min, p.stock_min) AS stock_min,
  COALESCE(pr.stock_objetivo_final, p.stock_objetivo) AS stock_objetivo_final,
  p.stock_objetivo,
  COALESCE(pr.criticidad, d.criticidad, p.criticidad, 'BAJO') AS criticidad,
  COALESCE(d.lt_days, p.lead_time_dias, 60) AS lt_days,
  COALESCE(d.p_stockout_at_current_stock, 0) AS p_stockout_at_current_stock,
  COALESCE(pr.backlog_qty_at_calc, 0) AS backlog_qty,
  pr.backlog_qty_at_calc AS backlog_qty_at_calc,
  f.demanda_prom_mensual_12m,
  f.demanda_prom_mensual_12m AS Forecast_m,
  f.meses_con_venta_12m,
  NULL AS margen_pct,
  NULL AS top1_share_12m,
  NULL AS demanda_6m,
  NULL AS demanda_24m,
  (CASE
    WHEN COALESCE(f.demanda_prom_mensual_12m, 0) > 0
    THEN (COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0))
         / (f.demanda_prom_mensual_12m * 12 / 365.0)
    ELSE NULL
  END) AS days_of_supply
FROM parametros_sku p
LEFT JOIN v_stock_estado_unidades se ON se.sku = p.sku
LEFT JOIN ss2_policy_results pr ON pr.sku = p.sku
LEFT JOIN ss2_demand_cache d ON d.sku = p.sku
LEFT JOIN v_sku_features_12m f ON f.SKU = p.sku
WHERE p.activo = 1 AND p.discontinuado = 0
"""

UPSERT_PURCHASE_SCORES_SQL = """
INSERT INTO ss2_purchase_scores
(sku, priority_score, stockout_score, criticidad_score, lead_time_score,
 acceleration_score, margen_score, backlog_score, overstock_penalty, cliente_penalty,
 priority_band, priority_reason, updated_at)
VALUES
(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON DUPLICATE KEY UPDATE
priority_score=VALUES(priority_score),
stockout_score=VALUES(stockout_score),
criticidad_score=VALUES(criticidad_score),
lead_time_score=VALUES(lead_time_score),
acceleration_score=VALUES(acceleration_score),
margen_score=VALUES(margen_score),
backlog_score=VALUES(backlog_score),
overstock_penalty=VALUES(overstock_penalty),
cliente_penalty=VALUES(cliente_penalty),
priority_band=VALUES(priority_band),
priority_reason=VALUES(priority_reason),
updated_at=NOW();
"""


def run_purchase_scoring_batch(conn: Any) -> tuple[int, list[dict]]:
    """
    Lee policy_results + demand_cache + stock + features,
    ejecuta Purchase Scoring y escribe en ss2_purchase_scores.
    Retorna (count_updated, results).
    """
    import pymysql

    try:
        with conn.cursor() as cur:
            cur.execute(FETCH_SCORING_INPUTS_SQL)
            rows = cur.fetchall()
    except pymysql.err.OperationalError as e:
        err = str(e).lower()
        if "unknown column" in err or "doesn't exist" in err or "unknown table" in err:
            with conn.cursor() as cur:
                cur.execute(FETCH_SCORING_INPUTS_SQL_LEGACY)
                rows = cur.fetchall()
        else:
            raise

    for r in rows:
        r.setdefault("top1_share_12m", None)
        r.setdefault("demand_6m", None)
        r.setdefault("demand_24m", None)

    results = run_purchase_scoring(rows)

    with conn.cursor() as cur:
        for res in results:
            cur.execute(
                UPSERT_PURCHASE_SCORES_SQL,
                (
                    res["sku"],
                    res["priority_score"],
                    res["stockout_score"],
                    res["criticidad_score"],
                    res["lead_time_score"],
                    res["acceleration_score"],
                    res["margen_score"],
                    res["backlog_score"],
                    res["overstock_penalty"],
                    res["cliente_penalty"],
                    res["priority_band"],
                    (res["priority_reason"] or "")[:255],
                ),
            )

    return len(results), results
