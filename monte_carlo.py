import os
import math
import random
import datetime as dt
from typing import Tuple, List, Dict, Optional

import pymysql


# -------------------------
# Config
# -------------------------
MYSQL_HOST = os.getenv("MYSQL_HOST", "190.228.29.65")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "neolab")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "MYsql437626#")
MYSQL_DB = os.getenv("MYSQL_DB", "neobd")

LOCATION_ID = 1
N_SIMS = int(os.getenv("MC_N_SIMS", "20000"))
SEED = int(os.getenv("MC_SEED", "42"))
random.seed(SEED)

# Política operativa REAL
LT_FIXED_DAYS = int(os.getenv("MC_LT_DAYS", "30"))        # LT = 30
REVIEW_DAYS = int(os.getenv("MC_REVIEW_DAYS", "45"))      # R = 45
HORIZON_DAYS = LT_FIXED_DAYS + REVIEW_DAYS                # H = 75

# Distribución tamaño de evento:
# - "auto": decide por SKU (TRUNCNORM / GAMMA / LOGNORMAL / BOOTSTRAP)
# - o forzá "lognormal" / "truncnorm" / "gamma"
EVENT_SIZE_DIST = os.getenv("EVENT_SIZE_DIST", "auto").strip().lower()


# -------------------------
# Helpers
# -------------------------
def z_to_service(z: float) -> float:
    """Aproximación: service target ~ Phi(z)."""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def percentile(sorted_vals: List[float], p: float) -> float:
    """p en [0,1]. Percentil con interpolación simple."""
    if not sorted_vals:
        return 0.0
    p = min(max(p, 0.0), 1.0)
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(sorted_vals[int(k)])
    d0 = sorted_vals[int(f)] * (c - k)
    d1 = sorted_vals[int(c)] * (k - f)
    return float(d0 + d1)


def poisson_knuth(lam: float) -> int:
    """Poisson sampler (Knuth)."""
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


# ---- Distribuciones para q_event (tamaño del evento) ----
def _sample_truncnorm(mean: float, sd: float) -> float:
    if mean <= 0:
        return 0.0
    if sd is None or sd <= 0:
        return max(0.0, mean)
    for _ in range(25):
        x = random.gauss(mean, sd)
        if x >= 0:
            return x
    return max(0.0, mean)


def _lognormal_mu_sigma_from_mean_sd(mean: float, sd: float) -> Tuple[float, float]:
    # sigma^2 = ln(1 + (sd^2/mean^2)); mu = ln(mean) - 0.5*sigma^2
    if mean <= 0:
        return 0.0, 1.0
    if sd is None or sd <= 0:
        return math.log(mean), 1e-9
    v = (sd ** 2) / (mean ** 2)
    sigma2 = math.log(1.0 + v)
    sigma = math.sqrt(sigma2)
    mu = math.log(mean) - 0.5 * sigma2
    return mu, sigma


def _sample_lognormal(mean: float, sd: float) -> float:
    if mean <= 0:
        return 0.0
    mu, sigma = _lognormal_mu_sigma_from_mean_sd(mean, sd)
    return random.lognormvariate(mu, sigma)


def _gamma_shape_scale_from_mean_sd(mean: float, sd: float) -> Tuple[float, float]:
    # k = (mean/sd)^2 ; theta = sd^2/mean
    if mean <= 0:
        return 1.0, 1.0
    if sd is None or sd <= 0:
        k = 1e6
        theta = mean / k
        return k, theta
    k = (mean / sd) ** 2
    theta = (sd ** 2) / mean
    k = max(1e-6, k)
    theta = max(1e-6, theta)
    return k, theta


def _sample_gamma(mean: float, sd: float) -> float:
    if mean <= 0:
        return 0.0
    k, theta = _gamma_shape_scale_from_mean_sd(mean, sd)
    return random.gammavariate(k, theta)


