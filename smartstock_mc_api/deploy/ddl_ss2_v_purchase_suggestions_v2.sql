-- =============================================================================
-- ss2_v_purchase_suggestions_v2 - Vista de sugerencias usando ss2_policy_results
-- =============================================================================
-- qty_recomendada: cálculo en tiempo real (stock_objetivo - oferta_total)
-- con MOQ, múltiplo y q_cap. Evita desfases cuando el stock cambia entre pipelines.
--
-- Requiere: parametros_sku, tablaprecios, v_stock_estado_unidades,
--   v_sku_features_12m, ss2_policy_results, ss2_purchase_scores, sku_mc_cache
--
-- Ejecutar: mysql -h HOST -u USER -p ss2_staging < deploy/ddl_ss2_v_purchase_suggestions_v2.sql
-- =============================================================================

USE ss2_staging;

DROP VIEW IF EXISTS ss2_v_purchase_suggestions_v2;

CREATE VIEW ss2_v_purchase_suggestions_v2 AS
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
        WHEN (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) < COALESCE(pr.stock_min, p.stock_min, 0) THEN 'BAJO_MIN'
        WHEN (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) < COALESCE(pr.stock_objetivo_final, p.stock_objetivo, 0) THEN 'BAJO_OBJ'
        ELSE 'OK' END) AS riesgo,
  COALESCE(f.meses_con_venta_12m,0) AS meses_con_venta_12m,
  COALESCE(f.demanda_prom_mensual_12m,0) AS demanda_prom_mensual_12m,
  (CASE WHEN (COALESCE(f.meses_con_venta_12m,0) >= 1) OR (COALESCE(f.demanda_prom_mensual_12m,0) > 0) THEN 1 ELSE 0 END) AS sku_activo,
  (CASE WHEN ((COALESCE(f.meses_con_venta_12m,0) >= 1) OR (COALESCE(f.demanda_prom_mensual_12m,0) > 0)) AND ((COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) <= COALESCE(pr.stock_min, p.stock_min, 0)) THEN 'CRITICO_REAL'
        WHEN (COALESCE(f.meses_con_venta_12m,0) = 0) AND (COALESCE(f.demanda_prom_mensual_12m,0) = 0) AND ((COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0)) <= 0) THEN 'INACTIVO'
        ELSE 'NORMAL' END) AS estado_operativo,
  p.modelo_recomendado,
  COALESCE(pr.stock_min, p.stock_min) AS stock_min,
  p.stock_objetivo AS stock_objetivo_parametrico,
  p.cap_objetivo,
  p.service_prob_usado,
  p.review_updated_at,
  COALESCE(p.sugerencia_aprobada,0) AS aprobado,
  p.fecha_sugerencia AS fecha_aprobacion,
  p.qty_aprobada,
  COALESCE(pr.stock_objetivo_final, p.stock_objetivo) AS stock_objetivo_final,
  COALESCE(pr.stock_objetivo_final, p.stock_objetivo) AS stock_objetivo_modelo,
  COALESCE(pr.stock_objetivo_final, p.stock_objetivo) AS stock_objetivo_capeado,
  GREATEST(0, COALESCE(pr.stock_objetivo_final, p.stock_objetivo) - (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0))) AS qty_recomendada_sin_cap,
  -- Cálculo en tiempo real: qty = stock_objetivo - oferta_total, con MOQ/múltiplo/q_cap
  (CASE WHEN COALESCE(p.sugerencia_aprobada,0) = 1 THEN COALESCE(p.qty_aprobada,0)
        ELSE (CASE
          WHEN (COALESCE(pr.q_cap, c.q_cap) IS NOT NULL AND COALESCE(pr.q_cap, c.q_cap) > 0)
            THEN LEAST(
              CEILING(GREATEST(
                GREATEST(0, COALESCE(pr.stock_objetivo_final, p.stock_objetivo) - (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0))),
                GREATEST(1, COALESCE(pr.moq, p.moq, c.moq, 1))
              ) / GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))) * GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1)),
              COALESCE(pr.q_cap, c.q_cap)
            )
          ELSE CEILING(GREATEST(
            GREATEST(0, COALESCE(pr.stock_objetivo_final, p.stock_objetivo) - (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0))),
            GREATEST(1, COALESCE(pr.moq, p.moq, c.moq, 1))
          ) / GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))) * GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))
        END) END) AS qty_recomendada,
  (CASE WHEN COALESCE(p.sugerencia_aprobada,0) = 1 THEN COALESCE(p.qty_aprobada,0)
        ELSE (CASE
          WHEN (COALESCE(pr.q_cap, c.q_cap) IS NOT NULL AND COALESCE(pr.q_cap, c.q_cap) > 0)
            THEN LEAST(
              CEILING(GREATEST(
                GREATEST(0, COALESCE(pr.stock_objetivo_final, p.stock_objetivo) - (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0))),
                GREATEST(1, COALESCE(pr.moq, p.moq, c.moq, 1))
              ) / GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))) * GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1)),
              COALESCE(pr.q_cap, c.q_cap)
            )
          ELSE CEILING(GREATEST(
            GREATEST(0, COALESCE(pr.stock_objetivo_final, p.stock_objetivo) - (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0))),
            GREATEST(1, COALESCE(pr.moq, p.moq, c.moq, 1))
          ) / GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))) * GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))
        END) END) AS qty_final,
  (CASE WHEN COALESCE(p.sugerencia_aprobada,0) = 1 THEN COALESCE(p.qty_aprobada,0)
        ELSE (CASE
          WHEN (COALESCE(pr.q_cap, c.q_cap) IS NOT NULL AND COALESCE(pr.q_cap, c.q_cap) > 0)
            THEN LEAST(
              CEILING(GREATEST(
                GREATEST(0, COALESCE(pr.stock_objetivo_final, p.stock_objetivo) - (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0))),
                GREATEST(1, COALESCE(pr.moq, p.moq, c.moq, 1))
              ) / GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))) * GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1)),
              COALESCE(pr.q_cap, c.q_cap)
            )
          ELSE CEILING(GREATEST(
            GREATEST(0, COALESCE(pr.stock_objetivo_final, p.stock_objetivo) - (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0))),
            GREATEST(1, COALESCE(pr.moq, p.moq, c.moq, 1))
          ) / GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))) * GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))
        END) END) AS qty_recomendada_final,
  tp.`DIST Price -30%` AS costo_unit,
  ((CASE WHEN COALESCE(p.sugerencia_aprobada,0) = 1 THEN COALESCE(p.qty_aprobada,0)
        ELSE (CASE
          WHEN (COALESCE(pr.q_cap, c.q_cap) IS NOT NULL AND COALESCE(pr.q_cap, c.q_cap) > 0)
            THEN LEAST(
              CEILING(GREATEST(
                GREATEST(0, COALESCE(pr.stock_objetivo_final, p.stock_objetivo) - (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0))),
                GREATEST(1, COALESCE(pr.moq, p.moq, c.moq, 1))
              ) / GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))) * GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1)),
              COALESCE(pr.q_cap, c.q_cap)
            )
          ELSE CEILING(GREATEST(
            GREATEST(0, COALESCE(pr.stock_objetivo_final, p.stock_objetivo) - (COALESCE(se.stock_libre_deposito,0) + COALESCE(se.impo_libre,0))),
            GREATEST(1, COALESCE(pr.moq, p.moq, c.moq, 1))
          ) / GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))) * GREATEST(1, COALESCE(pr.multiplo_compra, p.multiplo_compra, c.multiplo_compra, 1))
        END) END) * COALESCE(tp.`DIST Price -30%`,0)) AS impacto_usd,
  pr.demand_target_source,
  pr.selected_service_level,
  pr.applied_caps,
  pr.policy_reason,
  pr.explanation,
  pr.criticidad AS criticidad_policy,
  pr.updated_at AS policy_updated_at,
  ps.priority_score,
  ps.priority_band,
  ps.priority_reason
FROM parametros_sku p
LEFT JOIN v_stock_estado_unidades se ON se.sku = p.sku
LEFT JOIN tablaprecios tp ON tp.`Product Number` = p.sku
LEFT JOIN v_sku_features_12m f ON f.SKU = p.sku
LEFT JOIN ss2_policy_results pr ON pr.sku = p.sku
LEFT JOIN ss2_purchase_scores ps ON ps.sku = p.sku
LEFT JOIN sku_mc_cache c ON c.sku = p.sku
WHERE p.activo = 1 AND p.discontinuado = 0;
