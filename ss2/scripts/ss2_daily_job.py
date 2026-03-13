# ss2_daily_job.py
import argparse
import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

try:
    # Python 3.9+
    from zoneinfo import ZoneInfo
except Exception:  # pragma: no cover
    ZoneInfo = None

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

try:
    import pymysql
except Exception:  # pragma: no cover
    pymysql = None


TZ_NAME = "America/Argentina/Buenos_Aires"
DB_LOCK_NAME = os.getenv("SS2_DAILY_LOCK_NAME", "ss2_daily_job_lock")
DB_LOCK_TIMEOUT_SEC = int(os.getenv("SS2_DAILY_LOCK_TIMEOUT", "5"))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="SS2 Daily Job: rebuild_from_tabla1 -> monte_carlo (+ verificación inventory_policies) + DB lock"
    )
    p.add_argument(
        "--asof",
        type=str,
        default=None,
        help="Fecha asof YYYY-MM-DD (default: hoy en America/Argentina/Buenos_Aires).",
    )
    p.add_argument(
        "--location-id",
        type=int,
        default=int(os.getenv("SS2_LOCATION_ID", "1")),
        help="Location ID (default: env SS2_LOCATION_ID o 1).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run para MC (no escribe en BD). Rebuild se ejecuta igual salvo --skip-rebuild.",
    )
    p.add_argument("--skip-rebuild", action="store_true", help="Saltea ss2_rebuild_from_tabla1.py")
    p.add_argument("--skip-mc", action="store_true", help="Saltea ss2_monte_carlo.py")

    # checks / DB
    p.add_argument(
        "--skip-db-check",
        action="store_true",
        help="No valida que inventory_policies tenga calculation_date=asof.",
    )
    p.add_argument(
        "--run-sp-refresh",
        action="store_true",
        help="Intenta ejecutar sp_ss2_daily_refresh al final (si existe).",
    )
    p.add_argument(
        "--sp-name",
        type=str,
        default=os.getenv("SS2_SP_REFRESH", "sp_ss2_daily_refresh"),
        help="Nombre del stored procedure de refresh (default: sp_ss2_daily_refresh).",
    )
    p.add_argument(
        "--dotenv",
        type=str,
        default=None,
        help="Ruta a .env (si no se especifica, intenta cargar .env en el directorio actual).",
    )

    # locking
    p.add_argument(
        "--no-lock",
        action="store_true",
        help="Desactiva el lock DB (no recomendado).",
    )
    p.add_argument(
        "--lock-name",
        type=str,
        default=DB_LOCK_NAME,
        help=f"Nombre del lock (default: env SS2_DAILY_LOCK_NAME o '{DB_LOCK_NAME}').",
    )
    p.add_argument(
        "--lock-timeout",
        type=int,
        default=DB_LOCK_TIMEOUT_SEC,
        help=f"Timeout en segundos para GET_LOCK (default: env SS2_DAILY_LOCK_TIMEOUT o {DB_LOCK_TIMEOUT_SEC}).",
    )
    return p.parse_args()


def today_ba() -> dt.date:
    """Fecha de 'hoy' en Argentina (BA), evitando UTC/system clock raro."""
    if ZoneInfo is None:
        return dt.date.today()
    return dt.datetime.now(ZoneInfo(TZ_NAME)).date()


def parse_asof(asof_str: str | None) -> dt.date:
    if not asof_str:
        return today_ba()
    try:
        return dt.datetime.strptime(asof_str, "%Y-%m-%d").date()
    except ValueError as e:
        raise SystemExit(f"Invalid --asof format. Use YYYY-MM-DD. Got: {asof_str}") from e


def run_step(cmd: list[str], step_name: str) -> None:
    print(f"\n=== {step_name} ===")
    print("CMD:", " ".join(cmd))
    proc = subprocess.run(cmd, text=True)
    if proc.returncode != 0:
        raise SystemExit(f"Step failed: {step_name} (exit={proc.returncode})")


def load_env(dotenv_path: str | None) -> None:
    if load_dotenv is None:
        return
    if dotenv_path:
        load_dotenv(dotenv_path, override=False)
        return
    # fallback: try local .env
    load_dotenv(override=False)


def get_db_conn():
    if pymysql is None:
        raise RuntimeError("pymysql no está instalado. Instalá: pip install pymysql")

    host = os.getenv("MYSQL_HOST", "")
    user = os.getenv("MYSQL_USER", "")
    password = os.getenv("MYSQL_PASSWORD", "")
    db = os.getenv("MYSQL_DB", "")
    port = int(os.getenv("MYSQL_PORT", "3306"))

    if not host or not user or not db:
        raise RuntimeError(
            "Faltan env vars MySQL. Necesito MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB (y opcional MYSQL_PORT)."
        )

    return pymysql.connect(
        host=host,
        user=user,
        password=password,
        db=db,
        port=port,
        charset="utf8mb4",
        autocommit=True,
        cursorclass=pymysql.cursors.DictCursor,
    )


def acquire_db_lock(lock_name: str, timeout_sec: int) -> bool:
    """
    Adquiere un lock global de MySQL (GET_LOCK). Devuelve True si lo obtiene.
    Esto evita ejecuciones simultáneas del job.
    """
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT GET_LOCK(%s, %s) AS got_lock", (lock_name, int(timeout_sec)))
            row = cur.fetchone() or {}
            got = row.get("got_lock", 0)
            return int(got) == 1
    finally:
        conn.close()


def release_db_lock(lock_name: str) -> None:
    """
    Libera el lock global de MySQL (RELEASE_LOCK).
    """
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT RELEASE_LOCK(%s) AS released", (lock_name,))
            # no hace falta validar el return; si no lo teníamos, devuelve NULL/0
    finally:
        conn.close()


