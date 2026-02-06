"""
SQLAlchemy Models for NeoLab SmartStock
"""
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy import (
    Column, String, Integer, DateTime, Date, Boolean, Numeric, Text,
    ForeignKey, Enum, JSON, Index, func
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


# ============================================
# FASE 1: Core Models
# ============================================

class SKUMaster(Base):
    """Master SKU table."""
    __tablename__ = "sku_master"
    
    sku = Column(String(50), primary_key=True)
    descripcion = Column(String(255), nullable=False)
    activo = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    parameters = relationship("SKUParameters", back_populates="sku_master", uselist=False)
    stock = relationship("Stock", back_populates="sku_master", uselist=False)


class SKUParameters(Base):
    """SKU-level parameters for replenishment."""
    __tablename__ = "sku_parameters"
    
    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)
    stock_objetivo = Column(Integer, nullable=False, default=0)
    stock_seguridad = Column(Integer, nullable=False, default=0)
    punto_reorden = Column(Integer, nullable=False, default=0)
    moq = Column(Integer, nullable=True)
    multiplo = Column(Integer, nullable=True)
    activo = Column(Boolean, default=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    updated_by = Column(String(100))
    
    # Relationships
    sku_master = relationship("SKUMaster", back_populates="parameters")


class Stock(Base):
    """Current stock position."""
    __tablename__ = "stock"
    
    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)
    stock_posicion = Column(Integer, nullable=False, default=0)
    stock_transito = Column(Integer, default=0)
    stock_comprometido = Column(Integer, default=0)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # Relationships
    sku_master = relationship("SKUMaster", back_populates="stock")


class MLPipelineRun(Base):
    """ML Pipeline execution tracking."""
    __tablename__ = "ml_run"
    
    run_id = Column(String(36), primary_key=True)
    started_at = Column(DateTime, default=func.now())
    finished_at = Column(DateTime, nullable=True)
    skus_procesados = Column(Integer, default=0)
    skus_exitosos = Column(Integer, default=0)
    skus_fallidos = Column(Integer, default=0)
    duracion_segundos = Column(Integer, nullable=True)
    triggered_by = Column(Enum("SCHEDULER", "MANUAL", "API", name="trigger_type"), default="SCHEDULER")
    error_log = Column(JSON, nullable=True)


class MLSuggestion(Base):
    """ML-generated purchase suggestions."""
    __tablename__ = "ml_suggestions"
    
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), primary_key=True)
    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)
    qty_sugerida = Column(Integer, nullable=False)
    qty_final = Column(Integer, nullable=True)
    estado = Column(Enum("PENDIENTE", "APROBADO", "RECHAZADO", name="suggestion_status"), default="PENDIENTE")
    modelo_seleccionado = Column(String(50), nullable=False)
    s_policy = Column(Integer, nullable=True)
    S_policy = Column(Integer, nullable=True)
    notas = Column(Text, nullable=True)
    aprobado_por = Column(String(100), nullable=True)
    fecha_aprobacion = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class OrderApproval(Base):
    """Purchase order approvals."""
    __tablename__ = "orders_approvals"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("sku_master.sku"), nullable=False)
    qty_sugerida_ml = Column(Integer, nullable=False)
    qty_final = Column(Integer, nullable=False)
    estado = Column(Enum("PENDIENTE", "APROBADO", "RECHAZADO", name="approval_status"), default="PENDIENTE")
    aprobado_por = Column(String(100), nullable=True)
    fecha_aprobacion = Column(DateTime, nullable=True)
    notas = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


class AuditLog(Base):
    """Audit log for data changes."""
    __tablename__ = "audit_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tabla = Column(String(50), nullable=False)
    registro_id = Column(String(100), nullable=False)
    accion = Column(Enum("INSERT", "UPDATE", "DELETE", name="audit_action"), nullable=False)
    usuario = Column(String(100), nullable=True)
    cambios = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())


