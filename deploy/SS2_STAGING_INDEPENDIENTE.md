# ss2_staging independiente – Guía completa

Para que AWS funcione sin depender de neobd: Stock HUD lee de ss2_staging local.

---

## Requisitos previos

- MySQL en AWS con base `ss2_staging` y usuario `ss2`
- MC API en AWS con acceso a neobd (para pipeline)
- Stock HUD en AWS

---

## Paso 1: Pipeline en neobd (una vez)

El pipeline escribe en neobd. Ejecutar desde donde corra la MC API (neobd o AWS):

```bash
curl -X POST "http://localhost:8001/mc/run" -H "Content-Type: application/json" -d '{"review_days":120}'
curl -X POST "http://localhost:8001/policy/run" -H "Content-Type: application/json" -d '{}'
curl -X POST "http://localhost:8001/scoring/run" -H "Content-Type: application/json" -d '{}'
```

---

## Paso 2: Sync completo (en AWS)

Sincroniza tablas maestras + SS2 desde neobd a ss2_staging:

```bash
cd /home/ubuntu/neolab-smartstock/smartstock_mc_api
source venv/bin/activate
python deploy/sync_neobd_to_aws.py
```

**Tablas sincronizadas:**
- Maestras: `parametros_sku`, `tablaprecios`, `tabla1`
- SS2: `ss2_sku_features_12m`, `ss2_demand_classification`, `ss2_demand_cache`, `ss2_policy_results`, `ss2_purchase_scores`

El script crea las tablas en destino si no existen (copiando estructura desde neobd).

---

## Paso 3: Crear vistas (en AWS, una vez)

```bash
cd /home/ubuntu/neolab-smartstock/smartstock_mc_api
source venv/bin/activate
python deploy/setup_ss2_staging_views.py
```

Crea: `v_sku_features_12m`, `v_stock_estado_unidades`, `ss2_v_purchase_suggestions_v2`.

---

## Paso 4: Configurar Stock HUD (AWS)

En `/home/ubuntu/SCANNER_REPO/.env`:

```
MYSQL_HOST=127.0.0.1
MYSQL_DB=neobd
SMARTSTOCK_DB_NAME=ss2_staging
SMARTSTOCK_MC_API_URL=http://localhost:8001
```

Reiniciar:

```bash
sudo systemctl restart stock-hud
```

---

## Paso 5: Cron diario (AWS)

Usar `cron-daily-with-sync.sh` para pipeline + sync:

```bash
0 2 * * * /home/ubuntu/neolab-smartstock/smartstock_mc_api/deploy/cron-daily-with-sync.sh >> /var/log/smartstock-mc-cron.log 2>&1
```

---

## Orden de ejecución (primera vez)

1. Pipeline (mc, policy, scoring) → escribe en neobd
2. `sync_neobd_to_aws.py` → copia todo a ss2_staging
3. `setup_ss2_staging_views.py` → crea vistas
4. Reiniciar stock-hud
5. Probar: https://tu-ip/stock/ → modal SmartStock debe mostrar "Policy Engine"

---

## Verificación

```bash
# En AWS
mysql -h 127.0.0.1 -u ss2 -p ss2_staging -e "SELECT COUNT(*) FROM ss2_v_purchase_suggestions_v2"
```

Debe devolver filas > 0.
