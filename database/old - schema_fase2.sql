-- ============================================
-- FASE 2: ML Advanced Schema
-- ============================================

-- ML SKU Features (computed features per run)
CREATE TABLE IF NOT EXISTS ml_sku_features (
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    periodo_inicio DATE NOT NULL,
    periodo_fin DATE NOT NULL,
    
    -- 12 month features
    dias_observados_12m INT DEFAULT 0,
    eventos_12m INT DEFAULT 0,
    unidades_12m INT DEFAULT 0,
    meses_con_venta_12m INT DEFAULT 0,
    pct_meses_con_venta_12m DECIMAL(5,4) DEFAULT 0,
    lambda_eventos_mes_12m DECIMAL(10,6) DEFAULT 0,
    mu_unidades_evento_12m DECIMAL(12,4) DEFAULT 0,
    cv_12m DECIMAL(10,6) DEFAULT 0,
    adi_12m DECIMAL(10,6) DEFAULT 0,
    squared_cv_12m DECIMAL(10,6) DEFAULT 0,
    
    -- 24 month features
    dias_observados_24m INT DEFAULT 0,
    eventos_24m INT DEFAULT 0,
    unidades_24m INT DEFAULT 0,
    cv_24m DECIMAL(10,6) DEFAULT 0,
    
    -- 90 day features
    dias_observados_90d INT DEFAULT 0,
    eventos_90d INT DEFAULT 0,
    unidades_90d INT DEFAULT 0,
    tendencia_90d DECIMAL(10,6) DEFAULT 0,
    
    -- Additional features
    ultima_venta DATE,
    dias_desde_ultima_venta INT DEFAULT 0,
    
    PRIMARY KEY (run_id, sku),
    INDEX idx_sku (sku),
    INDEX idx_cv_12m (cv_12m),
    INDEX idx_lambda (lambda_eventos_mes_12m),
    FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE,
    FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ML Model Registry (selected models per SKU)
CREATE TABLE IF NOT EXISTS ml_model_registry (
    sku VARCHAR(50) PRIMARY KEY,
    modelo_actual VARCHAR(50) NOT NULL,
    modelo_anterior VARCHAR(50),
    fecha_seleccion TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    run_id_seleccion VARCHAR(36),
    
    -- Model performance metrics
    rmse DECIMAL(12,4),
    mae DECIMAL(12,4),
    bias DECIMAL(10,6),
    service_level DECIMAL(5,4),
    coverage_95 DECIMAL(5,4),
    
    -- Selection criteria scores
    score_error DECIMAL(8,6),
    score_service DECIMAL(8,6),
    score_stability DECIMAL(8,6),
    score_complexity DECIMAL(8,6),
    score_composite DECIMAL(8,6),
    
    -- Model parameters
    model_params JSON,
    
    INDEX idx_modelo_actual (modelo_actual),
    INDEX idx_fecha_seleccion (fecha_seleccion),
    FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE,
    FOREIGN KEY (run_id_seleccion) REFERENCES ml_run(run_id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ML Model Switch Log
CREATE TABLE IF NOT EXISTS ml_model_switch_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    modelo_anterior VARCHAR(50) NOT NULL,
    modelo_nuevo VARCHAR(50) NOT NULL,
    razon_cambio ENUM('PRIMER_MODELO', 'MEJOR_SCORE', 'DRIFT', 'MANUAL') NOT NULL,
    score_anterior DECIMAL(8,6),
    score_nuevo DECIMAL(8,6),
    detalle JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sku (sku),
    INDEX idx_run_id (run_id),
    INDEX idx_created_at (created_at),
    FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ML Drift Detection Log
CREATE TABLE IF NOT EXISTS ml_drift_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    drift_detected BOOLEAN DEFAULT FALSE,
    cv_change_pct DECIMAL(10,4),
    lambda_change_pct DECIMAL(10,4),
    gap_ratio_change_pct DECIMAL(10,4),
    cv_threshold DECIMAL(5,4) DEFAULT 0.5,
    lambda_threshold DECIMAL(5,4) DEFAULT 0.5,
    detalle JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_run_id (run_id),
    INDEX idx_sku (sku),
    INDEX idx_drift_detected (drift_detected),
    FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE,
    FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Backtesting results
CREATE TABLE IF NOT EXISTS ml_backtest_results (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    modelo VARCHAR(50) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    fold_number INT NOT NULL,
    train_start DATE NOT NULL,
    train_end DATE NOT NULL,
    test_start DATE NOT NULL,
    test_end DATE NOT NULL,
    rmse DECIMAL(12,4),
    mae DECIMAL(12,4),
    mape DECIMAL(10,4),
    bias DECIMAL(10,6),
    coverage_80 DECIMAL(5,4),
    coverage_95 DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sku_modelo_fold (sku, modelo, fold_number),
    INDEX idx_sku (sku),
    INDEX idx_modelo (modelo),
    INDEX idx_run_id (run_id),
    FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Model performance history
CREATE TABLE IF NOT EXISTS ml_model_performance (
    id INT AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    modelo VARCHAR(50) NOT NULL,
    run_id VARCHAR(36) NOT NULL,
    periodo_inicio DATE NOT NULL,
    periodo_fin DATE NOT NULL,
    rmse DECIMAL(12,4),
    mae DECIMAL(12,4),
    mape DECIMAL(10,4),
    service_level DECIMAL(5,4),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_sku (sku),
    INDEX idx_modelo (modelo),
    INDEX idx_run_id (run_id),
    FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE,
    FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
