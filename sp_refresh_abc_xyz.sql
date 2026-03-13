CREATE DEFINER=`neolab`@`%` PROCEDURE `sp_refresh_abc_xyz`()
BEGIN
  -- 1) Upsert métricas base (solo activos)
  INSERT INTO neobd.sku_abc_xyz (sku, margen_12m, cv, pct_mes_venta, abc_class, xyz_class, updated_at)
  SELECT
    d.sku,
    COALESCE(f.margen_total_12m, 0) AS margen_12m,
    CASE
      WHEN COALESCE(f.demanda_prom_mensual_12m,0) > 0
      THEN f.sigma_mensual_12m / f.demanda_prom_mensual_12m
      ELSE NULL
    END AS cv,
    COALESCE(f.pct_meses_con_venta_12m, 0) AS pct_mes_venta,
    'C' AS abc_class,
    'Z' AS xyz_class,
    NOW() AS updated_at
  FROM neobd.v_dim_sku_excel d
  LEFT JOIN neobd.v_sku_features f
    ON f.SKU = d.sku
  WHERE d.activo = 1
  ON DUPLICATE KEY UPDATE
    margen_12m     = VALUES(margen_12m),
    cv            = VALUES(cv),
    pct_mes_venta = VALUES(pct_mes_venta),
    updated_at    = VALUES(updated_at);

  -- 2) Eliminar SKUs que ya no están activos (opcional, pero ordena)
  DELETE t
  FROM neobd.sku_abc_xyz t
  LEFT JOIN neobd.v_dim_sku_excel d ON d.sku = t.sku
  WHERE d.sku IS NULL OR d.activo <> 1;

  -- 3) Calcular ABC por acumulado de margen usando variables
  SET @total := (SELECT IFNULL(SUM(margen_12m),0) FROM neobd.sku_abc_xyz);
  SET @run := 0;

  UPDATE neobd.sku_abc_xyz t
  JOIN (
    SELECT sku, (@run := @run + margen_12m) AS acum
    FROM neobd.sku_abc_xyz
    ORDER BY margen_12m DESC
  ) r ON r.sku = t.sku
  SET t.abc_class =
    CASE
      WHEN @total <= 0 THEN 'C'
      WHEN r.acum / @total <= 0.80 THEN 'A'
      WHEN r.acum / @total <= 0.95 THEN 'B'
      ELSE 'C'
    END,
    t.updated_at = NOW();

  -- 4) Calcular XYZ por CV e intermitencia
  UPDATE neobd.sku_abc_xyz
  SET xyz_class =
    CASE
      WHEN pct_mes_venta < 0.25 THEN 'Z'
      WHEN cv IS NULL THEN 'Z'
      WHEN cv <= 0.50 THEN 'X'
      WHEN cv <= 1.00 THEN 'Y'
      ELSE 'Z'
    END,
    updated_at = NOW();
END