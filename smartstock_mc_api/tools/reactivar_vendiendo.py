"""
Red de seguridad: reactiva en ss2_staging los SKUs que estan vendiendo (figuran
en sku_obs_12m = tuvieron ventas recientes y pasaron la guardia de recencia)
pero quedaron marcados activo=0 y NO estan discontinuados.

Corre DESPUES del sync (que reimporta 'activo' desde el ERP neobd), y recalcula
policy + scoring para que los reactivados aparezcan con recomendacion en el Tablero.

Respeta discontinuado=1 (no reactiva lo dado de baja a proposito).
"""
import os
import urllib.request

import pymysql
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

conn = pymysql.connect(
    host=os.getenv("MYSQL_HOST"),
    port=int(os.getenv("MYSQL_PORT", "3306")),
    user=os.getenv("MYSQL_USER"),
    password=os.getenv("MYSQL_PASSWORD"),
    database=os.getenv("MYSQL_DB"),
    autocommit=True,
)
with conn.cursor() as cur:
    # 1) Aplicar overrides manuales (sobreviven al sync del ERP).
    try:
        ov = cur.execute(
            "UPDATE parametros_sku p JOIN ss2_manual_override o ON o.sku=p.sku "
            "SET p.activo=o.estado WHERE o.estado IN (0,1)"
        )
        print(f"Overrides manuales aplicados: {ov}")
    except Exception as _e:
        print(f"WARN overrides (falta ss2_manual_override?): {_e}")
    # 2) Red de seguridad: reactivar los que venden pero quedaron inactivos,
    #    salvo los forzados a INACTIVO por override.
    n = cur.execute(
        "UPDATE parametros_sku SET activo=1 "
        "WHERE discontinuado=0 AND activo=0 AND sku IN (SELECT sku FROM sku_obs_12m) "
        "AND sku NOT IN (SELECT sku FROM ss2_manual_override WHERE estado=0)"
    )
print(f"Reactivados (venden pero estaban inactivos): {n}")

# recalcular policy + scoring para que los reactivados tengan target/score
for ep in ("policy", "scoring"):
    try:
        req = urllib.request.Request(
            f"http://localhost:8001/{ep}/run",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=90).read()
        print(f"{ep}/run OK")
    except Exception as e:
        print(f"WARN {ep}/run: {e}")
