# Demand Classification - SmartStock SS2

Capa de clasificación automática de demanda por SKU (ADI + CV²). Determina el modelo de reposición más adecuado para cada producto.

## Arquitectura

```
sku_obs_12m / tabla1
        ↓
ss2_demand_classification
        ↓
ss2_demand_cache (decide_mc usa demand_class)
        ↓
ss2_policy_results (excluye DEAD)
        ↓
ss2_purchase_scores
        ↓
ss2_v_purchase_suggestions_v2
```

## Clasificaciones

| demand_class | ADI | CV² | Modelo recomendado |
|--------------|-----|-----|--------------------|
| REGULAR | < 1.32 | < 0.49 | Analítico |
| ERRATIC | < 1.32 | ≥ 0.49 | Analítico o MC según volatilidad |
| INTERMITTENT | ≥ 1.32 | < 0.49 | MC preferido |
| LUMPY | ≥ 1.32 | ≥ 0.49 | MC fuertemente preferido |

| lifecycle_state | Condición | Acción |
|-----------------|-----------|--------|
| NEW | eventos_12m < 3 o dias_observados < 180 | Fallback rules |
| DORMANT | days_since_last_sale > 180 y unidades_6m = 0 | No auto buy |
| DEAD | days_since_last_sale > 365 y unidades_12m = 0 | Excluir de reposición |
| ACTIVE | Resto | Usar demand_class |

## Instalación

### 1. Crear tabla y vista

```bash
mysql -h HOST -u USER -p DATABASE < smartstock_mc_api/deploy/ddl_ss2_demand_classification.sql
mysql -h HOST -u USER -p DATABASE < smartstock_mc_api/deploy/migration_add_v_sku_classification_input.sql
```

### 2. (Opcional) Agregar clasificación a la vista de sugerencias

```bash
mysql -h HOST -u USER -p DATABASE < smartstock_mc_api/deploy/migration_add_demand_class_to_v_purchase_suggestions.sql
```

### 3. Orden de ejecución en pipeline

1. `refresh_sku_obs_12m.py` (ya existente)
2. `POST /classification/run` (nuevo)
3. `POST /mc/run`
4. `POST /policy/run`
5. `POST /scoring/run`

El cron `cron-daily.sh` ya incluye el paso 2.

## Ejemplo: SKU M524-100L

Supongamos:

- `meses_observados` = 12
- `meses_con_demanda` = 5
- `mean_qty_event` = 3.1
- `std_qty_event` = 2.7

**Cálculos:**

- ADI = 12 / 5 = **2.4**
- CV = 2.7 / 3.1 = 0.87
- CV² = 0.87² = **0.76**

**Resultado:** ADI ≥ 1.32 y CV² ≥ 0.49 → **LUMPY**

**Implicaciones:**

- MC fuertemente preferido
- Percentil alto si criticidad alta
- Caps por cliente/vencimiento
- Scoring con castigo por sobrestock

## Estrategia de migración sin romper producción

### Fase 1: Despliegue paralelo (sin impacto)

1. Ejecutar DDL `ddl_ss2_demand_classification.sql`
2. Ejecutar `migration_add_v_sku_classification_input.sql` (opcional; mejora precisión)
3. El endpoint `/classification/run` existe pero el cron usa `|| { echo "WARN..."; }` — si falla, no detiene el pipeline

### Fase 2: Activar clasificación

1. Ejecutar `POST /classification/run` manualmente
2. Verificar: `SELECT * FROM ss2_demand_classification LIMIT 20;`
3. El MC run intenta `FETCH_ACTIVE_SKUS_SQL_WITH_DC`; si la tabla no existe, hace fallback automático

### Fase 3: Validación

1. Comparar `demand_class` con `tipo_demanda` existente
2. Revisar SKUs clasificados como LUMPY vs INTERMITTENT
3. Confirmar que DEAD se excluyen de `ss2_policy_results`

### Rollback

- Eliminar el paso `classification/run` del cron
- Las queries tienen fallback: si `ss2_demand_classification` no existe, se usa la query legacy
- No es necesario borrar la tabla; simplemente dejar de ejecutar el job

## Integración con Stock HUD (modal)

El modal SmartStock en `SCANNER_REPO/apps/stock-hud` ahora:

1. **Prioriza** `ss2_v_purchase_suggestions_v2` (Policy Engine) sobre v_sugerencias_compra y MC cache
2. **Muestra** demand_class, lifecycle_state, classification_reason cuando existen
3. **Usa** stock_objetivo_final y qty_recomendada_final del Policy Engine

## Integración con Policy Engine

- **REGULAR** → `choose_base_demand_target` usa analytic si mc_enabled=0
- **LUMPY** → `decide_mc` fuerza MC cuando LT ≥ 45 días
- **DEAD** → Excluido en `FETCH_POLICY_INPUTS_SQL` (no aparece en policy)
- **DORMANT** → `decide_mc` retorna `mc_enabled=0` con razón "no auto buy"

## Explainability

Cada fila en `ss2_demand_classification` tiene `classification_reason`, por ejemplo:

- `"ADI=2.40 CV²=0.76 => LUMPY."`
- `"Lifecycle DORMANT."`

Esto permite auditar por qué cada SKU recibió su clasificación.
