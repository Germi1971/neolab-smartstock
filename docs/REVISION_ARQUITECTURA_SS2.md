# Revisión: Implementación SS2 vs Especificación

**Fecha:** 2025-03-15  
**Objetivo:** Comparar lo implementado con la especificación arquitectónica Demand Engine → Policy Engine → Purchase Suggestion Layer.

---

## ✅ Lo que está bien implementado

### 1. Arquitectura de 3 capas
- **Demand Engine (Monte Carlo):** Escribe solo percentiles y métricas de riesgo en `ss2_demand_cache`. No escribe `stock_objetivo` ni `qty_recomendada`.
- **Policy Engine:** Lee `ss2_demand_cache` + `parametros_sku` + stock, aplica reglas y escribe en `ss2_policy_results`.
- **Purchase Suggestion Layer:** Vista `ss2_v_purchase_suggestions_v2` consume `ss2_policy_results`.

### 2. Monte Carlo refactorizado
- `main.py` escribe en `ss2_demand_cache` con: `demand_mean`, `demand_p50/p80/p90/p95/p99`, `p_stockout_at_current_stock`, `exp_lost_units`, `fill_rate_est`, `mc_enabled`, `mc_reason`.
- `sku_mc_cache` (legacy) se mantiene solo con `LEGACY_MC_CACHE=1` para compatibilidad durante migración.

### 3. Policy Engine modular
- Funciones: `choose_service_level`, `choose_base_demand_target`, `apply_cap_hist`, `apply_cap_cliente`, `apply_cap_vencimiento`, `apply_rounding`, `calculate_policy_for_sku`, `run_policy_engine`.
- Orden de caps: cap_hist → cap_cliente_dominante → cap_vencimiento.
- Criticidad unificada: CRITICO=0.97, ALTO=0.95, MEDIO=0.90, BAJO=0.80.

### 4. Tests de validación
- Casos 1–6 cubiertos: regular estable, intermitente MC, sin datos, cliente dominante, vencimiento, MOQ alto.

### 5. Pipeline
- `features → monte_carlo → ss2_demand_cache`
- `features → policy_engine → ss2_policy_results`
- Vista `ss2_v_purchase_suggestions_v2` usa `ss2_policy_results`.

---

## ⚠️ Discrepancias y mejoras recomendadas

### 1. **Percentil P97 para CRITICO** ✅ IMPLEMENTADO

**Especificación:**
> CRITICO → demand_p97 o p95

**Implementación:**
- `demand_p97` añadido a `ss2_demand_cache` (DDL).
- Monte Carlo calcula y guarda `demand_p97` en `mc_metrics`.
- `choose_base_demand_target`: CRITICO usa `demand_p97` si existe, fallback a `demand_p95` o `demand_p90`.

---

### 2. **Redondeo de stock_objetivo_final** ✅ IMPLEMENTADO

**Especificación:**
> stock_objetivo_final = redondear(target_after_caps)  
> qty_recomendada_final = max(0, stock_objetivo_final - stock_posicion)

**Implementación:**
- `apply_rounding_stock_target()` redondea `target_after_caps` con MOQ/múltiplo (sin q_cap).
- `stock_objetivo_final` = resultado redondeado.
- `qty_recomendada_final` = `apply_rounding(qty_raw)` para órdenes de compra (MOQ + q_cap).

---

### 3. **Nombres de columnas vs especificación** (Prioridad: Baja)

| Especificación | Implementación | Nota |
|----------------|----------------|------|
| `p_stockout_current` | `p_stockout_at_current_stock` | Más descriptivo; OK mantener |
| `base_demand_target` | `demand_target_value` en ss2_policy_results | Considerar alias o renombrar |
| `cap_hist`, `cap_cliente`, `cap_vencimiento` como columnas | Solo en `applied_caps` (string) | Spec pide columnas; impl tiene valores en string |

**Acción:** Opcional. Añadir columnas `base_demand_target`, `cap_hist`, `cap_cliente`, `cap_vencimiento` en `ss2_policy_results` para auditoría explícita.

---

### 4. **Fuente de cap_cliente y cap_vencimiento** ✅ IMPLEMENTADO

**Implementación:**
- `FETCH_POLICY_INPUTS_SQL` incluye `p.cap_cliente_dominante`, `p.cap_vencimiento`.
- Si las columnas no existen en `parametros_sku`, fallback automático a `FETCH_POLICY_INPUTS_SQL_LEGACY`.
- Migración `deploy/migration_add_caps_parametros.sql` para añadir columnas.

---

### 5. **Vista legacy v_sugerencias_compra** (Prioridad: Baja)

**Estado:** `ddl_v_sugerencias_compra_ss2_staging.sql` sigue usando `sku_mc_cache` y `stock_objetivo_mc`.

**Acción:** Mantener durante migración. El plan es usar `ss2_v_purchase_suggestions_v2` como nueva fuente. Cuando se migre, deprecar la vista legacy.

---

### 6. **Ejemplo M524-100L** (Prioridad: Baja)

**Especificación:** "ejemplo completo con SKU M524-100L".

**Acción:** Crear script o test que ejecute el flujo completo para M524-100L y documente el resultado esperado (inputs → demand cache → policy results → vista).

---

### 7. **MySQL 5.5** (Prioridad: Baja)

**Implementación:** Usa `utf8mb4`, `ENGINE=InnoDB`. Compatible con MySQL 5.5.3+.

**Acción:** Si el entorno es 5.5.0–5.5.2, cambiar a `utf8` en lugar de `utf8mb4`.

---

## 📋 Plan de migración (sin romper producción)

| Paso | Acción | Riesgo |
|------|--------|--------|
| 1 | Ejecutar DDL `ss2_demand_cache`, `ss2_policy_results` en staging | Bajo |
| 2 | Correr Monte Carlo → escribe en `ss2_demand_cache` | Bajo |
| 3 | Correr Policy Engine → escribe en `ss2_policy_results` | Bajo |
| 4 | Crear vista `ss2_v_purchase_suggestions_v2` | Bajo |
| 5 | Comparar `v_sugerencias_compra` vs `ss2_v_purchase_suggestions_v2` por SKU | Medio |
| 6 | Apuntar UI/dashboards a `ss2_v_purchase_suggestions_v2` | Medio |
| 7 | Desactivar `LEGACY_MC_CACHE` cuando todo esté validado | Bajo |
| 8 | Deprecar `v_sugerencias_compra` y `sku_mc_cache` | Bajo |

---

## Resumen de prioridades

1. **Alta:** Ninguna crítica; el flujo actual es coherente con la arquitectura.
2. **Media:** Añadir P97 para CRITICO, redondear `stock_objetivo_final`, definir fuente de `cap_cliente`/`cap_vencimiento`.
3. **Baja:** Alinear nombres de columnas, ejemplo M524-100L, compatibilidad MySQL 5.5.

---

## Archivos clave

| Archivo | Rol |
|---------|-----|
| `deploy/ddl_ss2_demand_cache.sql` | Tabla Demand Engine |
| `deploy/ddl_ss2_policy_results.sql` | Tabla Policy Engine |
| `deploy/ddl_ss2_v_purchase_suggestions_v2.sql` | Vista Purchase Suggestion |
| `app/policy_engine.py` | Lógica Policy Engine |
| `app/main.py` | Monte Carlo + escritura en ss2_demand_cache |
| `tests/test_policy_engine.py` | Tests funcionales |
