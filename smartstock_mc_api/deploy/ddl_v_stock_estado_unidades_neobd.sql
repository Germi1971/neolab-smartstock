-- =============================================================================
-- v_stock_estado_unidades para neobd (usa tabla1)
-- =============================================================================
-- Ejecutar: mysql -h HOST -u USER -p neobd < deploy/ddl_v_stock_estado_unidades_neobd.sql
-- =============================================================================

DROP VIEW IF EXISTS v_stock_estado_unidades;

CREATE VIEW v_stock_estado_unidades AS
SELECT
  t.`Código` AS sku,
  COALESCE(SUM(CASE WHEN t.`E/S` = 'STOCK' THEN 1 ELSE 0 END), 0) AS stock_libre_deposito,
  COALESCE(SUM(CASE WHEN t.`E/S` = 'R' THEN 1 ELSE 0 END), 0) AS stock_reservado_deposito,
  COALESCE(SUM(CASE WHEN t.`E/S` IN ('STOCK','R') THEN 1 ELSE 0 END), 0) AS stock_total_deposito,
  COALESCE(SUM(CASE WHEN t.`E/S` = 'IMPO - STOCK' THEN 1 ELSE 0 END), 0) AS impo_libre,
  COALESCE(SUM(CASE WHEN t.`E/S` = 'IMPO - R' THEN 1 ELSE 0 END), 0) AS impo_reservada,
  COALESCE(SUM(CASE WHEN t.`E/S` IN ('IMPO - STOCK','IMPO - R') THEN 1 ELSE 0 END), 0) AS impo_total
FROM tabla1 t
WHERE t.`Código` IS NOT NULL AND TRIM(t.`Código`) <> ''
GROUP BY t.`Código`;
