# ss2_monte_carlo.py  (SS2 PRO writer)
# CORREGIDO + robusto:
# - asof por timezone AR (BA) si no se pasa --asof
# - usa location_id runtime (no constante) en create_run
# - llama SP daily refresh
# - VERIFICA inventory_policies(asof) y si falta: CLONA último snapshot a asof
# - (opcional) actualiza stock_posicion y backlog_qty del snapshot a asof

import os
import math
import random
import argparse
import datetime as dt
from typing import Tuple, List, Any, Optional

import pymysql
from dotenv import load_dotenv

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:
    ZoneInfo = None

load_dotenv()

TZ_NAME = "America/Argentina/Buenos_Aires"

MYSQL_HOST = os.getenv("MYSQL_HOST", "190.228.29.65")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "neolab")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "CHANGE_ME")  # ⚠️ NO pegues el real
MYSQL_DB = os.getenv("MYSQL_DB", "neobd")

LOCATION_ID_DEFAULT = int(os.getenv("SS2_LOCATION_ID", "1"))

N_SIMS = int(os.getenv("MC_N_SIMS", "20000"))
SEED = int(os.getenv("MC_SEED", "42"))
random.seed(SEED)

LT_DAYS_DEFAULT = int(os.getenv("MC_LT_DAYS", "45"))
REVIEW_DAYS_DEFAULT = int(os.getenv("MC_REVIEW_DAYS", "45"))

EVENT_SIZE_DIST = os.getenv("EVENT_SIZE_DIST", "auto").strip().lower()

ENGINE_VERSION = os.getenv("SS2_MC_ENGINE_VERSION", "ss2_mc_v1").strip()
NOTES = os.getenv("SS2_MC_RUN_NOTES", "daily run").strip()

MC_SELECTION_MODE = os.getenv("SS2_MC_SELECTION_MODE", "enabled_only").strip().lower()

# Si querés que el fallback además actualice stock/backlog en inventory_policies(asof)
ENABLE_SNAPSHOT_REFRESH_STOCK = os.getenv("SS2_SNAPSHOT_REFRESH_STOCK", "1").strip() not in ("0", "false", "no")


