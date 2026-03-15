-- =============================================================================
-- v_sugerencias_compra_legacy - Alias de la vista actual (sku_mc_cache)
-- =============================================================================
-- Para comparación con ss2_v_purchase_suggestions_v2.
-- La vista v_sugerencias_compra original sigue existiendo.
-- Este script crea un alias opcional para claridad.
--
-- Ejecutar: mysql -h HOST -u USER -p ss2_staging < deploy/ddl_v_sugerencias_compra_legacy.sql
-- =============================================================================

USE ss2_staging;

DROP VIEW IF EXISTS v_sugerencias_compra_legacy;

CREATE VIEW v_sugerencias_compra_legacy AS
SELECT * FROM v_sugerencias_compra;
