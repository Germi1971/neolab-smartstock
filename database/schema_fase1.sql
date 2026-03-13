-- ============================================
-- FASE 1: Core Database Schema (MySQL 5.5.62 compatible)
-- ============================================

SET FOREIGN_KEY_CHECKS = 0;

-- Master SKU table
CREATE TABLE IF NOT EXISTS sku_master (
    sku VARCHAR(50) PRIMARY KEY,
    descripcion VARCHAR(255) NOT NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_activo (activo)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- SKU Parameters
CREATE TABLE IF NOT EXISTS sku_parameters (
    sku VARCHAR(50) PRIMARY KEY,
    stock_objetivo INT NOT NULL DEFAULT 0,
    stock_seguridad INT NOT NULL DEFAULT 0,
    punto_reorden INT NOT NULL DEFAULT 0,
    moq INT NULL,
    multiplo INT NULL,
    activo TINYINT(1) NOT NULL DEFAULT 1,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(100) NULL,
    CONSTRAINT fk_sku_parameters_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- Stock positions
CREATE TABLE IF NOT EXISTS stock (
    sku VARCHAR(50) PRIMARY KEY,
    stock_posicion INT NOT NULL DEFAULT 0,
    stock_transito INT NOT NULL DEFAULT 0,
    stock_comprometido INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_stock_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- Demand history
CREATE TABLE IF NOT EXISTS demand_history (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    fecha DATE NOT NULL,
    cantidad INT NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_sku_fecha (sku, fecha),
    INDEX idx_fecha (fecha),
    CONSTRAINT fk_demand_history_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ML Pipeline runs
CREATE TABLE IF NOT EXISTS ml_run (
    run_id VARCHAR(36) PRIMARY KEY,
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP NULL,
    skus_procesados INT NOT NULL DEFAULT 0,
    skus_exitosos INT NOT NULL DEFAULT 0,
    skus_fallidos INT NOT NULL DEFAULT 0,
    duracion_segundos INT NULL,
    triggered_by ENUM('SCHEDULER', 'MANUAL', 'API') NOT NULL DEFAULT 'SCHEDULER',
    error_log LONGTEXT NULL,              -- JSON -> LONGTEXT
    INDEX idx_started_at (started_at),
    INDEX idx_finished_at (finished_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- ML Suggestions
CREATE TABLE IF NOT EXISTS ml_suggestions (
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    qty_sugerida INT NOT NULL,
    qty_final INT NULL,
    estado ENUM('PENDIENTE', 'APROBADO', 'RECHAZADO') NOT NULL DEFAULT 'PENDIENTE',
    modelo_seleccionado VARCHAR(50) NOT NULL,
    s_policy INT NULL,
    S_policy INT NULL,
    notas TEXT NULL,
    aprobado_por VARCHAR(100) NULL,
    fecha_aprobacion TIMESTAMP NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, sku),
    INDEX idx_sku (sku),
    INDEX idx_estado (estado),
    INDEX idx_updated_at (updated_at),
    CONSTRAINT fk_ml_suggestions_run
        FOREIGN KEY (run_id) REFERENCES ml_run(run_id) ON DELETE CASCADE,
    CONSTRAINT fk_ml_suggestions_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- Order Approvals
CREATE TABLE IF NOT EXISTS orders_approvals (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    sku VARCHAR(50) NOT NULL,
    qty_sugerida_ml INT NOT NULL,
    qty_final INT NOT NULL,
    estado ENUM('PENDIENTE', 'APROBADO', 'RECHAZADO') NOT NULL DEFAULT 'PENDIENTE',
    aprobado_por VARCHAR(100) NULL,
    fecha_aprobacion TIMESTAMP NULL,
    notas TEXT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_sku (sku),
    INDEX idx_estado (estado),
    CONSTRAINT fk_orders_approvals_sku
        FOREIGN KEY (sku) REFERENCES sku_master(sku) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    id INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
    tabla VARCHAR(50) NOT NULL,
    registro_id VARCHAR(100) NOT NULL,
    accion ENUM('INSERT', 'UPDATE', 'DELETE') NOT NULL,
    usuario VARCHAR(100) NULL,
    cambios LONGTEXT NULL,                -- JSON -> LONGTEXT
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tabla (tabla),
    INDEX idx_registro (registro_id),
    INDEX idx_accion (accion),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- System Configuration
CREATE TABLE IF NOT EXISTS system_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT NOT NULL,
    config_type ENUM('string', 'int', 'float', 'bool', 'json') NOT NULL DEFAULT 'string',
    description VARCHAR(500) NULL,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(100) NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

SET FOREIGN_KEY_CHECKS = 1;

-- Insert default configurations (idempotente)
INSERT INTO system_config (config_key, config_value, config_type, description) VALUES
('system.name', 'NeoLab SmartStock', 'string', 'System name'),
('system.version', '2.0.0', 'string', 'System version'),
('ml.default_model', 'REGULAR', 'string', 'Default ML model for new SKUs'),
('ml.min_history_days', '30', 'int', 'Minimum days of history required for ML'),
('stock.default_stock_objetivo', '100', 'int', 'Default stock objetivo for new SKUs'),
('stock.default_stock_seguridad', '20', 'int', 'Default stock seguridad for new SKUs')
ON DUPLICATE KEY UPDATE 
    config_value = VALUES(config_value),
    config_type = VALUES(config_type),
    description = VALUES(description);
