-- =============================================================================
-- Clonar datos de neobd → ss2_staging (mismo servidor MySQL)
-- =============================================================================
-- Requiere: neobd y ss2_staging en el mismo servidor
-- Ejecutar: mysql -h TU_HOST -u TU_USER -p < deploy/sync_neobd_to_ss2_staging.sql
--
-- Tablas que alimentan v_sugerencias_compra: parametros_sku, tablaprecios, sku_mc_cache
-- =============================================================================

-- parametros_sku
DELETE FROM ss2_staging.parametros_sku;
INSERT INTO ss2_staging.parametros_sku SELECT * FROM neobd.parametros_sku;

-- tablaprecios
DELETE FROM ss2_staging.tablaprecios;
INSERT INTO ss2_staging.tablaprecios SELECT * FROM neobd.tablaprecios;

-- sku_mc_cache (omitir si neobd no lo tiene)
DELETE FROM ss2_staging.sku_mc_cache;
INSERT INTO ss2_staging.sku_mc_cache SELECT * FROM neobd.sku_mc_cache;

-- ss2_demand_cache (Demand Engine)
DELETE FROM ss2_staging.ss2_demand_cache;
INSERT INTO ss2_staging.ss2_demand_cache SELECT * FROM neobd.ss2_demand_cache;

-- ss2_policy_results (Policy Engine - requiere correr POST /policy/run antes)
DELETE FROM ss2_staging.ss2_policy_results;
INSERT INTO ss2_staging.ss2_policy_results SELECT * FROM neobd.ss2_policy_results;

-- ss2_purchase_scores (Purchase Scoring - requiere correr POST /scoring/run antes)
DELETE FROM ss2_staging.ss2_purchase_scores;
INSERT INTO ss2_staging.ss2_purchase_scores SELECT * FROM neobd.ss2_purchase_scores;

SELECT 'Sync completado' AS status;
SELECT COUNT(*) AS parametros_sku_count FROM ss2_staging.parametros_sku;
SELECT COUNT(*) AS tablaprecios_count FROM ss2_staging.tablaprecios;
SELECT COUNT(*) AS sku_mc_cache_count FROM ss2_staging.sku_mc_cache;
SELECT COUNT(*) AS ss2_demand_cache_count FROM ss2_staging.ss2_demand_cache;
SELECT COUNT(*) AS ss2_policy_results_count FROM ss2_staging.ss2_policy_results;
SELECT COUNT(*) AS ss2_purchase_scores_count FROM ss2_staging.ss2_purchase_scores;
