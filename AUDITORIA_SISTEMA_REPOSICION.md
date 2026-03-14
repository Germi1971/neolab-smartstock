# Auditoría: Sistema de Predicción de Reposición de Stock (NeoLab SmartStock)

**Fecha:** Marzo 2026  
**Versión:** Post-implementación truncamiento MC + export CSV

---

## 1. Arquitectura General

```
┌─────────────────┐     ┌──────────────────────┐     ┌─────────────────────┐
│  Frontend       │────▶│  Backend (port 8000)  │────▶│  MySQL (neobd)      │
│  React + Vite   │     │  FastAPI + routers     │     │  v_sugerencias_compra│
└─────────────────┘     └───────────┬───────────┘     │  v_analisis_sku_*   │
                                    │                  │  sku_mc_cache       │
                                    ▼                  └─────────────────────┘
                         ┌──────────────────────┐
                         │  MC API (port 8010)  │
                         │  smartstock_mc_api   │
                         │  Monte Carlo engine  │
                         └──────────────────────┘
```

**Flujo de datos:**
1. `v_analisis_sku_excel_mc` → vista con features 12m (Forecast_m, p_event, q_mean, etc.)
2. MC API lee vista → simula demanda → escribe `sku_mc_cache`
3. `v_sugerencias_compra` → vista que une cache + stock + parámetros
4. Backend/Frontend consumen `v_sugerencias_compra` para UI y export

---

## 2. Componentes Implementados ✅

### 2.1 Short-circuit para SKUs inactivos (`decide_mc`)
| Criterio | Umbral | Efecto |
|----------|--------|--------|
| `eventos_12m` | < 3 | No entra a MC |
| `unidades_12m` | <= 0 | No entra a MC |
| `dias_observados` | < 180 | No entra a MC |
| `activo` | != 1 | No entra a MC |

**Resultado:** SKUs sin historial o dormidos no reciben simulación MC → `qty_recomendada_mc = 0` en cache.

---

### 2.2 Lambda CAP (`infer_lambda_eventos_mes`)
- **Problema:** `p_event ≈ 1` → `-ln(1-p)` explota.
- **Solución:** `lam_cap = Forecast_m / q_mean`; si `p_event >= 0.90` usa CAP; guard-rail `lambda <= 2*Forecast_m/q_mean`.

---

### 2.3 Criticidad automática
| Criticidad | Condición | Service Target |
|------------|-----------|----------------|
| CRITICO | forecast_m≥3 o q_mean≥3 o (p_event≥0.70 y forecast_m≥1.5) | 95% |
| IMPORTANTE | forecast_m≥1 o p_event≥0.35 o INTERMIT cv≥0.70 o sigma_m≥1 | 90% |
| NO_CRITICO | Resto | 50% |

Configurable vía env: `SERVICE_CRITICO`, `SERVICE_IMPORTANTE`, `SERVICE_NO_CRITICO`.

---

### 2.4 Truncamiento MC (`q_cap`) — **IMPLEMENTADO**
- **Regla:** `q_cap = ceil(Q_CAP_MULTIPLE * Forecast_m)` (default 3).
- **Variable de entorno:** `Q_CAP_MULTIPLE` (default 3).
- **Override:** Si `row.get("q_cap")` viene de vista/dim, se usa ese valor.
- **Orden en `apply_rounding`:** MOQ → múltiplo → cap.

---

### 2.5 Override por SKU
- **Tabla:** `sku_service_override(sku, service_prob_override)`.
- **Tabla de override:** `SKU_OVERRIDE_TABLE` (env).

---

### 2.6 Export CSV
- **Backend:** `GET /api/purchases/export` → CSV con Content-Disposition.
- **MC API:** `GET /dashboard/sugerencias/export` → CSV alternativo.
- **Frontend:** Botón "Descargar reporte CSV" en header (siempre visible).

---

## 3. Pendientes del Blueprint

| Paso | Estado | Acción |
|------|--------|--------|
| **Paso 1: Hard-stop SQL** | ⏳ Pendiente | Añadir `CASE WHEN eventos_12m=0 AND unidades_12m=0 THEN 0` en `v_sugerencias_compra` |
| **Paso 3: apply_rounding 0 vs MoQ** | ✅ Verificado | `if q <= 0: return 0.0` antes de MoQ — correcto |
| **Paso 5: Tests** | ⏳ Pendiente | Script `verify_zero_sales_skus.py` |

---

## 4. Parámetros Configurables (env)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `LT_OPERATIVO_DEFAULT` | 60 | Lead time en días (todos los SKUs) |
| `SERVICE_CRITICO` | 0.95 | Service level SKUs críticos |
| `SERVICE_IMPORTANTE` | 0.90 | Service level SKUs importantes |
| `SERVICE_NO_CRITICO` | 0.50 | Service level SKUs no críticos |
| `Q_CAP_MULTIPLE` | 3 | Múltiplo de Forecast_m para truncar MC |
| `SKU_OVERRIDE_TABLE` | sku_service_override | Tabla override service_prob |
| `MYSQL_HOST`, `MYSQL_USER`, etc. | — | Conexión DB |

---

## 5. Flujo de Cálculo (resumen)

```
1. FETCH v_analisis_sku_excel_mc (Forecast_m, p_event, q_mean, stock_pos, etc.)
2. decide_mc() → ¿aplica MC? (gates: eventos≥3, unidades>0, dias≥180)
3. Si NO MC → qty_recomendada_mc=0, cachear
4. Si SÍ MC:
   a. infer_lambda_eventos_mes() → lambda (con CAP)
   b. simulate_demand_horizon() → 8000 simulaciones
   c. mc_metrics() → stock_objetivo_mc (percentil service_prob)
   d. qty_raw = stock_objetivo_mc - stock_pos
   e. q_cap = ceil(3 * Forecast_m)
   f. apply_rounding(qty_raw, moq, multiplo, q_cap) → qty_final
5. UPSERT sku_mc_cache
```

---

## 6. Recomendaciones

1. **Hard-stop SQL:** Implementar en `v_sugerencias_compra` para cubrir cache desactualizado.
2. **Cron:** Ejecutar `POST /mc/run` periódicamente (ej. diario) para actualizar cache.
3. **Tests:** Crear `verify_zero_sales_skus.py` y ejecutarlo pre-deploy.
4. **Monitoreo:** Revisar SKUs con `qty_recomendada_mc` muy alta vs `q_cap` para ajustar `Q_CAP_MULTIPLE` si hace falta.
