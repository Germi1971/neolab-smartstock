# Pasos para dejar todo funcionando (SmartStock SS2 + HUD)

Guía completa para poner en marcha el pipeline SS2 y el HUD con sugerencias correctas.

---

## Resumen del flujo

```
tabla1 (stock) + sku_obs_12m (ventas 12m)
        ↓
refresh_sku_obs_12m
        ↓
mc/run → ss2_demand_cache
        ↓
policy/run → ss2_policy_results
        ↓
scoring/run → ss2_purchase_scores
        ↓
ss2_v_purchase_suggestions_v2 (vista)
        ↓
v_sugerencias_compra (HUD lee aquí)
```

---

## Parte A: En tu PC (antes de desplegar)

### A1. Commit y push

```bash
cd c:\Users\germa\Documents\NEOLAB\DATO_SOLUTIONS\neolab_smartstock
git add -A
git status   # revisar qué se sube
git commit -m "Pipeline SS2 + migración HUD + scoring ampliado"
git push origin main
```

---

## Parte B: En AWS Lightsail

### B1. Conectar por SSH

```bash
ssh -i TU_CLAVE.pem ubuntu@TU_IP_LIGHTSAIL
```

### B2. Actualizar código

```bash
cd ~/neolab-smartstock
# Si la ruta es otra (ej. neolab_smartstock), ajustar

git pull origin main
```

Si hay conflicto con `cron-daily.sh`:
```bash
git restore smartstock_mc_api/deploy/cron-daily.sh
git pull origin main
```

### B3. Reiniciar la API

```bash
sudo systemctl restart smartstock-mc-api
```

Verificar:
```bash
curl http://localhost:8001/health
curl http://localhost:8001/
```

### B4. Comprobar .env

La API debe apuntar a la misma base que usa el HUD:

- Si el HUD usa **ss2_staging** → `MYSQL_DB=ss2_staging`
- Si el HUD usa **neobd** → `MYSQL_DB=neobd`

Revisar:
```bash
grep MYSQL /home/ubuntu/neolab-smartstock/smartstock_mc_api/.env
```

---

## Parte C: MySQL – DDL y migraciones

Ejecutar en este orden. Reemplazar `-h HOST -u USER` según tu entorno (ej. `-h 127.0.0.1 -u ss2` o `-h 190.228.29.65 -u neolab`).

```bash
cd ~/neolab-smartstock
DB="-h 127.0.0.1 -u ss2 -p"
BASE=ss2_staging   # o neobd si aplica

# 1. Tablas SS2 (crear si no existen)
mysql $DB $BASE < smartstock_mc_api/deploy/ddl_ss2_demand_cache.sql
mysql $DB $BASE < smartstock_mc_api/deploy/ddl_ss2_policy_results.sql
mysql $DB $BASE < smartstock_mc_api/deploy/ddl_ss2_purchase_scores.sql

# 2. Migraciones (puede dar "Duplicate column" si ya aplicaste – ignorar)
mysql $DB $BASE < smartstock_mc_api/deploy/migration_add_demand_p97.sql
mysql $DB $BASE < smartstock_mc_api/deploy/migration_add_caps_parametros.sql

# 3. Vista ss2_v_purchase_suggestions_v2
mysql $DB $BASE < smartstock_mc_api/deploy/ddl_ss2_v_purchase_suggestions_v2.sql
```

**Nota:** Si usas `neobd` en lugar de `ss2_staging`, editar los DDL que tienen `USE ss2_staging;` y cambiarlo por `USE neobd;`, o ejecutar sin `USE` y especificar la base en el comando.

---

## Parte D: Pipeline SS2 (llenar tablas)

### D1. Refrescar sku_obs_12m (datos de ventas 12m)

```bash
cd ~/neolab-smartstock/smartstock_mc_api
./venv/bin/python tools/refresh_sku_obs_12m.py
```

O si el venv está en otra ruta:
```bash
python tools/refresh_sku_obs_12m.py
```

### D2. Ejecutar pipeline (MC → Policy → Scoring)

```bash
curl -X POST http://localhost:8001/mc/run
curl -X POST http://localhost:8001/policy/run
curl -X POST http://localhost:8001/scoring/run
```

