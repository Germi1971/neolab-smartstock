# Sync neobd → ss2_staging (servidores distintos)

Cuando **neobd** (190.228.29.65) y **ss2_staging** (Lightsail 127.0.0.1:3306) están en servidores distintos.

## Opción 1: Script Python (en Lightsail)

El servidor Lightsail debe poder alcanzar 190.228.29.65 por red.

```bash
cd /home/ubuntu/neolab-smartstock/smartstock_mc_api/deploy

# Configurar contraseñas (no commitear)
export NEODB_PASS="TU_PASS_NEOLAB"
export SS2_PASS="TU_PASS_SS2"

python3 sync_neobd_to_ss2_remote.py
```

O crear `.env.sync` (añadir a .gitignore):
```
NEODB_PASS=...
SS2_PASS=...
```

Y ejecutar: `export $(cat .env.sync | xargs) && python3 sync_neobd_to_ss2_remote.py`

## Opción 2: HeidiSQL (manual)

1. **Conectar a neobd** (190.228.29.65)
2. `parametros_sku` → Clic derecho → Exportar datos como SQL
3. **Conectar a ss2_staging** (IP de Lightsail, puerto 3307)
4. Ejecutar el SQL exportado (o importar)

## Opción 3: Cron diario

En Lightsail, añadir a crontab para sync automático:

```bash
0 3 * * * cd /home/ubuntu/neolab-smartstock/smartstock_mc_api/deploy && NEODB_PASS=xxx SS2_PASS=yyy python3 sync_neobd_to_ss2_remote.py >> /var/log/sync-neobd-ss2.log 2>&1
```

## Tablas sincronizadas

- parametros_sku (crítico para CSV)
- tablaprecios
- ss2_demand_cache, ss2_policy_results, ss2_purchase_scores, ss2_demand_classification
- tabla1 (opcional, para v_stock_estado_unidades)