class SystemConfig(Base):
    """System configuration."""
    __tablename__ = "system_config"
    
    config_key = Column(String(100), primary_key=True)
    config_value = Column(Text, nullable=False)
    config_type = Column(Enum("string", "int", "float", "bool", "json", name="config_type"), default="string")
    description = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    updated_by = Column(String(100), nullable=True)


# ============================================
# FASE 2: ML Advanced Models
# ============================================

class MLSKUFeatures(Base):
    """Computed ML features per SKU."""
    __tablename__ = "ml_sku_features"
    
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), primary_key=True)
    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)
    periodo_inicio = Column(Date, nullable=False)
    periodo_fin = Column(Date, nullable=False)
    
    # 12 month features
    dias_observados_12m = Column(Integer, default=0)
    eventos_12m = Column(Integer, default=0)
    unidades_12m = Column(Integer, default=0)
    meses_con_venta_12m = Column(Integer, default=0)
    pct_meses_con_venta_12m = Column(Numeric(5, 4), default=0)
    lambda_eventos_mes_12m = Column(Numeric(10, 6), default=0)
    mu_unidades_evento_12m = Column(Numeric(12, 4), default=0)
    cv_12m = Column(Numeric(10, 6), default=0)
    adi_12m = Column(Numeric(10, 6), default=0)
    squared_cv_12m = Column(Numeric(10, 6), default=0)
    
    # 24 month features
    dias_observados_24m = Column(Integer, default=0)
    eventos_24m = Column(Integer, default=0)
    unidades_24m = Column(Integer, default=0)
    cv_24m = Column(Numeric(10, 6), default=0)
    
    # 90 day features
    dias_observados_90d = Column(Integer, default=0)
    eventos_90d = Column(Integer, default=0)
    unidades_90d = Column(Integer, default=0)
    tendencia_90d = Column(Numeric(10, 6), default=0)
    
    # Additional features
    ultima_venta = Column(Date, nullable=True)
    dias_desde_ultima_venta = Column(Integer, default=0)


class MLModelRegistry(Base):
    """Registry of selected models per SKU."""
    __tablename__ = "ml_model_registry"
    
    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)
    modelo_actual = Column(String(50), nullable=False)
    modelo_anterior = Column(String(50), nullable=True)
    fecha_seleccion = Column(DateTime, default=func.now())
    run_id_seleccion = Column(String(36), ForeignKey("ml_run.run_id"))
    
    # Model performance metrics
    rmse = Column(Numeric(12, 4), nullable=True)
    mae = Column(Numeric(12, 4), nullable=True)
    bias = Column(Numeric(10, 6), nullable=True)
    service_level = Column(Numeric(5, 4), nullable=True)
    coverage_95 = Column(Numeric(5, 4), nullable=True)
    
    # Selection criteria
    score_error = Column(Numeric(8, 6), nullable=True)
    score_service = Column(Numeric(8, 6), nullable=True)
    score_stability = Column(Numeric(8, 6), nullable=True)
    score_complexity = Column(Numeric(8, 6), nullable=True)
    score_composite = Column(Numeric(8, 6), nullable=True)
    
    # Model parameters (JSON)
    model_params = Column(JSON, nullable=True)


class MLModelSwitchLog(Base):
    """Log of model switches per SKU."""
    __tablename__ = "ml_model_switch_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    sku = Column(String(50), ForeignKey("sku_master.sku"), nullable=False)
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), nullable=False)
    modelo_anterior = Column(String(50), nullable=False)
    modelo_nuevo = Column(String(50), nullable=False)
    razon_cambio = Column(Enum("PRIMER_MODELO", "MEJOR_SCORE", "DRIFT", "MANUAL", name="switch_reason"), nullable=False)
    score_anterior = Column(Numeric(8, 6), nullable=True)
    score_nuevo = Column(Numeric(8, 6), nullable=True)
    detalle = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())


