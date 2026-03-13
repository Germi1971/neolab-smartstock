"""
SQLAlchemy Models for NeoLab SmartStock
(MySQL 5.5 compatible)
"""
from sqlalchemy import (
    Column, String, Integer, DateTime, Date, Boolean, Numeric, Text,
    ForeignKey, Enum as SAEnum, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ============================================
# FASE 1: Core Models
# ============================================

class SKUMaster(Base):
    __tablename__ = "sku_master"

    sku = Column(String(50), primary_key=True)
    descripcion = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True)

    # En tu DDL: created_at DATETIME NOT NULL (sin default automático)
    # En SQLAlchemy: default=func.now() está OK para inserts desde app
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    parameters = relationship("SKUParameters", back_populates="sku_master", uselist=False)
    stock = relationship("Stock", back_populates="sku_master", uselist=False)


class SKUParameters(Base):
    __tablename__ = "sku_parameters"

    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)

    stock_objetivo = Column(Integer, nullable=False, default=0)
    stock_seguridad = Column(Integer, nullable=False, default=0)
    punto_reorden = Column(Integer, nullable=False, default=0)
    moq = Column(Integer, nullable=True)
    multiplo = Column(Integer, nullable=True)
    activo = Column(Boolean, default=True)

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(String(100), nullable=True)

    sku_master = relationship("SKUMaster", back_populates="parameters")


class Stock(Base):
    __tablename__ = "stock"

    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)
    stock_posicion = Column(Integer, nullable=False, default=0)
    stock_transito = Column(Integer, default=0)
    stock_comprometido = Column(Integer, default=0)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

    sku_master = relationship("SKUMaster", back_populates="stock")


# --------- IMPORTANTÍSIMO: este es el ÚNICO modelo para ml_runs ----------
class MLRun(Base):
    __tablename__ = "ml_runs"

    run_id = Column(String(64), primary_key=True)

    started_at = Column(DateTime, default=func.now(), nullable=False)
    finished_at = Column(DateTime, nullable=True)

    skus_procesados = Column(Integer, default=0, nullable=False)
    skus_exitosos = Column(Integer, default=0, nullable=False)
    skus_fallidos = Column(Integer, default=0, nullable=False)

    duracion_segundos = Column(Integer, nullable=True)

    triggered_by = Column(String(16), default='MANUAL', nullable=False)
    status = Column(String(16), default='PENDING', nullable=False)

    # MySQL 5.5: evitar JSON nativo -> Text (guardás JSON serializado)
    error_log = Column(Text, nullable=True)


class MLSuggestion(Base):
    __tablename__ = "ml_suggestions"

    run_id = Column(String(64), ForeignKey("ml_runs.run_id"), primary_key=True)
    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)

    qty_sugerida = Column(Integer, nullable=False)
    qty_final = Column(Integer, nullable=True)

    estado = Column(String(20), default='PENDIENTE', nullable=False)

    modelo_seleccionado = Column(String(50), nullable=False)

    # Naming consistency (case-insensitive distinct names)
    policy_s_lower = Column(Integer, nullable=True)
    policy_s_upper = Column(Integer, nullable=True)

    notas = Column(Text, nullable=True)
    aprobado_por = Column(String(100), nullable=True)
    fecha_aprobacion = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class OrderApproval(Base):
    __tablename__ = "orders_approvals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("sku_master.sku"), nullable=False)

    qty_sugerida_ml = Column(Integer, nullable=False)
    qty_final = Column(Integer, nullable=False)

    estado = Column(
        SAEnum("PENDIENTE", "APROBADO", "RECHAZADO", name="approval_status"),
        default="PENDIENTE",
        nullable=False,
    )

    aprobado_por = Column(String(100), nullable=True)
    fecha_aprobacion = Column(DateTime, nullable=True)
    notas = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tabla = Column(String(50), nullable=False)
    registro_id = Column(String(100), nullable=False)
    accion = Column(SAEnum("INSERT", "UPDATE", "DELETE", name="audit_action"), nullable=False)
    usuario = Column(String(100), nullable=True)

    # MySQL 5.5: Text (json serializado)
    cambios = Column(Text, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)