# -------------------------
# Math helpers
# -------------------------
def z_to_service(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def percentile(sorted_vals: List[float], p: float) -> float:
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
    if lam <= 0:
        return 0
    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


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
    if mean <= 0:
        return 1.0, 1.0
    if sd is None or sd <= 0:
        k = 1e6
        theta = mean / k
        return k, theta
    k = (mean / sd) ** 2
    theta = (sd ** 2) / mean
    return max(1e-6, k), max(1e-6, theta)


def _sample_gamma(mean: float, sd: float) -> float:
    if mean <= 0:
        return 0.0
    k, theta = _gamma_shape_scale_from_mean_sd(mean, sd)
    return random.gammavariate(k, theta)


# -------------------------
# Distribution choice
# -------------------------
def choose_q_event_dist(
    *,
    smart_class: str,
    events_12m: int,
    lam_events_per_month: float,
    q_mean: float,
    q_sigma: float,
) -> Tuple[str, str]:
    if EVENT_SIZE_DIST in ("lognormal", "truncnorm", "gamma"):
        return EVENT_SIZE_DIST, f"forced_by_env={EVENT_SIZE_DIST}"

    if q_mean is None or q_mean <= 0:
        return "gamma", "q_mean<=0 fallback"
    if q_sigma is None or q_sigma < 0:
        return "gamma", "q_sigma invalid fallback"
    if events_12m is not None and events_12m < 6:
        return "gamma", "events_12m<6 => gamma"

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
    d = (dist or "").lower()
    if d == "lognormal":
        return max(0.0, _sample_lognormal(q_mean, q_sigma))
    if d == "gamma":
        return max(0.0, _sample_gamma(q_mean, q_sigma))
    if d == "truncnorm":
        return max(0.0, _sample_truncnorm(q_mean, q_sigma))
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
    return totals, positive / n_sims


def stats_from_totals(totals_sorted: List[float], service: float) -> Tuple[float, float]:
    if not totals_sorted:
        return 0.0, 0.0
    mean = sum(totals_sorted) / len(totals_sorted)
    p_srv = percentile(totals_sorted, service)
    return mean, p_srv


# -------------------------
# DB helpers
# -------------------------
def get_conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def ensure_required_objects(cur):
    cur.execute("""
      SELECT COUNT(*) AS n
      FROM INFORMATION_SCHEMA.TABLES
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ss2_mc_runs'
    """)
    if int(cur.fetchone()["n"]) == 0:
        raise RuntimeError("Missing table ss2_mc_runs (create it first).")

    cur.execute("""
      SELECT COUNT(*) AS n
      FROM INFORMATION_SCHEMA.TABLES
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ss2_mc_results'
    """)
    if int(cur.fetchone()["n"]) == 0:
        raise RuntimeError("Missing table ss2_mc_results (create it first).")

    cur.execute("""
      SELECT COUNT(*) AS n
      FROM INFORMATION_SCHEMA.TABLES
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ss2_mc_latest'
    """)
    if int(cur.fetchone()["n"]) == 0:
        raise RuntimeError("Missing table ss2_mc_latest (create it first).")

    cur.execute("""
      SELECT COUNT(*) AS n
      FROM INFORMATION_SCHEMA.VIEWS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ss2_v_backlog_open'
    """)
    if int(cur.fetchone()["n"]) == 0:
        print("WARN: ss2_v_backlog_open not found. backlog will be assumed 0.")


def ensure_sp_exists(cur, sp_name: str) -> None:
    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM INFORMATION_SCHEMA.ROUTINES
        WHERE ROUTINE_SCHEMA = DATABASE()
          AND ROUTINE_TYPE = 'PROCEDURE'
          AND ROUTINE_NAME = %s
        """,
        (sp_name,),
    )
    if int(cur.fetchone()["n"]) == 0:
        raise RuntimeError(f"Missing stored procedure {sp_name}. Create it first.")


def create_run(cur, asof: dt.date, location_id: int, lt_days: int, review_days: int, horizon_days: int) -> int:
    cur.execute(
        """
        INSERT INTO ss2_mc_runs (asof_date, location_id, n_sims, seed, lt_days, review_days, horizon_days, engine_version, notes)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (asof, location_id, N_SIMS, SEED, lt_days, review_days, horizon_days, ENGINE_VERSION, NOTES),
    )
    return int(cur.lastrowid)


def refresh_latest(cur):
    cur.execute(
        """
        REPLACE INTO ss2_mc_latest (sku, location_id, asof_date, run_id, updated_at)
        SELECT r.sku, r.location_id, r.asof_date, r.run_id, r.updated_at
        FROM ss2_mc_results r
        JOIN (
          SELECT sku, location_id, MAX(asof_date) AS max_asof
          FROM ss2_mc_results
          GROUP BY sku, location_id
        ) x
          ON x.sku = r.sku
         AND x.location_id = r.location_id
         AND x.max_asof = r.asof_date
        JOIN (
          SELECT sku, location_id, asof_date, MAX(updated_at) AS max_upd
          FROM ss2_mc_results
          GROUP BY sku, location_id, asof_date
        ) u
          ON u.sku = r.sku
         AND u.location_id = r.location_id
         AND u.asof_date = r.asof_date
         AND u.max_upd = r.updated_at
        """
    )


def call_daily_refresh(cur, asof: dt.date, location_id: int) -> None:
    ensure_sp_exists(cur, "sp_ss2_daily_refresh")
    cur.execute("CALL sp_ss2_daily_refresh(%s, %s)", (asof, location_id))


def inventory_policies_count(cur, asof: dt.date, location_id: int) -> int:
    cur.execute(
        """
        SELECT COUNT(*) AS n
        FROM inventory_policies
        WHERE location_id = %s AND calculation_date = %s
        """,
        (location_id, asof),
    )
    return int(cur.fetchone()["n"])


