"""
Policy Engine - SS2 Reposición en 3 capas

Demand Engine estima demanda; Policy Engine decide stock objetivo final.

Funciones modulares para:
- Elegir service level por criticidad
- Elegir demand target (percentil MC o analytic)
- Aplicar caps en orden: cap_hist, cap_cliente, cap_vencimiento
- Aplicar MOQ/múltiplos
- Construir explicación auditable
"""

from __future__ import annotations

import math
from typing import Any, Optional

# Mapeo criticidad -> service level (nivel de servicio objetivo)
SERVICE_LEVEL_MAP = {
    "CRITICO": 0.97,
    "ALTO": 0.95,
    "MEDIO": 0.90,
    "BAJO": 0.80,
}


def choose_service_level(criticidad: str) -> float:
    """
    Devuelve el service level (0.80-0.97) según criticidad unificada.
    CRITICO=0.97, ALTO=0.95, MEDIO=0.90, BAJO=0.80.
    """
    u = (criticidad or "BAJO").upper().strip()
    return SERVICE_LEVEL_MAP.get(u, 0.80)


def choose_base_demand_target(row: dict) -> tuple[float, str]:
    """
    Elige el demand target base: percentil MC o analytic_target.
    Retorna (valor, source) donde source es 'demand_p97', 'demand_p95', 'demand_p90', etc.
    Regla: CRITICO -> P97 o P95; ALTO -> P95; MEDIO -> P90; BAJO -> P80.
    """
    mc_enabled = int(row.get("mc_enabled") or 0)
    criticidad = (row.get("criticidad") or "BAJO").upper()

    if mc_enabled != 1:
        analytic = float(row.get("stock_objetivo") or row.get("analytic_target") or 0)
        return analytic, "analytic_target"

    # MC activo: elegir percentil según criticidad
    if criticidad == "CRITICO":
        p97, p95, p90 = row.get("demand_p97"), row.get("demand_p95"), row.get("demand_p90")
        for v, src in [(p97, "demand_p97"), (p95, "demand_p95"), (p90, "demand_p90")]:
            if v is not None:
                return float(v), src
        return 0.0, "demand_p95"
    if criticidad == "ALTO":
        val = float(row.get("demand_p95") or row.get("demand_p90") or 0)
        return val, "demand_p95"
    if criticidad == "MEDIO":
        val = float(row.get("demand_p90") or row.get("demand_p50") or 0)
        return val, "demand_p90"
    # BAJO
    val = float(row.get("demand_p80") or row.get("demand_p50") or 0)
    return val, "demand_p80"


def apply_cap_hist(target: float, row: dict) -> tuple[float, str | None]:
    """
    Aplica cap histórico (cap_objetivo o cap_hist).
    Retorna (target_capeado, "cap_hist:VAL" si recortó, None si no).
    """
    cap = row.get("cap_hist") or row.get("cap_objetivo")
    if cap is None:
        return target, None
    cap = float(cap)
    if cap <= 0:
        return target, None
    if target <= cap:
        return target, None
    return cap, f"cap_hist:{int(cap)}"


def apply_cap_cliente(target: float, row: dict) -> tuple[float, str | None]:
    """
    Aplica cap por share de cliente dominante.
    Retorna (target_capeado, "cap_cliente:VAL" si recortó, None si no).
    """
    cap = row.get("cap_cliente_dominante")
    if cap is None:
        return target, None
    cap = float(cap)
    if cap <= 0:
        return target, None
    if target <= cap:
        return target, None
    return cap, f"cap_cliente:{int(cap)}"


def apply_cap_vencimiento(target: float, row: dict) -> tuple[float, str | None]:
    """
    Aplica cap por vencimiento.
    Retorna (target_capeado, "cap_vencimiento:VAL" si recortó, None si no).
    """
    cap = row.get("cap_vencimiento")
    if cap is None:
        return target, None
    cap = float(cap)
    if cap <= 0:
        return target, None
    if target <= cap:
        return target, None
    return cap, f"cap_vencimiento:{int(cap)}"


