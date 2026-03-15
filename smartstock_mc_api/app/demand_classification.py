"""
Demand Classification - Clasificación automática de demanda por SKU.

Clasifica cada SKU según ADI + CV² (Syntetos & Boylan) y reglas de lifecycle.
La clasificación determina qué modelo de reposición aplicar en el Policy Engine.

Clases: REGULAR, ERRATIC, INTERMITTENT, LUMPY, NEW, DORMANT, DEAD
Flags: cliente_dominante_flag, accelerating_flag, perecedero_flag
"""

from __future__ import annotations

from typing import Any, Optional

# Umbrales ADI + CV² (Syntetos & Boylan)
ADI_THRESHOLD = 1.32
CV2_THRESHOLD = 0.49

# Reglas lifecycle
EVENTOS_MIN_NEW = 3
DIAS_OBS_MIN_NEW = 180
DIAS_DORMANT = 180
DIAS_DEAD = 365
TOP1_SHARE_CLIENTE_DOMINANTE = 0.60
MU_RATIO_ACCELERATING = 1.4


def safe_div(num: float, denom: float, default: float = 0.0) -> float:
    """División segura. Retorna default si denom <= 0."""
    if denom is None or denom <= 0:
        return default
    try:
        return float(num) / float(denom)
    except (TypeError, ZeroDivisionError):
        return default


def compute_adi(
    meses_observados: float,
    meses_con_demanda: Optional[float],
    eventos_12m: Optional[float] = None,
) -> float:
    """
    ADI = Average Demand Interval = meses_observados / meses_con_demanda.

    Si meses_con_demanda no está disponible, aproximación:
    meses_con_demanda ≈ min(eventos_12m, 12) (cada evento en mes distinto).
    """
    if meses_observados is None or meses_observados <= 0:
        return 0.0

    meses_obs = float(meses_observados)
    if meses_con_demanda is not None and meses_con_demanda > 0:
        return safe_div(meses_obs, meses_con_demanda, 0.0)

    # Fallback: usar eventos_12m
    if eventos_12m is not None and eventos_12m > 0:
        meses_approx = min(float(eventos_12m), 12.0)
        return safe_div(meses_obs, meses_approx, 0.0)

    return 0.0


def compute_cv2(mean_qty_event: float, std_qty_event: float) -> float:
    """
    CV² = (std / mean)² del tamaño de demanda por evento.

    CV = std / mean; CV² = CV * CV.
    """
    if mean_qty_event is None or mean_qty_event <= 0:
        return 0.0
    cv = safe_div(std_qty_event or 0, mean_qty_event, 0.0)
    return cv * cv


def classify_demand_pattern(adi: float, cv2: float) -> str:
    """
    Clasificación ADI + CV² (Syntetos & Boylan).

    ADI < 1.32, CV² < 0.49  => REGULAR
    ADI < 1.32, CV² >= 0.49 => ERRATIC
    ADI >= 1.32, CV² < 0.49 => INTERMITTENT
    ADI >= 1.32, CV² >= 0.49 => LUMPY
    """
    if adi < ADI_THRESHOLD and cv2 < CV2_THRESHOLD:
        return "REGULAR"
    if adi < ADI_THRESHOLD and cv2 >= CV2_THRESHOLD:
        return "ERRATIC"
    if adi >= ADI_THRESHOLD and cv2 < CV2_THRESHOLD:
        return "INTERMITTENT"
    if adi >= ADI_THRESHOLD and cv2 >= CV2_THRESHOLD:
        return "LUMPY"
    return "INTERMITTENT"  # fallback


