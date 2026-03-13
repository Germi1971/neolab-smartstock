# Cursor Blueprint: Refactoring del Sistema de Sugerencias de Reposición de Stock (NeoLab SmartStock)

## 📌 Contexto del Proyecto
**NeoLab SmartStock** es un sistema integral de gestión de inventarios y cálculo de sugerencias de compras.
- **Stack Tecnológico:** Backend en Python (FastAPI), Base de Datos MySQL (vistas y cache), Frontend en React (Vite).
- **Módulo Principal (Core):** Motor de cálculo de reposición basado en Reglas de Negocio (Mínimos, Objetivos, Cap) + Simulación Monte Carlo para Puntos de Pedido (ROP) y Stock de Seguridad.
- **Arquitectura actual:** `smartstock_mc_api/app/main.py` → lee `v_analisis_sku_excel_mc` → escribe `sku_mc_cache` → `v_sugerencias_compra` expone datos a la UI.

---

## ✅ Lo que ya está implementado (mantener / aprovechar)

| Componente | Ubicación | Descripción |
|------------|-----------|-------------|
| **Short-circuit `decide_mc`** | `main.py` L234-287 | Rechaza MC si `eventos_12m < 3`, `unidades_12m <= 0`, `dias_observados < 180`. SKUs inactivos no entran a simulación. |
| **Lambda CAP** | `infer_lambda_eventos_mes()` L316-353 | Evita explosión de lambda cuando `p_event ≈ 1`. Usa `lam_cap = Forecast_m / q_mean` y guard-rail `lambda <= 2*Forecast_m/q_mean`. |
| **Criticidad automática** | `compute_one()` L606-641 | Heurística por demanda/variabilidad: CRITICO (95%), IMPORTANTE (90%), NO_CRITICO (50%). |
| **`apply_rounding` con q_cap** | L293-310 | Función que aplica MOQ, múltiplo y **límite superior** (`q_cap`). Si `q_cap` es un número, trunca: `q = min(q, cap)`. |
| **Override por SKU** | `sku_service_override` | Tabla para forzar `service_prob_override` por SKU. |

---

## 🚨 Problemas a resolver

### 1. Falsos positivos (SKUs dormidos / sin historial)
SKUs con `eventos_12m = 0` o demanda nula pueden seguir mostrando sugerencias > 0 por:
- Cache desactualizado (`sku_mc_cache` con valores viejos).
- Vistas SQL que no aplican hard-stop final.

### 2. Truncamiento de MC desactivado
Monte Carlo suele recomendar cantidades **muy por encima** de lo operativamente razonable. El sistema tenía un mecanismo de truncamiento (`q_cap`) que está **implementado pero desactivado**:
- En `compute_one` L658: `q_cap = None  # hoy lo dejamos NULL hasta que lo tengas en dim/vista`
- En SQL: `NULL AS q_cap` — nunca se lee de la vista.
- **Efecto:** Las recomendaciones MC no se limitan; pueden ser excesivas.

### 3. MOQ convirtiendo 0 en mínimo
Si la matemática da `0` pero el MoQ es 20, el redondeo podría convertir en 20. El límite a cero debe aplicarse **antes** del MoQ.

---

## 🎯 Objetivo General
Refactorizar la tubería para:
1. **Cero sugerencia** para SKUs sin historial de venta (hard-stop en SQL + short-circuit en Python).
2. **Truncar** las recomendaciones MC con una regla heurística (`q_cap`) para evitar cantidades irracionales.
3. **Respetar** overrides manuales y lógicas MoQ/múltiplos sin distorsionar ceros reales.

---

## 🛠️ Plan de Ejecución Detallado

### Paso 1: Hard-Stop en Base de Datos (Views de Sugerencias)
**Objetivo:** La UI nunca muestre sugerencia > 0 para SKUs sin historial.
- **Archivos:** `v_sugerencias_compra.sql` (y vistas derivadas como `v_stock_semaforo_ui.sql` si existen).
- **Acción:**
  - Envolver el cálculo de `qty_recomendada` / `qty_final` con:
    ```sql
    CASE 
      WHEN COALESCE(f.eventos_12m, 0) = 0 AND COALESCE(f.unidades_12m, 0) = 0 THEN 0 
      ELSE <logica_actual_qty_final> 
    END AS qty_final
    ```
  - *(Opcional)* Columna `motivo_bloqueo` para auditar ("Forzado a 0 por falta de histórico").
