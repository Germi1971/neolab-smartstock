-- Retención sugerida (ajustable)
-- Dejar 365 días de runs/resultados (si las tablas lo soportan)
DELETE FROM ss2_mc_results
WHERE asof_date < DATE_SUB(CURDATE(), INTERVAL 365 DAY);

DELETE FROM ss2_mc_runs
WHERE asof_date < DATE_SUB(CURDATE(), INTERVAL 365 DAY);

-- Si algún día querés podar stock_daily
DELETE FROM ss2_stock_daily
WHERE snapshot_date < DATE_SUB(CURDATE(), INTERVAL 365 DAY);