def apply_caps(
    base_target: float,
    row: dict,
) -> tuple[float, str]:
    """
    Aplica caps en orden: cap_hist, cap_cliente_dominante, cap_vencimiento.
    Retorna (target_final, applied_caps_str) donde applied_caps_str es lista separada por |.
    """
    applied: list[str] = []
    t = base_target

    t, msg = apply_cap_hist(t, row)
    if msg:
        applied.append(msg)

    t, msg = apply_cap_cliente(t, row)
    if msg:
        applied.append(msg)

    t, msg = apply_cap_vencimiento(t, row)
    if msg:
        applied.append(msg)

    return t, "|".join(applied) if applied else ""


def apply_moq_rounding(target: float, row: dict, apply_q_cap: bool = True) -> float:
    """
    Aplica MOQ y múltiplo de compra.
    Si target <= 0 retorna 0. Si no, redondea hacia arriba al múltiplo y respeta MOQ.
    apply_q_cap: si True, aplica q_cap (límite de cantidad). Para stock_objetivo usar False.
    """
    q = max(0.0, float(target))
    moq = int(row.get("moq") or 1)
    multiplo = int(row.get("multiplo_compra") or row.get("multiplo") or 1)
    q_cap = row.get("q_cap") if apply_q_cap else None

    if moq < 1:
        moq = 1
    if multiplo < 1:
        multiplo = 1

    if q <= 0:
        return 0.0

    q = max(q, float(moq))
    q = math.ceil(q / multiplo) * multiplo

    if q_cap is not None:
        cap = int(q_cap)
        if cap > 0:
            q = min(q, float(cap))

    return float(q)


def apply_rounding(qty_raw: float, row: dict) -> float:
    """
    Alias de apply_moq_rounding para qty (stock_objetivo - stock_posicion).
    Aplica MOQ, múltiplo y q_cap.
    """
    return apply_moq_rounding(qty_raw, row, apply_q_cap=True)


def apply_rounding_stock_target(target: float, row: dict) -> float:
    """
    Redondea stock_objetivo_final con MOQ/múltiplo (sin q_cap).
    q_cap limita la cantidad a comprar, no el target de stock.
    """
    return apply_moq_rounding(target, row, apply_q_cap=False)


def build_explanation(
    row: dict,
    service_level: float,
    demand_target_source: str,
    base_demand_target: float,
    target_after_caps: float,
    applied_caps: str,
    stock_objetivo_final: float,
    qty_recomendada_final: float,
) -> str:
    """
    Construye explicación auditable por SKU.
    """
    parts: list[str] = []
    mc_enabled = int(row.get("mc_enabled") or 0)
    regimen = row.get("regimen") or "N/A"
    criticidad = row.get("criticidad") or "BAJO"

    if mc_enabled == 1:
        parts.append(f"Monte Carlo activo ({regimen}).")
        parts.append(f"Service level {service_level:.2f} por criticidad {criticidad}.")
        parts.append(f"Target {demand_target_source}={base_demand_target:.0f}.")
    else:
        parts.append("MC desactivado. Target analítico.")
        parts.append(f"stock_objetivo={base_demand_target:.0f}.")

    if applied_caps:
        parts.append(f"Caps aplicados: {applied_caps}.")

    parts.append(f"stock_objetivo_final={stock_objetivo_final:.0f}.")
    parts.append(f"qty_recomendada_final={qty_recomendada_final:.0f}.")

    return " ".join(parts)


