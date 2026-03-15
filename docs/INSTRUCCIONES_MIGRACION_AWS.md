# Instrucciones: Migración HUD SS2 en AWS Lightsail

Ejecutar en orden. Reemplazar `TU_IP`, `TU_KEY.pem`, `MYSQL_HOST`, `MYSQL_USER` según tu entorno.

---

## 0. Conectar por SSH

```bash
ssh -i TU_KEY.pem ubuntu@TU_IP_LIGHTSAIL
```

---

## 1. Actualizar código (git pull)

```bash
cd /home/ubuntu/neolab-smartstock
git pull origin main
```

Si hay conflictos con `cron-daily.sh`:
```bash
git restore smartstock_mc_api/deploy/cron-daily.sh
git pull origin main
```

---

## 2. Reiniciar la API (para cargar nuevo código)

```bash
sudo systemctl restart smartstock-mc-api
```

Verificar:
```bash
curl http://localhost:8001/health
curl http://localhost:8001/
```

---

## 3. Aplicar DDL en MySQL

**Si MySQL está en la misma instancia Lightsail** (ej. puerto 3306 o 3307 local):

```bash
cd /home/ubuntu/neolab-smartstock

# Tablas SS2
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_ss2_demand_cache.sql
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_ss2_policy_results.sql
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_ss2_purchase_scores.sql

# Migraciones (si las tablas ya existían, puede dar error "Duplicate column" - ignorar)
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/migration_add_demand_p97.sql
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/migration_add_caps_parametros.sql

# Vista SS2
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_ss2_v_purchase_suggestions_v2.sql
```

**Si MySQL está en otro servidor** (ej. neobd 190.228.29.65), cambiar `-h 127.0.0.1` por `-h MYSQL_HOST`.

---

## 4. Ejecutar el pipeline (llenar tablas SS2)

```bash
curl -X POST http://localhost:8001/mc/run
curl -X POST http://localhost:8001/policy/run
curl -X POST http://localhost:8001/scoring/run
```

Cada uno debe responder `{"ok": true, "updated": N, ...}`.

---

## 5. Reemplazar v_sugerencias_compra por versión SS2

```bash
cd /home/ubuntu/neolab-smartstock
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_v_sugerencias_compra_ss2.sql
```

(Usar el mismo `-h` y `-u` que en el paso 3.)

---

## 6. Verificar

1. Abrir el Stock HUD en el navegador.
2. Buscar SKU **M524-100L**.
3. Abrir el modal de SmartStock.
4. Comprobar:
   - **Stock objetivo** = valor calculado por Policy Engine (no el paramétrico viejo).
   - **Sugerencia** = cantidad coherente con la brecha hasta el objetivo.
   - **Estado** = BAJO_OBJ si stock < objetivo (no "Bajo mínimo" si stock > mínimo).

---

## Resumen de comandos (copiar/pegar)

```bash
# 1. SSH
ssh -i TU_KEY.pem ubuntu@TU_IP

# 2. Pull + restart
cd /home/ubuntu/neolab-smartstock
git pull origin main
sudo systemctl restart smartstock-mc-api

# 3. DDL (ajustar -h y -u si hace falta)
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_ss2_demand_cache.sql
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_ss2_policy_results.sql
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_ss2_purchase_scores.sql
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/migration_add_demand_p97.sql
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/migration_add_caps_parametros.sql
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_ss2_v_purchase_suggestions_v2.sql

# 4. Pipeline
curl -X POST http://localhost:8001/mc/run
curl -X POST http://localhost:8001/policy/run
curl -X POST http://localhost:8001/scoring/run

# 5. Vista HUD
mysql -h 127.0.0.1 -u ss2 -p ss2_staging < smartstock_mc_api/deploy/ddl_v_sugerencias_compra_ss2.sql
```
