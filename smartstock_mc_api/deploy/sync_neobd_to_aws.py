#!/usr/bin/env python3
"""
Sincroniza datos SS2 de neobd (origen) a AWS Lightsail (destino).

Uso:
  1. Configurar .env con MYSQL_* para neobd (origen)
  2. Configurar AWS_MYSQL_* para destino
  3. py deploy/sync_neobd_to_aws.py

Ejecutar desde: smartstock_mc_api/
"""

import os
import sys
from pathlib import Path

# Añadir parent para imports y cargar .env
_parent = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_parent))
try:
    from dotenv import load_dotenv
    load_dotenv(_parent / ".env")
except ImportError:
    load_dotenv = None

try:
    import pymysql
except ImportError:
    pymysql = None

# Origen: neobd (MYSQL_* en .env)
SRC_HOST = os.getenv("MYSQL_HOST", "")
SRC_PORT = int(os.getenv("MYSQL_PORT", "3306"))
SRC_USER = os.getenv("MYSQL_USER", "")
SRC_PASS = os.getenv("MYSQL_PASSWORD", "")
SRC_DB = os.getenv("MYSQL_DB", "neobd")

# Destino: AWS (AWS_MYSQL_* en .env)
AWS_HOST = os.getenv("AWS_MYSQL_HOST", "")
AWS_PORT = int(os.getenv("AWS_MYSQL_PORT", os.getenv("MYSQL_PORT", "3306")))
AWS_USER = os.getenv("AWS_MYSQL_USER", "")
AWS_PASS = os.getenv("AWS_MYSQL_PASSWORD", "")
AWS_DB = os.getenv("AWS_MYSQL_DB", "ss2_staging")

# Tablas maestras (neobd → ss2_staging): requeridas por ss2_v_purchase_suggestions_v2
TABLAS_MAESTRAS = ["parametros_sku", "tablaprecios", "tabla1"]

# Tablas SS2 (pipeline output)
TABLAS_SS2 = [
    "ss2_sku_features_12m",
    "ss2_demand_classification",
    "ss2_demand_cache",
    "ss2_policy_results",
    "ss2_purchase_scores",
]

TABLAS_SYNC = TABLAS_MAESTRAS + TABLAS_SS2


def get_conn(host, port, user, password, db):
    return pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        database=db,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def ensure_table_exists(src_conn, dst_conn, table: str, src_db: str, dst_db: str) -> bool:
    """Crea la tabla en destino si no existe, copiando estructura desde origen."""
    with dst_conn.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
            (dst_db, table),
        )
        if cur.fetchone().get("n", 0) > 0:
            return True
    try:
        with src_conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema = %s AND table_name = %s",
                (src_db, table),
            )
            if cur.fetchone().get("n", 0) == 0:
                return False
            cur.execute(f"SHOW CREATE TABLE `{table}`")
            row = cur.fetchone()
        create_sql = (row.get("Create Table") or row.get("create table") or (list(row.values())[1] if row and len(row) > 1 else "")) if row else ""
        if not create_sql:
            return False
        if "IF NOT EXISTS" not in create_sql:
            create_sql = create_sql.replace("CREATE TABLE ", "CREATE TABLE IF NOT EXISTS ", 1)
        with dst_conn.cursor() as cur:
            cur.execute(create_sql)
        dst_conn.commit()
        print(f"  {table}: tabla creada en destino")
        return True
    except Exception as e:
        print(f"  {table}: no se pudo crear tabla ({e})")
        return False


def sync_table(src_conn, dst_conn, table: str) -> int:
    try:
        with src_conn.cursor() as cur:
            cur.execute(f"SELECT * FROM `{table}`")
            rows = cur.fetchall()
    except Exception as e:
        print(f"  {table}: SKIP origen ({e})")
        return 0
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    # Escapar % en nombres de columnas (ej. "DIST Price -30%") para que execute() no lo interprete
    col_list = ", ".join(f"`{c.replace('%', '%%')}`" for c in cols)
    sql = f"REPLACE INTO `{table}` ({col_list}) VALUES ({placeholders})"
    with dst_conn.cursor() as cur:
        for r in rows:
            cur.execute(sql, [r[c] for c in cols])
    return len(rows)


def main():
    if load_dotenv:
        load_dotenv()
    if pymysql is None:
        print("pip install pymysql")
        sys.exit(1)
    if not AWS_HOST or not AWS_USER:
        print(
            "Configurá AWS_MYSQL_HOST, AWS_MYSQL_USER, AWS_MYSQL_PASSWORD en .env\n"
            " (o usá MYSQL_* si origen y destino son iguales)"
        )
        sys.exit(1)
    if not SRC_HOST or not SRC_USER or not SRC_PASS:
        print("Configurá MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD en .env (origen neobd)")
        sys.exit(1)
    src = get_conn(SRC_HOST, SRC_PORT, SRC_USER, SRC_PASS, SRC_DB)
    dst = get_conn(AWS_HOST, AWS_PORT, AWS_USER, AWS_PASS, AWS_DB)
    try:
        total = 0
        for t in TABLAS_SYNC:
            ensure_table_exists(src, dst, t, SRC_DB, AWS_DB)
            n = sync_table(src, dst, t)
            dst.commit()
            print(f"  {t}: {n} filas")
            total += n
        print(f"\nOK: {total} filas sincronizadas a {AWS_HOST}")
    finally:
        src.close()
        dst.close()


if __name__ == "__main__":
    main()