def calculate_policy_for_sku(row: dict) -> dict:
    """
    Calcula la política completa para un SKU.
    row debe tener: sku, stock_objetivo, stock_min, mc_enabled, criticidad,
    demand_p50/p80/p90/p95, cap_objetivo/cap_hist, cap_cliente_dominante, cap_vencimiento,
    moq, multiplo_compra, q_cap, stock_posicion (oferta_total o stock_libre_deposito+impo_libre).
    """
    sku = row.get("sku", "")
    stock_pos = float(row.get("stock_posicion") or row.get("oferta_total") or 0)
    backlog = int(row.get("backlog_qty") or 0)

    service_level = choose_service_level(row.get("criticidad"))
    base_target, demand_target_source = choose_base_demand_target(row)

    target_after_caps, applied_caps = apply_caps(base_target, row)
    # Spec: stock_objetivo_final = redondear(target_after_caps) con MOQ/múltiplo
    stock_objetivo_final = apply_rounding_stock_target(target_after_caps, row)

    # Spec: qty_recomendada_final = max(0, stock_objetivo_final - stock_posicion)
    # Aplicamos MOQ/q_cap a la qty para órdenes de compra
    qty_raw = max(0.0, stock_objetivo_final - stock_pos)
    qty_recomendada_final = apply_rounding(qty_raw, row)

    policy_reason = _build_policy_reason(row, demand_target_source, applied_caps)
    explanation = build_explanation(
        row,
        service_level,
        demand_target_source,
        base_target,
        target_after_caps,
        applied_caps,
        stock_objetivo_final,
        qty_recomendada_final,
    )

    return {
        "sku": sku,
        "service_level": service_level,
        "demand_target_source": demand_target_source,
        "base_demand_target": base_target,
        "target_after_caps": target_after_caps,
        "stock_objetivo_final": stock_objetivo_final,
        "qty_recomendada_final": qty_recomendada_final,
        "applied_caps": applied_caps or None,
        "policy_reason": policy_reason,
        "explanation": explanation,
        "stock_min": int(row.get("stock_min") or 0),
        "criticidad": row.get("criticidad"),
        "moq": row.get("moq"),
        "multiplo_compra": row.get("multiplo_compra") or row.get("multiplo"),
        "q_cap": row.get("q_cap"),
        "stock_posicion_at_calc": int(stock_pos),
        "backlog_qty_at_calc": backlog,
    }


def _build_policy_reason(row: dict, demand_target_source: str, applied_caps: str) -> str:
    """Razón corta para policy_reason."""
    mc_enabled = int(row.get("mc_enabled") or 0)
    if mc_enabled != 1:
        return "ANALYTIC"
    parts = [f"MC:{demand_target_source.replace('demand_', '')}"]
    if applied_caps:
        parts.append("CON_CAPS")
    return "_".join(parts)


def calculate_stock_objetivo_final(row: dict) -> dict:
    """Alias de calculate_policy_for_sku."""
    return calculate_policy_for_sku(row)


def run_policy_engine(rows: list[dict]) -> list[dict]:
    """
    Ejecuta el Policy Engine sobre una lista de filas (SKUs).
    Cada row debe tener la estructura esperada por calculate_policy_for_sku.
    Retorna lista de resultados.
    """
    return [calculate_policy_for_sku(r) for r in rows]


# -----------------------------
# Integración con DB (opcional)
# -----------------------------

FETCH_POLICY_INPUTS_SQL = """
SELECT
  p.sku,
  p.stock_min,
  p.stock_objetivo,
  p.cap_objetivo,
  COALESCE(p.moq, c.moq, 1) AS moq,
  COALESCE(p.multiplo_compra, c.multiplo_compra, 1) AS multiplo_compra,
  COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0) AS stock_posicion,
  0 AS backlog_qty,
  COALESCE(d.mc_enabled, 0) AS mc_enabled,
  COALESCE(d.criticidad, 'BAJO') AS criticidad,
  COALESCE(d.regimen, 'NUEVO') AS regimen,
  d.demand_p50, d.demand_p80, d.demand_p90, d.demand_p95, d.demand_p97, d.demand_p99,
  c.q_cap,
  p.cap_objetivo AS cap_hist,
  p.cap_cliente_dominante,
  p.cap_vencimiento
FROM parametros_sku p
LEFT JOIN v_stock_estado_unidades se ON se.sku = p.sku
LEFT JOIN ss2_demand_cache d ON d.sku = p.sku
LEFT JOIN sku_mc_cache c ON c.sku = p.sku
LEFT JOIN ss2_demand_classification dc ON dc.sku = p.sku
WHERE p.activo = 1 AND p.discontinuado = 0
  AND (dc.lifecycle_state IS NULL OR dc.lifecycle_state != 'DEAD')
"""