class SystemConfig(Base):
    __tablename__ = "system_config"

    config_key = Column(String(100), primary_key=True)
    config_value = Column(Text, nullable=False)
    config_type = Column(
        SAEnum("string", "int", "float", "bool", "json", name="config_type"),
        default="string",
        nullable=False,
    )
    description = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(String(100), nullable=True)


# ============================================
# FASE 2: ML Advanced Models
# ============================================

class MLSKUFeatures(Base):
    __tablename__ = "ml_sku_features"

    run_id = Column(String(36), ForeignKey("ml_run.run_id"), primary_key=True)
    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)

    periodo_inicio = Column(Date, nullable=False)
    periodo_fin = Column(Date, nullable=False)

    dias_observados_12m = Column(Integer, default=0, nullable=False)
    eventos_12m = Column(Integer, default=0, nullable=False)
    unidades_12m = Column(Integer, default=0, nullable=False)
    meses_con_venta_12m = Column(Integer, default=0, nullable=False)
    pct_meses_con_venta_12m = Column(Numeric(5, 4), default=0, nullable=False)
    lambda_eventos_mes_12m = Column(Numeric(10, 6), default=0, nullable=False)
    mu_unidades_evento_12m = Column(Numeric(12, 4), default=0, nullable=False)
    cv_12m = Column(Numeric(10, 6), default=0, nullable=False)
    adi_12m = Column(Numeric(10, 6), default=0, nullable=False)
    squared_cv_12m = Column(Numeric(10, 6), default=0, nullable=False)

    dias_observados_24m = Column(Integer, default=0, nullable=False)
    eventos_24m = Column(Integer, default=0, nullable=False)
    unidades_24m = Column(Integer, default=0, nullable=False)
    cv_24m = Column(Numeric(10, 6), default=0, nullable=False)

    dias_observados_90d = Column(Integer, default=0, nullable=False)
    eventos_90d = Column(Integer, default=0, nullable=False)
    unidades_90d = Column(Integer, default=0, nullable=False)
    tendencia_90d = Column(Numeric(10, 6), default=0, nullable=False)

    ultima_venta = Column(Date, nullable=True)
    dias_desde_ultima_venta = Column(Integer, default=0, nullable=False)


class MLModelRegistry(Base):
    __tablename__ = "ml_model_registry"

    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)

    modelo_actual = Column(String(50), nullable=False)
    modelo_anterior = Column(String(50), nullable=True)

    fecha_seleccion = Column(DateTime, default=func.now(), nullable=False)
    run_id_seleccion = Column(String(64), ForeignKey("ml_runs.run_id"), nullable=True)

    rmse = Column(Numeric(12, 4), nullable=True)
    mae = Column(Numeric(12, 4), nullable=True)
    bias = Column(Numeric(10, 6), nullable=True)
    service_level = Column(Numeric(5, 4), nullable=True)
    coverage_95 = Column(Numeric(5, 4), nullable=True)

    score_error = Column(Numeric(8, 6), nullable=True)
    score_service = Column(Numeric(8, 6), nullable=True)
    score_stability = Column(Numeric(8, 6), nullable=True)
    score_complexity = Column(Numeric(8, 6), nullable=True)
    score_composite = Column(Numeric(8, 6), nullable=True)

    # MySQL 5.5: Text (json serializado)
    model_params = Column(Text, nullable=True)


class MLModelSwitchLog(Base):
    __tablename__ = "ml_model_switch_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("sku_master.sku"), nullable=False)
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), nullable=False)

    modelo_anterior = Column(String(50), nullable=False)
    modelo_nuevo = Column(String(50), nullable=False)

    razon_cambio = Column(
        SAEnum("PRIMER_MODELO", "MEJOR_SCORE", "DRIFT", "MANUAL", name="switch_reason"),
        nullable=False,
    )

    score_anterior = Column(Numeric(8, 6), nullable=True)
    score_nuevo = Column(Numeric(8, 6), nullable=True)

    detalle = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class MLDriftLog(Base):
    __tablename__ = "ml_drift_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), nullable=False)
    sku = Column(String(50), ForeignKey("sku_master.sku"), nullable=False)

    drift_detected = Column(Boolean, default=False, nullable=False)

    cv_change_pct = Column(Numeric(10, 4), nullable=True)
    lambda_change_pct = Column(Numeric(10, 4), nullable=True)
    gap_ratio_change_pct = Column(Numeric(10, 4), nullable=True)

    cv_threshold = Column(Numeric(5, 4), default=0.5, nullable=False)
    lambda_threshold = Column(Numeric(5, 4), default=0.5, nullable=False)

    detalle = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)