- **Excepción:** Si `sugerencia_aprobada = 1` (override humano), respetar el valor aprobado.

---

### Paso 2: Reactivar truncamiento MC (`q_cap`)
**Objetivo:** Limitar la cantidad recomendada por MC a un techo operativamente razonable.
- **Archivo:** `smartstock_mc_api/app/main.py`.
- **Acción:**
  1. **Definir regla heurística** para `q_cap` cuando no exista en dim/vista. Ejemplos:
     - `q_cap = ceil(3 * Forecast_m)` — máximo 3 meses de demanda.
     - `q_cap = ceil(2 * stock_objetivo_analítico)` si existe.
     - Variable de entorno `Q_CAP_MULTIPLE` (default 3) para ajustar sin redeploy.
  2. **Reemplazar** en `compute_one` L658:
     ```python
     # Antes: q_cap = None
     # Después: calcular q_cap por heurística o leer de vista/dim
     forecast_m = float(row.get("Forecast_m") or 0.0)
     q_cap = int(math.ceil(float(os.getenv("Q_CAP_MULTIPLE", "3")) * forecast_m)) if forecast_m > 0 else None
     ```
  3. **Opcional:** Si existe tabla `sku_q_cap(sku, q_cap)` o columna en `v_analisis_sku_excel_mc`, leer de ahí y usar como override por SKU.
  4. **SQL:** Cambiar `NULL AS q_cap` por la columna real si la vista la expone.
- **Etiqueta:** `[FIX DOMICILIADO - TRUNCAMIENTO MC]`

---

### Paso 3: Orden correcto en `apply_rounding` (0 antes de MoQ)
**Objetivo:** Evitar que MoQ convierta un 0 real en el mínimo de compra.
- **Archivo:** `main.py` — función `apply_rounding` L293-310.
- **Verificar:** La lógica actual hace `q = max(0, qty)` y luego `q = max(q, moq)`. Si `qty_raw = 0`, `q` queda 0; pero `max(0, moq) = moq` — **esto podría ser el bug**. Revisar:
  - Si `qty <= 0` → retornar `0.0` **sin** aplicar MoQ. (Ya está: `if q <= 0: return 0.0`).
  - Confirmar que `qty_raw` que llega desde MC nunca es un "casi cero" que se redondea mal.

---

### Paso 4: Short-circuit ya cubierto por `decide_mc`
**Estado:** Implementado. `decide_mc` rechaza MC si `eventos_12m < 3`, `unidades_12m <= 0`, `dias_observados < 180`. No requiere cambios adicionales salvo ajustar umbrales si se considera necesario.

---

### Paso 5: Validaciones y tests pre-deploy
**Objetivo:** Detectar regresiones antes de producción.
- **Script:** `verify_zero_sales_skus.py` (o integrado en pytest).
- **Query:**
  ```sql
  SELECT c.sku, c.qty_recomendada_mc 
  FROM sku_mc_cache c
  JOIN v_analisis_sku_excel_mc f ON f.sku = c.sku
  WHERE COALESCE(f.eventos_12m, 0) = 0 
    AND COALESCE(f.unidades_12m, 0) = 0 
    AND c.qty_recomendada_mc > 0;
  ```
- Si devuelve filas → test falla.

---

## 🧠 Directrices Estratégicas

| Regla | Detalle |
|-------|---------|
| **MoQ vs 0** | Si la matemática da `0`, debe quedarse en `0`. El MoQ solo aplica cuando la cantidad es > 0. |
| **Override humano** | `sugerencia_aprobada = 1` o override manual **siempre** gana al "0 automático por inactividad". |
| **Truncamiento** | `q_cap` limita el exceso de MC; no debe ser tan bajo que impida cubrir demanda real. Empezar con múltiplo conservador (2–3x Forecast_m). |
| **Comentarios** | Etiquetar cambios con `[FIX DOMICILIADO - INTERMITENTE]` o `[FIX DOMICILIADO - TRUNCAMIENTO MC]` para trazabilidad. |

---

## 📋 Resumen de prioridades

1. **Paso 2** — Reactivar `q_cap` (truncamiento MC): impacto directo en recomendaciones excesivas.
2. **Paso 1** — Hard-stop SQL: red de seguridad para cache/vistas.
3. **Paso 3** — Revisar `apply_rounding`: asegurar que 0 no se convierta en MoQ.
4. **Paso 5** — Tests: prevenir regresiones.
