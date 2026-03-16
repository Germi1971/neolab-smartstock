-- =============================================================================
-- Clonar datos de neobd → ss2_staging (mismo servidor MySQL)
-- =============================================================================
-- Requiere: neobd y ss2_staging en el mismo servidor
-- Ejecutar: mysql -h 127.0.0.1 -P 3307 -u ss2 -p < deploy/sync_neobd_to_ss2_staging.sql
--
-- Prerrequisito: las tablas deben existir en ss2_staging (misma estructura que neobd).
-- Para ss2_demand_classification: mysql ... ss2_staging < deploy/ddl_ss2_demand_classification.sql
--
-- Tablas sincronizadas: parametros_sku, tablaprecios, sku_mc_cache, ss2_demand_cache,
--   ss2_policy_results, ss2_purchase_scores, ss2_demand_classification
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

-- ss2_demand_classification (Demand Classification - requiere correr POST /classification/run antes)
DELETE FROM ss2_staging.ss2_demand_classification;
INSERT INTO ss2_staging.ss2_demand_classification SELECT * FROM neobd.ss2_demand_classification;

SELECT 'Sync completado' AS status;
SELECT COUNT(*) AS parametros_sku_count FROM ss2_staging.parametros_sku;
SELECT COUNT(*) AS tablaprecios_count FROM ss2_staging.tablaprecios;
SELECT COUNT(*) AS sku_mc_cache_count FROM ss2_staging.sku_mc_cache;
SELECT COUNT(*) AS ss2_demand_cache_count FROM ss2_staging.ss2_demand_cache;
SELECT COUNT(*) AS ss2_policy_results_count FROM ss2_staging.ss2_policy_results;
SELECT COUNT(*) AS ss2_purchase_scores_count FROM ss2_staging.ss2_purchase_scores;
SELECT COUNT(*) AS ss2_demand_classification_count FROM ss2_staging.ss2_demand_classification;
