#!/usr/bin/env python3
"""
SS2 Full Pipeline - Ejecuta el pipeline completo SS2 PRO.

Orden: rebuild (opcional) -> classification -> mc -> policy -> scoring
Escribe en ss2_job_runs y ss2_job_logs para auditoría.

Uso:
  python run_full_pipeline.py [--asof YYYY-MM-DD] [--skip-rebuild] [--dry-run] [--no-sync-aws]

Si AWS_MYSQL_HOST está en .env, al final sincroniza resultados a AWS (para Stock HUD).
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
from pathlib import Path

# Asegurar que smartstock_mc_api esté en path para "from app.xxx"
_here = Path(__file__).resolve().parent  # smartstock_mc_api/
if str(_here) not in sys.path:
    sys.path.insert(0, str(_here))

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import pymysql
except ImportError:
    pymysql = None

try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None

TZ_NAME = "America/Argentina/Buenos_Aires"
DB_LOCK_NAME = os.getenv("SS2_DAILY_LOCK_NAME", "ss2_daily_job_lock")
DB_LOCK_TIMEOUT = int(os.getenv("SS2_DAILY_LOCK_TIMEOUT", "5"))
# Cobertura: review_days para horizonte MC (LT + review = meses). 120 = 6 meses.
MC_REVIEW_DAYS = int(os.getenv("MC_REVIEW_DAYS", "120"))


def today_ba() -> dt.date:
    if ZoneInfo is None:
        return dt.date.today()
    return dt.datetime.now(ZoneInfo(TZ_NAME)).date()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SS2 Full Pipeline: classification -> mc -> policy -> scoring"
    )
    p.add_argument("--asof", type=str, default=None, help="Fecha YYYY-MM-DD (default: hoy)")
    p.add_argument("--skip-rebuild", action="store_true", help="No ejecutar ss2_rebuild_from_tabla1")
    p.add_argument("--dry-run", action="store_true", help="No escribe en BD")
    p.add_argument("--no-lock", action="store_true", help="Desactiva DB lock")
    p.add_argument("--no-sync-aws", action="store_true", help="No sincronizar a AWS al final (aunque AWS_MYSQL_HOST esté configurado)")
    p.add_argument("--dotenv", type=str, default=None, help="Ruta a .env")
    return p.parse_args()


def load_env(dotenv_path: str | None) -> None:
    if load_dotenv is None:
        return
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)
    else:
        load_dotenv(override=False)


def get_conn():
    if pymysql is None:
        raise RuntimeError("pip install pymysql")
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", ""),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", ""),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", ""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def acquire_lock(lock_name: str, timeout: int) -> bool:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK(%s, %s) AS got", (lock_name, timeout))
            return int((cur.fetchone() or {}).get("got", 0)) == 1
    finally:
        conn.close()


def get_aws_conn():
    """Conexión a AWS si está configurado."""
    host = os.getenv("AWS_MYSQL_HOST", "")
    if not host:
        return None
    return pymysql.connect(
        host=host,
        port=int(os.getenv("AWS_MYSQL_PORT", os.getenv("MYSQL_PORT", "3306"))),
        user=os.getenv("AWS_MYSQL_USER", os.getenv("MYSQL_USER", "")),
        password=os.getenv("AWS_MYSQL_PASSWORD", os.getenv("MYSQL_PASSWORD", "")),
        database=os.getenv("AWS_MYSQL_DB", os.getenv("MYSQL_DB", "neobd")),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def sync_to_aws(src_conn, dry_run: bool) -> bool:
    """Copia tablas SS2 de src a AWS. Retorna True si se sincronizó."""
    aws = get_aws_conn()
    if aws is None:
        return False
    tables = ["ss2_sku_features_12m", "ss2_demand_classification", "ss2_demand_cache", "ss2_policy_results", "ss2_purchase_scores"]
    try:
        total = 0
        for t in tables:
            try:
                with src_conn.cursor() as cur:
                    cur.execute(f"SELECT * FROM `{t}`")
                    rows = cur.fetchall()
            except Exception:
                continue
            if not rows or dry_run:
                continue
            try:
                cols = list(rows[0].keys())
                ph = ", ".join(["%s"] * len(cols))
                col_list = ", ".join(f"`{c}`" for c in cols)
                sql = f"REPLACE INTO `{t}` ({col_list}) VALUES ({ph})"
                with aws.cursor() as cur:
                    for r in rows:
                        cur.execute(sql, [r[c] for c in cols])
                aws.commit()
                total += len(rows)
                print(f"  Sync AWS: {t} -> {len(rows)} filas")
            except Exception as e:
                print(f"  WARN: Sync {t} a AWS falló: {e}")
        return total > 0
    finally:
        aws.close()


def release_lock(lock_name: str) -> None:
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT RELEASE_LOCK(%s)", (lock_name,))
    finally:
        conn.close()


def ensure_job_tables(conn) -> bool:
    """Verifica que existan ss2_job_runs y ss2_job_logs."""
    with conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM INFORMATION_SCHEMA.TABLES "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'ss2_job_runs'"
        )
        if int((cur.fetchone() or {}).get("n", 0)) == 0:
            return False
    return True


def create_run(conn, asof: dt.date) -> int | None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ss2_job_runs (asof_date, status, started_at, pipeline_version)
            VALUES (%s, 'RUNNING', NOW(), 'ss2_pro_v1')
            """,
            (asof,),
        )
        return int(cur.lastrowid)


