"""
ML Pipeline - Main orchestrator for ML processing.
"""
from typing import Dict, Any, List, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class MLPipeline:
    """Main ML Pipeline orchestrator."""
    
    def __init__(self, session: AsyncSession, run_id: str):
        self.session = session
        self.run_id = run_id
    
    async def process_single_sku(self, sku: str) -> Dict[str, Any]:
        """
        Process a single SKU through the ML pipeline.
        
        Steps:
        1. Compute features
        2. Select model
        3. Generate policy
        4. Create suggestion
        """
        try:
            # Step 1: Compute features
            features = await self._compute_features(sku)
            
            # Step 2: Select model
            model_result = await self._select_model(sku, features)
            
            # Step 3: Generate policy
            policy = await self._generate_policy(sku, features, model_result)
            
            # Step 4: Create suggestion
            suggestion = await self._create_suggestion(sku, policy)
            
            return {
                "sku": sku,
                "status": "success",
                "features": features,
                "model": model_result,
                "policy": policy,
                "suggestion": suggestion
            }
            
        except Exception as e:
            logger.error(f"Error processing SKU {sku}: {e}")
            raise
    
    async def _compute_features(self, sku: str) -> Dict[str, Any]:
        """Compute ML features for a SKU."""
        # Query demand history
        result = await self.session.execute(
            text("""
                SELECT 
                    fecha,
                    cantidad
                FROM demand_history
                WHERE sku = :sku
                AND fecha >= DATE_SUB(CURDATE(), INTERVAL 24 MONTH)
                ORDER BY fecha
            """),
            {"sku": sku}
        )
        
        rows = result.fetchall()
        
        if not rows:
            # No data - return default features
            return {
                "has_data": False,
                "dias_observados_12m": 0,
                "eventos_12m": 0,
                "unidades_12m": 0,
                "cv_12m": 0,
                "lambda_eventos_mes_12m": 0
            }
        
        # Calculate features (simplified)
        from datetime import date
        
        today = date.today()
        
        # 12 month window
        window_12m = [r for r in rows if (today - r[0]).days <= 365]
        eventos_12m = len([r for r in window_12m if r[1] > 0])
        unidades_12m = sum(r[1] for r in window_12m)
        
        # Calculate CV
        if eventos_12m > 1:
            import numpy as np
            values = [r[1] for r in window_12m if r[1] > 0]
            cv_12m = float(np.std(values) / np.mean(values)) if np.mean(values) > 0 else 0
        else:
            cv_12m = 0
        
        features = {
            "has_data": True,
            "dias_observados_12m": len(window_12m),
            "eventos_12m": eventos_12m,
            "unidades_12m": unidades_12m,
            "cv_12m": cv_12m,
            "lambda_eventos_mes_12m": eventos_12m / 12 if eventos_12m > 0 else 0,
            "ultima_venta": max(r[0] for r in rows),
            "dias_desde_ultima_venta": (today - max(r[0] for r in rows)).days
        }
        
        # Store features
        await self._store_features(sku, features)
        
        return features
    
    async def _store_features(self, sku: str, features: Dict[str, Any]):
        """Store computed features."""
        from datetime import date
        
        await self.session.execute(
            text("""
                INSERT INTO ml_sku_features (
                    run_id, sku, periodo_inicio, periodo_fin,
                    dias_observados_12m, eventos_12m, unidades_12m,
                    cv_12m, lambda_eventos_mes_12m,
                    ultima_venta, dias_desde_ultima_venta
                ) VALUES (
                    :run_id, :sku, :inicio, :fin,
                    :dias_12m, :eventos_12m, :unidades_12m,
                    :cv_12m, :lambda_12m,
                    :ultima_venta, :dias_desde
                )
                ON DUPLICATE KEY UPDATE
                    periodo_inicio = VALUES(periodo_inicio),
                    periodo_fin = VALUES(periodo_fin),
                    dias_observados_12m = VALUES(dias_observados_12m),
                    eventos_12m = VALUES(eventos_12m),
                    unidades_12m = VALUES(unidades_12m),
                    cv_12m = VALUES(cv_12m),
                    lambda_eventos_mes_12m = VALUES(lambda_eventos_mes_12m),
                    ultima_venta = VALUES(ultima_venta),
                    dias_desde_ultima_venta = VALUES(dias_desde_ultima_venta)
            """),
            {
                "run_id": self.run_id,
                "sku": sku,
                "inicio": date.today().replace(year=date.today().year - 1),
                "fin": date.today(),
                "dias_12m": features["dias_observados_12m"],
                "eventos_12m": features["eventos_12m"],
                "unidades_12m": features["unidades_12m"],
                "cv_12m": features["cv_12m"],
                "lambda_12m": features["lambda_eventos_mes_12m"],
                "ultima_venta": features.get("ultima_venta"),
                "dias_desde": features.get("dias_desde_ultima_venta", 0)
            }
        )
        await self.session.commit()
    
    async def _select_model(self, sku: str, features: Dict[str, Any]) -> Dict[str, Any]:
        """Select the best model for a SKU."""
        if not features["has_data"]:
            return {
                "modelo": "SIN_DATOS",
                "score": 0
            }
        
        # Simple model selection based on CV
        cv = features["cv_12m"]
        eventos = features["eventos_12m"]
        
        if eventos == 0:
            modelo = "SIN_DATOS"
        elif cv < 0.5 and eventos > 6:
            modelo = "REGULAR"
        elif cv >= 0.5:
            modelo = "CROSTON"
        else:
            modelo = "SBA"
        
        # Store model selection
        await self.session.execute(
            text("""
                INSERT INTO ml_model_registry (
                    sku, modelo_actual, fecha_seleccion,
                    run_id_seleccion, score_composite
                ) VALUES (
                    :sku, :modelo, NOW(),
                    :run_id, :score
                )
                ON DUPLICATE KEY UPDATE
                    modelo_anterior = modelo_actual,
                    modelo_actual = VALUES(modelo_actual),
                    fecha_seleccion = VALUES(fecha_seleccion),
                    run_id_seleccion = VALUES(run_id_seleccion),
                    score_composite = VALUES(score_composite)
            """),
            {
                "sku": sku,
                "modelo": modelo,
                "run_id": self.run_id,
                "score": 0.8  # Placeholder score
            }
        )
        await self.session.commit()
        
        return {
            "modelo": modelo,
            "score": 0.8
        }
    
    async def _generate_policy(self, sku: str, features: Dict[str, Any], model: Dict[str, Any]) -> Dict[str, Any]:
        """Generate (s, S) policy for a SKU."""
        # Get parameters
        result = await self.session.execute(
            text("SELECT stock_seguridad, stock_objetivo FROM sku_parameters WHERE sku = :sku"),
            {"sku": sku}
        )
        row = result.fetchone()
        
        if not row:
            return {"s": 0, "S": 0}
        
        stock_seguridad = row[0]
        stock_objetivo = row[1]
        
        return {
            "s": stock_seguridad,
            "S": stock_objetivo
        }
    
    async def _create_suggestion(self, sku: str, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Create purchase suggestion for a SKU."""
        # Get current stock
        result = await self.session.execute(
            text("SELECT stock_posicion FROM stock WHERE sku = :sku"),
            {"sku": sku}
        )
        row = result.fetchone()
        stock_posicion = row[0] if row else 0
        
        # Calculate suggested quantity
        qty_sugerida = max(0, policy["S"] - stock_posicion)
        
        # Get model
        result = await self.session.execute(
            text("SELECT modelo_actual FROM ml_model_registry WHERE sku = :sku"),
            {"sku": sku}
        )
        row = result.fetchone()
        modelo = row[0] if row else "SIN_DATOS"
        
        # Store suggestion
        await self.session.execute(
            text("""
                INSERT INTO ml_suggestions (
                    run_id, sku, qty_sugerida, estado,
                    modelo_seleccionado, s_policy, S_policy
                ) VALUES (
                    :run_id, :sku, :qty, 'PENDIENTE',
                    :modelo, :s, :S
                )
                ON DUPLICATE KEY UPDATE
                    qty_sugerida = VALUES(qty_sugerida),
                    estado = VALUES(estado),
                    modelo_seleccionado = VALUES(modelo_seleccionado),
                    s_policy = VALUES(s_policy),
                    S_policy = VALUES(S_policy),
                    updated_at = NOW()
            """),
            {
                "run_id": self.run_id,
                "sku": sku,
                "qty": qty_sugerida,
                "modelo": modelo,
                "s": policy["s"],
                "S": policy["S"]
            }
        )
        await self.session.commit()
        
        return {
            "qty_sugerida": qty_sugerida,
            "estado": "PENDIENTE"
        }
