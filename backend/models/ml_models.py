"""
Compat layer (alias) para imports viejos.

El proyecto referencia `backend.models.ml_models`, pero los modelos reales están en
`backend.models.models`. Este archivo evita tocar muchos imports.
"""

from backend.models.models import (
    # Core / runs
    MLRun,

    # Cache materializado
    SKULatestCache,

    # Scheduler / config / observabilidad
    SchedulerLock,
    SchedulerConfig,
    SystemMetric,
    AuditLogExtended,

    # Errores por SKU
    MLRunError,
)

__all__ = [
    "MLRun",
    "SKULatestCache",
    "SchedulerLock",
    "SchedulerConfig",
    "SystemMetric",
    "AuditLogExtended",
    "MLRunError",
]
