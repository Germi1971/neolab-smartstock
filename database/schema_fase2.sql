-- ============================================
-- FASE 2: ML Advanced Schema (MySQL 5.5.62 compatible)
-- ============================================

SET FOREIGN_KEY_CHECKS = 0;

-- ML SKU Features (computed features per run)
CREATE TABLE IF NOT EXISTS ml_sku_features (
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    periodo_inicio DATE NOT NULL,
    periodo_fin DATE NOT NULL,

    -- 12 month features
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

    -- 24 month features
    dias_observados_24m INT NOT NULL DEFAULT 0,
    eventos_24m INT NOT NULL DEFAULT 0,
    unidades_24m INT NOT NULL DEFAULT 0,
    cv_24m DECIMAL(10,6) NOT NULL DEFAULT 0.000000,

    -- 90 day features
    dias_observados_90d INT NOT NULL DEFAULT 0,
    eventos_90d INT NOT NULL DEFAULT 0,
    unidades_90d INT NOT NULL DEFAULT 0,
    tendencia_90d DECIMAL(10,6) NOT NULL DEFAULT 0.000000,

    -- Additional features
    ultima_venta DATE NULL,
    dias_desde_ultima_venta INT NOT NULL DEFAULT 0,

    PRIMARY KEY (run_id, sku),
    INDEX idx_sku (sku),
    INDEX idx_cv_12m (cv_12m),
    INDEX idx_lambda (lambda_eventos_mes_12m),

    CONSTRAINT fk_ml_sku_features_run
        FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_ml_sku_features_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


-- ML Model Registry (selected models per SKU)
CREATE TABLE IF NOT EXISTS ml_model_registry (
    sku VARCHAR(50) PRIMARY KEY,
    modelo_actual VARCHAR(50) NOT NULL,
    modelo_anterior VARCHAR(50) NULL,
    fecha_seleccion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    run_id_seleccion VARCHAR(36) NULL,

    -- Model performance metrics
    rmse DECIMAL(12,4) NULL,
    mae DECIMAL(12,4) NULL,
    bias DECIMAL(10,6) NULL,
    service_level DECIMAL(5,4) NULL,
    coverage_95 DECIMAL(5,4) NULL,

    -- Selection criteria scores
    score_error DECIMAL(8,6) NULL,
    score_service DECIMAL(8,6) NULL,
    score_stability DECIMAL(8,6) NULL,
    score_complexity DECIMAL(8,6) NULL,
    score_composite DECIMAL(8,6) NULL,

    -- Model parameters (JSON como texto)
    model_params LONGTEXT NULL,

    INDEX idx_modelo_actual (modelo_actual),
    INDEX idx_fecha_seleccion (fecha_seleccion),

    CONSTRAINT fk_ml_model_registry_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE,
    CONSTRAINT fk_ml_model_registry_run
        FOREIGN KEY (run_id_seleccion) REFERENCES ml_run(run_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


-- ML Model Switch Log
CREATE TABLE IF NOT EXISTS ml_model_switch_log (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    modelo_anterior VARCHAR(50) NOT NULL,
    modelo_nuevo VARCHAR(50) NOT NULL,
    razon_cambio ENUM('PRIMER_MODELO', 'MEJOR_SCORE', 'DRIFT', 'MANUAL') NOT NULL,
    score_anterior DECIMAL(8,6) NULL,
    score_nuevo DECIMAL(8,6) NULL,
    detalle LONGTEXT NULL, -- JSON como texto
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_sku (sku),
    INDEX idx_run_id (run_id),
    INDEX idx_created_at (created_at),

    CONSTRAINT fk_ml_model_switch_log_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE,
    CONSTRAINT fk_ml_model_switch_log_run
        FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


-- ML Drift Detection Log
CREATE TABLE IF NOT EXISTS ml_drift_log (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    drift_detected TINYINT(1) NOT NULL DEFAULT 0,
    cv_change_pct DECIMAL(10,4) NULL,
    lambda_change_pct DECIMAL(10,4) NULL,
    gap_ratio_change_pct DECIMAL(10,4) NULL,
    cv_threshold DECIMAL(5,4) NOT NULL DEFAULT 0.5000,
    lambda_threshold DECIMAL(5,4) NOT NULL DEFAULT 0.5000,
    detalle LONGTEXT NULL, -- JSON como texto
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_run_id (run_id),
    INDEX idx_sku (sku),
    INDEX idx_drift_detected (drift_detected),

    CONSTRAINT fk_ml_drift_log_run
        FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_ml_drift_log_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


-- Backtesting results
CREATE TABLE IF NOT EXISTS ml_backtest_results (
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

    UNIQUE KEY uk_sku_modelo_fold (sku, modelo, fold_number),
    INDEX idx_sku (sku),
    INDEX idx_modelo (modelo),
    INDEX idx_run_id (run_id),

    CONSTRAINT fk_ml_backtest_results_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE,
    CONSTRAINT fk_ml_backtest_results_run
        FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;


-- Model performance history
CREATE TABLE IF NOT EXISTS ml_model_performance (
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

    CONSTRAINT fk_ml_model_performance_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE,
    CONSTRAINT fk_ml_model_performance_run
        FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

SET FOREIGN_KEY_CHECKS = 1;