def log_step(conn, run_id: int, step: str, status: str, n_processed: int | None, message: str | None, started_at: dt.datetime):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO ss2_job_logs (run_id, step_name, status, started_at, finished_at, duration_sec, n_processed, message)
            VALUES (%s, %s, %s, %s, NOW(), TIMESTAMPDIFF(SECOND, %s, NOW()), %s, %s)
            """,
            (run_id, step, status, started_at, started_at, n_processed, (message or "")[:500]),
        )


def finish_run(conn, run_id: int, status: str, n_classification: int, n_mc: int, n_policy: int, n_scoring: int, n_mc_enabled: int | None, error_msg: str | None, failed_step: str | None):
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE ss2_job_runs
            SET status = %s, finished_at = NOW(),
                n_skus_classification = %s, n_skus_demand_cache = %s,
                n_skus_policy = %s, n_skus_scoring = %s, n_mc_enabled = %s,
                error_message = %s, failed_step = %s
            WHERE run_id = %s
            """,
            (status, n_classification, n_mc, n_policy, n_scoring, n_mc_enabled, error_msg, failed_step, run_id),
        )


def run_rebuild(asof: dt.date) -> None:
    """Ejecuta ss2_rebuild_from_tabla1 si existe."""
    rebuild_py = _here.parent / "ss2" / "scripts" / "ss2_rebuild_from_tabla1.py"
    if not rebuild_py.exists():
        print("WARN: ss2_rebuild_from_tabla1.py no encontrado. Saltando rebuild.")
        return
    import subprocess
    subprocess.run([sys.executable, str(rebuild_py)], check=True)


def run_classification(conn) -> tuple[int, list]:
    from app.demand_classification import run_demand_classification_batch
    return run_demand_classification_batch(conn)


# Fallback cuando v_analisis_sku_excel_mc no existe o está rota (ej. en AWS)
# Usa: parametros_sku + v_sku_features_12m + v_stock_estado_unidades + ss2_demand_classification
FETCH_ACTIVE_SKUS_SQL_SS2 = """
SELECT
  p.sku,
  COALESCE(p.activo, 1) AS activo,
  NULL AS model,
  NULL AS tipo_demanda,
  (1 - COALESCE(f.p_event, 0)) AS PctZero,
  COALESCE(f.p_event, COALESCE(f.events_12m, 0) / 12.0) AS p_event,
  COALESCE(f.q_mean_event, 0) AS q_mean_event,
  COALESCE(f.q_sd_event, 0) AS q_sd_event,
  COALESCE(f.demanda_prom_mensual_12m, f.total_units_12m / 12.0, 0) AS Forecast_m,
  0 AS sigma_mensual_12m,
  (COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0)) AS stock_posicion,
  60 / 30.0 AS lt_months,
  60 AS lt_days,
  NULL AS service_target,
  1 AS moq,
  1 AS multiplo_compra,
  NULL AS q_cap,
  365 AS dias_observados,
  COALESCE(f.events_12m, 0) AS eventos_12m,
  COALESCE(f.total_units_12m, 0) AS unidades_12m,
  COALESCE(f.q_mean_event, 0) AS mu_unidades_evento,
  COALESCE(f.q_sd_event, 0) AS sigma_unidades_evento,
  NULL AS mu_gap_dias,
  NULL AS sigma_gap_dias,
  dc.demand_class,
  dc.lifecycle_state
FROM parametros_sku p
LEFT JOIN v_sku_features_12m f ON f.SKU = p.sku
LEFT JOIN v_stock_estado_unidades se ON se.sku = p.sku
LEFT JOIN ss2_demand_classification dc ON dc.sku = p.sku
WHERE COALESCE(p.activo, 1) = 1 AND COALESCE(p.discontinuado, 0) = 0
  AND COALESCE(f.events_12m, 0) + COALESCE(f.total_units_12m, 0) > 0
"""

