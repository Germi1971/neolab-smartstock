-- =============================================================================
-- Migración: Añadir cap_cliente_dominante y cap_vencimiento a parametros_sku
-- =============================================================================
-- Requerido para Policy Engine (caps por cliente dominante y vencimiento).
-- Ejecutar si parametros_sku no tiene estas columnas.
--
-- MySQL 5.5: usar procedimiento para evitar error si la columna ya existe.
-- Alternativa manual: ejecutar cada ALTER por separado; ignorar error si existe.
-- =============================================================================

-- Opción 1: ALTER directo (falla si la columna ya existe)
ALTER TABLE parametros_sku ADD COLUMN cap_cliente_dominante INT NULL COMMENT 'Cap por share cliente dominante';
ALTER TABLE parametros_sku ADD COLUMN cap_vencimiento INT NULL COMMENT 'Cap por vencimiento';

-- Si falla con "Duplicate column name", las columnas ya existen. Ignorar.
