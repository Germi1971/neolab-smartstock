-- ============================================
-- FASE 3: Scheduler, Locks, Observabilidad
-- ============================================

-- Tabla de errores por SKU en ejecuciones ML
CREATE TABLE IF NOT EXISTS ml_run_errors (
    id INT AUTO_INCREMENT PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    sku VARCHAR(50) NOT NULL,
    error_code VARCHAR(50) NOT NULL,
    error_message TEXT,
    error_detail JSON,
    retry_count INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP NULL,
    INDEX idx_run_id (run_id),
    INDEX idx_sku (sku),
    INDEX idx_created_at (created_at),
    INDEX idx_resolved (resolved_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de caché materializado por SKU (vista previa calculada)
CREATE TABLE IF NOT EXISTS sku_cache_latest (
    sku VARCHAR(50) PRIMARY KEY,
    run_id VARCHAR(36) NOT NULL,
    
    -- Stock info
    stock_posicion INT NOT NULL DEFAULT 0,
    stock_objetivo INT NOT NULL DEFAULT 0,
    stock_seguridad INT NOT NULL DEFAULT 0,
    
    -- Sugerencia
    qty_sugerida INT NOT NULL DEFAULT 0,
    estado ENUM('PENDIENTE', 'APROBADO', 'RECHAZADO') DEFAULT 'PENDIENTE',
    qty_final INT,
    
    -- ML info
    modelo_seleccionado VARCHAR(50),
    s_policy INT,
    S_policy INT,
    score_composite DECIMAL(8,6),
    
    -- Features summary
    cv_12m DECIMAL(10,6),
    lambda_eventos_mes_12m DECIMAL(10,6),
    eventos_12m INT,
    unidades_12m INT,
    drift_detected BOOLEAN DEFAULT FALSE,
    
    -- Metadata
    computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    
    INDEX idx_run_id (run_id),
    INDEX idx_estado (estado),
    INDEX idx_modelo (modelo_seleccionado),
    INDEX idx_drift (drift_detected),
    INDEX idx_expires (expires_at),
    INDEX idx_computed (computed_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de locks del scheduler (advisory locks persistentes)
CREATE TABLE IF NOT EXISTS scheduler_locks (
    lock_name VARCHAR(100) PRIMARY KEY,
    locked_by VARCHAR(100) NOT NULL,
    locked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    metadata JSON,
    INDEX idx_expires (expires_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de métricas y observabilidad
CREATE TABLE IF NOT EXISTS system_metrics (
    id INT AUTO_INCREMENT PRIMARY KEY,
    metric_name VARCHAR(100) NOT NULL,
    metric_value DECIMAL(18,6) NOT NULL,
    metric_type ENUM('counter', 'gauge', 'histogram') DEFAULT 'gauge',
    labels JSON,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_metric_name (metric_name),
    INDEX idx_recorded_at (recorded_at),
    INDEX idx_metric_type (metric_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de logs de auditoría extendida
CREATE TABLE IF NOT EXISTS audit_log_extended (
    id INT AUTO_INCREMENT PRIMARY KEY,
    tabla VARCHAR(50) NOT NULL,
    registro_id VARCHAR(100) NOT NULL,
    accion ENUM('INSERT', 'UPDATE', 'DELETE', 'EXECUTE') NOT NULL,
    usuario VARCHAR(100),
    cambios JSON,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    execution_time_ms INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_tabla (tabla),
    INDEX idx_registro (registro_id),
    INDEX idx_accion (accion),
    INDEX idx_usuario (usuario),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Tabla de configuración del scheduler
CREATE TABLE IF NOT EXISTS scheduler_config (
    config_key VARCHAR(100) PRIMARY KEY,
    config_value TEXT NOT NULL,
    config_type ENUM('string', 'int', 'float', 'bool', 'json') DEFAULT 'string',
    description VARCHAR(500),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(100)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Insertar configuraciones por defecto
INSERT INTO scheduler_config (config_key, config_value, config_type, description) VALUES
('ml_pipeline.cron', '0 2 * * *', 'string', 'Cron expression para ejecución automática del pipeline ML'),
('ml_pipeline.timeout_seconds', '3600', 'int', 'Timeout máximo para ejecución del pipeline'),
('ml_pipeline.max_retries', '3', 'int', 'Máximo de reintentos por SKU fallido'),
('ml_pipeline.retry_delay_seconds', '60', 'int', 'Delay entre reintentos'),
('ml_pipeline.batch_size', '100', 'int', 'Tamaño de batch para procesamiento'),
('cache.ttl_minutes', '60', 'int', 'TTL del caché materializado en minutos'),
('lock.timeout_seconds', '300', 'int', 'Timeout de locks del scheduler'),
('drift.threshold_cv_change', '0.5', 'float', 'Umbral de cambio de CV para detectar drift'),
('drift.threshold_lambda_change', '0.5', 'float', 'Umbral de cambio de lambda para detectar drift'),
('model_selection.hysteresis_threshold', '0.05', 'float', 'Umbral de histéresis para cambio de modelo')
ON DUPLICATE KEY UPDATE config_value = VALUES(config_value);

-- Vista de resumen de ejecuciones ML
CREATE OR REPLACE VIEW v_ml_run_summary AS
SELECT 
    r.run_id,
    r.started_at,
    r.finished_at,
    r.skus_procesados,
    r.skus_exitosos,
    r.skus_fallidos,
    r.duracion_segundos,
    r.triggered_by,
    COUNT(e.id) as errores_no_resueltos,
    CASE 
        WHEN r.skus_fallidos = 0 THEN 'SUCCESS'
        WHEN r.skus_exitosos = 0 THEN 'FAILED'
        ELSE 'PARTIAL'
    END as status
FROM ml_run r
LEFT JOIN ml_run_errors e ON r.run_id = e.run_id AND e.resolved_at IS NULL
GROUP BY r.run_id, r.started_at, r.finished_at, r.skus_procesados, 
         r.skus_exitosos, r.skus_fallidos, r.duracion_segundos, r.triggered_by;

-- Vista de SKUs con problemas
CREATE OR REPLACE VIEW v_skus_with_issues AS
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
    c.expires_at < NOW() as cache_expired,
    e.error_code as last_error,
    e.created_at as last_error_at
FROM sku_master s
LEFT JOIN sku_parameters p ON s.sku = p.sku
LEFT JOIN sku_cache_latest c ON s.sku = c.sku
LEFT JOIN (
    SELECT sku, error_code, created_at,
           ROW_NUMBER() OVER (PARTITION BY sku ORDER BY created_at DESC) as rn
    FROM ml_run_errors
    WHERE resolved_at IS NULL
) e ON s.sku = e.sku AND e.rn = 1
WHERE s.activo = TRUE
  AND (c.drift_detected = TRUE 
       OR c.expires_at < NOW() 
       OR e.error_code IS NOT NULL
       OR c.modelo_seleccionado = 'SIN_DATOS');
