# Changelog Policy Engine y Features

## 2025-03 — Evento = 1 factura (FAC)

### Corrección en conteo de eventos

**Problema:** events_12m y total_units_12m contaban líneas (36) en lugar de facturas (5) y unidades reales (9).

**Solución:**
1. **ss2_rebuild_from_tabla1.py**: Agrupa líneas por (sku, fac) y crea 1 evento SHIP por factura con qty = nº de líneas.
2. **sp_ss2_sku_features_12m_refresh**: Nuevo SP que lee desde tabla1 directamente:
   - events_12m = COUNT(DISTINCT FAC)
   - total_units_12m = SUM(Cantidad)

**Aplicar:** Ejecutar `deploy/sp_ss2_sku_features_12m_from_tabla1.sql` en la base de datos.

---

## 2025-03 — Política P90 + Cap automático

### Cambios

1. **Percentil unificado en P90**
   - CRITICO, ALTO y MEDIO usan ahora `demand_p90` (antes P97/P95).
   - BAJO sigue usando `demand_p80`.
   - Objetivo: evitar objetivos excesivos en SKUs de baja rotación.

2. **Cap automático por demanda anual**
   - Si `cap_objetivo` es null: `cap_auto = ceil(CAP_AUTO_FACTOR × unidades_12m)`.
   - `CAP_AUTO_FACTOR` configurable por env (default 1.5).
   - Ejemplo: 9 uds/año → cap = 14.

3. **Dependencia de v_sku_features_12m**
   - El Policy Engine ahora hace LEFT JOIN a `v_sku_features_12m` para obtener `unidades_12m`.
   - Si la vista no existe, fallback usa `unidades_12m = 0` (sin cap automático).

### Variables de entorno

| Variable | Default | Descripción |
|----------|---------|-------------|
| CAP_AUTO_FACTOR | 1.5 | Factor para cap automático de stock objetivo. |

### Verificación

```bash
cd smartstock_mc_api
python scripts/verify_policy_changes.py
```
