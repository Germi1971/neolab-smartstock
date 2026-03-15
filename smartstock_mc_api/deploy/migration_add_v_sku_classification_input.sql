-- =============================================================================
-- Vista v_sku_classification_input - Inputs para demand classification
-- =============================================================================
-- Proporciona meses_con_demanda, last_sale_date, unidades_6m para clasificación.
-- Opcional: ejecutar si sku_obs_12m no tiene estos campos.
--
-- Requiere: sku_obs_12m, tabla1 (tabla de movimientos)
-- =============================================================================

-- Vista que enriquece sku_obs_12m con meses_con_demanda y last_sale_date
DROP VIEW IF EXISTS v_sku_classification_input;
CREATE VIEW v_sku_classification_input AS
SELECT
  o.sku,
  o.dias_observados,
  o.eventos_12m,
  o.unidades_12m,
  o.mu_unidades_evento,
  o.sigma_unidades_evento,
  o.mu_gap_dias,
  o.sigma_gap_dias,
  o.updated_at AS obs_updated_at,
  COALESCE(m.meses_con_demanda, 0) AS meses_con_demanda,
  m.last_sale_date,
  DATEDIFF(CURDATE(), COALESCE(m.last_sale_date, '1900-01-01')) AS days_since_last_sale,
  COALESCE(u6.unidades_6m, 0) AS unidades_6m
FROM sku_obs_12m o
LEFT JOIN (
  SELECT
    t.`Código` AS sku,
    COUNT(DISTINCT DATE_FORMAT(t.`Fecha`, '%Y-%m')) AS meses_con_demanda,
    MAX(t.`Fecha`) AS last_sale_date
  FROM tabla1 t
  WHERE TRIM(t.`E/S`) IN ('S')
    AND t.`Fecha` >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)
    AND t.`Código` IS NOT NULL
  GROUP BY t.`Código`
) m ON m.sku = o.sku
LEFT JOIN (
  SELECT
    t.`Código` AS sku,
    SUM(CAST(t.`Cantidad` AS DECIMAL(18,6))) AS unidades_6m
  FROM tabla1 t
  WHERE TRIM(t.`E/S`) IN ('S')
    AND t.`Fecha` >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
    AND t.`Código` IS NOT NULL
  GROUP BY t.`Código`
) u6 ON u6.sku = o.sku;
