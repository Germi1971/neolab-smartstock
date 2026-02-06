"""
ML Pipeline Job - Executable job for the scheduler with retries and error handling.
"""
import asyncio
import traceback
from datetime import datetime, timedelta
from typing import List, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select

from backend.db.database import async_session_maker
from backend.jobs.scheduler import SchedulerLockManager, RetryableJob
from backend.ml_engine.pipeline import MLPipeline
from backend.utils.logger import get_logger
from backend.models.ml_models import MLRunError, SchedulerConfig

logger = get_logger(__name__)


class MLPipelineJob:
    """ML Pipeline job with per-SKU retry logic."""
    
    def __init__(self, session: AsyncSession, run_id: str):
        self.session = session
        self.run_id = run_id
        self.skus_procesados = 0
        self.skus_exitosos = 0
        self.skus_fallidos = 0
        self.errors: List[Dict[str, Any]] = []
        
        # Load config
        self.max_retries = 3
        self.retry_delay = 60
        self.batch_size = 100
    
    async def load_config(self):
        """Load scheduler configuration."""
        configs = await self.session.execute(
            select(SchedulerConfig).where(
                SchedulerConfig.config_key.in_([
                    "ml_pipeline.max_retries",
                    "ml_pipeline.retry_delay_seconds",
                    "ml_pipeline.batch_size"
                ])
            )
        )
        for config in configs.scalars():
            if config.config_key == "ml_pipeline.max_retries":
                self.max_retries = int(config.config_value)
            elif config.config_key == "ml_pipeline.retry_delay_seconds":
                self.retry_delay = int(config.config_value)
            elif config.config_key == "ml_pipeline.batch_size":
                self.batch_size = int(config.config_value)
    
    async def process_sku_with_retry(
        self, 
        pipeline: MLPipeline, 
        sku: str
    ) -> bool:
        """Process a single SKU with retry logic."""
        for attempt in range(self.max_retries + 1):
            try:
                await pipeline.process_single_sku(sku)
                self.skus_exitosos += 1
                return True
            except Exception as e:
                error_detail = {
                    "sku": sku,
                    "attempt": attempt + 1,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                }
                
                if attempt < self.max_retries:
                    logger.warning(
                        f"SKU {sku} failed (attempt {attempt + 1}/{self.max_retries + 1}): {e}. "
                        f"Retrying..."
                    )
                    await asyncio.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    logger.error(f"SKU {sku} failed after {self.max_retries + 1} attempts")
                    await self.log_error(sku, "MAX_RETRIES_EXCEEDED", str(e), error_detail)
                    self.skus_fallidos += 1
                    self.errors.append(error_detail)
        
        return False
    
    async def log_error(
        self, 
        sku: str, 
        error_code: str, 
        error_message: str,
        error_detail: Dict[str, Any]
    ):
        """Log error to ml_run_errors table."""
        error = MLRunError(
            run_id=self.run_id,
            sku=sku,
            error_code=error_code,
            error_message=error_message,
            error_detail=error_detail,
            retry_count=self.max_retries,
            max_retries=self.max_retries
        )
        self.session.add(error)
        await self.session.commit()
    
    async def run(self) -> Dict[str, Any]:
        """Run the ML pipeline job."""
        await self.load_config()
        
        # Get list of active SKUs
        result = await self.session.execute(
            text("""
                SELECT sku FROM sku_master 
                WHERE activo = TRUE 
                ORDER BY sku
            """)
        )
        skus = [row[0] for row in result.fetchall()]
        
        total_skus = len(skus)
        logger.info(f"Starting ML pipeline for {total_skus} SKUs")
        
        pipeline = MLPipeline(self.session, self.run_id)
        
        # Process in batches
        for i in range(0, total_skus, self.batch_size):
            batch = skus[i:i + self.batch_size]
            logger.info(f"Processing batch {i // self.batch_size + 1}: {len(batch)} SKUs")
            
            for sku in batch:
                self.skus_procesados += 1
                await self.process_sku_with_retry(pipeline, sku)
            
            # Commit batch progress
            await self.session.execute(
                text("""
                    UPDATE ml_run 
                    SET skus_procesados = :procesados,
                        skus_exitosos = :exitosos,
                        skus_fallidos = :fallidos
                    WHERE run_id = :run_id
                """),
                {
                    "run_id": self.run_id,
                    "procesados": self.skus_procesados,
                    "exitosos": self.skus_exitosos,
                    "fallidos": self.skus_fallidos
                }
            )
            await self.session.commit()
        
        # Finalize run
        await self.session.execute(
            text("""
                UPDATE ml_run 
                SET finished_at = NOW(),
                    duracion_segundos = TIMESTAMPDIFF(SECOND, started_at, NOW()),
                    error_log = :error_log
                WHERE run_id = :run_id
            """),
            {
                "run_id": self.run_id,
                "error_log": json.dumps(self.errors) if self.errors else None
            }
        )
        await self.session.commit()
        
        logger.info(
            f"ML pipeline completed. Processed: {self.skus_procesados}, "
            f"Success: {self.skus_exitosos}, Failed: {self.skus_fallidos}"
        )
        
        return {
            "run_id": self.run_id,
            "skus_procesados": self.skus_procesados,
            "skus_exitosos": self.skus_exitosos,
            "skus_fallidos": self.skus_fallidos,
            "errors": len(self.errors)
        }


