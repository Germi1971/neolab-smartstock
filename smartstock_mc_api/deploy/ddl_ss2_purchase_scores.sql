-- =============================================================================
-- ss2_purchase_scores - Smart Replenishment Score (SRS)
-- =============================================================================
-- Prioriza SKUs para reposición. NO decide cantidad (eso es Policy Engine).
-- Combina: riesgo stockout, criticidad, LT, aceleración, margen, backlog,
-- penalidades por sobrestock y dominancia cliente.
--
-- Pipeline: policy_engine → purchase_scoring → ss2_purchase_scores
--
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_ss2_purchase_scores.sql
-- Compatible: MySQL 5.5+
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss2_purchase_scores (
  sku VARCHAR(80) NOT NULL,

  -- Score final 0-100
  priority_score DOUBLE NULL,

  -- Componentes (0-100 cada uno, salvo penalidades que restan)
  stockout_score DOUBLE NULL,
  criticidad_score DOUBLE NULL,
  lead_time_score DOUBLE NULL,
  acceleration_score DOUBLE NULL,
  margen_score DOUBLE NULL,
  backlog_score DOUBLE NULL,
  overstock_penalty DOUBLE NULL,
  cliente_penalty DOUBLE NULL,

  -- Banda de prioridad
  priority_band VARCHAR(20) NULL,

  -- Explicación breve
  priority_reason VARCHAR(255) NULL,

  -- Auditoría
  updated_at DATETIME NOT NULL,

  PRIMARY KEY (sku),
  INDEX idx_priority_score (priority_score),
  INDEX idx_priority_band (priority_band),
  INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- Bandas de prioridad
-- =============================================================================
-- 85-100 = URGENTE   (Reponer ya)
-- 70-84  = ALTA      (Muy alta prioridad)
-- 55-69  = MEDIA     (Prioridad media)
-- 40-54  = BAJA     (Revisar)
-- <40    = MUY_BAJA (No priorizar ahora)
-- =============================================================================
