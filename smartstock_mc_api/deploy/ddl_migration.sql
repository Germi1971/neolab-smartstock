-- Migración: columnas adicionales para sku_mc_cache (compatible con main.py)
-- Ejecutar contra ss2_staging o neobd: mysql -u ss2 -p ss2_staging < deploy/ddl_migration.sql
-- Si alguna columna existe, ese ALTER fallará (ignorar).

ALTER TABLE sku_mc_cache ADD COLUMN service_prob_usado DOUBLE NULL AFTER service_prob;
ALTER TABLE sku_mc_cache ADD COLUMN service_prob_auto DOUBLE NULL AFTER service_prob_usado;
ALTER TABLE sku_mc_cache ADD COLUMN service_prob_override DOUBLE NULL AFTER service_prob_auto;
ALTER TABLE sku_mc_cache ADD COLUMN criticidad VARCHAR(50) NULL AFTER q_cap;
