# Deploy a los 2 servidores – Cobertura 6 meses + HUD

Guía para actualizar código y DB en ambos servidores después de los cambios de cobertura 6 meses.

**Checklist completo de espejado:** ver [CHECKLIST_ESPEJADO_SERVIDORES.md](./CHECKLIST_ESPEJADO_SERVIDORES.md)

---

## Paso 1: En tu PC – Commit y push

### Repo neolab_smartstock (MC API, pipeline)

```powershell
cd C:\Users\germa\Documents\NEOLAB\DATO_SOLUTIONS\neolab_smartstock

git add smartstock_mc_api/app/main.py smartstock_mc_api/deploy/cron-daily.sh smartstock_mc_api/run_full_pipeline.py smartstock_mc_api/.env.example
git commit -m "Cobertura 6 meses: MC_REVIEW_DAYS=120, API default, cron, health config"
git push origin main
```

### Repo SCANNER_REPO (Stock HUD)

```powershell
cd C:\Users\germa\Documents\NEOLAB\SCANNER_REPO

git add apps/stock-hud/index.html apps/stock-hud/server.py
git commit -m "HUD: mostrar cobertura de stock en barra (desde MC API /health)"
git push origin main
```

---

## Paso 2: Servidor 1 – neobd (190.228.29.65) o donde corre el pipeline

Si el pipeline corre en este servidor:

```bash
cd /ruta/neolab_smartstock   # Ajustar ruta
git pull origin main

# Asegurar MC_REVIEW_DAYS en .env
grep MC_REVIEW_DAYS .env || echo "MC_REVIEW_DAYS=120" >> smartstock_mc_api/.env

# Ejecutar pipeline para repoblar con horizonte 6 meses
cd smartstock_mc_api
python run_full_pipeline.py --skip-rebuild
# (o con --no-sync-aws si no querés sincronizar a AWS desde acá)
```

---

## Paso 3: Servidor 2 – AWS Lightsail (MC API + Stock HUD)

```bash
# Conectar
ssh -i tu-key.pem ubuntu@TU_IP_LIGHTSAIL

# --- MC API ---
cd /home/ubuntu/neolab-smartstock   # con guión (no neolab_smartstock)
git pull origin main

# Agregar MC_REVIEW_DAYS si no está
grep MC_REVIEW_DAYS smartstock_mc_api/.env || echo "MC_REVIEW_DAYS=120" >> smartstock_mc_api/.env

# Reiniciar MC API
sudo systemctl restart smartstock-mc-api

# Verificar
curl http://localhost:8001/health
# Debe incluir "config": {"coverage_months": 6, "review_days": 120, ...}

# --- Stock HUD ---
cd /home/ubuntu/SCANNER_REPO
git pull origin main

# Reiniciar HUD (si usa systemd)
sudo systemctl restart stock-hud
# O si corre con gunicorn/uwsgi, reiniciar ese servicio
```

---

## Paso 4: Repoblar DB con datos de 6 meses

Para que las sugerencias usen el nuevo horizonte, hay que volver a ejecutar el pipeline:

**Opción A – Pipeline en Lightsail (contra neobd remoto):**

```bash
cd /home/ubuntu/neolab_smartstock/smartstock_mc_api
# .env con MYSQL_HOST=190.228.29.65
python run_full_pipeline.py --skip-rebuild
```

**Opción B – Vía API (si la MC API ya está actualizada):**

```bash
curl -X POST "http://localhost:8001/mc/run" -H "Content-Type: application/json" -d '{"review_days":120}'
curl -X POST "http://localhost:8001/policy/run" -H "Content-Type: application/json" -d '{}'
curl -X POST "http://localhost:8001/scoring/run" -H "Content-Type: application/json" -d '{}'
```

**Opción C – Pipeline local con sync a AWS:**

Si el pipeline corre en tu PC contra neobd (190.228.29.65) y tenés AWS_MYSQL_* en .env:

```powershell
cd C:\Users\germa\Documents\NEOLAB\DATO_SOLUTIONS\neolab_smartstock\smartstock_mc_api
python run_full_pipeline.py --skip-rebuild
# Al final sincroniza a AWS automátic
```

---

## Verificación

1. **MC API:** `curl http://localhost:8001/health` → debe incluir `"config": {"coverage_months": 6}`
2. **HUD:** Abrir el HUD → en la barra debe verse "Cobertura: 6 meses"
3. **Sugerencias:** Revisar que `qty_recomendada` en la vista refleje stock para 6 meses