def classify_lifecycle(row: dict) -> tuple[str, bool]:
    """
    Determina lifecycle_state (NEW, DORMANT, DEAD, ACTIVE).

    Retorna (lifecycle_state, overrides_demand_class).
    Si overrides_demand_class=True, el lifecycle tiene prioridad sobre demand_class.
    """
    eventos_12m = int(row.get("eventos_12m") or 0)
    dias_observados = int(row.get("dias_observados") or 0)
    unidades_12m = float(row.get("unidades_12m") or 0)
    unidades_6m = float(row.get("unidades_6m") or 0)
    days_since_last_sale = row.get("days_since_last_sale")
    if days_since_last_sale is None:
        days_since_last_sale = 9999  # sin dato = asumir muy antiguo

    # NEW: poco historial
    if eventos_12m < EVENTOS_MIN_NEW or dias_observados < DIAS_OBS_MIN_NEW:
        return "NEW", True

    # DEAD: sin actividad en largo plazo
    if days_since_last_sale > DIAS_DEAD and unidades_12m <= 0:
        return "DEAD", True

    # DORMANT: sin ventas recientes
    if days_since_last_sale > DIAS_DORMANT and unidades_6m <= 0:
        return "DORMANT", True

    return "ACTIVE", False


def build_classification_reason(
    demand_class: str,
    lifecycle_state: str,
    adi: float,
    cv2: float,
    overrides: bool,
) -> str:
    """Construye explicación legible para classification_reason."""
    parts = []
    if overrides:
        parts.append(f"Lifecycle {lifecycle_state}.")
    else:
        parts.append(f"ADI={adi:.2f} CV²={cv2:.2f} => {demand_class}.")
    return " ".join(parts)[:255]


def classify_sku(row: dict) -> dict:
    """
    Clasifica un SKU completo.

    row debe tener: sku, eventos_12m, unidades_12m, dias_observados,
    mu_unidades_evento (o mean_qty_event), sigma_unidades_evento (o std_qty_event),
    meses_con_demanda (opcional), days_since_last_sale (opcional), unidades_6m (opcional),
    top1_share_12m (opcional), mu_6m (opcional), mu_24m (opcional).
    """
    sku = row.get("sku", "")

    # Métricas base
    mean_qty = float(row.get("mu_unidades_evento") or row.get("mean_qty_event") or 0)
    std_qty = float(row.get("sigma_unidades_evento") or row.get("std_qty_event") or 0)
    eventos_12m = row.get("eventos_12m")
    dias_observados = row.get("dias_observados") or 365
    meses_con_demanda = row.get("meses_con_demanda")
    meses_observados = 12.0  # ventana estándar 12m

    adi = compute_adi(meses_observados, meses_con_demanda, eventos_12m)
    cv2 = compute_cv2(mean_qty, std_qty)

    # Lifecycle primero (tiene prioridad)
    lifecycle_state, overrides = classify_lifecycle(row)
    if overrides:
        demand_class = lifecycle_state
    else:
        demand_class = classify_demand_pattern(adi, cv2)

    # Flags
    top1 = row.get("top1_share_12m") or row.get("top1_share")
    cliente_dominante = 1 if (top1 is not None and float(top1) >= TOP1_SHARE_CLIENTE_DOMINANTE) else 0

    mu_6m = row.get("mu_6m") or row.get("demanda_6m") or row.get("demand_6m")
    mu_24m = row.get("mu_24m") or row.get("demanda_24m") or row.get("demand_24m")
    accelerating = 0
    if mu_6m is not None and mu_24m is not None:
        try:
            ratio = float(mu_6m) / max(float(mu_24m), 1e-9)
            accelerating = 1 if ratio >= MU_RATIO_ACCELERATING else 0
        except (TypeError, ValueError):
            pass

    perecedero = int(row.get("perecedero_flag") or 0)

    reason = build_classification_reason(
        demand_class, lifecycle_state, adi, cv2, overrides
    )

    return {
        "sku": sku,
        "adi": round(adi, 4),
        "cv2": round(cv2, 4),
        "demand_class": demand_class,
        "lifecycle_state": lifecycle_state,
        "cliente_dominante_flag": cliente_dominante,
        "accelerating_flag": accelerating,
        "perecedero_flag": perecedero,
        "classification_reason": reason,
    }


def run_demand_classification(rows: list[dict]) -> list[dict]:
    """
    Ejecuta clasificación sobre una lista de filas.
    """
    return [classify_sku(r) for r in rows]


