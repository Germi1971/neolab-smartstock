-- Chequeos mínimos para que SS2 funcione
SELECT 'MySQL version' AS k, VERSION() AS v;

-- Tablas que deben existir (si faltan, algo no se cargó)
SELECT 'tabla1' AS required_table;
SELECT COUNT(*) AS exists_tabla1
FROM information_schema.tables
WHERE table_schema = DATABASE() AND table_name = 'tabla1';

-- SP obligatorios
SELECT ROUTINE_NAME
FROM information_schema.routines
WHERE routine_schema = DATABASE()
  AND routine_type = 'PROCEDURE'
  AND routine_name IN ('sp_ss2_sku_features_12m_refresh','sp_ss2_daily_refresh');