def inventory_policies_max_date(cur, location_id: int) -> Optional[dt.date]:
    cur.execute(
        """
        SELECT MAX(calculation_date) AS d
        FROM inventory_policies
        WHERE location_id = %s
        """,
        (location_id,),
    )
    row = cur.fetchone()
    return row["d"]


def clone_inventory_policies_snapshot(cur, from_date: dt.date, to_date: dt.date, location_id: int) -> int:
    """
    Clona snapshot completo de inventory_policies de from_date -> to_date para location_id.
    Mantiene ROP/targets/model/etc tal cual.
    """
    sql = """
    INSERT INTO inventory_policies
    (
      sku_id, location_id, calculation_date,
      mu_daily, sigma_daily, lead_time_days, z, mu_lt, sigma_lt,
      reorder_point, safety_stock, stock_posicion, suggested_qty,
      model_used, n_sims, reorder_point_mc, safety_stock_mc, p_stockout_mc, p95_demand_lt,
      reorder_point_final, suggested_qty_final, mc_updated_at,
      stock_objetivo_mc, stock_objetivo_final,
      dist_q_event, dist_reason, backlog_qty
    )
    SELECT
      sku_id, location_id, %s AS calculation_date,
      mu_daily, sigma_daily, lead_time_days, z, mu_lt, sigma_lt,
      reorder_point, safety_stock, stock_posicion, suggested_qty,
      model_used, n_sims, reorder_point_mc, safety_stock_mc, p_stockout_mc, p95_demand_lt,
      reorder_point_final, suggested_qty_final, mc_updated_at,
      stock_objetivo_mc, stock_objetivo_final,
      dist_q_event, dist_reason, backlog_qty
    FROM inventory_policies
    WHERE location_id = %s AND calculation_date = %s
    ON DUPLICATE KEY UPDATE
      mu_daily=VALUES(mu_daily),
      sigma_daily=VALUES(sigma_daily),
      lead_time_days=VALUES(lead_time_days),
      z=VALUES(z),
      mu_lt=VALUES(mu_lt),
      sigma_lt=VALUES(sigma_lt),
      reorder_point=VALUES(reorder_point),
      safety_stock=VALUES(safety_stock),
      stock_posicion=VALUES(stock_posicion),
      suggested_qty=VALUES(suggested_qty),
      model_used=VALUES(model_used),
      n_sims=VALUES(n_sims),
      reorder_point_mc=VALUES(reorder_point_mc),
      safety_stock_mc=VALUES(safety_stock_mc),
      p_stockout_mc=VALUES(p_stockout_mc),
      p95_demand_lt=VALUES(p95_demand_lt),
      reorder_point_final=VALUES(reorder_point_final),
      suggested_qty_final=VALUES(suggested_qty_final),
      mc_updated_at=VALUES(mc_updated_at),
      stock_objetivo_mc=VALUES(stock_objetivo_mc),
      stock_objetivo_final=VALUES(stock_objetivo_final),
      dist_q_event=VALUES(dist_q_event),
      dist_reason=VALUES(dist_reason),
      backlog_qty=VALUES(backlog_qty);
    """
    cur.execute(sql, (to_date, location_id, from_date))
    return int(cur.rowcount)


def snapshot_refresh_stock_and_backlog(cur, asof: dt.date, location_id: int) -> None:
    """
    Actualiza stock_posicion/backlog_qty en inventory_policies(asof) desde vistas,
    si existen. (No falla si no están.)
    """
    # Stock
    cur.execute("""
      SELECT COUNT(*) AS n
      FROM INFORMATION_SCHEMA.VIEWS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ss2_v_stock_enriched'
    """)
    if int(cur.fetchone()["n"]) > 0:
        cur.execute(
            """
            UPDATE inventory_policies ip
            JOIN ss2_v_stock_enriched vs
              ON vs.sku = ip.sku_id
            SET ip.stock_posicion = IFNULL(vs.virtual_available, 0)
            WHERE ip.location_id = %s AND ip.calculation_date = %s
            """,
            (location_id, asof),
        )

    # Backlog
    cur.execute("""
      SELECT COUNT(*) AS n
      FROM INFORMATION_SCHEMA.VIEWS
      WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ss2_v_backlog_open'
    """)
    if int(cur.fetchone()["n"]) > 0:
        cur.execute(
            """
            UPDATE inventory_policies ip
            LEFT JOIN ss2_v_backlog_open bo
              ON bo.sku = ip.sku_id
            SET ip.backlog_qty = IFNULL(bo.backlog_qty, 0)
            WHERE ip.location_id = %s AND ip.calculation_date = %s
            """,
            (location_id, asof),
        )