# ============================================
# FASE 3: Scheduler & Observability Models
# ============================================

class MLRunError(Base):
    __tablename__ = "ml_run_errors"

    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), nullable=False)
    sku = Column(String(50), ForeignKey("sku_master.sku"), nullable=False)

    error_code = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)
    error_detail = Column(Text, nullable=True)

    retry_count = Column(Integer, default=0, nullable=False)
    max_retries = Column(Integer, default=3, nullable=False)

    created_at = Column(DateTime, default=func.now(), nullable=False)
    resolved_at = Column(DateTime, nullable=True)


class SKULatestCache(Base):
    __tablename__ = "sku_cache_latest"

    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), nullable=False)

    stock_posicion = Column(Integer, default=0, nullable=False)
    stock_objetivo = Column(Integer, default=0, nullable=False)
    stock_seguridad = Column(Integer, default=0, nullable=False)

    qty_sugerida = Column(Integer, default=0, nullable=False)
    estado = Column(SAEnum("PENDIENTE", "APROBADO", "RECHAZADO", name="cache_status"), default="PENDIENTE", nullable=False)
    qty_final = Column(Integer, nullable=True)

    modelo_seleccionado = Column(String(50), nullable=True)
    policy_s_lower = Column(Integer, nullable=True)
    policy_s_upper = Column(Integer, nullable=True)

    score_composite = Column(Numeric(8, 6), nullable=True)

    cv_12m = Column(Numeric(10, 6), nullable=True)
    lambda_eventos_mes_12m = Column(Numeric(10, 6), nullable=True)
    eventos_12m = Column(Integer, nullable=True)
    unidades_12m = Column(Integer, nullable=True)

    drift_detected = Column(Boolean, default=False, nullable=False)

    computed_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)


class SchedulerLock(Base):
    __tablename__ = "scheduler_locks"

    lock_name = Column(String(100), primary_key=True)
    locked_by = Column(String(100), nullable=False)
    locked_at = Column(DateTime, default=func.now(), nullable=False)
    expires_at = Column(DateTime, nullable=False)

    # atributo python seguro, columna sigue siendo metadata
    metadata_json = Column("metadata", Text, nullable=True)


class SchedulerConfig(Base):
    __tablename__ = "scheduler_config"

    config_key = Column(String(100), primary_key=True)
    config_value = Column(Text, nullable=False)
    config_type = Column(
        SAEnum("string", "int", "float", "bool", "json", name="scheduler_config_type"),
        default="string",
        nullable=False,
    )
    description = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    updated_by = Column(String(100), nullable=True)


class SystemMetric(Base):
    __tablename__ = "system_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Numeric(18, 6), nullable=False)
    metric_type = Column(SAEnum("counter", "gauge", "histogram", name="metric_type"), default="gauge", nullable=False)

    labels = Column(Text, nullable=True)
    recorded_at = Column(DateTime, default=func.now(), nullable=False)


class AuditLogExtended(Base):
    __tablename__ = "audit_log_extended"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tabla = Column(String(50), nullable=False)
    registro_id = Column(String(100), nullable=False)
    accion = Column(SAEnum("INSERT", "UPDATE", "DELETE", "EXECUTE", name="extended_audit_action"), nullable=False)

    usuario = Column(String(100), nullable=True)
    cambios = Column(Text, nullable=True)

    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    execution_time_ms = Column(Integer, nullable=True)

    created_at = Column(DateTime, default=func.now(), nullable=False)