# Fallback con v_sku_classification_input (si v_sku_features_12m no existe)
FETCH_ACTIVE_SKUS_SQL_SS2_CI = """
SELECT
  p.sku,
  COALESCE(p.activo, 1) AS activo,
  NULL AS model,
  NULL AS tipo_demanda,
  (1 - COALESCE(ci.eventos_12m, 0) / 12.0) AS PctZero,
  COALESCE(ci.eventos_12m, 0) / 12.0 AS p_event,
  COALESCE(ci.mu_unidades_evento, 0) AS q_mean_event,
  COALESCE(ci.sigma_unidades_evento, 0) AS q_sd_event,
  COALESCE(ci.unidades_12m, 0) / 12.0 AS Forecast_m,
  0 AS sigma_mensual_12m,
  (COALESCE(se.stock_libre_deposito, 0) + COALESCE(se.impo_libre, 0)) AS stock_posicion,
  60 / 30.0 AS lt_months,
  60 AS lt_days,
  NULL AS service_target,
  1 AS moq,
  1 AS multiplo_compra,
  NULL AS q_cap,
  COALESCE(ci.dias_observados, 365) AS dias_observados,
  COALESCE(ci.eventos_12m, 0) AS eventos_12m,
  COALESCE(ci.unidades_12m, 0) AS unidades_12m,
  COALESCE(ci.mu_unidades_evento, 0) AS mu_unidades_evento,
  COALESCE(ci.sigma_unidades_evento, 0) AS sigma_unidades_evento,
  ci.mu_gap_dias,
  ci.sigma_gap_dias,
  dc.demand_class,
  dc.lifecycle_state
FROM parametros_sku p
LEFT JOIN v_sku_classification_input ci ON ci.sku = p.sku
LEFT JOIN v_stock_estado_unidades se ON se.sku = p.sku
LEFT JOIN ss2_demand_classification dc ON dc.sku = p.sku
WHERE COALESCE(p.activo, 1) = 1 AND COALESCE(p.discontinuado, 0) = 0
  AND (COALESCE(ci.eventos_12m, 0) > 0 OR COALESCE(ci.unidades_12m, 0) > 0)
"""

# Fallback mínimo: solo parametros_sku + classification (sin filtro de features)
FETCH_ACTIVE_SKUS_SQL_SS2_MIN = """
SELECT
  p.sku,
  COALESCE(p.activo, 1) AS activo,
  NULL AS model,
  NULL AS tipo_demanda,
  0.5 AS PctZero,
  0.5 AS p_event,
  1 AS q_mean_event,
  0 AS q_sd_event,
  0 AS Forecast_m,
  0 AS sigma_mensual_12m,
  0 AS stock_posicion,
  60 / 30.0 AS lt_months,
  60 AS lt_days,
  NULL AS service_target,
  1 AS moq,
  1 AS multiplo_compra,
  NULL AS q_cap,
  365 AS dias_observados,
  0 AS eventos_12m,
  0 AS unidades_12m,
  1 AS mu_unidades_evento,
  0 AS sigma_unidades_evento,
  NULL AS mu_gap_dias,
  NULL AS sigma_gap_dias,
  dc.demand_class,
  dc.lifecycle_state
FROM parametros_sku p
LEFT JOIN ss2_demand_classification dc ON dc.sku = p.sku
WHERE COALESCE(p.activo, 1) = 1 AND COALESCE(p.discontinuado, 0) = 0
"""