async def run_ml_pipeline_job():
    """Entry point for scheduled ML pipeline job."""
    import uuid
    
    run_id = str(uuid.uuid4())
    instance_id = f"scheduler-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    async with async_session_maker() as session:
        lock_manager = SchedulerLockManager(session)
        
        # Try to acquire lock
        lock_acquired = await lock_manager.acquire_lock(
            "ml_pipeline", 
            instance_id,
            timeout_seconds=3600  # 1 hour timeout
        )
        
        if not lock_acquired:
            logger.warning("Another ML pipeline is already running. Skipping.")
            return {"status": "skipped", "reason": "lock_not_acquired"}
        
        try:
            # Create run record
            await session.execute(
                text("""
                    INSERT INTO ml_run (run_id, started_at, triggered_by, skus_procesados, skus_exitosos, skus_fallidos)
                    VALUES (:run_id, NOW(), 'SCHEDULER', 0, 0, 0)
                """),
                {"run_id": run_id}
            )
            await session.commit()
            
            # Run pipeline
            job = MLPipelineJob(session, run_id)
            result = await job.run()
            
            return {"status": "success", **result}
            
        except Exception as e:
            logger.error(f"ML pipeline job failed: {e}")
            
            # Update run with error
            await session.execute(
                text("""
                    UPDATE ml_run 
                    SET finished_at = NOW(),
                        error_log = :error_log
                    WHERE run_id = :run_id
                """),
                {
                    "run_id": run_id,
                    "error_log": json.dumps({"error": str(e), "traceback": traceback.format_exc()})
                }
            )
            await session.commit()
            
            raise
            
        finally:
            # Always release lock
            await lock_manager.release_lock("ml_pipeline", instance_id)


# For manual execution
async def run_ml_pipeline_manual() -> Dict[str, Any]:
    """Run ML pipeline manually (via API)."""
    import uuid
    
    run_id = str(uuid.uuid4())
    instance_id = f"manual-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    async with async_session_maker() as session:
        lock_manager = SchedulerLockManager(session)
        
        lock_acquired = await lock_manager.acquire_lock(
            "ml_pipeline", 
            instance_id,
            timeout_seconds=3600
        )
        
        if not lock_acquired:
            raise RuntimeError("Another ML pipeline is already running")
        
        try:
            await session.execute(
                text("""
                    INSERT INTO ml_run (run_id, started_at, triggered_by, skus_procesados, skus_exitosos, skus_fallidos)
                    VALUES (:run_id, NOW(), 'MANUAL', 0, 0, 0)
                """),
                {"run_id": run_id}
            )
            await session.commit()
            
            job = MLPipelineJob(session, run_id)
            return await job.run()
            
        finally:
            await lock_manager.release_lock("ml_pipeline", instance_id)
