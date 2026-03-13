CREATE DEFINER=`neolab`@`%` PROCEDURE `sp_auto_activate_skus`()
BEGIN
  UPDATE neobd.parametros_sku ps
  JOIN neobd.v_dim_sku_excel d ON d.sku = ps.sku
  LEFT JOIN neobd.v_sku_features f ON f.SKU = ps.sku
  SET ps.activo = 1
  WHERE ps.activo = 0
    AND (
      COALESCE(d.stock_posicion,0) > 0
      OR COALESCE(f.meses_con_venta_12m,0) > 0
      OR COALESCE(f.margen_total_12m,0) > 0
    );
END