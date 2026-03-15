# Smart Replenishment Score (SRS)

## Objetivo

Priorizar SKUs para reposición. **No decide cantidad** (eso es Policy Engine). Decide **qué comprar primero**.

Entre cientos de SKUs, el sistema muestra primero los que merecen atención.

---

## Fórmula

```
SRS = 0.30 * stockout_score
    + 0.20 * criticidad_score
    + 0.15 * lead_time_score
    + 0.10 * acceleration_score
    + 0.10 * margen_score
    + 0.10 * backlog_score
    - 0.10 * overstock_penalty
    - 0.05 * cliente_penalty
```

Reescalado a 0-100.

---

## Bandas de prioridad

| SRS | Banda | Acción |
|-----|-------|--------|
| 85-100 | URGENTE | Reponer ya |
| 70-84 | ALTA | Muy alta prioridad |
| 55-69 | MEDIA | Prioridad media |
| 40-54 | BAJA | Revisar |
| <40 | MUY_BAJA | No priorizar ahora |

---

## Ejemplo M524-100L

| Variable | Valor | Score |
|----------|-------|-------|
| p_stockout_current | 0.78 | 78 |
| criticidad | ALTO | 80 |
| LT días | 75 | 70 |
| aceleración | 1.55 (15.5/10) | 80 |
| margen | alto | 80 |
| backlog | bajo | 30 |
| riesgo sobrestock | medio | 40 |
| top1_share | 0.68 | -20 |

Cálculo:
```
SRS = 0.30*78 + 0.20*80 + 0.15*70 + 0.10*80 + 0.10*80 + 0.10*30 - 0.10*40 - 0.05*20
    = 23.4 + 16 + 10.5 + 8 + 8 + 3 - 4 - 1
    ≈ 64.9
```

**Resultado:** Prioridad MEDIA-ALTA (banda MEDIA o ALTA según cortes).

---

## Pipeline de integración

```
features
  ↓
demand engine (Monte Carlo)
  ↓
ss2_demand_cache
  ↓
policy engine
  ↓
ss2_policy_results
  ↓
purchase scoring
  ↓
ss2_purchase_scores
  ↓
ss2_v_purchase_suggestions_v2
```

---

## Orden de ejecución diario

1. `POST /mc/run` → escribe ss2_demand_cache
2. `POST /policy/run` → escribe ss2_policy_results
3. `POST /scoring/run` → escribe ss2_purchase_scores

La vista `ss2_v_purchase_suggestions_v2` consume todo y muestra:
- `qty_recomendada_final` (cantidad)
- `priority_score`, `priority_band`, `priority_reason` (prioridad)

---

## Aceleración de demanda (futuro)

Para detectar productos en tendencia o en declive:

```
acceleration = demand_6m / demand_24m
```

Si `demand_6m` y `demand_24m` existen en las vistas/tablas, el scoring los usa. Si no, usa fallback neutral (40 puntos).

Para habilitar: añadir columnas `demanda_6m`, `demanda_24m` a `v_sku_features_12m` o vista equivalente.

---

## Inputs ampliados (FETCH_SCORING_INPUTS_SQL)

El scoring usa estos campos cuando existen:

| Campo | Fuente | Uso |
|-------|--------|-----|
| `margen_pct` | v_sku_event_features_12m (margen/revenue) | score_margen |
| `top1_share_12m` | Vista de share cliente dominante | penalty_cliente |
| `demanda_6m`, `demanda_24m` | v_sku_features_12m o similar | score_acceleration |
| `days_of_supply` | Calculado: stock / demanda_anual_diaria | penalty_overstock |
| `lead_time_dias` | parametros_sku (fallback si ss2_demand_cache no tiene lt_days) | score_lead_time |

Si `v_sku_event_features_12m` no existe, se usa `FETCH_SCORING_INPUTS_SQL_LEGACY` (sin margen_pct).