class MLDriftLog(Base):
    """Log of drift detections."""
    __tablename__ = "ml_drift_log"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), nullable=False)
    sku = Column(String(50), ForeignKey("sku_master.sku"), nullable=False)
    drift_detected = Column(Boolean, default=False)
    cv_change_pct = Column(Numeric(10, 4), nullable=True)
    lambda_change_pct = Column(Numeric(10, 4), nullable=True)
    gap_ratio_change_pct = Column(Numeric(10, 4), nullable=True)
    cv_threshold = Column(Numeric(5, 4), default=0.5)
    lambda_threshold = Column(Numeric(5, 4), default=0.5)
    detalle = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=func.now())


# ============================================
# FASE 3: Scheduler & Observability Models
# ============================================

class MLRunError(Base):
    """Errors per SKU in ML runs with retry tracking."""
    __tablename__ = "ml_run_errors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), nullable=False)
    sku = Column(String(50), ForeignKey("sku_master.sku"), nullable=False)
    error_code = Column(String(50), nullable=False)
    error_message = Column(Text, nullable=True)
    error_detail = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime, default=func.now())
    resolved_at = Column(DateTime, nullable=True)


class SKULatestCache(Base):
    """Materialized cache of latest SKU data."""
    __tablename__ = "sku_cache_latest"
    
    sku = Column(String(50), ForeignKey("sku_master.sku"), primary_key=True)
    run_id = Column(String(36), ForeignKey("ml_run.run_id"), nullable=False)
    
    # Stock info
    stock_posicion = Column(Integer, default=0)
    stock_objetivo = Column(Integer, default=0)
    stock_seguridad = Column(Integer, default=0)
    
    # Suggestion
    qty_sugerida = Column(Integer, default=0)
    estado = Column(Enum("PENDIENTE", "APROBADO", "RECHAZADO", name="cache_status"), default="PENDIENTE")
    qty_final = Column(Integer, nullable=True)
    
    # ML info
    modelo_seleccionado = Column(String(50), nullable=True)
    s_policy = Column(Integer, nullable=True)
    S_policy = Column(Integer, nullable=True)
    score_composite = Column(Numeric(8, 6), nullable=True)
    
    # Features summary
    cv_12m = Column(Numeric(10, 6), nullable=True)
    lambda_eventos_mes_12m = Column(Numeric(10, 6), nullable=True)
    eventos_12m = Column(Integer, nullable=True)
    unidades_12m = Column(Integer, nullable=True)
    drift_detected = Column(Boolean, default=False)
    
    # Metadata
    computed_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)


class SchedulerLock(Base):
    """Distributed locks for scheduler."""
    __tablename__ = "scheduler_locks"
    
    lock_name = Column(String(100), primary_key=True)
    locked_by = Column(String(100), nullable=False)
    locked_at = Column(DateTime, default=func.now())
    expires_at = Column(DateTime, nullable=False)
    metadata = Column(JSON, nullable=True)


class SchedulerConfig(Base):
    """Scheduler configuration."""
    __tablename__ = "scheduler_config"
    
    config_key = Column(String(100), primary_key=True)
    config_value = Column(Text, nullable=False)
    config_type = Column(Enum("string", "int", "float", "bool", "json", name="scheduler_config_type"), default="string")
    description = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    updated_by = Column(String(100), nullable=True)


class SystemMetric(Base):
    """System metrics for observability."""
    __tablename__ = "system_metrics"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String(100), nullable=False)
    metric_value = Column(Numeric(18, 6), nullable=False)
    metric_type = Column(Enum("counter", "gauge", "histogram", name="metric_type"), default="gauge")
    labels = Column(JSON, nullable=True)
    recorded_at = Column(DateTime, default=func.now())


class AuditLogExtended(Base):
    """Extended audit log with more details."""
    __tablename__ = "audit_log_extended"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    tabla = Column(String(50), nullable=False)
    registro_id = Column(String(100), nullable=False)
    accion = Column(Enum("INSERT", "UPDATE", "DELETE", "EXECUTE", name="extended_audit_action"), nullable=False)
    usuario = Column(String(100), nullable=True)
    cambios = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    execution_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, default=func.now())
