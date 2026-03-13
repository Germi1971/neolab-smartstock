# SmartStock Monte Carlo API

Microservicio FastAPI para:
- decidir MC sí/no por SKU (según intermitencia + riesgo)
- simular demanda en horizonte H = LT + Review con Poisson (eventos) + Lognormal (tamaño)
- calcular stock objetivo por percentil (service level)
- calcular qty recomendada con reglas MOQ/múltiplo/cap
- cachear resultados en `neobd.sku_mc_cache`

## Instalación (Windows)
```bat
cd smartstock_mc_api
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Ejecutar
Dev:
```bat
scripts\run_dev.bat
```

Prod:
```bat
scripts\run_prod.bat
```

## Endpoints
- GET /health
- POST /mc/run
- POST /mc/sku/{sku}
- GET /mc/cache/{sku}
- GET /mc/top_stockout

## DB
Crear tabla cache:
`app/sql/ddl_sku_mc_cache.sql`
