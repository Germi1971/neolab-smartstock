-- Database Migrations for NeoLab SmartStock PRO (MySQL 5.5 compat)

-- 1. Unify ML Runs table
CREATE TABLE IF NOT EXISTS ml_runs (
    run_id VARCHAR(64) PRIMARY KEY,
    started_at DATETIME NOT NULL,
    finished_at DATETIME NULL,
    skus_procesados INT DEFAULT 0,
    skus_exitosos INT DEFAULT 0,
    skus_fallidos INT DEFAULT 0,
    duracion_segundos INT DEFAULT 0,
    status VARCHAR(16) DEFAULT 'PENDING',
    triggered_by VARCHAR(16) DEFAULT 'MANUAL',
    error_log TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 2. ML Model Registry
CREATE TABLE IF NOT EXISTS ml_model_registry (
    sku VARCHAR(50) PRIMARY KEY,
    modelo_actual VARCHAR(50) NOT NULL,
    modelo_anterior VARCHAR(50) NULL,
    fecha_seleccion DATETIME NOT NULL,
    run_id_seleccion VARCHAR(64) NULL,
    rmse NUMERIC(12, 4) NULL,
    mae NUMERIC(12, 4) NULL,
    bias NUMERIC(10, 6) NULL,
    service_level NUMERIC(5, 4) NULL,
    coverage_95 NUMERIC(5, 4) NULL,
    score_composite NUMERIC(8, 6) NULL,
    model_params TEXT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 3. SKU Features
CREATE TABLE IF NOT EXISTS ml_sku_features (
    run_id VARCHAR(64),
    sku VARCHAR(50),
    periodo_inicio DATE NOT NULL,
    periodo_fin DATE NOT NULL,
    dias_observados_12m INT DEFAULT 0,
    eventos_12m INT DEFAULT 0,
    unidades_12m INT DEFAULT 0,
    cv_12m NUMERIC(10, 6) DEFAULT 0,
    lambda_eventos_mes_12m NUMERIC(10, 6) DEFAULT 0,
    ultima_venta DATE NULL,
    dias_desde_ultima_venta INT DEFAULT 0,
    PRIMARY KEY (run_id, sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- 4. ML Suggestions
CREATE TABLE IF NOT EXISTS ml_suggestions (
    run_id VARCHAR(64),
    sku VARCHAR(50),
    qty_sugerida INT NOT NULL,
    qty_final INT NULL,
    estado VARCHAR(20) DEFAULT 'PENDIENTE',
    modelo_seleccionado VARCHAR(50) NOT NULL,
    policy_s_lower INT NULL,
    policy_s_upper INT NULL,
    notas TEXT NULL,
    aprobado_por VARCHAR(100) NULL,
    fecha_aprobacion DATETIME NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (run_id, sku)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- Note: Information about views and other components can be found in README.md or technical documentation.
