-- =============================================================================
-- Migración: Añadir demand_p97 a ss2_demand_cache (tablas existentes)
-- =============================================================================
-- Requerido para Policy Engine CRITICO (percentil P97).
-- Ejecutar si ss2_demand_cache ya existe sin la columna demand_p97.
--
-- Si la tabla se creó con el DDL actualizado, no es necesario.
-- =============================================================================

ALTER TABLE ss2_demand_cache ADD COLUMN demand_p97 DOUBLE NULL AFTER demand_p95;

-- Si falla con "Duplicate column name", la columna ya existe. Ignorar.
