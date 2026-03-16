# Deploy SmartStock SS2 en AWS Lightsail

Guía para replicar el setup de neobd local en AWS Lightsail, para que el Stock HUD muestre los resultados.

---

## Opción A: Pipeline corre en AWS (recomendado)

Si `tabla1`, `parametros_sku`, `tablaprecios` ya están en AWS:

### 1. Ejecutar DDLs en orden (contra AWS)

```bash
# Variables (ajustar con tu host AWS)
AWS_HOST="tu-instancia.region.cs.amazonlightsail.com"  # o IP pública
AWS_USER="neolab"
AWS_PASS="tu_password"
AWS_DB="neobd"

# Vista stock (requiere tabla1)
mysql -h $AWS_HOST -u $AWS_USER -p$AWS_PASS $AWS_DB < deploy/ddl_v_stock_estado_unidades_neobd.sql

# ss2_sku_features_12m (requerida por v_sku_features_12m)
mysql -h $AWS_HOST -u $AWS_USER -p$AWS_PASS $AWS_DB < deploy/ddl_ss2_sku_features_12m.sql

# Tablas SS2
mysql -h $AWS_HOST -u $AWS_USER -p$AWS_PASS $AWS_DB < deploy/ddl_ss2_demand_classification.sql
mysql -h $AWS_HOST -u $AWS_USER -p$AWS_PASS $AWS_DB < deploy/ddl_ss2_demand_cache.sql
mysql -h $AWS_HOST -u $AWS_USER -p$AWS_PASS $AWS_DB < deploy/ddl_ss2_policy_results.sql
mysql -h $AWS_HOST -u $AWS_USER -p$AWS_PASS $AWS_DB < deploy/ddl_ss2_purchase_scores.sql

# Vistas (requieren v_stock_estado_unidades, tabla1, parametros_sku, tablaprecios)
mysql -h $AWS_HOST -u $AWS_USER -p$AWS_PASS $AWS_DB < deploy/ddl_v_sku_classification_input_from_ss2.sql
mysql -h $AWS_HOST -u $AWS_USER -p$AWS_PASS $AWS_DB < deploy/ddl_v_sku_features_12m_from_ss2.sql
mysql -h $AWS_HOST -u $AWS_USER -p$AWS_PASS $AWS_DB < deploy/migration_add_demand_class_to_v_purchase_suggestions.sql
```

### 2. Configurar .env para apuntar a AWS

En `SCANNER_REPO/.env` (Stock HUD) y `smartstock_mc_api/.env`:

```
MYSQL_HOST=tu-instancia.region.cs.amazonlightsail.com
MYSQL_PORT=3306
MYSQL_USER=neolab
MYSQL_PASSWORD=tu_password
MYSQL_DB=neobd
```

### 3. Correr pipeline contra AWS

```bash
cd smartstock_mc_api
# Con .env apuntando a AWS:
py run_full_pipeline.py --skip-rebuild
```

---

## Opción B: Sincronizar desde neobd local → AWS

Si el pipeline corre en local y querés copiar los resultados a AWS:

### 1. Crear tablas/vistas en AWS (igual que Opción A, paso 1)

### 2. Ejecutar script de sync

```bash
py deploy/sync_neobd_to_aws.py
```

O manualmente con mysqldump:

```bash
# Exportar desde neobd local
mysqldump -h LOCAL_HOST -u user -p neobd \
  ss2_demand_classification ss2_demand_cache ss2_policy_results ss2_purchase_scores \
  parametros_sku tablaprecios \
  --no-create-info --complete-insert > ss2_export.sql

# Importar en AWS
mysql -h AWS_HOST -u user -p neobd < ss2_export.sql
```

---

## Requisitos previos en AWS

- MySQL 5.5+ accesible (puerto 3306 abierto en Lightsail)
- Tablas base: `tabla1`, `parametros_sku`, `tablaprecios`
- Vista `v_stock_estado_unidades` (ver `ddl_v_stock_estado_unidades_tabla1.sql`)
- Tabla `ss2_sku_features_12m` (si usás rebuild, debe existir y tener datos)

---

## Stock HUD

El Stock HUD usa `MYSQL_*` del `.env` y consulta:
1. `v_sugerencias_compra` (legacy)
2. `ss2_v_purchase_suggestions_v2` (fallback)

Si ambas vistas existen en AWS con datos, el HUD mostrará las sugerencias.

---

## Verificación

```sql
-- En AWS
SELECT COUNT(*) FROM ss2_v_purchase_suggestions_v2;
SELECT sku, stock_objetivo_final, qty_recomendada_final, priority_band 
FROM ss2_v_purchase_suggestions_v2 
WHERE qty_recomendada_final > 0 LIMIT 5;
```
