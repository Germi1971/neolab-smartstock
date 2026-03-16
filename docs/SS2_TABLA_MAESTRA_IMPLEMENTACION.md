# SmartStock SS2 — Tabla Maestra de Implementación

Documento técnico para Cursor y desarrollo. Diseño modular y ejecutable, priorizando Fase 1.

---

## 1. Resumen del pipeline

```
tabla1 / ss2_inv_event
        ↓
ss2_rebuild_from_tabla1.py  →  sp_ss2_sku_features_12m_refresh
        ↓
ss2_sku_features_12m  (o v_sku_features_12m)
        ↓
demand_classification.py   →  ss2_demand_classification
        ↓
ss2_monte_carlo / main.py  →  ss2_demand_cache
        ↓
policy_engine.py           →  ss2_policy_results
        ↓
purchase_scoring.py        →  ss2_purchase_scores
        ↓
ss2_v_purchase_suggestions_v2
```

---

## 2. Módulos Fase 1 — Dependencias y estado

| # | Módulo | Tabla principal | Script Python | Entrada | Salida | Estado |
|---|--------|-----------------|---------------|---------|--------|--------|
| 1 | Features | ss2_sku_features_12m | ss2_rebuild_from_tabla1.py + SP | tabla1, ss2_inv_event | ss2_sku_features_12m | EXISTE |
| 2 | Classification | ss2_demand_classification | demand_classification.py | v_sku_classification_input / sku_obs_12m | ss2_demand_classification | EXISTE |
| 3 | Demand Engine | ss2_demand_cache | main.py (MC) / ss2_monte_carlo.py | features, stock, classification | ss2_demand_cache | EXISTE |
| 4 | Policy Engine | ss2_policy_results | policy_engine.py | ss2_demand_cache, parametros_sku, stock | ss2_policy_results | EXISTE |
| 5 | Purchase Scoring | ss2_purchase_scores | purchase_scoring.py | ss2_policy_results, features | ss2_purchase_scores | EXISTE |
| 6 | Output | ss2_v_purchase_suggestions_v2 | Vista SQL | policy, scores, classification, stock | Vista final | EXISTE |
| 7 | Job control | ss2_job_runs | ss2_daily_job.py | — | ss2_job_runs | CREAR |
| 8 | Job logs | ss2_job_logs | ss2_daily_job.py | run_id | ss2_job_logs | CREAR |

---

## 3. DDLs por módulo (MySQL 5.5)

### 3.1 Ya existentes en `deploy/`

| Archivo | Tabla/Vista |
|---------|-------------|
| ddl_ss2_demand_classification.sql | ss2_demand_classification |
| ddl_ss2_demand_cache.sql | ss2_demand_cache |
| ddl_ss2_policy_results.sql | ss2_policy_results |
| ddl_ss2_purchase_scores.sql | ss2_purchase_scores |
| ddl_ss2_v_purchase_suggestions_v2.sql | ss2_v_purchase_suggestions_v2 |
| migration_add_demand_class_to_v_purchase_suggestions.sql | Vista actualizada con demand_class |

### 3.2 Nuevos (Fase 1)

| Archivo | Tabla | Descripción |
|---------|-------|-------------|
| ddl_ss2_features.sql | ss2_features | Tabla opcional de features (alternativa a ss2_sku_features_12m) |
| ddl_ss2_job_runs.sql | ss2_job_runs, ss2_job_logs, ss2_v_job_status | Control y logs del pipeline |

### 3.3 Orden de ejecución DDL

```bash
# 1. Tablas base (asumidas existentes)
# parametros_sku, tablaprecios, tabla1, v_stock_estado_unidades

# 2. Tablas SS2 core
mysql ... < deploy/ddl_ss2_demand_classification.sql
mysql ... < deploy/ddl_ss2_demand_cache.sql
mysql ... < deploy/ddl_ss2_policy_results.sql
mysql ... < deploy/ddl_ss2_purchase_scores.sql

# 3. Job control
mysql ... < deploy/ddl_ss2_job_runs.sql

# 4. Vista v_sku_features_12m (elegir UNA según tu setup)
mysql ... < deploy/ddl_v_sku_features_12m_from_ss2.sql       # si usás ss2_sku_features_12m
# O
mysql ... < deploy/ddl_v_sku_features_12m_from_sku_obs.sql   # si usás sku_obs_12m

# 5. Vista final (requiere v_sku_features_12m)
mysql ... < deploy/migration_add_v_sku_classification_input.sql  # si usás sku_obs_12m para classification
mysql ... < deploy/migration_add_demand_class_to_v_purchase_suggestions.sql
```

---

## 4. Scripts Python — Entrada/Salida

### 4.1 ss2_features.py (opcional)

Si usás `ss2_features` en lugar de `ss2_sku_features_12m`:

| Entrada | Salida |
|---------|--------|
| ss2_inv_event (SHIP) | ss2_features |
| tabla1 (ventas) | |

**Alternativa actual:** `ss2_rebuild_from_tabla1.py` llama `sp_ss2_sku_features_12m_refresh` → escribe en `ss2_sku_features_12m`.

### 4.2 demand_classification.py

| Entrada | Salida |
|---------|--------|
| v_sku_classification_input (o sku_obs_12m + tabla1) | ss2_demand_classification |
| parametros_sku (activo) | |

**Ubicación:** `smartstock_mc_api/app/demand_classification.py`

### 4.3 ss2_monte_carlo.py / main.py (MC)

| Entrada | Salida |
|---------|--------|
| ss2_sku_features_12m (o ss2_features) | ss2_demand_cache |
| ss2_demand_classification | |
| v_stock_estado_unidades / ss2_v_stock_enriched | |
| parametros_sku (LT, MOQ, criticidad) | |