# -----------------------------
# Integración con DB
# -----------------------------

FETCH_CLASSIFICATION_INPUTS_SQL = """
SELECT
  sku,
  dias_observados,
  eventos_12m,
  unidades_12m,
  mu_unidades_evento,
  sigma_unidades_evento,
  meses_con_demanda,
  days_since_last_sale,
  unidades_6m,
  NULL AS top1_share_12m,
  NULL AS mu_6m,
  NULL AS mu_24m
FROM v_sku_classification_input
"""

# Fallback si v_sku_classification_input no existe
FETCH_CLASSIFICATION_INPUTS_SQL_LEGACY = """
SELECT
  sku,
  dias_observados,
  eventos_12m,
  unidades_12m,
  mu_unidades_evento,
  sigma_unidades_evento,
  NULL AS meses_con_demanda,
  NULL AS days_since_last_sale,
  NULL AS unidades_6m,
  NULL AS top1_share_12m,
  NULL AS mu_6m,
  NULL AS mu_24m
FROM sku_obs_12m
"""

UPSERT_CLASSIFICATION_SQL = """
INSERT INTO ss2_demand_classification
(sku, adi, cv2, demand_class, lifecycle_state,
 cliente_dominante_flag, accelerating_flag, perecedero_flag,
 classification_reason, updated_at)
VALUES
(%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
ON DUPLICATE KEY UPDATE
adi=VALUES(adi),
cv2=VALUES(cv2),
demand_class=VALUES(demand_class),
lifecycle_state=VALUES(lifecycle_state),
cliente_dominante_flag=VALUES(cliente_dominante_flag),
accelerating_flag=VALUES(accelerating_flag),
perecedero_flag=VALUES(perecedero_flag),
classification_reason=VALUES(classification_reason),
updated_at=NOW();
"""


def run_demand_classification_batch(conn: Any) -> tuple[int, list[dict]]:
    """
    Lee sku_obs_12m (+ v_sku_classification_input si existe),
    ejecuta clasificación y escribe en ss2_demand_classification.
    Retorna (count_updated, results).
    """
    import pymysql

    try:
        with conn.cursor() as cur:
            cur.execute(FETCH_CLASSIFICATION_INPUTS_SQL)
            rows = cur.fetchall()
    except pymysql.err.OperationalError as e:
        err = str(e).lower()
        if "unknown column" in err or "doesn't exist" in err or "unknown table" in err:
            with conn.cursor() as cur:
                cur.execute(FETCH_CLASSIFICATION_INPUTS_SQL_LEGACY)
                rows = cur.fetchall()
        else:
            raise

    results = run_demand_classification(rows)

    with conn.cursor() as cur:
        for res in results:
            cur.execute(
                UPSERT_CLASSIFICATION_SQL,
                (
                    res["sku"],
                    res["adi"],
                    res["cv2"],
                    res["demand_class"],
                    res["lifecycle_state"],
                    res["cliente_dominante_flag"],
                    res["accelerating_flag"],
                    res["perecedero_flag"],
                    (res["classification_reason"] or "")[:255],
                ),
            )

    return len(results), results


# -----------------------------
# Mapeo para Policy Engine
# -----------------------------

def get_model_preference(demand_class: str, lifecycle_state: str) -> str:
    """
    Indica qué modelo prefiere el Policy Engine según clasificación.

    Retorna: 'analytic' | 'mc_preferred' | 'mc_strong' | 'fallback' | 'no_buy' | 'exclude'
    """
    if lifecycle_state == "DEAD":
        return "exclude"
    if lifecycle_state == "DORMANT":
        return "no_buy"
    if lifecycle_state == "NEW":
        return "fallback"

    if demand_class == "REGULAR":
        return "analytic"
    if demand_class == "ERRATIC":
        return "analytic"  # o mc según CV
    if demand_class == "INTERMITTENT":
        return "mc_preferred"
    if demand_class == "LUMPY":
        return "mc_strong"

    return "mc_preferred"
