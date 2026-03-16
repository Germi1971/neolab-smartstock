-- =============================================================================
-- v_sku_features_12m - Vista desde sku_obs_12m
-- =============================================================================
-- Usar ESTE archivo si tu pipeline usa refresh_sku_obs_12m.py y la tabla sku_obs_12m existe.
-- (No usás ss2_sku_features_12m)
--
-- La vista ss2_v_purchase_suggestions_v2 requiere: SKU, meses_con_venta_12m, demanda_prom_mensual_12m
--
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_v_sku_features_12m_from_sku_obs.sql
-- =============================================================================

DROP VIEW IF EXISTS v_sku_features_12m;

CREATE VIEW v_sku_features_12m AS
SELECT
  o.sku AS SKU,
  -- Aproximación: si hay eventos, asumimos al menos 1 mes; máx 12
  LEAST(COALESCE(o.eventos_12m, 0), 12) AS meses_con_venta_12m,
  -- Demanda promedio mensual = unidades_12m / 12
  (COALESCE(o.unidades_12m, 0) / 12.0) AS demanda_prom_mensual_12m,
  o.unidades_12m AS total_units_12m,
  o.eventos_12m AS events_12m,
  o.mu_unidades_evento AS q_mean_event,
  o.sigma_unidades_evento AS q_sd_event,
  (CASE WHEN COALESCE(o.eventos_12m, 0) > 0 THEN o.eventos_12m / 12.0 ELSE 0 END) AS p_event,
  NULL AS last_ship_date,
  o.updated_at AS asof_date
FROM sku_obs_12m o;