# -------------------------
# CLI
# -------------------------
def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SS2 Monte Carlo writer (ss2_mc_results + ss2_mc_latest) + daily refresh.")
    p.add_argument("--dry-run", action="store_true", help="No escribe en BD (solo calcula y muestra un resumen).")
    p.add_argument("--asof", type=str, default=None, help="Fecha asof YYYY-MM-DD (default: hoy AR/BA).")
    p.add_argument("--location-id", type=int, default=LOCATION_ID_DEFAULT, help="Location ID (default: env SS2_LOCATION_ID o 1).")
    return p.parse_args()


def today_ba() -> dt.date:
    if ZoneInfo is None:
        return dt.date.today()
    return dt.datetime.now(ZoneInfo(TZ_NAME)).date()


def parse_asof(asof_str: Optional[str]) -> dt.date:
    if not asof_str:
        return today_ba()
    try:
        return dt.datetime.strptime(asof_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid --asof format. Use YYYY-MM-DD. Got: {asof_str}") from e


# -------------------------
# Main
# -------------------------
def main():
    args = parse_args()
    asof = parse_asof(args.asof)
    location_id = int(args.location_id)
    dry_run = bool(args.dry_run)

    conn = get_conn()
    try:
        with conn.cursor() as cur:
            ensure_required_objects(cur)

            base_sql = """
                SELECT
                  p.sku,
                  IFNULL(p.service_z, 1.65) AS z,
                  IFNULL(p.moq, 1) AS moq,
                  IFNULL(p.pack_multiple, 1) AS pack_multiple,
                  IFNULL(p.lead_time_days, %s) AS lt_days_sku,
                  IFNULL(p.review_days, %s) AS review_days_sku,

                  IFNULL(vs.virtual_available, 0) AS stock_pos,
                  {backlog_expr} AS backlog_open_qty,

                  IFNULL(f.events_12m, 0) AS events_12m,
                  IFNULL(f.total_units_12m, 0) AS total_units_12m,

                  '' AS smart_class

                FROM ss2_v_policy_effective2 p
                LEFT JOIN ss2_v_stock_enriched vs
                  ON vs.sku = p.sku
                LEFT JOIN ss2_sku_features_12m f
                  ON f.asof_date = %s AND f.sku = p.sku
                {backlog_join}
                WHERE p.is_active = 1
            """

            # backlog join opcional si existe view
            cur.execute("""
              SELECT COUNT(*) AS n
              FROM INFORMATION_SCHEMA.VIEWS
              WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ss2_v_backlog_open'
            """)
            has_backlog_view = int(cur.fetchone()["n"]) > 0

            backlog_join = ""
            backlog_expr = "0"
            if has_backlog_view:
                backlog_join = "LEFT JOIN ss2_v_backlog_open bo ON bo.sku = p.sku"
                backlog_expr = "IFNULL(bo.backlog_qty, 0)"

            sql = base_sql.format(backlog_join=backlog_join, backlog_expr=backlog_expr)

            # Filtro selección MC
            if MC_SELECTION_MODE == "enabled_only":
                sql += " AND IFNULL(f.events_12m,0) > 0 AND IFNULL(f.total_units_12m,0) > 0 "
            elif MC_SELECTION_MODE == "all_active":
                pass
            else:
                raise RuntimeError(f"Invalid SS2_MC_SELECTION_MODE={MC_SELECTION_MODE}")

            cur.execute(sql, (LT_DAYS_DEFAULT, REVIEW_DAYS_DEFAULT, asof))
            rows = cur.fetchall()

            if not rows:
                print("No SKUs selected for MC run (check SS2_MC_SELECTION_MODE and features table).")
                conn.rollback()
                return

            run_id = None
            if not dry_run:
                run_id = create_run(
                    cur,
                    asof=asof,
                    location_id=location_id,
                    lt_days=LT_DAYS_DEFAULT,
                    review_days=REVIEW_DAYS_DEFAULT,
                    horizon_days=LT_DAYS_DEFAULT + REVIEW_DAYS_DEFAULT,
                )

            results: List[Tuple[Any, ...]] = []

            n_pos = 0
            max_sug = 0

            for r in rows:
                sku = r["sku"]

                z = float(r["z"] or 0.0)
                service = z_to_service(z) if z > 0 else 0.90
                service = min(max(service, 0.50), 0.995)

                events_12m = int(r["events_12m"] or 0)
                total_units_12m = float(r["total_units_12m"] or 0.0)

                lam_m = events_12m / 12.0
                q_mean_raw = (total_units_12m / events_12m) if events_12m > 0 else 0.0

                if events_12m > 0:
                    prior_mean = 1.0
                    alpha = min(1.0, events_12m / 6.0)
                    q_mean = alpha * q_mean_raw + (1 - alpha) * prior_mean
                else:
                    q_mean = 0.0
                    alpha = 0.0

                if events_12m <= 3:
                    q_sigma = q_mean
                else:
                    q_sigma = max(0.5, 0.75 * q_mean)

                smart_class = (r["smart_class"] or "").upper()

                stock_pos = float(r["stock_pos"] or 0.0)
                backlog_open_qty = float(r["backlog_open_qty"] or 0.0)

                moq = int(r["moq"] or 1)
                multiplo = int(r["pack_multiple"] or 1)
                multiplo = max(1, multiplo)

                lt_days = int(r["lt_days_sku"] or LT_DAYS_DEFAULT)
                review_days = int(r["review_days_sku"] or REVIEW_DAYS_DEFAULT)
                horizon_days = max(1, lt_days + review_days)

                q_dist, q_reason = choose_q_event_dist(
                    smart_class=smart_class,
                    events_12m=events_12m,
                    lam_events_per_month=lam_m,
                    q_mean=q_mean,
                    q_sigma=q_sigma,
                )
                q_reason = f"q=total_units/events (upe={q_mean:.3f}, raw={q_mean_raw:.3f}, a={alpha:.2f}, sig={q_sigma:.3f}) | {q_reason}"

                totals_h, _ = simulate_compound_poisson_totals(
                    horizon_days=horizon_days,
                    lam_events_per_month=lam_m,
                    q_mean=q_mean,
                    q_sigma=q_sigma,
                    n_sims=N_SIMS,
                    q_event_dist=q_dist,
                )
                _, target_mc = stats_from_totals(totals_h, service)

                qty_raw = max(0.0, (target_mc + backlog_open_qty) - stock_pos)

                if qty_raw > 0:
                    if moq > 0 and qty_raw < moq:
                        qty_raw = float(moq)
                    qty_rounded = int(math.ceil(qty_raw / multiplo) * multiplo)
                else:
                    qty_rounded = 0

                if qty_rounded > 0:
                    n_pos += 1
                    max_sug = max(max_sug, qty_rounded)

                service_prob = float(service)
                p_stockout = max(0.0, min(1.0, 1.0 - service_prob))

                demand_p50 = percentile(totals_h, 0.50)
                demand_p90 = percentile(totals_h, 0.90)
                demand_p95 = percentile(totals_h, 0.95)
                demand_p97 = percentile(totals_h, 0.97)
                demand_p99 = percentile(totals_h, 0.99)

                if not dry_run:
                    results.append((
                        run_id, asof, sku, location_id,
                        N_SIMS,
                        lam_m, q_mean, q_sigma,
                        service_prob, 1, (q_reason or "")[:255],
                        demand_p50, demand_p90, demand_p95, demand_p97, demand_p99,
                        target_mc, qty_raw,
                        p_stockout, None, None,
                        moq, multiplo, None,
                        None, None, None, None,
                        dt.datetime.now()
                    ))

            print(f"MC computed. asof={asof} location_id={location_id} skus={len(rows)} n_pos={n_pos} max_sug={max_sug} dry_run={dry_run}")

            if dry_run:
                conn.rollback()
                return

            insert_sql = """
                INSERT INTO ss2_mc_results (
                  run_id, asof_date, sku, location_id,
                  n_sims,
                  lambda_eventos_mes, q_mean_event, q_sd_event,
                  service_prob, mc_enabled, mc_reason,
                  demand_p50, demand_p90, demand_p95, demand_p97, demand_p99,
                  stock_objetivo_mc, qty_recomendada_mc,
                  p_stockout, exp_lost_units, exp_lost_margin_usd,
                  moq, multiplo_compra, q_cap,
                  criticidad, service_prob_usado, service_prob_override, service_prob_auto,
                  updated_at
                ) VALUES (
                  %s,%s,%s,%s,
                  %s,
                  %s,%s,%s,
                  %s,%s,%s,
                  %s,%s,%s,%s,%s,
                  %s,%s,
                  %s,%s,%s,
                  %s,%s,%s,
                  %s,%s,%s,%s,
                  %s
                )
                ON DUPLICATE KEY UPDATE
                  run_id=VALUES(run_id),
                  n_sims=VALUES(n_sims),
                  lambda_eventos_mes=VALUES(lambda_eventos_mes),
                  q_mean_event=VALUES(q_mean_event),
                  q_sd_event=VALUES(q_sd_event),
                  service_prob=VALUES(service_prob),
                  mc_enabled=VALUES(mc_enabled),
                  mc_reason=VALUES(mc_reason),
                  demand_p50=VALUES(demand_p50),
                  demand_p90=VALUES(demand_p90),
                  demand_p95=VALUES(demand_p95),
                  demand_p97=VALUES(demand_p97),
                  demand_p99=VALUES(demand_p99),
                  stock_objetivo_mc=VALUES(stock_objetivo_mc),
                  qty_recomendada_mc=VALUES(qty_recomendada_mc),
                  p_stockout=VALUES(p_stockout),
                  exp_lost_units=VALUES(exp_lost_units),
                  exp_lost_margin_usd=VALUES(exp_lost_margin_usd),
                  moq=VALUES(moq),
                  multiplo_compra=VALUES(multiplo_compra),
                  q_cap=VALUES(q_cap),
                  criticidad=VALUES(criticidad),
                  service_prob_usado=VALUES(service_prob_usado),
                  service_prob_override=VALUES(service_prob_override),
                  service_prob_auto=VALUES(service_prob_auto),
                  updated_at=VALUES(updated_at)
            """
            cur.executemany(insert_sql, results)

            # latest
            refresh_latest(cur)

        # Commit MC results + latest
        conn.commit()

        # Daily refresh (SP) en su propia transacción
        with conn.cursor() as cur2:
            call_daily_refresh(cur2, asof, location_id)
        conn.commit()

        # --------- Fallback robusto: asegurar snapshot en inventory_policies(asof) ---------
        with conn.cursor() as cur3:
            n_asof = inventory_policies_count(cur3, asof, location_id)
            if n_asof <= 0:
                max_date = inventory_policies_max_date(cur3, location_id)
                if max_date is None:
                    raise RuntimeError("inventory_policies está vacío para este location_id; no puedo clonar snapshot.")
                if max_date > asof:
                    # raro: el max es futuro. igual intentamos crear asof desde ese max.
                    from_date = max_date
                else:
                    from_date = max_date

                print(f"WARN: inventory_policies NO tiene snapshot asof={asof}. Clonando desde {from_date} -> {asof} (location_id={location_id})")
                clone_inventory_policies_snapshot(cur3, from_date, asof, location_id)

                if ENABLE_SNAPSHOT_REFRESH_STOCK:
                    snapshot_refresh_stock_and_backlog(cur3, asof, location_id)

        conn.commit()

        print(f"OK SS2 MC + DAILY. run_id={run_id} SKUs processed={len(rows)} mode={MC_SELECTION_MODE}")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()