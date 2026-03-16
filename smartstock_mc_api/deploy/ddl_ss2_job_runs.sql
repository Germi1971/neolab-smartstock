-- =============================================================================
-- ss2_job_runs - Control de ejecuciones del pipeline SS2
-- =============================================================================
-- Registra cada corrida del pipeline diario para auditoría y monitoreo.
--
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_ss2_job_runs.sql
-- Compatible: MySQL 5.5+
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss2_job_runs (
  run_id INT NOT NULL AUTO_INCREMENT,

  -- Identificación
  asof_date DATE NOT NULL,
  location_id INT NULL DEFAULT 1,

  -- Estado
  status VARCHAR(20) NOT NULL DEFAULT 'RUNNING' COMMENT 'RUNNING | SUCCESS | PARTIAL | FAILED',
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,

  -- Resumen
  n_skus_features INT NULL,
  n_skus_classification INT NULL,
  n_skus_demand_cache INT NULL,
  n_skus_policy INT NULL,
  n_skus_scoring INT NULL,
  n_mc_enabled INT NULL,

  -- Errores
  error_message VARCHAR(500) NULL,
  failed_step VARCHAR(80) NULL,

  -- Metadata
  pipeline_version VARCHAR(50) NULL,
  notes VARCHAR(255) NULL,

  PRIMARY KEY (run_id),
  INDEX idx_asof_date (asof_date),
  INDEX idx_status (status),
  INDEX idx_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- ss2_job_logs - Logs detallados por etapa
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss2_job_logs (
  log_id BIGINT NOT NULL AUTO_INCREMENT,
  run_id INT NOT NULL,

  step_name VARCHAR(80) NOT NULL COMMENT 'features | classification | demand_cache | policy | scoring',
  status VARCHAR(20) NOT NULL DEFAULT 'OK' COMMENT 'OK | WARN | ERROR',
  started_at DATETIME NOT NULL,
  finished_at DATETIME NULL,
  duration_sec INT NULL,

  n_processed INT NULL,
  n_errors INT NULL,
  message TEXT NULL,

  PRIMARY KEY (log_id),
  INDEX idx_run_id (run_id),
  INDEX idx_step_name (step_name),
  INDEX idx_started_at (started_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- Vista ss2_v_job_status - Último estado del pipeline
-- =============================================================================

DROP VIEW IF EXISTS ss2_v_job_status;
CREATE VIEW ss2_v_job_status AS
SELECT
  r.run_id,
  r.asof_date,
  r.location_id,
  r.status,
  r.started_at,
  r.finished_at,
  TIMESTAMPDIFF(SECOND, r.started_at, r.finished_at) AS duration_sec,
  r.n_skus_features,
  r.n_skus_classification,
  r.n_skus_demand_cache,
  r.n_skus_policy,
  r.n_skus_scoring,
  r.n_mc_enabled,
  r.error_message,
  r.failed_step
FROM ss2_job_runs r
WHERE r.run_id = (SELECT MAX(run_id) FROM ss2_job_runs);
