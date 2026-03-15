-- =============================================================================
-- ss2_demand_cache - Capa Demand Engine (estimación de demanda y riesgo)
-- =============================================================================
-- Contrato: Monte Carlo NO escribe stock objetivo ni qty recomendada.
-- Solo escribe: percentiles de demanda, métricas de riesgo, mc_enabled, mc_reason.
--
-- El Policy Engine lee esta tabla y decide stock_objetivo_final / qty_recomendada_final.
--
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_ss2_demand_cache.sql
-- Compatible: MySQL 5.5+
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss2_demand_cache (
  sku VARCHAR(80) NOT NULL,

  -- Parámetros de simulación (trazabilidad)
  n_sims INT NOT NULL DEFAULT 8000,
  horizon_days INT NULL,
  lt_days INT NULL,
  review_days INT NULL,

  -- Inputs del modelo (para reproducibilidad)
  lambda_eventos_mes DOUBLE NULL,
  q_mean_event DOUBLE NULL,
  q_sd_event DOUBLE NULL,

  -- Regimen detectado (REGULAR, INTERMITENTE, NUEVO)
  regimen VARCHAR(50) NULL,

  -- Criticidad unificada: CRITICO | ALTO | MEDIO | BAJO
  criticidad VARCHAR(20) NULL,

  -- Service level usado en simulación (0.50 - 0.999)
  service_prob_usado DOUBLE NULL,

  -- ========== SALIDAS DEMAND ENGINE (solo estimación, NO decisión) ==========

  -- Percentiles de demanda en horizonte (LT + review)
  demand_mean DOUBLE NULL,
  demand_p50 DOUBLE NULL,
  demand_p80 DOUBLE NULL,
  demand_p90 DOUBLE NULL,
  demand_p95 DOUBLE NULL,
  demand_p97 DOUBLE NULL,
  demand_p99 DOUBLE NULL,

  -- Métricas de riesgo (evaluadas con stock_posicion al momento de la simulación)
  p_stockout_at_current_stock DOUBLE NULL,
  exp_lost_units DOUBLE NULL,
  fill_rate_est DOUBLE NULL,

  -- Control MC
  mc_enabled TINYINT NOT NULL DEFAULT 0,
  mc_reason VARCHAR(255) NULL,

  -- Auditoría
  updated_at DATETIME NOT NULL,

  PRIMARY KEY (sku),
  INDEX idx_mc_enabled (mc_enabled),
  INDEX idx_criticidad (criticidad),
  INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- Notas de contrato
-- =============================================================================
-- demand_mean: media de la distribución simulada
-- demand_pXX: percentil XX de demanda en el horizonte
-- p_stockout_at_current_stock: P(demanda > stock_posicion) en las simulaciones
-- exp_lost_units: unidades esperadas perdidas por stockout
-- fill_rate_est: 1 - p_stockout_at_current_stock (o cálculo explícito)
--
-- Mapeo criticidad -> service level (Policy Engine):
--   CRITICO = 0.97
--   ALTO    = 0.95
--   MEDIO   = 0.90
--   BAJO    = 0.80
-- =============================================================================
