# Contrato de Datos SS2 - Demand Engine + Policy Engine

## Principio rector

> **Demand Engine estima demanda futura; Policy Engine decide stock objetivo final.**

---

## 1. ss2_demand_cache (Demand Engine)

### Responsabilidad
Almacenar **únicamente** estimaciones de demanda y métricas de riesgo. **No** stock objetivo ni cantidad recomendada.

### Campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sku` | VARCHAR(80) | PK |
| `n_sims` | INT | Simulaciones ejecutadas |
| `horizon_days` | INT | LT + review |
| `lt_days` | INT | Lead time operativo |
| `review_days` | INT | Período de revisión |
| `lambda_eventos_mes` | DOUBLE | Lambda Poisson |
| `q_mean_event` | DOUBLE | Media por evento |
| `q_sd_event` | DOUBLE | Desv. estándar por evento |
| `regimen` | VARCHAR(50) | REGULAR, INTERMITENTE, NUEVO |
| `criticidad` | VARCHAR(20) | CRITICO, ALTO, MEDIO, BAJO |
| `service_prob_usado` | DOUBLE | Service level en simulación |
| **demand_mean** | DOUBLE | Media de demanda simulada |
| **demand_p50** | DOUBLE | Percentil 50 |
| **demand_p80** | DOUBLE | Percentil 80 |
| **demand_p90** | DOUBLE | Percentil 90 |
| **demand_p95** | DOUBLE | Percentil 95 |
| **demand_p99** | DOUBLE | Percentil 99 |
| **p_stockout_at_current_stock** | DOUBLE | P(demanda > stock_posicion) |
| **exp_lost_units** | DOUBLE | Unidades esperadas perdidas |
| **fill_rate_est** | DOUBLE | 1 - p_stockout (o estimación explícita) |
| **mc_enabled** | TINYINT | 1=MC activo, 0=fallback |
| **mc_reason** | VARCHAR(255) | Razón de activación/desactivación |
| `updated_at` | DATETIME | Última actualización |

### Mapeo criticidad → service level (Policy Engine)

| Criticidad | Service level |
|------------|---------------|
| CRITICO | 0.97 |
| ALTO | 0.95 |
| MEDIO | 0.90 |
| BAJO | 0.80 |

### Mapeo desde legacy

| Legacy (sku_mc_cache) | ss2_demand_cache |
|------------------------|------------------|
| CRITICO | CRITICO |
| IMPORTANTE | ALTO |
| NO_CRITICO | BAJO |
| (nuevo) | MEDIO |

---

## 2. ss2_policy_results (Policy Engine)

### Responsabilidad
Almacenar **únicamente** resultados de decisión de inventario: stock_min, stock_objetivo_final, qty_recomendada_final, y trazabilidad completa.

### Campos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `sku` | VARCHAR(80) | PK |
| **stock_min** | INT | Mínimo operativo |
| **stock_objetivo_final** | DOUBLE | Objetivo tras caps y rounding |
| **qty_recomendada_final** | DOUBLE | Cantidad a comprar |
| `demand_target_source` | VARCHAR(80) | Origen: demand_p95, demand_p90, analytic_target |
| `demand_target_value` | DOUBLE | Valor usado antes de caps |
| `selected_service_level` | DOUBLE | 0.80, 0.90, 0.95, 0.97 |
| `applied_caps` | VARCHAR(500) | Caps que recortaron (ej: "cap_hist:120") |
| `policy_reason` | VARCHAR(255) | Razón corta |
| `explanation` | TEXT | Explicación auditable |
| `criticidad` | VARCHAR(20) | CRITICO, ALTO, MEDIO, BAJO |
| `moq` | INT | MOQ aplicado |
| `multiplo_compra` | INT | Múltiplo aplicado |
| `q_cap` | INT | Cap de cantidad aplicado |
| `stock_posicion_at_calc` | INT | Stock al momento del cálculo |
| `backlog_qty_at_calc` | INT | Backlog al momento del cálculo |
| `updated_at` | DATETIME | Última actualización |

### Orden de aplicación de caps

1. `base_demand_target` (percentil o analytic_target)
2. `cap_hist`
3. `cap_cliente_dominante`
4. `cap_vencimiento`
5. MOQ / múltiplos / redondeo comercial

### Regla de selección de demand target

| Condición | Target |
|-----------|--------|
| mc_enabled=1, CRITICO o ALTO | demand_p95 o demand_p97 |
| mc_enabled=1, MEDIO | demand_p90 |
| mc_enabled=1, BAJO | demand_p80 |
| mc_enabled=0 | analytic_target (parametros_sku.stock_objetivo) |

---

## 3. Flujo de datos

```
v_analisis_sku_excel_mc  →  Demand Engine (MC API)  →  ss2_demand_cache
                                                              ↓
parametros_sku + v_stock_estado_unidades + ss2_demand_cache  →  Policy Engine  →  ss2_policy_results
                                                                                      ↓
                                                                              v_sugerencias_compra (futura)
```

---

## 4. Compatibilidad con sku_mc_cache

Durante la migración:

- `sku_mc_cache` sigue existiendo y puede ser usada por la vista actual.
- `ss2_demand_cache` y `ss2_policy_results` son tablas nuevas.
- **Bloque 2:** MC API escribe en `ss2_demand_cache` (nuevo contrato) y opcionalmente en `sku_mc_cache` (LEGACY_MC_CACHE=1).
- El sync `sync_neobd_to_ss2_staging.sql` incluye `ss2_demand_cache` (requiere DDL aplicado en neobd y ss2_staging).
- Se depreca `sku_mc_cache` gradualmente cuando la vista migre a `ss2_policy_results`.

---

## 5. Ejemplo de auditoría por SKU (M524-100L)

| Campo | Valor |
|-------|-------|
| regimen | INTERMITENTE |
| mc_enabled | 1 |
| demand_target_source | demand_p90 |
| selected_service_level | 0.90 |
| applied_caps | cap_hist:150 |
| policy_reason | MC:p90 MEDIO |
| explanation | INTERMITENTE U=0.65. MC activo. demand_p90=85. Cap hist 150 recortó. MOQ 20 aplicado. qty_final=60. |
