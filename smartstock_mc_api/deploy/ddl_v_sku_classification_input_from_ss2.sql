-- =============================================================================
-- v_sku_classification_input - Vista desde ss2_sku_features_12m
-- =============================================================================
-- Usar si tu pipeline usa ss2_sku_features_12m (no sku_obs_12m).
-- Requiere: ss2_sku_features_12m
--
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_v_sku_classification_input_from_ss2.sql
-- =============================================================================

DROP VIEW IF EXISTS v_sku_classification_input;

-- MySQL 5.5: no permite subquery en FROM. Usamos WHERE con subquery escalar.
CREATE VIEW v_sku_classification_input AS
SELECT
  f.sku,
  365 AS dias_observados,
  COALESCE(f.events_12m, 0) AS eventos_12m,
  COALESCE(f.total_units_12m, 0) AS unidades_12m,
  COALESCE(f.q_mean_event, 0) AS mu_unidades_evento,
  COALESCE(f.q_sd_event, 0) AS sigma_unidades_evento,
  NULL AS mu_gap_dias,
  NULL AS sigma_gap_dias,
  f.created_at AS obs_updated_at,
  COALESCE(f.months_active, 0) AS meses_con_demanda,
  f.last_ship_date AS last_sale_date,
  DATEDIFF(CURDATE(), COALESCE(f.last_ship_date, '1900-01-01')) AS days_since_last_sale,
  (COALESCE(f.total_units_12m, 0) / 2.0) AS unidades_6m
FROM ss2_sku_features_12m f
WHERE f.asof_date = (SELECT MAX(asof_date) FROM ss2_sku_features_12m);
