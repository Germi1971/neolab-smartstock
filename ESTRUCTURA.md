# Estructura consolidada neolab_smartstock

Todo lo necesario para SmartStock está ahora en esta carpeta.

## Carpetas principales

| Carpeta | Descripción |
|---------|-------------|
| `backend/` | API principal FastAPI (sugerencias, ML, dashboard) |
| `frontend/` | React + Vite + Tailwind |
| `smartstock_mc_api/` | API Monte Carlo (usada por Stock HUD). Endpoints: `/mc/run`, `/mc/cache/{sku}` |
| `ss2/` | Scripts batch: `ss2_daily_job.py`, `ss2_monte_carlo.py`, vistas SQL |
| `database/` | Schemas MySQL |

## Ejecutar API Monte Carlo (smartstock_mc_api)

```bash
cd smartstock_mc_api
py -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8001
```

## Ejecutar job SS2 daily

```bash
cd ss2\scripts
py ss2_daily_job.py
```

## Deploy en AWS Lightsail

Ver `smartstock_mc_api/deploy/README.md`

## Subir a GitHub (SmartStock)

Si neolab_smartstock es el contenido del repo https://github.com/Germi1971/SmartStock:

```bash
cd neolab_smartstock
git add -A
git status   # Revisar qué se sube
git commit -m "Consolidar: smartstock_mc_api + ss2 en neolab_smartstock"
git push origin main
```
