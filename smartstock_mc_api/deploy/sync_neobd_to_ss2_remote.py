#!/usr/bin/env python3
"""
Sincroniza neobd (servidor remoto) → ss2_staging (Lightsail local).
Para servidores MySQL en máquinas distintas.

Uso:
  python sync_neobd_to_ss2_remote.py

Variables de entorno (o editar abajo):
  NEODB_HOST, NEODB_PORT, NEODB_USER, NEODB_PASS, NEODB_DB
  SS2_HOST, SS2_PORT, SS2_USER, SS2_PASS, SS2_DB
"""
import os
import sys

try:
    import pymysql
except ImportError:
    print("Instalar: pip install pymysql")
    sys.exit(1)

# === neobd (remoto) ===
NEODB_HOST = os.getenv("NEODB_HOST", "190.228.29.65")
NEODB_PORT = int(os.getenv("NEODB_PORT", "3306"))
NEODB_USER = os.getenv("NEODB_USER", "neolab")
NEODB_PASS = os.getenv("NEODB_PASS", "")
NEODB_DB = os.getenv("NEODB_DB", "neobd")

# === ss2_staging (Lightsail local) ===
SS2_HOST = os.getenv("SS2_HOST", "127.0.0.1")
SS2_PORT = int(os.getenv("SS2_PORT", "3307"))
SS2_USER = os.getenv("SS2_USER", "ss2")
SS2_PASS = os.getenv("SS2_PASS", "")
SS2_DB = os.getenv("SS2_DB", "ss2_staging")

TABLAS = [
    "parametros_sku",
    "tablaprecios",
    "ss2_demand_cache",
    "ss2_policy_results",
    "ss2_purchase_scores",
    "ss2_demand_classification",
]
# sku_mc_cache puede no existir; tabla1 para v_stock_estado_unidades (puede ser grande)
TABLAS_OPCIONALES = ["sku_mc_cache", "tabla1"]


def sync_table(table: str, optional: bool = False) -> int:
    """Copia tabla de neobd a ss2_staging. Retorna filas copiadas."""
    conn_src = pymysql.connect(
        host=NEODB_HOST, port=NEODB_PORT, user=NEODB_USER, password=NEODB_PASS,
        database=NEODB_DB, charset="utf8mb4", cursorclass=pymysql.cursors.DictCursor,
    )
    conn_dst = pymysql.connect(
        host=SS2_HOST, port=SS2_PORT, user=SS2_USER, password=SS2_PASS,
        database=SS2_DB, charset="utf8mb4",
    )
    try:
        with conn_src.cursor() as cur:
            cur.execute(f"SELECT * FROM `{table}`")
            rows = cur.fetchall()
        if not rows:
            print(f"  {table}: 0 filas (origen vacío)")
            return 0
        cols = list(rows[0].keys())
        placeholders = ", ".join(["%s"] * len(cols))
        cols_str = ", ".join(f"`{c}`" for c in cols)
        sql_insert = f"INSERT INTO `{table}` ({cols_str}) VALUES ({placeholders})"
        with conn_dst.cursor() as cur:
            cur.execute(f"DELETE FROM `{table}`")
            for r in rows:
                cur.execute(sql_insert, [r[c] for c in cols])
        conn_dst.commit()
        print(f"  {table}: {len(rows)} filas")
        return len(rows)
    except pymysql.err.ProgrammingError as e:
        if optional and ("doesn't exist" in str(e).lower() or "1146" in str(e)):
            print(f"  {table}: omitida (no existe)")
            return 0
        raise
    finally:
        conn_src.close()
        conn_dst.close()


def main():
    if not NEODB_PASS or not SS2_PASS:
        print("Configurar NEODB_PASS y SS2_PASS (env o editar script)")
        sys.exit(1)
    print("Sync neobd → ss2_staging (servidores distintos)")
    print(f"  Origen: {NEODB_HOST}:{NEODB_PORT}/{NEODB_DB}")
    print(f"  Destino: {SS2_HOST}:{SS2_PORT}/{SS2_DB}")
    total = 0
    for t in TABLAS:
        total += sync_table(t)
    for t in TABLAS_OPCIONALES:
        try:
            total += sync_table(t, optional=True)
        except Exception:
            pass
    print(f"Total: {total} filas sincronizadas")


if __name__ == "__main__":
    main()