def db_check_inventory_policies(asof: dt.date, location_id: int) -> None:
    """
    Valida que existan filas para calculation_date = asof.
    Si no, imprime max calculation_date y aborta con error.
    """
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  COUNT(*) AS n_asof
                FROM inventory_policies
                WHERE location_id = %s
                  AND calculation_date = %s
                """,
                (location_id, asof.strftime("%Y-%m-%d")),
            )
            n_asof = int((cur.fetchone() or {}).get("n_asof", 0))

            cur.execute(
                """
                SELECT
                  MAX(calculation_date) AS max_calc,
                  COUNT(*) AS n_total
                FROM inventory_policies
                WHERE location_id = %s
                """,
                (location_id,),
            )
            row = cur.fetchone() or {}
            max_calc = row.get("max_calc")
            n_total = int(row.get("n_total", 0))

        print("\n=== DB CHECK: inventory_policies ===")
        print(f"location_id={location_id}")
        print(f"asof={asof} | filas con calculation_date=asof: {n_asof}")
        print(f"max(calculation_date): {max_calc} | total filas: {n_total}")

        if n_asof <= 0:
            raise SystemExit(
                "\nERROR: El job terminó pero NO hay policies para calculation_date=asof.\n"
                "       Esto explica por qué tu vista no matchea con CURDATE().\n"
                "       Revisar ss2_monte_carlo.py (writer/upsert) y/o el SP de refresh.\n"
            )
    finally:
        conn.close()


def try_run_sp_refresh(sp_name: str, asof: dt.date, location_id: int) -> None:
    """
    Intenta ejecutar el SP de refresh si existe.
    Como no sabemos la firma, prueba 2 formas:
      1) CALL sp()
      2) CALL sp(asof, location_id)
    """
    conn = get_db_conn()
    try:
        with conn.cursor() as cur:
            print("\n=== SP REFRESH ===")
            print(f"Intentando CALL {sp_name}()")
            try:
                cur.execute(f"CALL {sp_name}()")
                print("OK: SP ejecutado sin argumentos.")
                return
            except Exception as e1:
                print(f"Fallo sin args: {e1}")

            print(f"Intentando CALL {sp_name}(%s,%s) con asof/location_id")
            try:
                cur.execute(f"CALL {sp_name}(%s,%s)", (asof.strftime("%Y-%m-%d"), location_id))
                print("OK: SP ejecutado con (asof, location_id).")
                return
            except Exception as e2:
                print(f"Fallo con (asof, location_id): {e2}")
                print("WARN: No se pudo ejecutar el SP. Seguir con diagnóstico del writer.")
    finally:
        conn.close()


def main() -> None:
    args = parse_args()
    load_env(args.dotenv)

    asof = parse_asof(args.asof)

    here = Path(__file__).resolve().parent
    rebuild_py = here / "ss2_rebuild_from_tabla1.py"
    mc_py = here / "ss2_monte_carlo.py"

    if not rebuild_py.exists():
        raise SystemExit(f"Missing {rebuild_py}. Put ss2_daily_job.py in the same folder as the scripts.")
    if not mc_py.exists():
        raise SystemExit(f"Missing {mc_py}. Put ss2_daily_job.py in the same folder as the scripts.")

    print(f"\nSS2 DAILY JOB | asof={asof} | location_id={args.location_id} | tz={TZ_NAME}")

    if args.asof and not args.skip_rebuild:
        print(
            f"\nWARN: --asof={asof} pero rebuild no está parametrizado por asof (usa 'hoy' / tabla1).\n"
            "      Para backfills reales: usá --skip-rebuild o adaptá ss2_rebuild_from_tabla1.py para aceptar --asof.\n"
        )

    # Acquire DB lock to prevent concurrent runs
    lock_acquired = False
    if not args.no_lock and not args.dry_run:
        print(f"\n=== DB LOCK ===\nTrying GET_LOCK('{args.lock_name}', {args.lock_timeout}) ...")
        lock_acquired = acquire_db_lock(args.lock_name, args.lock_timeout)
        if not lock_acquired:
            raise SystemExit(
                f"\nABORT: Otro SS2 daily job ya está corriendo (lock='{args.lock_name}').\n"
                "       Esperá a que termine o corré con --no-lock (no recomendado).\n"
            )
        print("OK: Lock adquirido.")

    try:
        # 1) Rebuild
        if not args.skip_rebuild:
            run_step([sys.executable, str(rebuild_py)], "REBUILD (ss2_rebuild_from_tabla1.py)")

        # 2) Monte Carlo
        if not args.skip_mc:
            mc_cmd = [
                sys.executable,
                str(mc_py),
                "--asof",
                asof.strftime("%Y-%m-%d"),
                "--location-id",
                str(args.location_id),
            ]
            if args.dry_run:
                mc_cmd.append("--dry-run")

            run_step(mc_cmd, "MONTE CARLO + DAILY (ss2_monte_carlo.py)")

        # 3) Opcional SP refresh
        if args.run_sp_refresh:
            try_run_sp_refresh(args.sp_name, asof, args.location_id)

        # 4) Check DB
        if not args.skip_db_check and not args.dry_run:
            db_check_inventory_policies(asof, args.location_id)

        print("\nOK: SS2 daily job finished.")

    finally:
        # Always release lock if acquired
        if lock_acquired:
            try:
                print(f"\n=== DB LOCK ===\nReleasing lock '{args.lock_name}' ...")
                release_db_lock(args.lock_name)
                print("OK: Lock liberado.")
            except Exception as e:
                print(f"WARN: No se pudo liberar el lock ({e}). Puede liberarse solo al cerrar conexión.")


if __name__ == "__main__":
    main()