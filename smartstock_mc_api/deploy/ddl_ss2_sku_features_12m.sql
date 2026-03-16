-- =============================================================================
-- ss2_sku_features_12m - Tabla de features (poblada por sp_ss2_sku_features_12m_refresh)
-- =============================================================================
-- Requerida por v_sku_features_12m y v_sku_classification_input.
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_ss2_sku_features_12m.sql
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss2_sku_features_12m (
  asof_date DATE NOT NULL,
  sku VARCHAR(50) NOT NULL,
  months_calendar INT NULL,
  months_active INT NULL,
  demand_mean_m DECIMAL(12,4) NULL,
  demand_std_m DECIMAL(12,4) NULL,
  total_units_12m INT NULL,
  events_12m INT NULL,
  p_event DECIMAL(12,6) NULL,
  q_mean_event DECIMAL(12,4) NULL,
  q_sd_event DECIMAL(12,4) NULL,
  pct_zero_months DECIMAL(12,6) NULL,
  last_ship_date DATE NULL,
  last_book_date DATE NULL,
  created_at DATETIME NULL,
  PRIMARY KEY (asof_date, sku),
  INDEX idx_sku (sku),
  INDEX idx_asof (asof_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
