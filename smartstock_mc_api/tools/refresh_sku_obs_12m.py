# tools/refresh_sku_obs_12m.py
import os
from dotenv import load_dotenv
load_dotenv()

import pymysql

DB_HOST = os.getenv("MYSQL_HOST", "190.228.29.65")
DB_PORT = int(os.getenv("MYSQL_PORT", "3306"))
DB_USER = os.getenv("MYSQL_USER", "neolab")
DB_PASS = os.getenv("MYSQL_PASSWORD", "")
DB_NAME = os.getenv("MYSQL_DB", "neobd")

# 👉 Evento(s) de demanda: por defecto SOLO 'S'
DEMAND_ES_VALUES = ("S",)  # si querés sumar 'V': ("S","V")

TABLE_OBS = f"{DB_NAME}.sku_obs_12m"
TABLE_MOV = f"{DB_NAME}.tabla1"

def get_conn():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )

DDL = f"""
CREATE TABLE IF NOT EXISTS {TABLE_OBS} (
  sku VARCHAR(50) NOT NULL,
  dias_observados INT NULL,
  eventos_12m INT NULL,
  unidades_12m DOUBLE NULL,
  mu_unidades_evento DOUBLE NULL,
  sigma_unidades_evento DOUBLE NULL,
  mu_gap_dias DOUBLE NULL,
  sigma_gap_dias DOUBLE NULL,
  updated_at DATETIME NOT NULL,
  PRIMARY KEY (sku),
  KEY idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

# MySQL 5.5 compatible (sin window functions)
REFRESH_SQL = f"""
REPLACE INTO {TABLE_OBS}
(sku, dias_observados, eventos_12m, unidades_12m,
 mu_unidades_evento, sigma_unidades_evento,
 mu_gap_dias, sigma_gap_dias, updated_at)
SELECT
  z.sku,
  z.dias_observados,
  z.eventos_12m,
  z.unidades_12m,
  z.mu_unidades_evento,
  z.sigma_unidades_evento,
  z.mu_gap_dias,
  z.sigma_gap_dias,
  NOW()
FROM (
  SELECT
    x.sku,
    (DATEDIFF(MAX(x.fecha_dt), MIN(x.fecha_dt)) + 1) AS dias_observados,
    COUNT(*) AS eventos_12m,
    SUM(x.qty) AS unidades_12m,
    AVG(x.qty) AS mu_unidades_evento,
    STDDEV_SAMP(x.qty) AS sigma_unidades_evento,
    AVG(x.gap_dias) AS mu_gap_dias,
    STDDEV_SAMP(x.gap_dias) AS sigma_gap_dias
  FROM (
    SELECT
      e.sku,
      e.fecha_dt,
      e.qty,
      IF(@prev_sku = e.sku, DATEDIFF(e.fecha_dt, @prev_fecha), NULL) AS gap_dias,
      @prev_sku := e.sku,
      @prev_fecha := e.fecha_dt
    FROM (
      SELECT
        t.`Código` AS sku,
        t.`Fecha` AS fecha_dt,
        CAST(t.`Cantidad` AS DECIMAL(18,6)) AS qty
      FROM {TABLE_MOV} t
      WHERE TRIM(t.`E/S`) IN ({",".join(["%s"]*len(DEMAND_ES_VALUES))})
        AND t.`Fecha` >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
        AND t.`Código` IS NOT NULL
        AND t.`Fecha` IS NOT NULL
    ) e
    CROSS JOIN (SELECT @prev_sku := '', @prev_fecha := NULL) vars
    ORDER BY e.sku, e.fecha_dt
  ) x
  GROUP BY x.sku
) z;
"""

COUNT_SQL = f"SELECT COUNT(*) AS c FROM {TABLE_OBS};"
SAMPLE_SQL = f"SELECT * FROM {TABLE_OBS} ORDER BY eventos_12m DESC LIMIT 10;"

def main():
    print(f"Ensuring table {TABLE_OBS} ...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(DDL)

    print(f"Refreshing {TABLE_OBS} (12m window, E/S in {DEMAND_ES_VALUES}) ...")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(REFRESH_SQL, DEMAND_ES_VALUES)

        with conn.cursor() as cur:
            cur.execute(COUNT_SQL)
            c = cur.fetchone()["c"]
            print(f"OK. sku_obs_12m rows: {c}")

        with conn.cursor() as cur:
            cur.execute(SAMPLE_SQL)
            rows = cur.fetchall()
            print("Sample rows:")
            for r in rows:
                print(r)

if __name__ == "__main__":
    main()
