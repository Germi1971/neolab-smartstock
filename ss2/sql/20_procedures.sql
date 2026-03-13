-- sql/20_procedures.sql
-- SS2 core stored procedures (MySQL 5.5 compatible)

DELIMITER ;;

DROP PROCEDURE IF EXISTS `sp_ss2_sku_features_12m_refresh`;;
/*!50003 CREATE DEFINER=`neolab`@`%` PROCEDURE `sp_ss2_sku_features_12m_refresh`(IN p_asof DATE)
BEGIN
  DECLARE v_month0 DATE;
  DECLARE v_asof_next DATE;

  IF p_asof IS NULL THEN
    SET p_asof = CURDATE();
  END IF;

  -- Primer día del mes de asof
  SET v_month0 = DATE_SUB(p_asof, INTERVAL (DAYOFMONTH(p_asof)-1) DAY);
  -- Límite exclusivo para recortar mes actual (asof inclusive)
  SET v_asof_next = DATE_ADD(p_asof, INTERVAL 1 DAY);

  -- 1) meses (12 filas): month_start / month_end
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

  -- 2) Universo SKUs activos
  DROP TEMPORARY TABLE IF EXISTS tmp_ss2_sku_u;
  CREATE TEMPORARY TABLE tmp_ss2_sku_u (
    sku VARCHAR(50) NOT NULL,
    PRIMARY KEY (sku)
  ) ENGINE=MEMORY;

  INSERT IGNORE INTO tmp_ss2_sku_u (sku)
  SELECT p.sku
  FROM ss2_v_policy_effective p
  WHERE p.is_active = 1;

  -- 3) Unidades por mes (12 valores por SKU) usando qty en SHIP
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
    IFNULL(SUM(e.qty), 0) AS units_m
  FROM tmp_ss2_sku_u u
  JOIN tmp_ss2_m12 m
  LEFT JOIN ss2_inv_event e
    ON e.sku = u.sku
   AND e.event_type = 'SHIP'
   AND e.event_ts >= m.month_start
   AND e.event_ts <  LEAST(m.month_end, v_asof_next)  -- recorta mes actual a asof
  GROUP BY u.sku, m.m;

  -- 4) Stats de eventos SHIP (eventos y sd por evento) en la ventana completa
  DROP TEMPORARY TABLE IF EXISTS tmp_ss2_ship_stats;
  CREATE TEMPORARY TABLE tmp_ss2_ship_stats (
    sku VARCHAR(50) NOT NULL,
    events_12m INT NOT NULL,
    q_sd_event DECIMAL(12,4) NOT NULL,
    last_ship_date DATE NULL,
    PRIMARY KEY (sku)
  ) ENGINE=MEMORY;

  INSERT INTO tmp_ss2_ship_stats (sku, events_12m, q_sd_event, last_ship_date)
  SELECT
    u.sku,
    IFNULL(COUNT(e.event_id), 0) AS events_12m,
    IFNULL(STDDEV_SAMP(e.qty), 0.0000) AS q_sd_event,
    MAX(DATE(e.event_ts)) AS last_ship_date
  FROM tmp_ss2_sku_u u
  LEFT JOIN ss2_inv_event e
    ON e.sku = u.sku
   AND e.event_type = 'SHIP'
   AND e.event_ts >= DATE_SUB(v_month0, INTERVAL 11 MONTH)
   AND e.event_ts < v_asof_next
  GROUP BY u.sku;

  -- 5) last_book_date (PO/RECEIVE) opcional
  DROP TEMPORARY TABLE IF EXISTS tmp_ss2_book_stats;
  CREATE TEMPORARY TABLE tmp_ss2_book_stats (
    sku VARCHAR(50) NOT NULL,
    last_book_date DATE NULL,
    PRIMARY KEY (sku)
  ) ENGINE=MEMORY;

  INSERT INTO tmp_ss2_book_stats (sku, last_book_date)
  SELECT
    u.sku,
    MAX(DATE(e.event_ts)) AS last_book_date
  FROM tmp_ss2_sku_u u
  LEFT JOIN ss2_inv_event e
    ON e.sku = u.sku
   AND e.event_type IN ('PO_CREATE','PO_UPDATE','RECEIVE')
   AND e.event_ts < v_asof_next
  GROUP BY u.sku;

  -- 6) Upsert final a ss2_sku_features_12m
  -- (borramos solo ese asof para mantener histórico si querés)
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
    p_asof AS asof_date,
    u.sku,

    12 AS months_calendar,
    SUM(CASE WHEN mu.units_m > 0 THEN 1 ELSE 0 END) AS months_active,

    CAST(AVG(mu.units_m) AS DECIMAL(12,4)) AS demand_mean_m,
    CAST(IFNULL(STDDEV_SAMP(mu.units_m), 0) AS DECIMAL(12,4)) AS demand_std_m,

    SUM(mu.units_m) AS total_units_12m,
    ss.events_12m AS events_12m,

    CAST(ss.events_12m / 12.0 AS DECIMAL(12,6)) AS p_event,

    CAST(
      CASE WHEN ss.events_12m > 0 THEN SUM(mu.units_m) / ss.events_12m ELSE 0 END
      AS DECIMAL(12,4)
    ) AS q_mean_event,

    ss.q_sd_event AS q_sd_event,

    CAST(SUM(CASE WHEN mu.units_m = 0 THEN 1 ELSE 0 END) / 12.0 AS DECIMAL(12,6)) AS pct_zero_months,

    ss.last_ship_date AS last_ship_date,
    bs.last_book_date AS last_book_date,

    NOW() AS created_at
  FROM tmp_ss2_sku_u u
  JOIN tmp_ss2_sku_m_units mu
    ON mu.sku = u.sku
  JOIN tmp_ss2_ship_stats ss
    ON ss.sku = u.sku
  LEFT JOIN tmp_ss2_book_stats bs
    ON bs.sku = u.sku
  GROUP BY u.sku;

END */;;


DROP PROCEDURE IF EXISTS `sp_ss2_daily_refresh`;;
/*!50003 CREATE DEFINER=`neolab`@`%` PROCEDURE `sp_ss2_daily_refresh`(IN p_asof_date DATE, IN p_location_id INT)
BEGIN
  -- 1) Refrescar clases (incluye nuevos SKUs)
  CALL sp_ss2_sku_class_refresh(p_asof_date);

  -- 2) Refrescar snapshot policy MC (usa cap por clase)
  CALL sp_ss2_mc_policy_refresh(p_asof_date, p_location_id);
END */;;

DELIMITER ;