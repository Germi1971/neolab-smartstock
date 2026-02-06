# NeoLab SmartStock

**Professional Purchase Replenishment Prediction System**

Sistema profesional de predicción de reposición de compras con motor ML, scheduler automatizado y panel de control React.

## Características

### Fase 1: Arquitectura Base
- ✅ Modelo de datos MySQL optimizado para +5,000 SKUs
- ✅ FastAPI backend con SQLAlchemy Async
- ✅ Endpoints RESTful para stock, parámetros y compras
- ✅ Sistema de aprobaciones con persistencia

### Fase 2: Motor ML Avanzado
- ✅ Feature computation (12m, 24m, 90d windows)
- ✅ Modelos: SIN_DATOS, REGULAR, CROSTON, SBA, TSB, MONTE_CARLO
- ✅ Backtesting y selección automática de modelos
- ✅ Generación de políticas (s, S)
- ✅ Detección de drift

### Fase 3: Frontend PRO
- ✅ React + TypeScript + Tailwind CSS
- ✅ Tabs: Stock, Compras, Parámetros, ML
- ✅ Paginación server-side real
- ✅ Filtros avanzados y exports
- ✅ Modal SKU con detalles ML
- ✅ Acciones de aprobación/rechazo

### Fase 4: Scheduler y Observabilidad
- ✅ APScheduler con locks MySQL
- ✅ Retries con backoff exponencial
- ✅ Tabla ml_run_errors para tracking
- ✅ Caché materializado (sku_cache_latest)
- ✅ Health endpoints (K8s ready)
- ✅ Métricas y logs de auditoría

## Estructura del Proyecto

```
neolab_smartstock/
├── backend/
│   ├── main.py                 # FastAPI app
│   ├── requirements.txt        # Python dependencies
│   ├── db/
│   │   ├── __init__.py
│   │   └── database.py         # SQLAlchemy config
│   ├── models/
│   │   ├── __init__.py
│   │   └── models.py           # SQLAlchemy models
│   ├── routers/
│   │   └── health.py           # Health endpoints
│   ├── jobs/
│   │   ├── scheduler.py        # APScheduler + locks
│   │   ├── ml_pipeline_job.py  # ML pipeline job
│   │   └── cache_refresh_job.py # Cache refresh
│   ├── ml_engine/
│   │   ├── __init__.py
│   │   └── pipeline.py         # ML pipeline
│   └── utils/
│       ├── __init__.py
│       └── logger.py           # Logging config
├── frontend/
│   ├── package.json            # NPM dependencies
│   ├── vite.config.ts          # Vite config
│   ├── tailwind.config.js      # Tailwind config
│   ├── tsconfig.json           # TypeScript config
│   ├── index.html
│   └── src/
│       ├── main.tsx            # React entry
│       ├── App.tsx             # Main app
│       ├── index.css           # Global styles
│       ├── types/
│       │   └── index.ts        # TypeScript types
│       ├── services/
│       │   └── apiClient.ts    # API client
│       ├── hooks/
│       │   ├── useDebounce.ts
│       │   ├── usePaginatedData.ts
│       │   └── useSKUCache.ts
│       ├── components/
│       │   ├── DataTable.tsx
│       │   ├── Pagination.tsx
│       │   ├── FilterBar.tsx
│       │   ├── KPICards.tsx
│       │   └── ModalSKU.tsx
│       └── pages/
│           ├── StockTab.tsx
│           ├── ComprasTab.tsx
│           ├── ParametrosTab.tsx
│           └── MLTab.tsx
└── database/
    ├── schema_fase1.sql        # Core schema
    ├── schema_fase2.sql        # ML advanced schema
    └── schema_fase3.sql        # Scheduler & observability
```

## Instalación

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

### Base de Datos

```bash
# Ejecutar scripts SQL en orden
mysql -u user -p neolab_smartstock < database/schema_fase1.sql
mysql -u user -p neolab_smartstock < database/schema_fase2.sql
mysql -u user -p neolab_smartstock < database/schema_fase3.sql
```

## Configuración

### Variables de Entorno

Crear archivo `.env` en `backend/`:

```env
DATABASE_URL=mysql+aiomysql://user:password@localhost:3306/neolab_smartstock
LOG_LEVEL=INFO
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

### Configuración del Scheduler

La configuración del scheduler se almacena en la tabla `scheduler_config`:

| Key | Default | Descripción |
|-----|---------|-------------|
| `ml_pipeline.cron` | `0 2 * * *` | Cron para ejecución automática |
| `ml_pipeline.timeout_seconds` | `3600` | Timeout del pipeline |
| `ml_pipeline.max_retries` | `3` | Máximo de reintentos |
| `ml_pipeline.batch_size` | `100` | Tamaño de batch |
| `cache.ttl_minutes` | `60` | TTL del caché |
| `lock.timeout_seconds` | `300` | Timeout de locks |

## Uso

### Iniciar Backend

```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Iniciar Frontend

```bash
cd frontend
npm run dev
```

### Health Endpoints

