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
AWS_USER = os.getenv("AWS_MYSQL_USER", os.getenv("MYSQL_USER", "ss2"))
AWS_PASS = os.getenv("AWS_MYSQL_PASSWORD", os.getenv("MYSQL_PASSWORD", ""))
AWS_DB = os.getenv("AWS_MYSQL_DB", os.getenv("MYSQL_DB", "ss2_staging"))

TABLAS_SYNC = [
    "ss2_sku_features_12m",  # requerida por v_sku_features_12m
    "ss2_demand_classification",
    "ss2_demand_cache",
    "ss2_policy_results",
    "ss2_purchase_scores",
]


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


def sync_table(src_conn, dst_conn, table: str) -> int:
    try:
        with src_conn.cursor() as cur:
            cur.execute(f"SELECT * FROM `{table}`")
            rows = cur.fetchall()
    except Exception as e:
        print(f"  {table}: SKIP ({e})")
        return 0
    if not rows:
        return 0
    cols = list(rows[0].keys())
    placeholders = ", ".join(["%s"] * len(cols))
    col_list = ", ".join(f"`{c}`" for c in cols)
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
    src = get_conn(SRC_HOST, SRC_PORT, SRC_USER, SRC_PASS, SRC_DB)
    dst = get_conn(AWS_HOST, AWS_PORT, AWS_USER, AWS_PASS, AWS_DB)
    try:
        total = 0
        for t in TABLAS_SYNC:
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
