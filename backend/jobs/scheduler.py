"""
Scheduler Module - APScheduler-based job scheduling with MySQL locks.
"""
import asyncio
import json
import uuid
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, JobExecutionEvent

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from backend.db.database import async_session_maker
from backend.models.models import SchedulerLock, SchedulerConfig, SystemMetric, AuditLogExtended

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class LockAcquisitionError(Exception):
    """Raised when lock acquisition fails."""
    pass


class SchedulerLockManager:
    """MySQL-based distributed lock manager for scheduler."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def acquire_lock(
        self,
        lock_name: str,
        locked_by: str,
        timeout_seconds: int = 300
    ) -> bool:
        """Try to acquire a distributed lock."""
        expires_at = datetime.utcnow() + timedelta(seconds=timeout_seconds)

        # Clean expired locks first
        await self.session.execute(
            text("DELETE FROM scheduler_locks WHERE expires_at < NOW()")
        )
        await self.session.commit()

        # Try to insert new lock (PK on lock_name will enforce exclusivity)
        try:
            lock = SchedulerLock(
                lock_name=lock_name,
                locked_by=locked_by,
                expires_at=expires_at,

                # ❗ NO usar atributo "metadata" (reservado en SQLAlchemy Declarative)
                # Guardamos JSON como string (MySQL 5.5: LONGTEXT)
                metadata_json=json.dumps({"acquired_at": datetime.utcnow().isoformat()})
            )
            self.session.add(lock)
            await self.session.commit()
            logger.info(f"Lock '{lock_name}' acquired by {locked_by}")
            return True
        except Exception as e:
            await self.session.rollback()
            logger.debug(f"Could not acquire lock '{lock_name}': {e}")
            return False

    async def release_lock(self, lock_name: str, locked_by: str) -> bool:
        """Release a distributed lock."""
        result = await self.session.execute(
            text("""
                DELETE FROM scheduler_locks
                WHERE lock_name = :lock_name AND locked_by = :locked_by
            """),
            {"lock_name": lock_name, "locked_by": locked_by}
        )
        await self.session.commit()

        if result.rowcount and result.rowcount > 0:
            logger.info(f"Lock '{lock_name}' released by {locked_by}")
            return True
        return False

    async def extend_lock(
        self,
        lock_name: str,
        locked_by: str,
        additional_seconds: int = 300
    ) -> bool:
        """Extend lock expiration."""
        new_expires = datetime.utcnow() + timedelta(seconds=additional_seconds)

        result = await self.session.execute(
            text("""
                UPDATE scheduler_locks
                SET expires_at = :expires_at
                WHERE lock_name = :lock_name AND locked_by = :locked_by
            """),
            {
                "lock_name": lock_name,
                "locked_by": locked_by,
                "expires_at": new_expires
            }
        )
        await self.session.commit()

        return bool(result.rowcount and result.rowcount > 0)

    @asynccontextmanager
    async def lock_context(
        self,
        lock_name: str,
        locked_by: str,
        timeout_seconds: int = 300
    ):
        """Context manager for lock acquisition/release."""
        acquired = await self.acquire_lock(lock_name, locked_by, timeout_seconds)
        if not acquired:
            raise LockAcquisitionError(f"Could not acquire lock '{lock_name}'")

        try:
            yield self
        finally:
            await self.release_lock(lock_name, locked_by)


class RetryableJob:
    """Wrapper for jobs with retry logic."""

    def __init__(
        self,
        func: Callable,
        max_retries: int = 3,
        retry_delay_seconds: int = 60,
        retry_exceptions: tuple = (Exception,)
    ):
        self.func = func
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self.retry_exceptions = retry_exceptions

    async def execute(self, *args, **kwargs) -> Any:
        """Execute with retries."""
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return await self.func(*args, **kwargs)
            except self.retry_exceptions as e:
                last_exception = e
                if attempt < self.max_retries:
                    logger.warning(
                        f"Job failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying in {self.retry_delay_seconds}s..."
                    )
                    await asyncio.sleep(self.retry_delay_seconds)
                else:
                    logger.error(f"Job failed after {self.max_retries + 1} attempts: {e}")

        raise last_exception


class MetricsCollector:
    """Collect and store system metrics."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def record_metric(
        self,
        name: str,
        value: float,
        metric_type: str = "gauge",
        labels: Optional[dict] = None
    ):
        """Record a metric."""
        metric = SystemMetric(
            metric_name=name,
            metric_value=value,
            metric_type=metric_type,
            labels_json=json.dumps(labels or {})  # MySQL 5.5 LONGTEXT (si tu modelo usa labels_json)
        )
        self.session.add(metric)
        await self.session.commit()

    async def get_metrics(
        self,
        name: Optional[str] = None,
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> list:
        """Get metrics with filtering."""
        query = select(SystemMetric)

        if name:
            query = query.where(SystemMetric.metric_name == name)
        if since:
            query = query.where(SystemMetric.recorded_at >= since)

        query = query.order_by(SystemMetric.recorded_at.desc()).limit(limit)

        result = await self.session.execute(query)
        return result.scalars().all()


class SmartStockScheduler:
    """Main scheduler for SmartStock ML pipeline."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self._instance_id = str(uuid.uuid4())[:8]

    def _on_job_event(self, event: JobExecutionEvent):
        """
        Listener único compatible APScheduler 3.x:
        - En errores: event.exception != None
        - En OK: event.exception == None
        """
        if getattr(event, "exception", None):
            logger.error(f"Job {event.job_id} failed: {event.exception}")
            tb = getattr(event, "traceback", None)
            if tb:
                logger.error(tb)
        else:
            logger.info(f"Job {event.job_id} executed successfully")

    async def start(self):
        """Start the scheduler."""
        # Listener único (executed + error)
        self.scheduler.add_listener(
            self._on_job_event,
            EVENT_JOB_EXECUTED | EVENT_JOB_ERROR
        )

        self.scheduler.start()
        logger.info(f"Scheduler started (instance: {self._instance_id})")

    async def shutdown(self):
        """Shutdown the scheduler."""
        try:
            self.scheduler.shutdown(wait=False)
        except Exception:
            # si ya está apagado, no romper
            pass
        logger.info("Scheduler shutdown")

    async def schedule_ml_pipeline(
        self,
        cron_expression: str = "0 2 * * *",  # Daily at 2 AM
        job_id: str = "ml_pipeline_daily"
    ):
        """Schedule the ML pipeline job."""
        from backend.jobs.ml_pipeline_job import run_ml_pipeline_job

        # Remove existing job if exists
        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

        self.scheduler.add_job(
            func=run_ml_pipeline_job,
            trigger=CronTrigger.from_crontab(cron_expression),
            id=job_id,
            name="ML Pipeline Daily Run",
            replace_existing=True,
            misfire_grace_time=3600,  # 1 hour grace time
            coalesce=True,            # Coalesce missed jobs
        )

        logger.info(f"Scheduled ML pipeline with cron: {cron_expression}")

    async def schedule_cache_refresh(
        self,
        interval_minutes: int = 30,
        job_id: str = "cache_refresh"
    ):
        """Schedule cache refresh job."""
        from backend.jobs.cache_refresh_job import refresh_materialized_cache

        try:
            self.scheduler.remove_job(job_id)
        except Exception:
            pass

        self.scheduler.add_job(
            func=refresh_materialized_cache,
            trigger="interval",
            minutes=interval_minutes,
            id=job_id,
            name="Cache Refresh",
            replace_existing=True,
        )

        logger.info(f"Scheduled cache refresh every {interval_minutes} minutes")

    async def run_job_now(self, job_id: str):
        """Trigger a job to run immediately."""
        job = self.scheduler.get_job(job_id)
        if job:
            job.modify(next_run_time=datetime.now())
            logger.info(f"Triggered job {job_id} to run now")
        else:
            raise ValueError(f"Job {job_id} not found")

    def get_jobs(self):
        """Get all scheduled jobs."""
        return self.scheduler.get_jobs()


# Global scheduler instance
_scheduler_instance: Optional[SmartStockScheduler] = None


async def get_scheduler() -> SmartStockScheduler:
    """Get or create scheduler singleton."""
    global _scheduler_instance
    if _scheduler_instance is None:
        _scheduler_instance = SmartStockScheduler()
    return _scheduler_instance


async def init_scheduler():
    """Initialize and start the scheduler."""
    scheduler = await get_scheduler()
    await scheduler.start()

    # Schedule default jobs from config
    async with async_session_maker() as session:
        result = await session.execute(
            select(SchedulerConfig).where(SchedulerConfig.config_key == "ml_pipeline.cron")
        )
        config = result.scalar_one_or_none()
        cron = config.config_value if config else "0 2 * * *"

        # cache refresh config opcional
        result2 = await session.execute(
            select(SchedulerConfig).where(SchedulerConfig.config_key == "cache.refresh_minutes")
        )
        cfg2 = result2.scalar_one_or_none()
        refresh_minutes = int(cfg2.config_value) if (cfg2 and str(cfg2.config_value).isdigit()) else 30

    await scheduler.schedule_ml_pipeline(cron)
    await scheduler.schedule_cache_refresh(refresh_minutes)


async def shutdown_scheduler():
    """Shutdown the scheduler."""
    global _scheduler_instance
    if _scheduler_instance:
        await _scheduler_instance.shutdown()
        _scheduler_instance = None
