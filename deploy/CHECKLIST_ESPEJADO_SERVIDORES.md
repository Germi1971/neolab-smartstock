# Checklist para espejar servidores (neobd ↔ AWS Lightsail)

Objetivo: que ambos servidores tengan la misma funcionalidad y datos para poder migrar solo a AWS cuando se decida.

---

## 1. Rutas de directorios

| Componente | Servidor 1 (neobd) | Servidor 2 (AWS Lightsail) |
|------------|--------------------|----------------------------|
| MC API (neolab_smartstock) | `/ruta/neolab_smartstock` o `neolab-smartstock` | `/home/ubuntu/neolab-smartstock` |
| Stock HUD (SCANNER_REPO) | `/ruta/SCANNER_REPO` | `/home/ubuntu/SCANNER_REPO` |

**Importante:** En AWS el repo se clona como `neolab-smartstock` (con guión). Verificar que el cron y systemd usen esa ruta.

---

## 2. MC API – smartstock_mc_api/.env

| Variable | Servidor 1 | Servidor 2 |
|----------|------------|------------|
| `MYSQL_HOST` | `127.0.0.1` o `190.228.29.65` (según dónde esté MySQL) | `190.228.29.65` (neobd remoto) |
| `MYSQL_PORT` | `3306` | `3306` |
| `MYSQL_USER` | `neolab` | `neolab` |
| `MYSQL_PASSWORD` | (mismo) | (mismo) |
| `MYSQL_DB` | `neobd` | `neobd` |
| `MC_REVIEW_DAYS` | `120` | `120` |
| `AWS_MYSQL_HOST` | (opcional, para sync) | (no necesario si no sincroniza) |
| `AWS_MYSQL_*` | Si sync a AWS | - |

**Nota:** Si en AWS tenés una base `ss2_staging` local, podrías usar `MYSQL_DB=ss2_staging` y sincronizar desde neobd. Para espejado simple, ambos apuntan a `neobd`.

---

## 3. Stock HUD – SCANNER_REPO/.env

El HUD lee `.env` desde la raíz del repo (`REPO_ROOT = parents[2]` desde `apps/stock-hud/server.py`).

| Variable | Servidor 1 (neobd) | Servidor 2 (AWS) |
|----------|-------------------|-----------------|
| `MYSQL_HOST` | `127.0.0.1` | `127.0.0.1` (MySQL local) |
| `MYSQL_PORT` | `3306` | `3306` |
| `MYSQL_USER` | `neolab` | `neolab` (o el user de ss2_staging) |
| `MYSQL_PASSWORD` | (mismo) | (mismo) |
| `MYSQL_DB` | `neobd` | `neobd` (o base por defecto) |
| `SMARTSTOCK_MC_API_URL` | `http://localhost:8001` | `http://localhost:8001` |
| `SMARTSTOCK_DB_NAME` | (vacío = usa MYSQL_DB/neobd) | `ss2_staging` (base local con datos sincronizados) |

---

## 4. Cron diario

**Solo debe correr en UN servidor** (donde el pipeline escribe a la base). Si ambos escriben a la misma `neobd`, correr en uno solo evita duplicar trabajo.

**Ruta en crontab:** debe coincidir con la ubicación real del repo:

```bash
# En el servidor donde corre el pipeline (ej. AWS):
0 2 * * * /home/ubuntu/neolab-smartstock/smartstock_mc_api/deploy/cron-daily.sh >> /var/log/smartstock-mc-cron.log 2>&1
```

**En Servidor 1** (si el cron corre ahí):

```bash
0 2 * * * /ruta/real/neolab_smartstock/smartstock_mc_api/deploy/cron-daily.sh >> /var/log/smartstock-mc-cron.log 2>&1
```

**Verificar:** `crontab -l` y que la ruta exista.

---

## 5. Servicios systemd

### MC API (smartstock-mc-api.service)

El servicio usa `__WORK_DIR__` reemplazado por `setup-lightsail.sh`. Si instalás manualmente:

```bash
sudo sed -i "s|__WORK_DIR__|/home/ubuntu/neolab-smartstock/smartstock_mc_api|g" /etc/systemd/system/smartstock-mc-api.service
sudo systemctl daemon-reload
sudo systemctl restart smartstock-mc-api
```

### Stock HUD (stock-hud.service)

Tiene ruta fija `/home/ubuntu/SCANNER_REPO`. Si en Servidor 1 usás otra ruta, copiá el `.service` y ajustá:

```ini
WorkingDirectory=/ruta/real/SCANNER_REPO/apps/stock-hud
ExecStart=/ruta/real/SCANNER_REPO/apps/stock-hud/venv/bin/gunicorn ...
```

---

## 6. Sincronización de datos (si usa ss2_staging en AWS)

Si AWS tiene su propia base `ss2_staging` y querés espejar desde neobd:

**Opción A – Sync explícito:**

```bash
cd /home/ubuntu/neolab-smartstock/smartstock_mc_api
source venv/bin/activate
python deploy/sync_neobd_to_aws.py
```

**Opción B – Pipeline con sync:**

```bash
python run_full_pipeline.py --skip-rebuild
# Al final sincroniza si AWS_MYSQL_* está en .env
```

**Opción C – Pipeline local en ambos:** ambos servidores ejecutan el pipeline contra `neobd` (MYSQL_HOST=190.228.29.65). No hace falta sync si hay una sola base.

---

## 7. Repoblar datos tras cambios (cobertura 6 meses)

Ejecutar en el servidor donde corre el pipeline (o en ambos si usan bases distintas):

```bash
curl -X POST "http://localhost:8001/mc/run" -H "Content-Type: application/json" -d '{"review_days":120}'
curl -X POST "http://localhost:8001/policy/run" -H "Content-Type: application/json" -d '{}'
curl -X POST "http://localhost:8001/scoring/run" -H "Content-Type: application/json" -d '{}'
```

---

## 8. Verificación rápida

| Check | Comando / Acción |
|-------|------------------|
| MC API responde | `curl http://localhost:8001/health` → incluye `"config": {"coverage_months": 6}` |
| HUD muestra cobertura | Abrir HUD → barra superior "Cobertura: 6 meses" |
| Crontab correcto | `crontab -l` → ruta existe y apunta al script |
| Servicios activos | `sudo systemctl status smartstock-mc-api stock-hud` |

