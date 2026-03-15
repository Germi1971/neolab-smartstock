-- =============================================================================
-- ss2_demand_classification - Capa de clasificación automática de demanda
-- =============================================================================
-- Clasifica cada SKU según su patrón de demanda (ADI + CV²) y lifecycle.
-- Usa la clasificación para decidir qué modelo de reposición aplicar.

-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_ss2_demand_classification.sql
-- Compatible: MySQL 5.5+
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss2_demand_classification (
  sku VARCHAR(80) NOT NULL,

  -- Métricas ADI + CV² (clasificación estándar supply chain)
  adi DOUBLE NULL COMMENT 'Average Demand Interval: meses_obs / meses_con_demanda',
  cv2 DOUBLE NULL COMMENT 'CV² = (std/mean)² del tamaño de demanda por evento',

  -- Clasificación principal (REGULAR | ERRATIC | INTERMITTENT | LUMPY)
  demand_class VARCHAR(30) NULL,

  -- Estado de ciclo de vida (NEW | DORMANT | DEAD | ACTIVE)
  lifecycle_state VARCHAR(30) NULL,

  -- Flags adicionales
  cliente_dominante_flag TINYINT NOT NULL DEFAULT 0 COMMENT 'top1_share >= 0.60',
  accelerating_flag TINYINT NOT NULL DEFAULT 0 COMMENT 'mu_6m/mu_24m >= 1.4',
  perecedero_flag TINYINT NOT NULL DEFAULT 0 COMMENT 'Reservado para futuro',

  -- Explicación legible para auditoría
  classification_reason VARCHAR(255) NULL,

  -- Auditoría
  updated_at DATETIME NOT NULL,

  PRIMARY KEY (sku),
  INDEX idx_demand_class (demand_class),
  INDEX idx_lifecycle_state (lifecycle_state),
  INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- Notas de uso
-- =============================================================================
-- demand_class: ADI + CV² (Syntetos & Boylan)
--   ADI < 1.32, CV² < 0.49  => REGULAR
--   ADI < 1.32, CV² >= 0.49 => ERRATIC
--   ADI >= 1.32, CV² < 0.49 => INTERMITTENT
--   ADI >= 1.32, CV² >= 0.49 => LUMPY
--
-- lifecycle_state (prioridad sobre demand_class):
--   eventos_12m < 3 o dias_observados < 180 => NEW
--   days_since_last_sale > 180 y unidades_6m = 0 => DORMANT
--   days_since_last_sale > 365 y unidades_12m = 0 => DEAD
--
-- Integración con Policy Engine:
--   REGULAR       -> analytic preferred
--   ERRATIC       -> analytic or MC según volatilidad
--   INTERMITTENT  -> MC preferred si hay datos
--   LUMPY         -> MC strongly preferred
--   NEW           -> fallback rules
--   DORMANT       -> no auto buy
--   DEAD          -> excluir de reposición
-- =============================================================================