def run_mc(conn) -> tuple[int, int, int]:
    """Ejecuta MC vía lógica de main. Retorna (updated, simulated, skipped)."""
    from app.main import FETCH_ACTIVE_SKUS_SQL_WITH_DC, FETCH_ACTIVE_SKUS_SQL
    from app.main import compute_one, _upsert_demand_cache, _upsert_legacy_cache

    updated = simulated = skipped = 0
    rows = []
    with conn.cursor() as cur:
        last_err = None
        for sql, name in [
            (FETCH_ACTIVE_SKUS_SQL_WITH_DC, "v_analisis_sku_excel_mc+dc"),
            (FETCH_ACTIVE_SKUS_SQL, "v_analisis_sku_excel_mc"),
            (FETCH_ACTIVE_SKUS_SQL_SS2, "ss2 (v_sku_features_12m)"),
            (FETCH_ACTIVE_SKUS_SQL_SS2_CI, "ss2 (v_sku_classification_input)"),
            (FETCH_ACTIVE_SKUS_SQL_SS2_MIN, "ss2 (solo parametros_sku)"),
        ]:
            try:
                cur.execute(sql)
                rows = cur.fetchall()
                if rows:
                    if "ss2" in name:
                        print(f"  MC: usando fallback {name} (v_analisis_sku_excel_mc no disponible)")
                    break
            except Exception as e:
                last_err = str(e)[:120]
                continue

    if not rows:
        msg = (
            "No se pudo obtener SKUs para MC. Verificá: parametros_sku, ss2_demand_classification. "
            "Para features: v_sku_features_12m o v_sku_classification_input."
        )
        if last_err:
            msg += f" Último error: {last_err}"
        raise RuntimeError(msg)

    n_total = len(rows)
    print(f"  MC: procesando {n_total} SKUs (8000 sims c/u, horizonte={60 + MC_REVIEW_DAYS}d ~{(60 + MC_REVIEW_DAYS) // 30}m, puede tardar varios min)...")
    for i, r in enumerate(rows):
        try:
            out = compute_one(conn, r, 8000, MC_REVIEW_DAYS, None, force=False)
            if int(out.get("mc_enabled", 0)) == 1:
                simulated += 1
            else:
                skipped += 1
            _upsert_demand_cache(conn, out)
            _upsert_legacy_cache(conn, out)
            updated += 1
            if (i + 1) % 50 == 0 or (i + 1) == n_total:
                print(f"  MC: {i + 1}/{n_total} SKUs...")
        except Exception:
            pass  # continuar con otros SKUs

    return updated, simulated, skipped


def run_policy(conn) -> tuple[int, list]:
    from app.policy_engine import run_policy_engine_batch
    return run_policy_engine_batch(conn)


def run_scoring(conn) -> tuple[int, list]:
    from app.purchase_scoring import run_purchase_scoring_batch
    return run_purchase_scoring_batch(conn)


