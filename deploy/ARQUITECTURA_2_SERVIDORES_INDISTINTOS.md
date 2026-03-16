# Arquitectura: 2 servidores indistintos

Objetivo: tener todo en ambos servidores y que sea indistinto correr en uno u otro.

---

## Esquema general

```
                    ┌─────────────────────────────────────┐
                    │  neobd (190.228.29.65)              │
                    │  - MySQL: neobd (tabla1, ss2_*)      │
                    │  - MC API + Stock HUD               │
                    │  - Pipeline escribe aquí            │
                    └──────────────┬──────────────────────┘
                                   │
                    sync (neobd → ss2_staging)            │
                                   │
                    ┌──────────────▼──────────────────────┐
                    │  AWS Lightsail (13.220.27.221)       │
                    │  - MySQL: ss2_staging (copia)        │
                    │  - MC API + Stock HUD                │
                    │  - Pipeline puede correr aquí       │
                    └─────────────────────────────────────┘
```

**Fuente de verdad:** neobd tiene `tabla1` (inventario) y es donde el pipeline escribe por defecto.

---

## Configuración por servidor

### Servidor neobd (190.228.29.65)

| Componente | Variable | Valor |
|------------|----------|-------|
| **MC API** | MYSQL_HOST | `127.0.0.1` |
| | MYSQL_DB | `neobd` |
| | MC_REVIEW_DAYS | `120` |
| **Stock HUD** | MYSQL_HOST | `127.0.0.1` |
| | MYSQL_DB | `neobd` |
| | SMARTSTOCK_DB_NAME | (vacío, usa neobd) |
| | SMARTSTOCK_MC_API_URL | `http://localhost:8001` |

### Servidor AWS (13.220.27.221)

| Componente | Variable | Valor |
|------------|----------|-------|
| **MC API** | MYSQL_HOST | `190.228.29.65` (neobd remoto) |
| | MYSQL_DB | `neobd` |
| | MC_REVIEW_DAYS | `120` |
| | AWS_MYSQL_HOST | `127.0.0.1` (para sync local) |
| | AWS_MYSQL_USER | `ss2` |
| | AWS_MYSQL_PASSWORD | ... |
| | AWS_MYSQL_DB | `ss2_staging` |
| **Stock HUD** | MYSQL_HOST | `127.0.0.1` |
| | SMARTSTOCK_DB_NAME | `ss2_staging` |
| | SMARTSTOCK_MC_API_URL | `http://localhost:8001` |

---

## Flujo: correr en cualquiera

### Pipeline (mc → policy → scoring)

**En neobd:**
```bash
curl -X POST "http://localhost:8001/mc/run" -H "Content-Type: application/json" -d '{"review_days":120}'
curl -X POST "http://localhost:8001/policy/run" -H "Content-Type: application/json" -d '{}'
curl -X POST "http://localhost:8001/scoring/run" -H "Content-Type: application/json" -d '{}'
```
→ Escribe en neobd (local).

**En AWS:**
```bash
# Mismo comando; la MC API escribe en neobd (remoto)
curl -X POST "http://localhost:8001/mc/run" -H "Content-Type: application/json" -d '{"review_days":120}'
curl -X POST "http://localhost:8001/policy/run" -H "Content-Type: application/json" -d '{}'
curl -X POST "http://localhost:8001/scoring/run" -H "Content-Type: application/json" -d '{}'
```
→ Escribe en neobd (remoto). Luego hay que hacer sync para que el HUD en AWS tenga datos.

### Sync (solo en AWS)

```bash
cd /home/ubuntu/neolab-smartstock/smartstock_mc_api
source venv/bin/activate
python deploy/sync_neobd_to_aws.py
```
→ Copia neobd → ss2_staging (local en AWS).

**Importante:** Si corriste el pipeline en AWS, ejecutá el sync ahí mismo para que el HUD en AWS muestre los datos nuevos.

---

## Cron diario

Para que sea indistinto, el cron puede estar en **cualquiera** de los dos. Lo importante: después del pipeline, si el cron está en AWS, agregar el sync.

**Cron en AWS (recomendado):**

```bash
0 2 * * * /home/ubuntu/neolab-smartstock/smartstock_mc_api/deploy/cron-daily-with-sync.sh >> /var/log/smartstock-mc-cron.log 2>&1
```

El script `cron-daily-with-sync.sh` ejecuta el pipeline y luego el sync automáticamente.

**Cron en neobd:** no hace falta sync (el HUD lee neobd directo). Pero el HUD en AWS quedaría desactualizado hasta que alguien corra el sync manualmente o haya un cron en AWS que solo haga sync.

---

## Resumen: qué hace cada servidor

| Acción | neobd | AWS |
|--------|-------|-----|
| Pipeline | ✓ escribe en neobd local | ✓ escribe en neobd remoto |
| Sync | No necesario | ✓ neobd → ss2_staging local |
| HUD | ✓ lee neobd | ✓ lee ss2_staging (tras sync) |
| MC API | ✓ | ✓ (ambos usan neobd para leer/escribir) |

**Para que sea indistinto:** podés correr el pipeline en cualquiera. Si lo corrés en AWS, ejecutá el sync ahí mismo. Si lo corrés en neobd, el HUD en neobd ya tiene datos; para AWS, corré el sync en AWS.