# Fallback si parametros_sku no tiene cap_cliente_dominante, cap_vencimiento
# o si ss2_demand_classification no existe
FETCH_POLICY_INPUTS_SQL_LEGACY = """
SELECT
  p.sku,
  p.stock_min,
  p.stock_objetivo,
  p.cap_objetivo,
  COALESCE(p.moq, c.moq, 1) AS moq,
  COALESCE(p.multiplo_compra, c.multiplo_compra, 1) AS multiplo_compra,
  COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0) AS stock_posicion,
  0 AS backlog_qty,
  COALESCE(d.mc_enabled, 0) AS mc_enabled,
  COALESCE(d.criticidad, 'BAJO') AS criticidad,
  COALESCE(d.regimen, 'NUEVO') AS regimen,
  d.demand_p50, d.demand_p80, d.demand_p90, d.demand_p95, d.demand_p97, d.demand_p99,
  c.q_cap,
  p.cap_objetivo AS cap_hist
FROM parametros_sku p
LEFT JOIN v_stock_estado_unidades se ON se.sku = p.sku
LEFT JOIN ss2_demand_cache d ON d.sku = p.sku
LEFT JOIN sku_mc_cache c ON c.sku = p.sku
WHERE p.activo = 1 AND p.discontinuado = 0
"""

UPSERT_POLICY_RESULTS_SQL = """
INSERT INTO ss2_policy_results
(sku, stock_min, stock_objetivo_final, qty_recomendada_final,
 demand_target_source, demand_target_value, selected_service_level,
 applied_caps, policy_reason, explanation,
 criticidad, moq, multiplo_compra, q_cap,
 stock_posicion_at_calc, backlog_qty_at_calc, updated_at)
VALUES
(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON DUPLICATE KEY UPDATE
stock_min=VALUES(stock_min),
stock_objetivo_final=VALUES(stock_objetivo_final),
qty_recomendada_final=VALUES(qty_recomendada_final),
demand_target_source=VALUES(demand_target_source),
demand_target_value=VALUES(demand_target_value),
selected_service_level=VALUES(selected_service_level),
applied_caps=VALUES(applied_caps),
policy_reason=VALUES(policy_reason),
explanation=VALUES(explanation),
criticidad=VALUES(criticidad),
moq=VALUES(moq),
multiplo_compra=VALUES(multiplo_compra),
q_cap=VALUES(q_cap),
stock_posicion_at_calc=VALUES(stock_posicion_at_calc),
backlog_qty_at_calc=VALUES(backlog_qty_at_calc),
updated_at=NOW();
"""


def run_policy_engine_batch(conn: Any) -> tuple[int, list[dict]]:
    """
    Lee parametros_sku + ss2_demand_cache + v_stock_estado_unidades,
    ejecuta Policy Engine y escribe en ss2_policy_results.
    Retorna (count_updated, results).
    Si parametros_sku no tiene cap_cliente_dominante/cap_vencimiento, usa query legacy.
    """
    import pymysql

    try:
        with conn.cursor() as cur:
            cur.execute(FETCH_POLICY_INPUTS_SQL)
            rows = cur.fetchall()
    except pymysql.err.OperationalError as e:
        err = str(e).lower()
        if "unknown column" in err or "doesn't exist" in err or "unknown table" in err:
            with conn.cursor() as cur:
                cur.execute(FETCH_POLICY_INPUTS_SQL_LEGACY)
                rows = cur.fetchall()
        else:
            raise

    for r in rows:
        r.setdefault("cap_cliente_dominante", None)
        r.setdefault("cap_vencimiento", None)

    results = run_policy_engine(rows)

    with conn.cursor() as cur:
        for res in results:
            cur.execute(
                UPSERT_POLICY_RESULTS_SQL,
                (
                    res["sku"],
                    res["stock_min"],
                    res["stock_objetivo_final"],
                    res["qty_recomendada_final"],
                    res["demand_target_source"],
                    res["base_demand_target"],
                    res["service_level"],
                    res.get("applied_caps"),
                    res["policy_reason"],
                    res["explanation"],
                    res.get("criticidad"),
                    res.get("moq"),
                    res.get("multiplo_compra"),
                    res.get("q_cap"),
                    res.get("stock_posicion_at_calc"),
                    res.get("backlog_qty_at_calc"),
                ),
            )

    return len(results), results
