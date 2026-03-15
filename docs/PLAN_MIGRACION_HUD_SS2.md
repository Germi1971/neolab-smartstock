# Plan: Migrar Stock HUD a SS2

Para que M524-100L (y el resto) muestre datos correctos según el pipeline SS2.

**Importante:** La API debe apuntar a la misma base que usa el HUD. Si el HUD usa `ss2_staging`, configurar `MYSQL_DB=ss2_staging` en el `.env` de la API.

---

## Problema actual

- El HUD usa **v_sugerencias_compra** → lee de **sku_mc_cache** (legacy).
- La sugerencia de 2 unidades y el estado "Bajo mínimo" vienen de esa lógica antigua.
- El pipeline SS2 (Policy Engine + ss2_policy_results) no está conectado al HUD.

---

## Solución: 4 pasos

### Paso 1. Aplicar DDL y migraciones en la base (neobd o ss2_staging)

Ejecutar en orden:

```bash
# 1. Tablas SS2 (si no existen)
mysql -h HOST -u USER -p DATABASE < smartstock_mc_api/deploy/ddl_ss2_demand_cache.sql
mysql -h HOST -u USER -p DATABASE < smartstock_mc_api/deploy/ddl_ss2_policy_results.sql
mysql -h HOST -u USER -p DATABASE < smartstock_mc_api/deploy/ddl_ss2_purchase_scores.sql

# 2. Migraciones (si las tablas ya existían)
mysql -h HOST -u USER -p DATABASE < smartstock_mc_api/deploy/migration_add_demand_p97.sql
mysql -h HOST -u USER -p DATABASE < smartstock_mc_api/deploy/migration_add_caps_parametros.sql

# 3. Vista SS2
mysql -h HOST -u USER -p ss2_staging < smartstock_mc_api/deploy/ddl_ss2_v_purchase_suggestions_v2.sql
```

### Paso 2. Ejecutar el pipeline completo (en AWS o local)

```bash
# En AWS Lightsail (API en 8001)
curl -X POST http://localhost:8001/mc/run
curl -X POST http://localhost:8001/policy/run
curl -X POST http://localhost:8001/scoring/run
```

O usar el cron diario (ya incluye estos 3 pasos).

### Paso 3. Reemplazar v_sugerencias_compra por la versión SS2

```bash
mysql -h HOST -u USER -p ss2_staging < smartstock_mc_api/deploy/ddl_v_sugerencias_compra_ss2.sql
```

Esto redefine `v_sugerencias_compra` para que lea de `ss2_v_purchase_suggestions_v2` (Policy Engine). El HUD no requiere cambios; sigue usando la misma vista.

### Paso 4. Verificar

- Abrir el modal de M524-100L en el HUD.
- Debe mostrar:
  - **Stock objetivo** = valor de ss2_policy_results (Policy Engine).
  - **Sugerencia** = qty_recomendada_final (gap hasta objetivo, con MOQ).
  - **Estado** = BAJO_OBJ si stock < objetivo, BAJO_MIN si stock < mínimo.

---

## DDL: v_sugerencias_compra apuntando a SS2

El archivo `ddl_v_sugerencias_compra_ss2.sql` redefine `v_sugerencias_compra` para que sea un alias de `ss2_v_purchase_suggestions_v2` con las columnas que el HUD espera.
