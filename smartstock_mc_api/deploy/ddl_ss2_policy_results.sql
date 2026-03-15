-- =============================================================================
-- ss2_policy_results - Capa Policy Engine (decisión de inventario)
-- =============================================================================
-- Contrato: El Policy Engine lee ss2_demand_cache + parametros_sku + stock,
-- aplica caps y reglas, y escribe aquí los resultados finales.
--
-- Esta tabla es la fuente de verdad para stock_objetivo y qty_recomendada.
-- La vista v_sugerencias_compra (futura) consumirá ss2_policy_results.
--
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_ss2_policy_results.sql
-- Compatible: MySQL 5.5+
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss2_policy_results (
  sku VARCHAR(80) NOT NULL,

  -- ========== RESULTADOS FINALES ==========
  stock_min INT NULL,
  stock_objetivo_final DOUBLE NULL,
  qty_recomendada_final DOUBLE NULL,

  -- ========== TRAZABILIDAD / AUDITORÍA ==========

  -- Origen del demand target: 'demand_p95' | 'demand_p90' | 'analytic_target' | etc.
  demand_target_source VARCHAR(80) NULL,

  -- Valor del target antes de aplicar caps (para debug)
  demand_target_value DOUBLE NULL,

  -- Service level seleccionado (0.80, 0.90, 0.95, 0.97)
  selected_service_level DOUBLE NULL,

  -- Caps aplicados en orden: base, cap_hist, cap_cliente_dominante, cap_vencimiento
  -- Formato: "cap_hist:120|cap_cliente:80" o lista legible
  applied_caps VARCHAR(500) NULL,

  -- Razón corta: "MC:p95" | "ANALYTIC" | "MC:p80_fallback"
  policy_reason VARCHAR(255) NULL,

  -- Explicación auditable por SKU (texto libre)
  explanation TEXT NULL,

  -- Criticidad usada en la decisión
  criticidad VARCHAR(20) NULL,

  -- Parámetros de compra aplicados (MOQ, múltiplo, q_cap)
  moq INT NULL,
  multiplo_compra INT NULL,
  q_cap INT NULL,

  -- Snapshot de inputs usados (para reproducibilidad)
  stock_posicion_at_calc INT NULL,
  backlog_qty_at_calc INT NULL,

  -- Auditoría
  updated_at DATETIME NOT NULL,

  PRIMARY KEY (sku),
  INDEX idx_updated_at (updated_at),
  INDEX idx_criticidad (criticidad)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- Notas de contrato
-- =============================================================================
-- Orden de aplicación de caps (Policy Engine):
--   1. base_demand_target (percentil o analytic_target)
--   2. cap_hist
--   3. cap_cliente_dominante
--   4. cap_vencimiento
--   5. MOQ / múltiplos / redondeo comercial
--
-- Regla demand target:
--   mc_enabled=1, CRITICO/ALTO  -> demand_p95 o demand_p97
--   mc_enabled=1, MEDIO         -> demand_p90
--   mc_enabled=1, BAJO         -> demand_p80
--   mc_enabled=0               -> analytic_target (parametros_sku.stock_objetivo)
-- =============================================================================
