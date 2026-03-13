# Despliegue SmartStock Monte Carlo API en AWS Lightsail

## Resumen rápido

1. Subir código al servidor Lightsail (Ubuntu)
2. Configurar `.env` con credenciales MySQL (neobd)
3. Ejecutar `bash deploy/setup-lightsail.sh`
4. Abrir puerto 8001 en Lightsail Networking
5. Configurar Stock HUD con `SMARTSTOCK_MC_API_URL`
6. Poblar cache: `POST /mc/run`

---

## Paso a paso

### 1. Subir el proyecto al servidor

```powershell
# Opción A: Git en el servidor
ssh -i tu-key.pem ubuntu@TU_IP_LIGHTSAIL
git clone https://github.com/Germi1971/SmartStock.git
cd SmartStock/smartstock_mc_api
```

```powershell
# Opción B: SCP desde tu PC
scp -i tu-key.pem -r C:\Users\germa\Documents\NEOLAB\DATO_SOLUTIONS\neolab_smartstock\smartstock_mc_api ubuntu@TU_IP_LIGHTSAIL:/home/ubuntu/
```

### 2. En el servidor: configurar y ejecutar

```bash
cd /home/ubuntu/smartstock_mc_api
# (o cd /home/ubuntu/SmartStock/smartstock_mc_api si clonaste el repo)

# Crear .env
cp deploy/env.lightsail.example .env
nano .env   # Completar MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB

# Ejecutar setup (instala Python, venv, systemd)
bash deploy/setup-lightsail.sh
```

### 3. Verificar

```bash
sudo systemctl status smartstock-mc-api
curl http://localhost:8001/health
curl http://localhost:8001/
```

### 4. Lightsail Console → Networking

Agregar regla: **TCP 8001** (o el puerto que uses)

### 5. Crear tabla sku_mc_cache (si no existe)

La vista `v_analisis_sku_excel_mc` debe existir en ss2_staging (clon de neobd). La tabla cache:

```bash
mysql -h TU_MYSQL_HOST -u ss2 -p ss2_staging < app/sql/ddl_sku_mc_cache.sql
```

Si la tabla ya existía con un DDL antiguo, ejecutar la migración:

```bash
mysql -h TU_MYSQL_HOST -u ss2 -p ss2_staging < deploy/ddl_migration.sql
```

### 6. Poblar el cache Monte Carlo

```bash
curl -X POST http://localhost:8001/mc/run
# o con parámetros:
curl -X POST "http://localhost:8001/mc/run" -H "Content-Type: application/json" -d '{"n_sims":8000,"review_days":30}'
```

### 7. Configurar Stock HUD

En el `.env` del Stock HUD (o en la instancia donde corre):

```
SMARTSTOCK_MC_API_URL=http://TU_IP_LIGHTSAIL:8001
```

Si Stock HUD y la API MC están en la misma instancia:

```
SMARTSTOCK_MC_API_URL=http://127.0.0.1:8001
```

---

## Comandos útiles

```bash
# Logs
sudo journalctl -u smartstock-mc-api -f

# Reiniciar
sudo systemctl restart smartstock-mc-api

# Probar un SKU
curl "http://localhost:8001/mc/cache/M524-100L"
```

---

## Requisitos previos

- **MySQL** accesible desde Lightsail
- Base **ss2_staging** (clon de neolab en AWS) o **neobd** con las mismas tablas
- Vista `v_analisis_sku_excel_mc` en la base
- Tabla `sku_mc_cache` (creada con `app/sql/ddl_sku_mc_cache.sql` contra ss2_staging)