def choose_q_event_dist(
    *,
    smart_class: str,
    events_12m: int,
    lam_events_per_month: float,
    q_mean: float,
    q_sigma: float,
) -> Tuple[str, str]:
    """
    Selector PRO para q_event (tamaño de evento), usando CV=sd/mean y #eventos.
    Devuelve (dist, reason).
      dist: "bootstrap" | "truncnorm" | "gamma" | "lognormal"
    """
    if EVENT_SIZE_DIST in ("lognormal", "truncnorm", "gamma"):
        return EVENT_SIZE_DIST, f"forced_by_env={EVENT_SIZE_DIST}"

    if q_mean is None or q_mean <= 0:
        return "bootstrap", "q_mean<=0"
    if q_sigma is None or q_sigma < 0:
        return "bootstrap", "q_sigma invalid"

    if events_12m is not None and events_12m < 6:
        return "bootstrap", f"events_12m<{6}"

    cv = (q_sigma / q_mean) if q_mean > 0 else float("inf")

    if lam_events_per_month is not None and lam_events_per_month > 0.75 and cv <= 1.2:
        return "truncnorm", f"near-continuous: lam_m={lam_events_per_month:.2f}, cv={cv:.2f}"

    if cv < 0.5:
        return "truncnorm", f"cv={cv:.2f}<0.5"

    if cv <= 1.2:
        is_critical = (smart_class or "").upper() == "CRITICO"
        if is_critical and cv >= 1.0:
            return "lognormal", f"CRITICO & cv={cv:.2f} in [1.0,1.2]"
        return "gamma", f"cv={cv:.2f} in [0.5,1.2]"

    return "lognormal", f"cv={cv:.2f}>1.2"


def sample_q_event(dist: str, q_mean: float, q_sigma: float) -> float:
    """Samplea tamaño de evento (>=0) según dist."""
    d = (dist or "").lower()
    if d == "lognormal":
        return max(0.0, _sample_lognormal(q_mean, q_sigma))
    if d == "gamma":
        return max(0.0, _sample_gamma(q_mean, q_sigma))
    if d == "truncnorm":
        return max(0.0, _sample_truncnorm(q_mean, q_sigma))
    if d == "bootstrap":
        # sin muestras -> gamma como fallback robusto
        return max(0.0, _sample_gamma(q_mean, q_sigma))
    return max(0.0, _sample_gamma(q_mean, q_sigma))


def simulate_compound_poisson_totals(
    horizon_days: int,
    lam_events_per_month: float,
    q_mean: float,
    q_sigma: float,
    n_sims: int,
    *,
    q_event_dist: str,
) -> Tuple[List[float], float]:
    """
    Devuelve (totals_sorted, p_dem_gt0) para demanda total en horizonte.
    N eventos ~ Poisson(lam_h)
    Q tamaño evento ~ dist elegida por SKU (lognormal/gamma/truncnorm/bootstrap->gamma)
    """
    if horizon_days <= 0 or lam_events_per_month <= 0 or q_mean <= 0 or n_sims <= 0:
        return [0.0] * max(n_sims, 0), 0.0

    lam_h = lam_events_per_month * (horizon_days / 30.0)

    totals: List[float] = []
    positive = 0

    for _ in range(n_sims):
        n = poisson_knuth(lam_h)
        total = 0.0
        for _ in range(n):
            total += sample_q_event(q_event_dist, q_mean, q_sigma)
        totals.append(total)
        if total > 0:
            positive += 1

    totals.sort()
    p_dem_gt0 = positive / n_sims
    return totals, p_dem_gt0


def stats_from_totals(totals_sorted: List[float], service: float) -> Tuple[float, float, float, float]:
    """Devuelve mean, p90, p95, p_service."""
    n = len(totals_sorted)
    if n == 0:
        return 0.0, 0.0, 0.0, 0.0
    mean = sum(totals_sorted) / n
    p90 = percentile(totals_sorted, 0.90)
    p95 = percentile(totals_sorted, 0.95)
    p_srv = percentile(totals_sorted, service)
    return mean, p90, p95, p_srv


def _table_has_columns(cur, table_schema: str, table_name: str, cols: List[str]) -> Dict[str, bool]:
    """Chequea existencia de columnas (para no romper si todavía no agregaste dist_q_event)."""
    if not cols:
        return {}
    placeholders = ",".join(["%s"] * len(cols))
    cur.execute(
        f"""
        SELECT COLUMN_NAME
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME=%s AND COLUMN_NAME IN ({placeholders})
        """,
        [table_schema, table_name, *cols],
    )
    found = {row["COLUMN_NAME"] for row in cur.fetchall()}
    return {c: (c in found) for c in cols}


