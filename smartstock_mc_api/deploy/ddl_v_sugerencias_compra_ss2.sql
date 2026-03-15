-- =============================================================================
-- v_sugerencias_compra - Versión SS2 (usa ss2_policy_results)
-- =============================================================================
-- Reemplaza la vista legacy que usaba sku_mc_cache.
-- El HUD consume v_sugerencias_compra; esta versión usa Policy Engine.
--
-- PRERREQUISITOS:
--   1. Tablas ss2_demand_cache, ss2_policy_results, ss2_purchase_scores
--   2. Ejecutar pipeline: mc/run -> policy/run -> scoring/run
--   3. Vista ss2_v_purchase_suggestions_v2 creada
--
-- Ejecutar: mysql -h HOST -u USER -p ss2_staging < deploy/ddl_v_sugerencias_compra_ss2.sql
-- =============================================================================

USE ss2_staging;

DROP VIEW IF EXISTS v_sugerencias_compra;

CREATE VIEW v_sugerencias_compra AS
SELECT
  s.sku,
  s.producto,
  s.proveedor,
  s.stock_actual,
  s.reservado_deposito,
  s.stock_total_deposito,
  s.impo_libre,
  s.impo_reservada,
  s.impo_total,
  s.oferta_total,
  s.riesgo,
  s.meses_con_venta_12m,
  s.demanda_prom_mensual_12m,
  s.sku_activo,
  s.estado_operativo,
  s.modelo_recomendado,
  s.stock_min,
  s.stock_objetivo_parametrico AS stock_objetivo,
  s.cap_objetivo,
  s.service_prob_usado,
  s.review_updated_at,
  s.aprobado,
  s.fecha_aprobacion,
  s.qty_aprobada,
  s.stock_objetivo_modelo,
  s.stock_objetivo_capeado,
  s.qty_recomendada_sin_cap,
  s.qty_recomendada,
  s.qty_final,
  s.costo_unit,
  s.impacto_usd,
  (CASE WHEN s.policy_reason IS NOT NULL AND s.policy_reason LIKE 'MC%' THEN 1 ELSE 0 END) AS mc_enabled,
  s.stock_objetivo_final AS stock_objetivo_mc,
  s.qty_recomendada AS qty_recomendada_mc,
  NULL AS q_cap,
  s.policy_reason AS mc_reason,
  NULL AS p_stockout,
  NULL AS exp_lost_units,
  s.policy_updated_at AS mc_updated_at
FROM ss2_v_purchase_suggestions_v2 s;
