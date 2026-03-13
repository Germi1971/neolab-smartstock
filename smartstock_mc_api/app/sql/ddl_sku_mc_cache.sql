-- Crear en la base configurada (neobd, ss2_staging, etc.). Ej: mysql -u ss2 -p ss2_staging < ddl_sku_mc_cache.sql
CREATE TABLE IF NOT EXISTS sku_mc_cache (
  sku VARCHAR(80) NOT NULL,
  n_sims INT NOT NULL,
  horizon_days INT NOT NULL,
  lt_days INT NULL,
  review_days INT NULL,
  lambda_eventos_mes DOUBLE NULL,
  q_mean_event DOUBLE NULL,
  q_sd_event DOUBLE NULL,
  service_prob DOUBLE NULL,
  service_prob_usado DOUBLE NULL,
  service_prob_auto DOUBLE NULL,
  service_prob_override DOUBLE NULL,

  mc_enabled TINYINT NOT NULL DEFAULT 0,
  mc_reason VARCHAR(255) NULL,

  demand_p50 DOUBLE NULL,
  demand_p90 DOUBLE NULL,
  demand_p95 DOUBLE NULL,
  demand_p97 DOUBLE NULL,
  demand_p99 DOUBLE NULL,

  stock_objetivo_mc DOUBLE NULL,
  qty_recomendada_mc DOUBLE NULL,

  p_stockout DOUBLE NULL,
  exp_lost_units DOUBLE NULL,

  moq INT NULL,
  multiplo_compra INT NULL,
  q_cap INT NULL,
  criticidad VARCHAR(50) NULL,

  updated_at DATETIME NOT NULL,

  PRIMARY KEY (sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
