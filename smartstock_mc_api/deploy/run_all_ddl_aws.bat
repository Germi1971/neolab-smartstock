@echo off
REM Ejecutar todos los DDLs contra AWS Lightsail
REM Ajustar variables abajo con tu instancia AWS

set AWS_HOST=tu-instancia.region.cs.amazonlightsail.com
set AWS_USER=neolab
set AWS_PASS=tu_password
set AWS_DB=neobd

echo === Deploy SS2 a AWS Lightsail ===

REM v_stock_estado_unidades (requiere tabla1)
mysql -h %AWS_HOST% -u %AWS_USER% -p%AWS_PASS% %AWS_DB% < ddl_v_stock_estado_unidades_neobd.sql

REM ss2_sku_features_12m (requerida por v_sku_features_12m; si no existe)
mysql -h %AWS_HOST% -u %AWS_USER% -p%AWS_PASS% %AWS_DB% < ddl_ss2_sku_features_12m.sql

mysql -h %AWS_HOST% -u %AWS_USER% -p%AWS_PASS% %AWS_DB% < ddl_ss2_demand_classification.sql
mysql -h %AWS_HOST% -u %AWS_USER% -p%AWS_PASS% %AWS_DB% < ddl_ss2_demand_cache.sql
mysql -h %AWS_HOST% -u %AWS_USER% -p%AWS_PASS% %AWS_DB% < ddl_ss2_policy_results.sql
mysql -h %AWS_HOST% -u %AWS_USER% -p%AWS_PASS% %AWS_DB% < ddl_ss2_purchase_scores.sql
mysql -h %AWS_HOST% -u %AWS_USER% -p%AWS_PASS% %AWS_DB% < ddl_v_sku_classification_input_from_ss2.sql
mysql -h %AWS_HOST% -u %AWS_USER% -p%AWS_PASS% %AWS_DB% < ddl_v_sku_features_12m_from_ss2.sql
mysql -h %AWS_HOST% -u %AWS_USER% -p%AWS_PASS% %AWS_DB% < migration_add_demand_class_to_v_purchase_suggestions.sql

echo === Listo ===
pause
