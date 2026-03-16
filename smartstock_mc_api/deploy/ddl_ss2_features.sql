-- =============================================================================
-- ss2_features - Capa Feature Engine (features calculadas por SKU)
-- =============================================================================
-- Tabla unificada de features para Demand Classification, Demand Engine y Policy.
-- Alternativa a ss2_sku_features_12m cuando se quiere estructura explícita.
--
-- Si ya usás ss2_sku_features_12m + sp_ss2_sku_features_12m_refresh, esta tabla
-- es OPCIONAL. Podés crear una vista v_sku_features_12m que lea de ss2_sku_features_12m
-- con los alias necesarios (meses_con_venta_12m, demanda_prom_mensual_12m, etc).
--
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/ddl_ss2_features.sql
-- Compatible: MySQL 5.5+
-- =============================================================================

CREATE TABLE IF NOT EXISTS ss2_features (
  sku VARCHAR(80) NOT NULL,
  asof_date DATE NULL COMMENT 'Fecha de cálculo (NULL = último)',

  -- Demanda básica
  unidades_3m DOUBLE NULL,
  unidades_6m DOUBLE NULL,
  unidades_12m DOUBLE NULL,
  unidades_24m DOUBLE NULL,

  -- Eventos
  eventos_3m INT NULL,
  eventos_6m INT NULL,
  eventos_12m INT NULL,
  eventos_24m INT NULL,

  -- Frecuencia / intervalos
  dias_observados INT NULL,
  days_since_last_sale INT NULL,
  days_since_last_movement INT NULL,
  meses_con_demanda INT NULL,

  -- Tamaño de evento
  mean_qty_event DOUBLE NULL,
  std_qty_event DOUBLE NULL,
  cv_event DOUBLE NULL,
  cv2_event DOUBLE NULL,

  -- Intermitencia (ADI)
  adi DOUBLE NULL,

  -- Tendencia (mu por ventana)
  mu_6m DOUBLE NULL,
  mu_12m DOUBLE NULL,
  mu_24m DOUBLE NULL,
  acceleration_ratio DOUBLE NULL COMMENT 'mu_6m / mu_24m',

  -- Mix clientes
  n_clientes_12m INT NULL,
  top1_share_12m DOUBLE NULL,

  -- Riesgo operativo
  lead_time_dias INT NULL,
  review_days INT NULL,
  days_of_supply DOUBLE NULL,
  backlog_qty INT NULL,

  -- Económicas
  costo_unitario DOUBLE NULL,
  margen_pct DOUBLE NULL,
  inventory_value DOUBLE NULL,

  -- Auditoría
  updated_at DATETIME NOT NULL,

  PRIMARY KEY (sku),
  INDEX idx_asof_date (asof_date),
  INDEX idx_eventos_12m (eventos_12m),
  INDEX idx_unidades_12m (unidades_12m),
  INDEX idx_updated_at (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;


-- =============================================================================
-- Notas
-- =============================================================================
-- Fuente de datos: ss2_inv_event (SHIP) o tabla1 según pipeline.
-- El SP sp_ss2_sku_features_12m_refresh escribe en ss2_sku_features_12m.
-- Esta tabla ss2_features es para pipelines que quieran estructura explícita.
--
-- Mapeo ss2_sku_features_12m -> ss2_features (si migrás):
--   total_units_12m -> unidades_12m
--   events_12m -> eventos_12m
--   q_mean_event -> mean_qty_event
--   q_sd_event -> std_qty_event
--   demand_mean_m * 12 -> mu_12m (aprox)
-- =============================================================================