# -------------------------
# Main
# -------------------------
def main():
    today = dt.date.today()

    conn = pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

    try:
        with conn.cursor() as cur:
            # Detectar columnas nuevas opcionales en inventory_policies
            col_flags = _table_has_columns(
                cur,
                MYSQL_DB,
                "inventory_policies",
                ["dist_q_event", "dist_reason", "backlog_qty"],
            )

            # KPIs + backlog (R + IMPO - R) por SKU desde tabla1
            # Nota: usamos `Código` como SKU en tabla1.
            # Si tu vista KPI no tiene eventos_12m, podés cambiar COALESCE(f.eventos_12m,0) por 0.
            cur.execute("""
                SELECT
                  f.sku,
                  f.smart_class,
                  f.z_servicio,
                  f.Stock_Posicion_universal AS stock_posicion,
                  f.stock_objetivo_dinamico AS stock_objetivo_dinamico,
                  f.moq,
                  f.multiplo_compra,
                  f.p_m_12m,
                  f.q_mean_12m,
                  f.sigma_q_12m,
                  f.reorder_point AS reorder_point_normal,
                  COALESCE(f.eventos_12m, 0) AS eventos_12m,
                  IFNULL(b.backlog_qty,0) AS backlog_qty
                FROM v_sku_kpis_final_v1_full f
                JOIN v_sku_model_selector_v1 s ON s.sku = f.sku
                LEFT JOIN (
                    SELECT
                        `Código` AS sku,
                        SUM(CASE WHEN `E/S` IN ('R','IMPO - R') THEN Cantidad ELSE 0 END) AS backlog_qty
                    FROM tabla1
                    WHERE `E/S` IN ('R','IMPO - R')
                    GROUP BY `Código`
                ) b ON b.sku = f.sku
                WHERE s.mc_enabled = 1
            """)
            rows = cur.fetchall()

            for r in rows:
                sku = r["sku"]
                smart_class = (r["smart_class"] or "").upper()

                z = float(r["z_servicio"] or 0.0)
                service = z_to_service(z) if z > 0 else 0.90
                service = min(max(service, 0.50), 0.995)

                stock_pos = float(r["stock_posicion"] or 0.0)  # asumimos stock libre
                stock_obj_dyn = float(r["stock_objetivo_dinamico"] or 0.0)
                moq = float(r["moq"] or 0.0)
                mult = int(r["multiplo_compra"] or 1)

                lam_m = float(r["p_m_12m"] or 0.0)
                q_mean = float(r["q_mean_12m"] or 0.0)
                q_sig = float(r["sigma_q_12m"] or 0.0)
                events_12m = int(r.get("eventos_12m") or 0)

                # NUEVO: backlog comprometido (R + IMPO - R)
                backlog_qty = float(r.get("backlog_qty") or 0.0)

                # Normal (desde vista)
                rop_normal: Optional[float] = None
                if r.get("reorder_point_normal") is not None:
                    try:
                        rop_normal = float(r["reorder_point_normal"])
                    except (TypeError, ValueError):
                        rop_normal = None

                # selector dist por SKU
                q_dist, q_reason = choose_q_event_dist(
                    smart_class=smart_class,
                    events_12m=events_12m,
                    lam_events_per_month=lam_m,
                    q_mean=q_mean,
                    q_sigma=q_sig,
                )

                # (1) MC para ROP (LT = 30)
                totals_lt, p_dem_gt0_lt = simulate_compound_poisson_totals(
                    horizon_days=LT_FIXED_DAYS,
                    lam_events_per_month=lam_m,
                    q_mean=q_mean,
                    q_sigma=q_sig,
                    n_sims=N_SIMS,
                    q_event_dist=q_dist,
                )
                mean_lt, _, _, rop_mc = stats_from_totals(totals_lt, service)
                ss_mc = max(0.0, rop_mc - mean_lt)

                # (2) MC para Stock Objetivo (H = 75)
                totals_h, _ = simulate_compound_poisson_totals(
                    horizon_days=HORIZON_DAYS,
                    lam_events_per_month=lam_m,
                    q_mean=q_mean,
                    q_sigma=q_sig,
                    n_sims=N_SIMS,
                    q_event_dist=q_dist,
                )
                _, _, _, stock_obj_mc = stats_from_totals(totals_h, service)

                # model_used + ROP final
                if smart_class == "CRITICO" and rop_normal is not None:
                    rop_final = max(rop_normal, rop_mc)
                    model_used = "MC_MAX"
                else:
                    rop_final = rop_mc
                    model_used = "MC"

                # Objetivo final
                if smart_class == "CRITICO":
                    stock_obj_final = max(stock_obj_dyn, stock_obj_mc)
                else:
                    stock_obj_final = stock_obj_mc

                # ---------
                # Qty final (AJUSTADO POR BACKLOG)
                # Demanda a cubrir = objetivo + backlog
                # ---------
                qty_raw = max(0.0, (stock_obj_final + backlog_qty) - stock_pos)

                if qty_raw > 0:
                    if moq > 0 and qty_raw < moq:
                        qty_raw = moq
                    if mult > 1:
                        qty_raw = math.ceil(qty_raw / mult) * mult

                qty_final = qty_raw

                # ---- UPSERT ----
                base_cols = [
                    "sku_id", "location_id", "calculation_date",
                    "model_used", "n_sims",
                    "reorder_point",
                    "reorder_point_mc", "safety_stock_mc", "p_stockout_mc",
                    "stock_objetivo_mc",
                    "stock_objetivo_final",
                    "reorder_point_final",
                    "stock_posicion",
                    "suggested_qty_final",
                    "mc_updated_at",
                ]
                base_vals = [
                    sku, LOCATION_ID, today,
                    model_used, N_SIMS,
                    rop_normal,
                    rop_mc, ss_mc, p_dem_gt0_lt,
                    stock_obj_mc,
                    stock_obj_final,
                    rop_final,
                    stock_pos,
                    qty_final,
                ]

                extra_cols = []
                extra_vals = []
                if col_flags.get("dist_q_event"):
                    extra_cols.append("dist_q_event")
                    extra_vals.append(q_dist.upper())
                if col_flags.get("dist_reason"):
                    extra_cols.append("dist_reason")
                    extra_vals.append(q_reason[:255])
                # opcional: guardar backlog_qty si agregaste la columna
                if col_flags.get("backlog_qty"):
                    extra_cols.append("backlog_qty")
                    extra_vals.append(backlog_qty)

                cols = base_cols[:-1] + extra_cols + [base_cols[-1]]  # extras antes de mc_updated_at
                insert_cols_sql = ", ".join(cols)
                placeholders = ", ".join(["%s"] * (len(cols) - 1) + ["NOW()"])

                update_parts = [
                    "model_used=VALUES(model_used)",
                    "n_sims=VALUES(n_sims)",
                    "reorder_point=VALUES(reorder_point)",
                    "reorder_point_mc=VALUES(reorder_point_mc)",
                    "safety_stock_mc=VALUES(safety_stock_mc)",
                    "p_stockout_mc=VALUES(p_stockout_mc)",
                    "stock_objetivo_mc=VALUES(stock_objetivo_mc)",
                    "stock_objetivo_final=VALUES(stock_objetivo_final)",
                    "reorder_point_final=VALUES(reorder_point_final)",
                    "stock_posicion=VALUES(stock_posicion)",
                    "suggested_qty_final=VALUES(suggested_qty_final)",
                ]
                if col_flags.get("dist_q_event"):
                    update_parts.append("dist_q_event=VALUES(dist_q_event)")
                if col_flags.get("dist_reason"):
                    update_parts.append("dist_reason=VALUES(dist_reason)")
                if col_flags.get("backlog_qty"):
                    update_parts.append("backlog_qty=VALUES(backlog_qty)")
                update_parts.append("mc_updated_at=NOW()")
                update_sql = ",\n                       ".join(update_parts)

                params = base_vals + extra_vals

                cur.execute(f"""
                    INSERT INTO inventory_policies
                      ({insert_cols_sql})
                    VALUES
                      ({placeholders})
                    ON DUPLICATE KEY UPDATE
                       {update_sql}
                """, params)

            conn.commit()

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
