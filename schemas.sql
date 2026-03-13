
-- TABLE: ml_run
CREATE TABLE `ml_run` (
  `run_id` varchar(36) NOT NULL,
  `started_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `finished_at` datetime DEFAULT NULL,
  `skus_procesados` int(11) NOT NULL DEFAULT '0',
  `skus_exitosos` int(11) NOT NULL DEFAULT '0',
  `skus_fallidos` int(11) NOT NULL DEFAULT '0',
  `duracion_segundos` int(11) DEFAULT NULL,
  `triggered_by` enum('SCHEDULER','MANUAL','API') NOT NULL DEFAULT 'SCHEDULER',
  `error_log` longtext,
  PRIMARY KEY (`run_id`),
  KEY `idx_started_at` (`started_at`),
  KEY `idx_finished_at` (`finished_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- TABLE: ss_ml_run
CREATE TABLE `ss_ml_run` (
  `run_id` varchar(36) NOT NULL,
  `started_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `finished_at` datetime DEFAULT NULL,
  `skus_procesados` int(11) NOT NULL DEFAULT '0',
  `skus_exitosos` int(11) NOT NULL DEFAULT '0',
  `skus_fallidos` int(11) NOT NULL DEFAULT '0',
  `duracion_segundos` int(11) DEFAULT NULL,
  `status` varchar(16) DEFAULT NULL,
  `triggered_by` enum('SCHEDULER','MANUAL','API') NOT NULL DEFAULT 'SCHEDULER',
  `error_log` longtext,
  PRIMARY KEY (`run_id`),
  KEY `idx_started_at` (`started_at`),
  KEY `idx_finished_at` (`finished_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- TABLE: ml_suggestions
CREATE TABLE `ml_suggestions` (
  `run_id` varchar(36) NOT NULL,
  `sku` varchar(50) NOT NULL,
  `qty_sugerida` int(11) NOT NULL,
  `qty_final` int(11) DEFAULT NULL,
  `estado` enum('PENDIENTE','APROBADO','RECHAZADO') NOT NULL DEFAULT 'PENDIENTE',
  `modelo_seleccionado` varchar(50) NOT NULL,
  `policy_min` int(11) DEFAULT NULL,
  `policy_max` int(11) DEFAULT NULL,
  `notas` text,
  `aprobado_por` varchar(100) DEFAULT NULL,
  `fecha_aprobacion` datetime DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`run_id`,`sku`),
  KEY `idx_sku` (`sku`),
  KEY `idx_estado` (`estado`),
  KEY `idx_updated_at` (`updated_at`),
  CONSTRAINT `fk_ml_suggestions_run` FOREIGN KEY (`run_id`) REFERENCES `ml_run` (`run_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ml_suggestions_sku` FOREIGN KEY (`sku`) REFERENCES `sku_master` (`sku`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- TABLE: ss_ml_suggestions
CREATE TABLE `ss_ml_suggestions` (
  `run_id` varchar(36) NOT NULL,
  `sku` varchar(50) NOT NULL,
  `qty_sugerida` int(11) NOT NULL,
  `qty_final` int(11) DEFAULT NULL,
  `estado` enum('PENDIENTE','APROBADO','RECHAZADO') NOT NULL DEFAULT 'PENDIENTE',
  `modelo_seleccionado` varchar(50) NOT NULL,
  `policy_min` int(11) DEFAULT NULL,
  `policy_max` int(11) DEFAULT NULL,
  `notas` text,
  `aprobado_por` varchar(100) DEFAULT NULL,
  `fecha_aprobacion` datetime DEFAULT NULL,
  `updated_at` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`run_id`,`sku`),
  KEY `idx_sku` (`sku`),
  KEY `idx_estado` (`estado`),
  KEY `idx_updated_at` (`updated_at`),
  CONSTRAINT `fk_ss_ml_suggestions_run` FOREIGN KEY (`run_id`) REFERENCES `ss_ml_run` (`run_id`) ON DELETE CASCADE,
  CONSTRAINT `fk_ss_ml_suggestions_sku` FOREIGN KEY (`sku`) REFERENCES `ss_sku_master` (`sku`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- TABLE: ml_model_registry
CREATE TABLE `ml_model_registry` (
  `sku` varchar(50) NOT NULL,
  `modelo_actual` varchar(50) NOT NULL,
  `modelo_anterior` varchar(50) DEFAULT NULL,
  `fecha_seleccion` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `run_id_seleccion` varchar(36) DEFAULT NULL,
  `rmse` decimal(12,4) DEFAULT NULL,
  `mae` decimal(12,4) DEFAULT NULL,
  `bias` decimal(10,6) DEFAULT NULL,
  `service_level` decimal(5,4) DEFAULT NULL,
  `coverage_95` decimal(5,4) DEFAULT NULL,
  `score_error` decimal(8,6) DEFAULT NULL,
  `score_service` decimal(8,6) DEFAULT NULL,
  `score_stability` decimal(8,6) DEFAULT NULL,
  `score_complexity` decimal(8,6) DEFAULT NULL,
  `score_composite` decimal(8,6) DEFAULT NULL,
  `model_params` longtext,
  PRIMARY KEY (`sku`),
  KEY `idx_modelo_actual` (`modelo_actual`),
  KEY `idx_fecha_seleccion` (`fecha_seleccion`),
  KEY `fk_ml_model_registry_run` (`run_id_seleccion`),
  CONSTRAINT `fk_ml_model_registry_sku` FOREIGN KEY (`sku`) REFERENCES `sku_master` (`sku`) ON DELETE CASCADE,
  CONSTRAINT `fk_ml_model_registry_run` FOREIGN KEY (`run_id_seleccion`) REFERENCES `ml_run` (`run_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- TABLE: ss_ml_model_registry
CREATE TABLE `ss_ml_model_registry` (
  `sku` varchar(50) NOT NULL,
  `modelo_actual` varchar(50) NOT NULL,
  `modelo_anterior` varchar(50) DEFAULT NULL,
  `fecha_seleccion` timestamp NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `run_id_seleccion` varchar(36) DEFAULT NULL,
  `rmse` decimal(12,4) DEFAULT NULL,
  `mae` decimal(12,4) DEFAULT NULL,
  `bias` decimal(10,6) DEFAULT NULL,
  `service_level` decimal(5,4) DEFAULT NULL,
  `coverage_95` decimal(5,4) DEFAULT NULL,
  `score_error` decimal(8,6) DEFAULT NULL,
  `score_service` decimal(8,6) DEFAULT NULL,
  `score_stability` decimal(8,6) DEFAULT NULL,
  `score_complexity` decimal(8,6) DEFAULT NULL,
  `score_composite` decimal(8,6) DEFAULT NULL,
  `model_params` longtext,
  PRIMARY KEY (`sku`),
  KEY `idx_modelo_actual` (`modelo_actual`),
  KEY `idx_fecha_seleccion` (`fecha_seleccion`),
  KEY `fk_ss_ml_model_registry_run` (`run_id_seleccion`),
  CONSTRAINT `fk_ss_ml_model_registry_sku` FOREIGN KEY (`sku`) REFERENCES `ss_sku_master` (`sku`) ON DELETE CASCADE,
  CONSTRAINT `fk_ss_ml_model_registry_run` FOREIGN KEY (`run_id_seleccion`) REFERENCES `ss_ml_run` (`run_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- TABLE: parametros_sku
CREATE TABLE `parametros_sku` (
  `sku` varchar(50) NOT NULL,
  `familia` varchar(50) DEFAULT NULL,
  `criticidad` enum('ALTA','MEDIA','BAJA') DEFAULT NULL,
  `tipo_demanda` enum('ESTABLE','ESTACIONAL','INTERMITENTE') DEFAULT NULL,
  `lead_time_dias` int(11) DEFAULT NULL,
  `lead_time_sigma` float DEFAULT NULL,
  `stock_min` int(11) DEFAULT NULL,
  `stock_objetivo` int(11) DEFAULT NULL,
  `moq` int(11) DEFAULT NULL,
  `multiplo_compra` int(11) DEFAULT NULL,
  `temp_storage` enum('AMBIENTE','2-8','-20') DEFAULT NULL,
  `dias_minimos_antes_vencimiento` int(11) DEFAULT NULL,
  `z_servicio` float DEFAULT '1.65',
  `activo` tinyint(1) DEFAULT '1',
  `discontinuado` tinyint(1) DEFAULT '0',
  `sugerencia_aprobada` int(11) DEFAULT '0',
  `fecha_sugerencia` datetime DEFAULT NULL,
  `stock_cache_int` decimal(12,4) DEFAULT '0.0000' COMMENT 'Stock calculado (Cache Rapido)',
  `fisico_cache_int` decimal(12,4) DEFAULT '0.0000' COMMENT 'Fisico calculado (Cache Rapido)',
  `last_stock_update` datetime DEFAULT NULL,
  `modelo_recomendado` varchar(40) DEFAULT NULL,
  `service_prob_usado` decimal(5,3) DEFAULT NULL,
  `cap_objetivo` int(11) DEFAULT NULL,
  `review_updated_at` datetime DEFAULT NULL,
  `qty_aprobada` decimal(18,4) DEFAULT NULL,
  PRIMARY KEY (`sku`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;

-- TABLE: sku_abc_xyz
CREATE TABLE `sku_abc_xyz` (
  `sku` varchar(50) NOT NULL,
  `margen_12m` decimal(65,6) DEFAULT '0.000000',
  `cv` double DEFAULT NULL,
  `pct_mes_venta` decimal(27,4) DEFAULT NULL,
  `abc_class` char(1) DEFAULT 'C',
  `xyz_class` char(1) DEFAULT 'Z',
  `updated_at` datetime NOT NULL,
  PRIMARY KEY (`sku`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;
