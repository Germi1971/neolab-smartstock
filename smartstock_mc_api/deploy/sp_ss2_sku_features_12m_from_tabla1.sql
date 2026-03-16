-- =============================================================================
-- sp_ss2_sku_features_12m_refresh - Lee desde tabla1 (1 evento = 1 factura FAC)
-- =============================================================================
-- Corrige: events_12m = nº facturas (FAC), total_units_12m = suma de líneas (Cantidad)
-- Cada línea en tabla1 con E/S='S' tiene cantidad=1; se agrupa por FAC.
--
-- Requiere: tabla1 con columnas E/S, FAC, Código, Cantidad, Fecha
-- Ejecutar: mysql -h HOST -u USER -p DATABASE < deploy/sp_ss2_sku_features_12m_from_tabla1.sql
-- =============================================================================

DELIMITER ;;

DROP PROCEDURE IF EXISTS `sp_ss2_sku_features_12m_refresh`;;

CREATE PROCEDURE `sp_ss2_sku_features_12m_refresh`(IN p_asof DATE)
BEGIN
  DECLARE v_month0 DATE;
  DECLARE v_asof_next DATE;

  IF p_asof IS NULL THEN
    SET p_asof = CURDATE();
  END IF;

  SET v_month0 = DATE_SUB(p_asof, INTERVAL (DAYOFMONTH(p_asof)-1) DAY);
  SET v_asof_next = DATE_ADD(p_asof, INTERVAL 1 DAY);

  -- 1) Meses (12 filas)
  DROP TEMPORARY TABLE IF EXISTS tmp_ss2_m12;
  CREATE TEMPORARY TABLE tmp_ss2_m12 (
    m INT NOT NULL,
    month_start DATE NOT NULL,
    month_end DATE NOT NULL,
    PRIMARY KEY (m)
  ) ENGINE=MEMORY;

  INSERT INTO tmp_ss2_m12 (m, month_start, month_end)
  SELECT 0,  v_month0,                               DATE_ADD(v_month0, INTERVAL 1 MONTH) UNION ALL
  SELECT 1,  DATE_SUB(v_month0, INTERVAL 1 MONTH),   v_month0                               UNION ALL
  SELECT 2,  DATE_SUB(v_month0, INTERVAL 2 MONTH),   DATE_SUB(v_month0, INTERVAL 1 MONTH)   UNION ALL
  SELECT 3,  DATE_SUB(v_month0, INTERVAL 3 MONTH),   DATE_SUB(v_month0, INTERVAL 2 MONTH)   UNION ALL
  SELECT 4,  DATE_SUB(v_month0, INTERVAL 4 MONTH),   DATE_SUB(v_month0, INTERVAL 3 MONTH)   UNION ALL
  SELECT 5,  DATE_SUB(v_month0, INTERVAL 5 MONTH),   DATE_SUB(v_month0, INTERVAL 4 MONTH)   UNION ALL
  SELECT 6,  DATE_SUB(v_month0, INTERVAL 6 MONTH),   DATE_SUB(v_month0, INTERVAL 5 MONTH)   UNION ALL
  SELECT 7,  DATE_SUB(v_month0, INTERVAL 7 MONTH),   DATE_SUB(v_month0, INTERVAL 6 MONTH)   UNION ALL
  SELECT 8,  DATE_SUB(v_month0, INTERVAL 8 MONTH),   DATE_SUB(v_month0, INTERVAL 7 MONTH)   UNION ALL
  SELECT 9,  DATE_SUB(v_month0, INTERVAL 9 MONTH),   DATE_SUB(v_month0, INTERVAL 8 MONTH)   UNION ALL
  SELECT 10, DATE_SUB(v_month0, INTERVAL 10 MONTH),  DATE_SUB(v_month0, INTERVAL 9 MONTH)   UNION ALL
  SELECT 11, DATE_SUB(v_month0, INTERVAL 11 MONTH),  DATE_SUB(v_month0, INTERVAL 10 MONTH);

  -- 2) Universo SKUs (fallback si ss2_v_policy_effective no existe)
  DROP TEMPORARY TABLE IF EXISTS tmp_ss2_sku_u;
  CREATE TEMPORARY TABLE tmp_ss2_sku_u (sku VARCHAR(50) NOT NULL, PRIMARY KEY (sku)) ENGINE=MEMORY;

  INSERT IGNORE INTO tmp_ss2_sku_u (sku)
  SELECT p.sku FROM parametros_sku p
  WHERE COALESCE(p.activo,1)=1 AND COALESCE(p.discontinuado,0)=0;

  -- 3) Unidades por mes desde tabla1 (E/S='S', agrupado por Código + mes)
  DROP TEMPORARY TABLE IF EXISTS tmp_ss2_sku_m_units;
  CREATE TEMPORARY TABLE tmp_ss2_sku_m_units (
    sku VARCHAR(50) NOT NULL,
    m INT NOT NULL,
    units_m INT NOT NULL,
    PRIMARY KEY (sku, m),
    KEY idx_m (m)
  ) ENGINE=MEMORY;

  INSERT INTO tmp_ss2_sku_m_units (sku, m, units_m)
  SELECT
    u.sku,
    m.m,
    IFNULL(SUM(IFNULL(t.`Cantidad`, 1)), 0) AS units_m
  FROM tmp_ss2_sku_u u
  JOIN tmp_ss2_m12 m
  LEFT JOIN tabla1 t
    ON TRIM(t.`Código`) = u.sku
   AND UPPER(TRIM(IFNULL(t.`E/S`,''))) = 'S'
   AND t.`Fecha` >= m.month_start
   AND t.`Fecha` < LEAST(m.month_end, v_asof_next)
  GROUP BY u.sku, m.m;

  -- 4) Stats SHIP desde tabla1: events_12m = COUNT(DISTINCT FAC), total = SUM(Cantidad)
  DROP TEMPORARY TABLE IF EXISTS tmp_ss2_ship_stats;
  CREATE TEMPORARY TABLE tmp_ss2_ship_stats (
    sku VARCHAR(50) NOT NULL,
    events_12m INT NOT NULL,
    total_units_12m INT NOT NULL,
    q_mean_event DECIMAL(12,4) NOT NULL,
    q_sd_event DECIMAL(12,4) NOT NULL,
    last_ship_date DATE NULL,
    PRIMARY KEY (sku)
  ) ENGINE=MEMORY;

  INSERT INTO tmp_ss2_ship_stats (sku, events_12m, total_units_12m, q_mean_event, q_sd_event, last_ship_date)
  SELECT
    TRIM(t.`Código`) AS sku,
    COUNT(DISTINCT t.`FAC`) AS events_12m,
    SUM(IFNULL(t.`Cantidad`, 1)) AS total_units_12m,
    CAST(CASE WHEN COUNT(DISTINCT t.`FAC`) > 0
      THEN SUM(IFNULL(t.`Cantidad`, 1)) / COUNT(DISTINCT t.`FAC`) ELSE 0 END AS DECIMAL(12,4)) AS q_mean_event,
    0.0000 AS q_sd_event,
    MAX(t.`Fecha`) AS last_ship_date
  FROM tabla1 t
  WHERE UPPER(TRIM(IFNULL(t.`E/S`,''))) = 'S'
    AND t.`Fecha` >= DATE_SUB(v_month0, INTERVAL 11 MONTH)
    AND t.`Fecha` < v_asof_next
    AND TRIM(IFNULL(t.`Código`,'')) <> ''
    AND TRIM(IFNULL(t.`FAC`,'')) <> ''
  GROUP BY TRIM(t.`Código`);

  -- 5) last_book_date desde ss2_inv_event (PO/RECEIVE)
  DROP TEMPORARY TABLE IF EXISTS tmp_ss2_book_stats;
  CREATE TEMPORARY TABLE tmp_ss2_book_stats (sku VARCHAR(50) NOT NULL, last_book_date DATE NULL, PRIMARY KEY (sku)) ENGINE=MEMORY;

  INSERT INTO tmp_ss2_book_stats (sku, last_book_date)
  SELECT u.sku, MAX(DATE(e.event_ts)) AS last_book_date
  FROM tmp_ss2_sku_u u
  LEFT JOIN ss2_inv_event e ON e.sku = u.sku
   AND e.event_type IN ('PO_CREATE','PO_UPDATE','RECEIVE')
   AND e.event_ts < v_asof_next
  GROUP BY u.sku;

  -- 6) Upsert final
  DELETE FROM ss2_sku_features_12m WHERE asof_date = p_asof;

  INSERT INTO ss2_sku_features_12m (
    asof_date, sku,
    months_calendar, months_active,
    demand_mean_m, demand_std_m,
    total_units_12m, events_12m,
    p_event, q_mean_event, q_sd_event,
    pct_zero_months,
    last_ship_date, last_book_date,
    created_at
  )
  SELECT
    p_asof,
    u.sku,
    12,
    SUM(CASE WHEN mu.units_m > 0 THEN 1 ELSE 0 END),
    CAST(AVG(mu.units_m) AS DECIMAL(12,4)),
    CAST(IFNULL(STDDEV_SAMP(mu.units_m), 0) AS DECIMAL(12,4)),
    IFNULL(ss.total_units_12m, 0),
    IFNULL(ss.events_12m, 0),
    CAST(IFNULL(ss.events_12m, 0) / 12.0 AS DECIMAL(12,6)),
    IFNULL(ss.q_mean_event, 0),
    IFNULL(ss.q_sd_event, 0),
    CAST(SUM(CASE WHEN mu.units_m = 0 THEN 1 ELSE 0 END) / 12.0 AS DECIMAL(12,6)),
    ss.last_ship_date,
    bs.last_book_date,
    NOW()
  FROM tmp_ss2_sku_u u
  JOIN tmp_ss2_sku_m_units mu ON mu.sku = u.sku
  LEFT JOIN tmp_ss2_ship_stats ss ON ss.sku = u.sku
  LEFT JOIN tmp_ss2_book_stats bs ON bs.sku = u.sku
  GROUP BY u.sku;

END;;

DELIMITER ;