**Nota:** `ss2_monte_carlo.py` en `ss2/scripts/` escribe en `ss2_mc_results` + `inventory_policies`. La API `main.py` escribe en `ss2_demand_cache`. Son pipelines distintos.

### 4.4 policy_engine.py

| Entrada | Salida |
|---------|--------|
| ss2_demand_cache | ss2_policy_results |
| parametros_sku | |
| v_stock_estado_unidades | |

**Ubicación:** `smartstock_mc_api/app/policy_engine.py`

### 4.5 purchase_scoring.py

| Entrada | Salida |
|---------|--------|
| ss2_policy_results | ss2_purchase_scores |
| ss2_demand_cache (p_stockout) | |
| features (mu, LT) | |

**Ubicación:** `smartstock_mc_api/app/purchase_scoring.py`

### 4.6 Orquestadores

| Script | Pipeline | Ubicación |
|--------|----------|-----------|
| ss2_daily_job.py | rebuild → monte_carlo → inventory_policies (legacy) | ss2/scripts/ |
| run_full_pipeline.py | rebuild → classification → mc → policy → scoring → job_runs | smartstock_mc_api/ |

**run_full_pipeline.py** es el orquestador del pipeline SS2 PRO (Fase 1).

---

## 5. Integración con ss2_daily_job.py

### 5.1 Flujo propuesto

```
1. Adquirir DB lock
2. Crear run en ss2_job_runs (status=RUNNING)
3. ss2_rebuild_from_tabla1.py
4. Log: features
5. demand_classification.py (o POST /classification/run)
6. Log: classification
7. Monte Carlo → ss2_demand_cache (o POST /mc/run)
8. Log: demand_cache
9. policy_engine.py (o POST /policy/run)
10. Log: policy
11. purchase_scoring.py (o POST /scoring/run)
12. Log: scoring
13. Actualizar ss2_job_runs (status=SUCCESS, n_skus_*, finished_at)
14. Liberar DB lock
```

### 5.2 Opciones de ejecución

**A) Script unificado (recomendado)**

```bash
cd smartstock_mc_api
python run_full_pipeline.py [--asof YYYY-MM-DD] [--skip-rebuild] [--dry-run]
```

Ejecuta: rebuild (opcional) → classification → mc → policy → scoring.  
Escribe en ss2_job_runs y ss2_job_logs si existen.

**B) Llamar API FastAPI (HTTP)**

```python
import requests
requests.post(f"{API_URL}/classification/run")
requests.post(f"{API_URL}/mc/run", json={})
requests.post(f"{API_URL}/policy/run")
requests.post(f"{API_URL}/scoring/run")
```

**C) Importar funciones (como hace run_full_pipeline.py)**

```python
from app.demand_classification import run_demand_classification_batch
from app.policy_engine import run_policy_engine_batch
from app.purchase_scoring import run_purchase_scoring_batch
n, _ = run_demand_classification_batch(conn)
n, _ = run_policy_engine_batch(conn)
n, _ = run_purchase_scoring_batch(conn)
```

---

## 6. Vista final ss2_v_purchase_suggestions_v2

### 6.1 Campos principales

| Campo | Tipo | Descripción |
|-------|------|-------------|
| sku | VARCHAR | Código |
| producto | VARCHAR | Descripción |
| stock_actual | INT | Stock libre depósito |
| stock_objetivo_final | DOUBLE | Target final |
| qty_recomendada / qty_final | DOUBLE | Compra sugerida |
| priority_score | DOUBLE | Score 0–100 |
| priority_band | VARCHAR | URGENTE / ALTA / MEDIA / BAJA |
| demand_class | VARCHAR | REGULAR / LUMPY / etc |
| lifecycle_state | VARCHAR | ACTIVE / DORMANT / etc |
| policy_reason | VARCHAR | Razón de política |
| priority_reason | VARCHAR | Razón de prioridad |
| explanation | TEXT | Explicación completa |

### 6.2 Dependencias de la vista

- parametros_sku
- v_stock_estado_unidades
- tablaprecios
- v_sku_features_12m
- ss2_policy_results
- ss2_purchase_scores
- ss2_demand_classification

---

## 7. Roadmap de implementación

### Fase 1 (actual)

1. **Ejecutar DDLs:** `ddl_ss2_job_runs.sql`
2. **Crear/actualizar ss2_daily_job.py** para pipeline unificado
3. **Definir v_sku_features_12m** si no existe (alias de ss2_sku_features_12m o sku_obs_12m)
4. **Probar pipeline completo** end-to-end

### Fase 2

- ss2_metrics.py
- ss2_alerts.py
- ss2_v_kpis
- ss2_v_alerts

### Fase 3

- ss2_backtest.py
- ss2_simulator.py
- ss2_economic_optimizer.py

---

## 8. Checklist de verificación

- [ ] ss2_demand_classification tiene datos
- [ ] ss2_demand_cache tiene datos (mc_enabled=1 donde aplica)
- [ ] ss2_policy_results tiene stock_objetivo_final / qty_recomendada_final
- [ ] ss2_purchase_scores tiene priority_score / priority_band
- [ ] ss2_v_purchase_suggestions_v2 devuelve filas
- [ ] ss2_job_runs registra cada corrida
- [ ] ss2_job_logs registra cada etapa

---

## 9. Variables de entorno

```
MYSQL_HOST
MYSQL_PORT
MYSQL_USER
MYSQL_PASSWORD
MYSQL_DB
SS2_LOCATION_ID
SS2_DAILY_LOCK_NAME
SS2_DAILY_LOCK_TIMEOUT
MC_N_SIMS
MC_LT_DAYS
MC_REVIEW_DAYS
```

---

*Documento generado para SmartStock SS2 PRO. Última actualización: 2025-03.*