- `GET /health` - Health check completo
- `GET /health/ready` - Readiness probe (K8s)
- `GET /health/live` - Liveness probe (K8s)
- `GET /health/metrics` - Métricas del sistema
- `GET /health/runs` - Estado de ejecuciones ML
- `GET /health/errors` - Errores del pipeline
- `GET /health/cache` - Estado del caché

## API Endpoints

### Stock
- `GET /api/v1/stock` - Listar stock con filtros
- `GET /api/v1/stock/{sku}` - Detalle de SKU

### Compras
- `GET /api/v1/purchases/suggestions` - Sugerencias de compra
- `POST /api/v1/purchases/suggestions/{sku}/approve` - Aprobar sugerencia
- `POST /api/v1/purchases/suggestions/{sku}/unapprove` - Revertir aprobación
- `GET /api/v1/purchases/export` - Exportar orden de compra (CSV)

### Parámetros
- `GET /api/v1/parameters` - Listar parámetros
- `PUT /api/v1/parameters/{sku}` - Actualizar parámetros
- `PUT /api/v1/parameters/bulk` - Actualización masiva

### ML
- `GET /api/v1/ml/runs` - Listar ejecuciones
- `GET /api/v1/ml/models` - Modelos por SKU
- `GET /api/v1/ml/features/{sku}` - Features de SKU
- `POST /api/v1/ml/run` - Ejecutar pipeline manualmente

## Arquitectura ML

### Modelos Soportados

| Modelo | Descripción | Uso |
|--------|-------------|-----|
| `SIN_DATOS` | Sin historial disponible | SKUs nuevos |
| `REGULAR` | Demanda regular (CV < 0.5) | SKU estable |
| `CROSTON` | Demanda intermitente | Eventos esporádicos |
| `SBA` | Syntetos-Boylan Approximation | Intermitencia moderada |
| `TSB` | Teunter-Syntetos-Babai | Intermitencia con tendencia |
| `MONTE_CARLO` | Simulación Monte Carlo | Casos complejos |

### Selección de Modelo

1. **Feature Computation**: Calcula métricas (CV, lambda, ADI)
2. **Backtesting**: Evalúa múltiples modelos con validación cruzada
3. **Scoring**: Composite score ponderado:
   - Error (40%): RMSE, MAE, bias
   - Service (30%): Service level, coverage
   - Stability (20%): Varianza entre folds
   - Complexity (10%): Penalización por complejidad
4. **Hysteresis**: Evita cambios frecuentes de modelo

### Detección de Drift

Monitorea cambios en:
- CV (coefficient of variation)
- Lambda (tasa de eventos)
- Gap ratio (días entre eventos)

Umbral configurable (default: 50% de cambio)

## Scheduler

### Locks Distribuidos

Los locks se implementan mediante tabla MySQL `scheduler_locks`:

```sql
-- Adquirir lock
INSERT INTO scheduler_locks (lock_name, locked_by, expires_at)
VALUES ('ml_pipeline', 'instance-1', NOW() + INTERVAL 1 HOUR);

-- Liberar lock
DELETE FROM scheduler_locks WHERE lock_name = 'ml_pipeline' AND locked_by = 'instance-1';
```

### Jobs Programados

| Job | Frecuencia | Descripción |
|-----|------------|-------------|
| `ml_pipeline_daily` | Cron configurable | Pipeline ML completo |
| `cache_refresh` | Cada 30 min | Refrescar caché materializado |

### Retries

```python
for attempt in range(max_retries + 1):
    try:
        process_sku(sku)
        break
    except Exception as e:
        if attempt < max_retries:
            sleep(retry_delay * (attempt + 1))  # Backoff exponencial
        else:
            log_error(sku, e)  # Guardar en ml_run_errors
```

## Caché Materializado

La tabla `sku_cache_latest` almacena una vista pre-calculada:

```sql
SELECT 
    sku,
    stock_posicion,
    qty_sugerida,
    estado,
    modelo_seleccionado,
    cv_12m,
    drift_detected,
    expires_at
FROM sku_cache_latest
WHERE estado = 'PENDIENTE'
```

Beneficios:
- Consultas sub-100ms para +5,000 SKUs
- Reduce carga en base de datos
- TTL configurable (default: 60 min)

## Testing

### Backend

```bash
cd backend
pytest tests/
```

### Frontend

```bash
cd frontend
npm test
```

## Deployment

### Docker

```dockerfile
# Backend Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Kubernetes

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: smartstock-api
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: api
        image: neolab/smartstock:2.0.0
        ports:
        - containerPort: 8000
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8000
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8000
```

## Roadmap

- [ ] Integración con ERP (SAP, Oracle)
- [ ] Alertas por email/Slack
- [ ] Dashboard de métricas (Grafana)
- [ ] A/B testing de modelos
- [ ] Auto-tuning de hiperparámetros
- [ ] Soporte para múltiples almacenes

## Licencia

Copyright © 2024 NeoLab. Todos los derechos reservados.

## Soporte

Para soporte técnico, contactar a: soporte@neolab.com
