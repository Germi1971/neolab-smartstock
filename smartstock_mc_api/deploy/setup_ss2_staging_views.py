#!/usr/bin/env python3
"""
Crea las vistas en ss2_staging para que el Stock HUD muestre datos de Policy Engine.
Ejecutar DESPUÉS del sync (parametros_sku, tablaprecios, tabla1, ss2_* ya deben existir).

Uso:
  cd smartstock_mc_api
  python deploy/setup_ss2_staging_views.py
"""
import os
import sys
from pathlib import Path

_parent = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_parent))
try:
    from dotenv import load_dotenv
    load_dotenv(_parent / ".env")
except ImportError:
    pass

try:
    import pymysql
except ImportError:
    pymysql = None

HOST = os.getenv("AWS_MYSQL_HOST", "127.0.0.1")
PORT = int(os.getenv("AWS_MYSQL_PORT", "3306"))
USER = os.getenv("AWS_MYSQL_USER", "")
PASS = os.getenv("AWS_MYSQL_PASSWORD", "")
DB = os.getenv("AWS_MYSQL_DB", "ss2_staging")

SCRIPT_DIR = Path(__file__).resolve().parent
DDL_FILES = [
    "ddl_v_sku_features_12m_from_ss2.sql",
    "ddl_v_stock_estado_unidades_neobd.sql",
    "ddl_ss2_v_purchase_suggestions_v2.sql",
]


def main():
    if pymysql is None:
        print("pip install pymysql")
        sys.exit(1)
    if not USER:
        print("Configurar AWS_MYSQL_USER y AWS_MYSQL_PASSWORD en .env")
        sys.exit(1)
    conn = pymysql.connect(
        host=HOST, port=PORT, user=USER, password=PASS, database=DB,
        charset="utf8mb4",
    )
    try:
        for fname in DDL_FILES:
            path = SCRIPT_DIR / fname
            if not path.exists():
                print(f"  {fname}: no existe, omitiendo")
                continue
            sql = path.read_text(encoding="utf-8", errors="replace")
            # Ejecutar cada statement (separados por ;)
            for stmt in sql.split(";"):
                stmt = stmt.strip()
                if not stmt or stmt.startswith("--"):
                    continue
                if stmt.upper().startswith("USE "):
                    continue
                # No ejecutar comentarios de bloque
                if stmt.startswith("/*"):
                    continue
                try:
                    with conn.cursor() as cur:
                        cur.execute(stmt)
                    conn.commit()
                except Exception as e:
                    if "already exists" in str(e).lower() or "Unknown column" in str(e):
                        print(f"  {fname}: {e}")
                    else:
                        print(f"  {fname}: ERROR {e}")
                        raise
            print(f"  {fname}: OK")
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM ss2_v_purchase_suggestions_v2")
            n = cur.fetchone()["n"]
        print(f"\nOK: ss2_v_purchase_suggestions_v2 tiene {n} filas")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
