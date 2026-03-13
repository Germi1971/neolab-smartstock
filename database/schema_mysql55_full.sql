-- =============================================================================
-- NeoLab SmartStock - Full Schema (MySQL 5.5.62 compatible)
-- Modo B: TODO dentro de la BD existente "neobd" con prefijo ss_
-- Unificado: Fase 1 + Fase 2 + Fase 3
-- NOTA MySQL 5.5: 1 solo TIMESTAMP auto por tabla; sin JSON; nombres case-insensitive
-- =============================================================================

USE neobd;

SET FOREIGN_KEY_CHECKS = 0;

-- =============================================================================
-- FASE 1: CORE
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss_sku_master (
    sku VARCHAR(50) PRIMARY KEY,
    descripcion VARCHAR(255) NOT NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    created_at DATETIME NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_sku_parameters (
    sku VARCHAR(50) PRIMARY KEY,
    stock_objetivo INT NOT NULL DEFAULT 0,
    stock_seguridad INT NOT NULL DEFAULT 0,
    punto_reorden INT NOT NULL DEFAULT 0,
    moq INT NULL,
    multiplo INT NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(100) NULL,
    CONSTRAINT fk_ss_sku_parameters_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_stock (
    sku VARCHAR(50) PRIMARY KEY,
    stock_posicion INT NOT NULL DEFAULT 0,
    stock_transito INT NOT NULL DEFAULT 0,
    stock_comprometido INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_ss_stock_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_demand_history (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    fecha DATE NOT NULL,
    cantidad INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ss_sku_fecha (sku, fecha),
    INDEX idx_fecha (fecha),
    CONSTRAINT fk_ss_demand_history_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_ml_run (
    run_id VARCHAR(36) PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at DATETIME NULL,
    skus_procesados INT NOT NULL DEFAULT 0,
    skus_exitosos INT NOT NULL DEFAULT 0,
    skus_fallidos INT NOT NULL DEFAULT 0,
    duracion_segundos INT NULL,
    triggered_by ENUM('SCHEDULER', 'MANUAL', 'API') NOT NULL DEFAULT 'SCHEDULER',
    error_log LONGTEXT NULL,
    INDEX idx_started_at (started_at),
    INDEX idx_finished_at (finished_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_ml_suggestions (
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    qty_sugerida INT NOT NULL,
    qty_final INT NULL,
    estado ENUM('PENDIENTE', 'APROBADO', 'RECHAZADO') NOT NULL DEFAULT 'PENDIENTE',
    modelo_seleccionado VARCHAR(50) NOT NULL,
    policy_min INT NULL,
    policy_max INT NULL,
    notas TEXT NULL,
    aprobado_por VARCHAR(100) NULL,
    fecha_aprobacion DATETIME NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, sku),
    INDEX idx_sku (sku),
    INDEX idx_estado (estado),
    INDEX idx_updated_at (updated_at),
    CONSTRAINT fk_ss_ml_suggestions_run
        FOREIGN KEY (run_id) REFERENCES ss_ml_run(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_ss_ml_suggestions_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_orders_approvals (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    qty_sugerida_ml INT NOT NULL,
    qty_final INT NOT NULL,
    estado ENUM('PENDIENTE', 'APROBADO', 'RECHAZADO') NOT NULL DEFAULT 'PENDIENTE',
    aprobado_por VARCHAR(100) NULL,
    fecha_aprobacion DATETIME NULL,
    notas TEXT NULL,
    created_at DATETIME NOT NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_sku (sku),
    INDEX idx_estado (estado),
    CONSTRAINT fk_ss_orders_approvals_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_audit_log (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tabla VARCHAR(50) NOT NULL,
    registro_id VARCHAR(100) NOT NULL,
    accion ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    usuario VARCHAR(100) NULL,
    cambios LONGTEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tabla (tabla),
    INDEX idx_registro (registro_id),
    INDEX idx_accion (accion),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT NOT NULL,
    config_type ENUM('string', 'int', 'float', 'bool', 'json') NOT NULL DEFAULT 'string',
    description VARCHAR(500) NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(100) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO ss_system_config (config_key, config_value, config_type, description) VALUES
('system.name', 'NeoLab SmartStock', 'string', 'System name'),
('system.version', '2.0.0', 'string', 'System version'),
('ml.default_model', 'REGULAR', 'string', 'Default ML model for new SKUs'),
('ml.min_history_days', '30', 'int', 'Minimum days of history required for ML'),
('stock.default_stock_objetivo', '100', 'int', 'Default stock objetivo for new SKUs'),
('stock.default_stock_seguridad', '20', 'int', 'Default stock seguridad for new SKUs')
ON DUPLICATE KEY UPDATE
    config_value = VALUES(config_value),
    config_type  = VALUES(config_type),
    description  = VALUES(description);

-- =============================================================================
-- FASE 2: ML ADVANCED
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss_ml_sku_features (
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    periodo_inicio DATE NOT NULL,
    periodo_fin DATE NOT NULL,
    dias_observados_12m INT NOT NULL DEFAULT 0,
    eventos_12m INT NOT NULL DEFAULT 0,
    unidades_12m INT NOT NULL DEFAULT 0,
    meses_con_venta_12m INT NOT NULL DEFAULT 0,
    pct_meses_con_venta_12m DECIMAL(5,4) NOT NULL DEFAULT 0.0000,
    lambda_eventos_mes_12m DECIMAL(10,6) NOT NULL DEFAULT 0.000000,
    mu_unidades_evento_12m DECIMAL(12,4) NOT NULL DEFAULT 0.0000,
    cv_12m DECIMAL(10,6) NOT NULL DEFAULT 0.000000,
    adi_12m DECIMAL(10,6) NOT NULL DEFAULT 0.000000,
    squared_cv_12m DECIMAL(10,6) NOT NULL DEFAULT 0.000000,
    dias_observados_24m INT NOT NULL DEFAULT 0,
    eventos_24m INT NOT NULL DEFAULT 0,
    unidades_24m INT NOT NULL DEFAULT 0,
    cv_24m DECIMAL(10,6) NOT NULL DEFAULT 0.000000,
    dias_observados_90d INT NOT NULL DEFAULT 0,
    eventos_90d INT NOT NULL DEFAULT 0,
    unidades_90d INT NOT NULL DEFAULT 0,
    tendencia_90d DECIMAL(10,6) NOT NULL DEFAULT 0.000000,
    ultima_venta DATE NULL,
    dias_desde_ultima_venta INT NOT NULL DEFAULT 0,
    PRIMARY KEY (run_id, sku),
    INDEX idx_sku (sku),
    INDEX idx_cv_12m (cv_12m),
    INDEX idx_lambda (lambda_eventos_mes_12m),
    CONSTRAINT fk_ss_ml_sku_features_run
        FOREIGN KEY (run_id) REFERENCES ss_ml_run(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_ss_ml_sku_features_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_ml_model_registry (
    sku VARCHAR(50) PRIMARY KEY,
    modelo_actual VARCHAR(50) NOT NULL,
    modelo_anterior VARCHAR(50) NULL,
    fecha_seleccion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id_seleccion VARCHAR(36) NULL,
    rmse DECIMAL(12,4) NULL,
    mae DECIMAL(12,4) NULL,
    bias DECIMAL(10,6) NULL,
    service_level DECIMAL(5,4) NULL,
    coverage_95 DECIMAL(5,4) NULL,
    score_error DECIMAL(8,6) NULL,
    score_service DECIMAL(8,6) NULL,
    score_stability DECIMAL(8,6) NULL,
    score_complexity DECIMAL(8,6) NULL,
    score_composite DECIMAL(8,6) NULL,
    model_params LONGTEXT NULL,
    INDEX idx_modelo_actual (modelo_actual),
    INDEX idx_fecha_seleccion (fecha_seleccion),
    CONSTRAINT fk_ss_ml_model_registry_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE,
    CONSTRAINT fk_ss_ml_model_registry_run
        FOREIGN KEY (run_id_seleccion) REFERENCES ss_ml_run(run_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_ml_model_switch_log (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    modelo_anterior VARCHAR(50) NOT NULL,
    modelo_nuevo VARCHAR(50) NOT NULL,
    razon_cambio ENUM('PRIMER_MODELO', 'MEJOR_SCORE', 'DRIFT', 'MANUAL') NOT NULL,
    score_anterior DECIMAL(8,6) NULL,
    score_nuevo DECIMAL(8,6) NULL,
    detalle LONGTEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sku (sku),
    INDEX idx_run_id (run_id),
    INDEX idx_created_at (created_at),
    CONSTRAINT fk_ss_ml_model_switch_log_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE,
    CONSTRAINT fk_ss_ml_model_switch_log_run
        FOREIGN KEY (run_id) REFERENCES ss_ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_ml_drift_log (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    drift_detected TINYINT(1) NOT NULL DEFAULT 0,
    cv_change_pct DECIMAL(10,4) NULL,
    lambda_change_pct DECIMAL(10,4) NULL,
    gap_ratio_change_pct DECIMAL(10,4) NULL,
    cv_threshold DECIMAL(5,4) NOT NULL DEFAULT 0.5000,
    lambda_threshold DECIMAL(5,4) NOT NULL DEFAULT 0.5000,
    detalle LONGTEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run_id (run_id),
    INDEX idx_sku (sku),
    INDEX idx_drift_detected (drift_detected),
    CONSTRAINT fk_ss_ml_drift_log_run
        FOREIGN KEY (run_id) REFERENCES ss_ml_run(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_ss_ml_drift_log_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_ml_backtest_results (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    modelo VARCHAR(50) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    fold_number INT NOT NULL,
    train_start DATE NOT NULL,
    train_end DATE NOT NULL,
    test_start DATE NOT NULL,
    test_end DATE NOT NULL,
    rmse DECIMAL(12,4) NULL,
    mae DECIMAL(12,4) NULL,
    mape DECIMAL(10,4) NULL,
    bias DECIMAL(10,6) NULL,
    coverage_80 DECIMAL(5,4) NULL,
    coverage_95 DECIMAL(5,4) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_ss_sku_modelo_fold (sku, modelo, fold_number),
    INDEX idx_sku (sku),
    INDEX idx_modelo (modelo),
    INDEX idx_run_id (run_id),
    CONSTRAINT fk_ss_ml_backtest_results_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE,
    CONSTRAINT fk_ss_ml_backtest_results_run
        FOREIGN KEY (run_id) REFERENCES ss_ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_ml_model_performance (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    modelo VARCHAR(50) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    periodo_inicio DATE NOT NULL,
    periodo_fin DATE NOT NULL,
    rmse DECIMAL(12,4) NULL,
    mae DECIMAL(12,4) NULL,
    mape DECIMAL(10,4) NULL,
    service_level DECIMAL(5,4) NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sku (sku),
    INDEX idx_modelo (modelo),
    INDEX idx_run_id (run_id),
    CONSTRAINT fk_ss_ml_model_performance_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE,
    CONSTRAINT fk_ss_ml_model_performance_run
        FOREIGN KEY (run_id) REFERENCES ss_ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- =============================================================================
-- FASE 3: SCHEDULER, LOCKS, OBSERVABILIDAD
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss_ml_run_errors (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    error_code VARCHAR(50) NOT NULL,
    error_message TEXT,
    error_detail LONGTEXT,
    retry_count INT NOT NULL DEFAULT 0,
    max_retries INT NOT NULL DEFAULT 3,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    resolved_at DATETIME NULL,
    INDEX idx_run_id (run_id),
    INDEX idx_sku (sku),
    INDEX idx_created_at (created_at),
    INDEX idx_resolved (resolved_at),
    CONSTRAINT fk_ss_ml_run_errors_run
        FOREIGN KEY (run_id) REFERENCES ss_ml_run(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_ss_ml_run_errors_sku
        FOREIGN KEY (sku) REFERENCES ss_sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_sku_cache_latest (
    sku VARCHAR(50) PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    stock_posicion INT NOT NULL DEFAULT 0,
    stock_objetivo INT NOT NULL DEFAULT 0,
    stock_seguridad INT NOT NULL DEFAULT 0,
    qty_sugerida INT NOT NULL DEFAULT 0,
    estado ENUM('PENDIENTE', 'APROBADO', 'RECHAZADO') NOT NULL DEFAULT 'PENDIENTE',
    qty_final INT NULL,
    modelo_seleccionado VARCHAR(50),
    policy_min INT NULL,
    policy_max INT NULL,
    score_composite DECIMAL(8,6) NULL,
    cv_12m DECIMAL(10,6) NULL,
    lambda_eventos_mes_12m DECIMAL(10,6) NULL,
    eventos_12m INT NULL,
    unidades_12m INT NULL,
    drift_detected TINYINT(1) NOT NULL DEFAULT 0,
    computed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    INDEX idx_run_id (run_id),
    INDEX idx_estado (estado),
    INDEX idx_modelo (modelo_seleccionado),
    INDEX idx_drift (drift_detected),
    INDEX idx_expires (expires_at),
    INDEX idx_computed (computed_at),
    CONSTRAINT fk_ss_sku_cache_latest_run
        FOREIGN KEY (run_id) REFERENCES ss_ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_scheduler_locks (
    lock_name VARCHAR(100) PRIMARY KEY,
    locked_by VARCHAR(100) NOT NULL,
    locked_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    metadata LONGTEXT NULL,
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_system_metrics (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(18,6) NOT NULL,
    metric_type ENUM('counter', 'gauge', 'histogram') NOT NULL DEFAULT 'gauge',
    labels LONGTEXT NULL,
    recorded_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_metric_name (metric_name),
    INDEX idx_recorded_at (recorded_at),
    INDEX idx_metric_type (metric_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_audit_log_extended (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tabla VARCHAR(50) NOT NULL,
    registro_id VARCHAR(100) NOT NULL,
    accion ENUM('INSERT', 'UPDATE', 'DELETE', 'EXECUTE') NOT NULL,
    usuario VARCHAR(100),
    cambios LONGTEXT NULL,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    execution_time_ms INT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tabla (tabla),
    INDEX idx_registro (registro_id),
    INDEX idx_accion (accion),
    INDEX idx_usuario (usuario),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

CREATE TABLE IF NOT EXISTS ss_scheduler_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT NOT NULL,
    config_type ENUM('string', 'int', 'float', 'bool', 'json') NOT NULL DEFAULT 'string',
    description VARCHAR(500),
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

INSERT INTO ss_scheduler_config (config_key, config_value, config_type, description) VALUES
('ml_pipeline.cron', '0 2 * * *', 'string', 'Cron ejecución pipeline ML'),
('ml_pipeline.timeout_seconds', '3600', 'int', 'Timeout pipeline'),
('ml_pipeline.max_retries', '3', 'int', 'Máximo reintentos'),
('ml_pipeline.retry_delay_seconds', '60', 'int', 'Delay reintentos'),
('ml_pipeline.batch_size', '100', 'int', 'Batch size'),
('cache.ttl_minutes', '60', 'int', 'TTL cache'),
('lock.timeout_seconds', '300', 'int', 'Timeout locks'),
('drift.threshold_cv_change', '0.5', 'float', 'Umbral CV'),
('drift.threshold_lambda_change', '0.5', 'float', 'Umbral lambda'),
('model_selection.hysteresis_threshold', '0.05', 'float', 'Histéresis modelo')
ON DUPLICATE KEY UPDATE
    config_value = VALUES(config_value),
    config_type  = VALUES(config_type),
    description  = VALUES(description);

-- =============================================================================
-- VIEWS
-- =============================================================================

DROP VIEW IF EXISTS ss_v_ml_run_summary;
CREATE VIEW ss_v_ml_run_summary AS
SELECT 
    r.run_id,
    r.started_at,
    r.finished_at,
    r.skus_procesados,
    r.skus_exitosos,
    r.skus_fallidos,
    r.duracion_segundos,
    r.triggered_by,
    COUNT(e.id) AS errores_no_resueltos,
    CASE 
        WHEN r.skus_fallidos = 0 THEN 'SUCCESS'
        WHEN r.skus_exitosos = 0 THEN 'FAILED'
        ELSE 'PARTIAL'
    END AS status
FROM ss_ml_run r
LEFT JOIN ss_ml_run_errors e
    ON r.run_id = e.run_id AND e.resolved_at IS NULL
GROUP BY 
    r.run_id, r.started_at, r.finished_at,
    r.skus_procesados, r.skus_exitosos, r.skus_fallidos,
    r.duracion_segundos, r.triggered_by;

DROP VIEW IF EXISTS ss_v_skus_with_issues;
CREATE VIEW ss_v_skus_with_issues AS
SELECT 
    s.sku,
    s.descripcion,
    s.activo,
    p.stock_objetivo,
    p.stock_seguridad,
    c.qty_sugerida,
    c.estado,
    c.modelo_seleccionado,
    c.drift_detected,
    c.cv_12m,
    (c.expires_at < NOW()) AS cache_expired,
    e.error_code AS last_error,
    e.created_at AS last_error_at
FROM ss_sku_master s
LEFT JOIN ss_sku_parameters p ON s.sku = p.sku
LEFT JOIN ss_sku_cache_latest c ON s.sku = c.sku
LEFT JOIN ss_ml_run_errors e
    ON e.sku = s.sku
   AND e.resolved_at IS NULL
   AND e.created_at = (
       SELECT MAX(e2.created_at)
       FROM ss_ml_run_errors e2
       WHERE e2.sku = s.sku
         AND e2.resolved_at IS NULL
   )
WHERE s.activo = 1
  AND (
       c.drift_detected = 1
       OR c.expires_at < NOW()
       OR e.error_code IS NOT NULL
       OR c.modelo_seleccionado = 'SIN_DATOS'
  );

SET FOREIGN_KEY_CHECKS = 1;

-- =============================================================================
-- TRIGGERS para created_at DATETIME NOT NULL (MySQL 5.5)
-- =============================================================================
DELIMITER $$

DROP TRIGGER IF EXISTS trg_ss_sku_master_created_at $$
CREATE TRIGGER trg_ss_sku_master_created_at
BEFORE INSERT ON ss_sku_master
FOR EACH ROW
BEGIN
    IF NEW.created_at IS NULL THEN
        SET NEW.created_at = NOW();
    END IF;
END $$

DROP TRIGGER IF EXISTS trg_ss_orders_approvals_created_at $$
CREATE TRIGGER trg_ss_orders_approvals_created_at
BEFORE INSERT ON ss_orders_approvals
FOR EACH ROW
BEGIN
    IF NEW.created_at IS NULL THEN
        SET NEW.created_at = NOW();
    END IF;
END $$

DELIMITER ;