def main() -> None:
    args = parse_args()
    load_env(args.dotenv)

    asof_str = args.asof or today_ba().strftime("%Y-%m-%d")
    try:
        asof = dt.datetime.strptime(asof_str, "%Y-%m-%d").date()
    except ValueError:
        sys.exit(f"Invalid --asof. Use YYYY-MM-DD. Got: {asof_str}")

    print(f"\n=== SS2 Full Pipeline | asof={asof} ===\n")

    lock_acquired = False
    if not args.no_lock and not args.dry_run:
        lock_acquired = acquire_lock(DB_LOCK_NAME, DB_LOCK_TIMEOUT)
        if not lock_acquired:
            sys.exit(f"ABORT: Lock '{DB_LOCK_NAME}' no disponible. Otro job en ejecución?")

    conn = None
    run_id = None
    n_class, n_mc, n_policy, n_scoring = 0, 0, 0, 0
    n_mc_enabled = None
    failed_step = None
    err_msg = None

    try:
        # 1) Rebuild (opcional) - corre ANTES de abrir conn (evita "Lost connection" por timeout)
        t0_rebuild = dt.datetime.now()
        if not args.skip_rebuild:
            run_rebuild(asof)
            print("  Rebuild: OK")

        # Abrir conexión DESPUÉS del rebuild
        conn = get_conn()

        if not ensure_job_tables(conn):
            print("WARN: ss2_job_runs no existe. Ejecutá ddl_ss2_job_runs.sql. Continuando sin logs.")

        if not args.dry_run and ensure_job_tables(conn):
            run_id = create_run(conn, asof)
            conn.commit()
            if not args.skip_rebuild:
                log_step(conn, run_id, "rebuild", "OK", None, "ss2_rebuild_from_tabla1", t0_rebuild)
                conn.commit()

        # 2) Classification
        print("  Classification: iniciando...")
        t0 = dt.datetime.now()
        try:
            n_class, _ = run_classification(conn)
            conn.commit()
            if run_id:
                log_step(conn, run_id, "classification", "OK", n_class, None, t0)
                conn.commit()
            print(f"  Classification: {n_class} SKUs")
        except Exception as e:
            err_msg = str(e)
            failed_step = "classification"
            if run_id:
                log_step(conn, run_id, "classification", "ERROR", None, err_msg, t0)
                conn.commit()
            raise

        # 3) Monte Carlo (el paso más lento: ~8000 sims por SKU)
        print("  MC: iniciando (puede tardar varios minutos)...")
        t0 = dt.datetime.now()
        try:
            n_mc, n_mc_enabled, _ = run_mc(conn)
            conn.commit()
            if run_id:
                log_step(conn, run_id, "demand_cache", "OK", n_mc, f"mc_enabled={n_mc_enabled}", t0)
                conn.commit()
            print(f"  MC: {n_mc} updated, {n_mc_enabled} con Monte Carlo")
        except Exception as e:
            err_msg = str(e)
            failed_step = "demand_cache"
            if run_id:
                log_step(conn, run_id, "demand_cache", "ERROR", None, err_msg, t0)
                conn.commit()
            raise

        # 4) Policy
        print("  Policy: iniciando...")
        t0 = dt.datetime.now()
        try:
            n_policy, _ = run_policy(conn)
            conn.commit()
            if run_id:
                log_step(conn, run_id, "policy", "OK", n_policy, None, t0)
                conn.commit()
            print(f"  Policy: {n_policy} SKUs")
        except Exception as e:
            err_msg = str(e)
            failed_step = "policy"
            if run_id:
                log_step(conn, run_id, "policy", "ERROR", None, err_msg, t0)
                conn.commit()
            raise

        # 5) Scoring
        print("  Scoring: iniciando...")
        t0 = dt.datetime.now()
        try:
            n_scoring, _ = run_scoring(conn)
            conn.commit()
            if run_id:
                log_step(conn, run_id, "scoring", "OK", n_scoring, None, t0)
                conn.commit()
            print(f"  Scoring: {n_scoring} SKUs")
        except Exception as e:
            err_msg = str(e)
            failed_step = "scoring"
            if run_id:
                log_step(conn, run_id, "scoring", "ERROR", None, err_msg, t0)
                conn.commit()
            raise

        if run_id and not args.dry_run:
            finish_run(conn, run_id, "SUCCESS", n_class, n_mc, n_policy, n_scoring, n_mc_enabled, None, None)
            conn.commit()

        # 6) Sync opcional a AWS (para Stock HUD)
        if not args.no_sync_aws and os.getenv("AWS_MYSQL_HOST", "").strip():
            print("  Sync AWS: iniciando...")
            try:
                sync_to_aws(conn, args.dry_run)
            except Exception as e:
                print(f"  WARN: Sync AWS falló: {e}")

        print("\nOK: SS2 Full Pipeline completado.")

    except Exception as e:
        if run_id and not args.dry_run and conn:
            try:
                finish_run(conn, run_id, "FAILED", n_class, n_mc, n_policy, n_scoring, n_mc_enabled, str(e)[:500], failed_step)
                conn.commit()
            except Exception:
                pass
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass
        if lock_acquired:
            release_lock(DB_LOCK_NAME)


if __name__ == "__main__":
    main()
