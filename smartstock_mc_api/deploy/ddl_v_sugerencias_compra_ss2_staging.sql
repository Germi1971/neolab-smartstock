-- =============================================================================
-- v_sugerencias_compra en ss2_staging
-- =============================================================================
-- Requiere en ss2_staging: parametros_sku, tablaprecios, sku_mc_cache,
--   v_stock_estado_unidades, v_sku_features_12m
--
-- Ejecutar: mysql -h TU_HOST -u TU_USER -p ss2_staging < deploy/ddl_v_sugerencias_compra_ss2_staging.sql
-- =============================================================================

USE ss2_staging;

DROP VIEW IF EXISTS v_sugerencias_compra;

CREATE VIEW v_sugerencias_compra AS
SELECT
  p.sku AS sku,
  COALESCE(CONVERT(tp.`Item Description` USING utf8mb4), tp.Descripcion_Completa, CONVERT(p.sku USING utf8mb4)) AS producto,
  COALESCE(NULLIF(tp.Marca,''),'PROVEEDOR_PRINCIPAL') AS proveedor,
  COALESCE(se.stock_libre_deposito,0) AS stock_actual,
  COALESCE(se.stock_reservado_deposito,0) AS reservado_deposito,
  COALESCE(se.stock_total_deposito,0) AS stock_total_deposito,
  COALESCE(se.impo_libre,0) AS impo_libre,
  COALESCE(se.impo_reservada,0) AS impo_reservada,
  COALESCE(se.impo_total,0) AS impo_total,
  (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) AS oferta_total,
  (CASE WHEN (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) <= 0 THEN 'CRITICO'
        WHEN (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) < p.stock_min THEN 'BAJO_MIN'
        WHEN (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) < p.stock_objetivo THEN 'BAJO_OBJ'
        ELSE 'OK' END) AS riesgo,
  COALESCE(f.meses_con_venta_12m,0) AS meses_con_venta_12m,
  COALESCE(f.demanda_prom_mensual_12m,0) AS demanda_prom_mensual_12m,
  (CASE WHEN (COALESCE(f.meses_con_venta_12m,0) >= 1) OR (COALESCE(f.demanda_prom_mensual_12m,0) > 0) THEN 1 ELSE 0 END) AS sku_activo,
  (CASE WHEN ((COALESCE(f.meses_con_venta_12m,0) >= 1) OR (COALESCE(f.demanda_prom_mensual_12m,0) > 0)) AND ((COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) <= COALESCE(p.stock_min,0)) THEN 'CRITICO_REAL'
        WHEN (COALESCE(f.meses_con_venta_12m,0) = 0) AND (COALESCE(f.demanda_prom_mensual_12m,0) = 0) AND ((COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) <= 0) THEN 'INACTIVO'
        ELSE 'NORMAL' END) AS estado_operativo,
  p.modelo_recomendado, p.stock_min, p.stock_objetivo, p.cap_objetivo, p.service_prob_usado,
  p.review_updated_at, COALESCE(p.sugerencia_aprobada,0) AS aprobado, p.fecha_sugerencia AS fecha_aprobacion, p.qty_aprobada,
  (CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END) AS stock_objetivo_modelo,
  (CASE WHEN (p.cap_objetivo IS NOT NULL AND p.cap_objetivo > 0) THEN LEAST((CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END), p.cap_objetivo)
        ELSE (CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END) END) AS stock_objetivo_capeado,
  GREATEST(0, ((CASE WHEN (p.cap_objetivo IS NOT NULL AND p.cap_objetivo > 0) THEN LEAST((CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END), p.cap_objetivo)
        ELSE (CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END) END) - COALESCE(se.stock_libre_deposito,0))) AS qty_recomendada_sin_cap,
  (CASE WHEN COALESCE(c.q_cap,0) > 0 THEN LEAST(GREATEST(0, ((CASE WHEN (p.cap_objetivo IS NOT NULL AND p.cap_objetivo > 0) THEN LEAST((CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END), p.cap_objetivo)
        ELSE (CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END) END) - COALESCE(se.stock_libre_deposito,0))), c.q_cap)
        ELSE GREATEST(0, ((CASE WHEN (p.cap_objetivo IS NOT NULL AND p.cap_objetivo > 0) THEN LEAST((CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END), p.cap_objetivo)
        ELSE (CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END) END) - COALESCE(se.stock_libre_deposito,0))) END) AS qty_recomendada,
  (CASE WHEN COALESCE(p.sugerencia_aprobada,0) = 1 THEN COALESCE(p.qty_aprobada,0)
        ELSE (CASE WHEN COALESCE(c.q_cap,0) > 0 THEN LEAST(GREATEST(0, ((CASE WHEN (p.cap_objetivo IS NOT NULL AND p.cap_objetivo > 0) THEN LEAST((CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END), p.cap_objetivo)
        ELSE (CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END) END) - COALESCE(se.stock_libre_deposito,0))), c.q_cap)
        ELSE GREATEST(0, ((CASE WHEN (p.cap_objetivo IS NOT NULL AND p.cap_objetivo > 0) THEN LEAST((CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END), p.cap_objetivo)
        ELSE (CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END) END) - COALESCE(se.stock_libre_deposito,0))) END) END) AS qty_final,
  tp.`DIST Price -30%` AS costo_unit,
  ((CASE WHEN COALESCE(p.sugerencia_aprobada,0) = 1 THEN COALESCE(p.qty_aprobada,0)
        ELSE (CASE WHEN COALESCE(c.q_cap,0) > 0 THEN LEAST(GREATEST(0, ((CASE WHEN (p.cap_objetivo IS NOT NULL AND p.cap_objetivo > 0) THEN LEAST((CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END), p.cap_objetivo)
        ELSE (CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END) END) - COALESCE(se.stock_libre_deposito,0))), c.q_cap)
        ELSE GREATEST(0, ((CASE WHEN (p.cap_objetivo IS NOT NULL AND p.cap_objetivo > 0) THEN LEAST((CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END), p.cap_objetivo)
        ELSE (CASE WHEN COALESCE(c.mc_enabled,0) = 1 THEN COALESCE(c.stock_objetivo_mc,p.stock_objetivo) ELSE p.stock_objetivo END) END) - COALESCE(se.stock_libre_deposito,0))) END) END) * COALESCE(tp.`DIST Price -30%`,0)) AS impacto_usd,
  COALESCE(c.mc_enabled,0) AS mc_enabled, c.stock_objetivo_mc, c.qty_recomendada_mc, c.q_cap, c.mc_reason,
  c.p_stockout, c.exp_lost_units, c.updated_at AS mc_updated_at
FROM parametros_sku p
LEFT JOIN v_stock_estado_unidades se ON se.sku = p.sku
LEFT JOIN tablaprecios tp ON tp.`Product Number` = p.sku
LEFT JOIN v_sku_features_12m f ON f.SKU = p.sku
LEFT JOIN sku_mc_cache c ON c.sku = p.sku
WHERE p.activo = 1 AND p.discontinuado = 0;