Cada uno debe responder algo como: `{"ok": true, "updated": N, ...}`.

### D3. Reemplazar v_sugerencias_compra por versión SS2

```bash
cd ~/neolab-smartstock
mysql $DB $BASE < smartstock_mc_api/deploy/ddl_v_sugerencias_compra_ss2.sql
```

---

## Parte E: Verificación

1. Abrir el Stock HUD en el navegador.
2. Buscar SKU **M524-100L**.
3. Abrir el modal de SmartStock.
4. Comprobar:
   - **Stock objetivo** = valor de Policy Engine (no el paramétrico viejo).
   - **Sugerencia** = cantidad coherente con la brecha hasta el objetivo.
   - **Estado** = BAJO_OBJ si stock < objetivo (no "Bajo mínimo" si stock > mínimo).

---

## Parte F: Cron diario (opcional)

Para que el pipeline corra automáticamente cada día:

```bash
crontab -e
```

Añadir (ajustar ruta si hace falta):

```
0 2 * * * /home/ubuntu/neolab-smartstock/smartstock_mc_api/deploy/cron-daily.sh >> /var/log/smartstock-mc-cron.log 2>&1
```

El cron ejecuta: refresh_sku_obs_12m → mc/run → policy/run → scoring/run.

---

## Prerrequisitos en la base de datos

Las vistas/tablas siguientes deben existir:

| Objeto | Uso |
|--------|-----|
| `tabla1` | Stock, refresh_sku_obs_12m |
| `parametros_sku` | Policy, Scoring |
| `v_stock_estado_unidades` | Stock actual por SKU |
| `v_sku_features_12m` | Demand features 12m |
| `v_sku_event_features_12m` | Margen (opcional; si no existe, scoring usa fallback) |
| `v_analisis_sku_excel_mc` | Monte Carlo |
| `tablaprecios` | Precios, descripción |

Si `v_sku_event_features_12m` no existe, el scoring usa `FETCH_SCORING_INPUTS_SQL_LEGACY` (sin margen_pct).

---

## Resumen de comandos (copiar/pegar)

```bash
# SSH
ssh -i TU_KEY.pem ubuntu@TU_IP

# Pull + restart
cd ~/neolab-smartstock
git pull origin main
sudo systemctl restart smartstock-mc-api

# DDL (ajustar -h -u y BASE)
DB="-h 127.0.0.1 -u ss2 -p"
BASE=ss2_staging

mysql $DB $BASE < smartstock_mc_api/deploy/ddl_ss2_demand_cache.sql
mysql $DB $BASE < smartstock_mc_api/deploy/ddl_ss2_policy_results.sql
mysql $DB $BASE < smartstock_mc_api/deploy/ddl_ss2_purchase_scores.sql
mysql $DB $BASE < smartstock_mc_api/deploy/migration_add_demand_p97.sql
mysql $DB $BASE < smartstock_mc_api/deploy/migration_add_caps_parametros.sql
mysql $DB $BASE < smartstock_mc_api/deploy/ddl_ss2_v_purchase_suggestions_v2.sql

# Refresh + pipeline
cd smartstock_mc_api
./venv/bin/python tools/refresh_sku_obs_12m.py
curl -X POST http://localhost:8001/mc/run
curl -X POST http://localhost:8001/policy/run
curl -X POST http://localhost:8001/scoring/run

# Vista HUD
cd ~/neolab-smartstock
mysql $DB $BASE < smartstock_mc_api/deploy/ddl_v_sugerencias_compra_ss2.sql
```

---

## Troubleshooting

| Problema | Solución |
|----------|----------|
| `Unknown column` en scoring | Normal si falta `v_sku_event_features_12m`. Se usa fallback automático. |
| `v_analisis_sku_excel_mc` no existe | Crear la vista o verificar que el MC tenga su fuente de datos. |
| HUD sigue mostrando datos viejos | Verificar que `v_sugerencias_compra` se haya reemplazado (paso D3). |
| API no responde en 8001 | Revisar `systemctl status smartstock-mc-api` y logs. |
