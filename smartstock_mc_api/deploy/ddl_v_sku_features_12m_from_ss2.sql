-- =============================================================================
-- v_sku_features_12m - Vista desde ss2_sku_features_12m
-- =============================================================================
-- Usar ESTE archivo si tu pipeline usa ss2_rebuild_from_tabla1 + sp_ss2_sku_features_12m_refresh
-- y la tabla ss2_sku_features_12m existe.
--
-- La vista ss2_v_purchase_suggestions_v2 requiere: SKU, meses_con_venta_12m, demanda_prom_mensual_12m
--
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_v_sku_features_12m_from_ss2.sql
-- =============================================================================

DROP VIEW IF EXISTS v_sku_features_12m;

-- MySQL 5.5: no permite subquery en FROM. Usamos WHERE con subquery escalar.
CREATE VIEW v_sku_features_12m AS
SELECT
  f.sku AS SKU,
  COALESCE(f.months_active, 0) AS meses_con_venta_12m,
  COALESCE(f.demand_mean_m, 0) AS demanda_prom_mensual_12m,
  f.total_units_12m,
  f.events_12m,
  f.q_mean_event,
  f.q_sd_event,
  f.p_event,
  f.last_ship_date,
  f.asof_date
FROM ss2_sku_features_12m f
WHERE f.asof_date = (SELECT MAX(asof_date) FROM ss2_sku_features_12m);
