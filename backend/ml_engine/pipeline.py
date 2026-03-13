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
                    Fecha as fecha,
                    Qty as cantidad
                FROM v_hist_ventas
                WHERE SKU = :sku
                AND Fecha >= DATE_SUB(CURDATE(), INTERVAL 24 MONTH)
                ORDER BY Fecha
            """),
            {"sku": sku}
        )
        
        rows = result.fetchall()
        
        # Determine dormancy (no sales in last 24 months)
        is_dormant = len(rows) == 0
        
        # Calculate features (simplified)
        from datetime import date
        today = date.today()
        
        # 12 month window
        window_12m = [r for r in rows if (today - r[0]).days <= 365]
        eventos_12m = len([r for r in window_12m if r[1] > 0])
        unidades_12m = sum(r[1] for r in window_12m)
        
        # Calculate CV
        cv_12m = 0
        if eventos_12m > 1:
            import numpy as np
            values = [r[1] for r in window_12m if r[1] > 0]
            cv_12m = np.std(values) / np.mean(values) if np.mean(values) > 0 else 0
            
        features = {
            "has_data": len(rows) > 0,
            "is_dormant": is_dormant,
            "dias_observados_12m": 365, # Assuming 365 days in the window
            "eventos_12m": eventos_12m,
            "unidades_12m": unidades_12m,
            "cv_12m": cv_12m,
            "lambda_eventos_mes_12m": eventos_12m / 12.0 if eventos_12m > 0 else 0,
            "ultima_venta": max(r[0] for r in rows) if rows else None,
            "dias_desde_ultima_venta": (today - max(r[0] for r in rows)).days if rows else None
        }
        
        # Store features
        await self._store_features(sku, features)
        
        return features
    
    async def _store_features(self, sku: str, features: Dict[str, Any]):
        """Store computed features."""
        from datetime import date
        
        await self.session.execute(
            text("""
                INSERT INTO ss_ml_sku_features (
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
                INSERT INTO ss_ml_model_registry (
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
        
        return {
            "modelo": modelo,
            "score": 0.8
        }
    
    async def _generate_policy(self, sku: str, features: Dict[str, Any], model: Dict[str, Any]) -> Dict[str, Any]:
        """Generate (s, S) policy for a SKU."""
        # Get parameters
        result = await self.session.execute(
            text("SELECT stock_min, stock_objetivo, lead_time_dias, z_servicio, criticidad FROM parametros_sku WHERE sku = :sku"),
            {"sku": sku}
        )
        row = result.fetchone()
        
        if not row:
            return {"s": 0, "S": 0}
        
        current_s = row[0] or 0
        current_S = row[1] or 0
        lt = row[2] or 30  # default 30 days
        z = row[3] or 1.65 # default 95%
        criticidad = row[4] or 'MEDIA'

        # 1. Handle Dormant SKUs (No sales in 24 months)
        # If a SKU has zero sales events in the last 12 months, suggest 0 regardless of criticality
        eventos_12m = features.get("eventos_12m", 0)
        if eventos_12m == 0:
            logger.info(f"SKU {sku} has zero sales events in 12 months. Suggesting 0.")
            return {"s": 0, "S": 0}
        
        # For truly dormant SKUs (24 months), also suggest 0 unless critical
        if features.get("is_dormant") and criticidad != 'ALTA':
            logger.info(f"SKU {sku} is dormant (24 months). Suggesting 0.")
            return {"s": 0, "S": 0}

        # 2. Basic Statistical Policy for Active Items
        # Demand per day * Lead Time + Safety Stock
        u_mes = features.get("unidades_12m", 0) / 12.0
        u_dia = u_mes / 30.0
        
        # Base demand for the lead time
        lead_time_demand = u_dia * lt
        
        # Simple Safety Stock (simplified for now)
        # In a real scenario we'd use sigma_demand * sqrt(LT) * Z
        # Here we'll use a 20% buffer if no variability info
        ss = lead_time_demand * 0.2 * z
        
        suggested_s = round(lead_time_demand + ss)
        suggested_S = round(suggested_s + lead_time_demand) # simplistic S = s + demand_cycle

        # If it's on-demand only (very low demand), but not dormant
        if suggested_S < 1 and u_mes > 0:
            suggested_S = 1 # Minimum 1 if it has some sales
        
        return {
            "s": suggested_s,
            "S": suggested_S
        }
    
    async def _create_suggestion(self, sku: str, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Create purchase suggestion for a SKU."""
        # Get current stock
        result = await self.session.execute(
            text("SELECT Stock_Posicion_Libre FROM v_stock_estado WHERE SKU = :sku"),
            {"sku": sku}
        )
        row = result.fetchone()
        stock_posicion = row[0] if row else 0
        
        # Calculate suggested quantity
        qty_sugerida = max(0, policy["S"] - stock_posicion)
        
        # Get model
        result = await self.session.execute(
            text("SELECT modelo_actual FROM ss_ml_model_registry WHERE sku = :sku"),
            {"sku": sku}
        )
        row = result.fetchone()
        modelo = row[0] if row else "SIN_DATOS"
        
        # Store suggestion
        await self.session.execute(
            text("""
                INSERT INTO ss_ml_suggestions (
                    run_id, sku, qty_sugerida, estado,
                    modelo_seleccionado, policy_min, policy_max
                ) VALUES (
                    :run_id, :sku, :qty, 'PENDIENTE',
                    :modelo, :policy_min, :policy_max
                )
                ON DUPLICATE KEY UPDATE
                    qty_sugerida = VALUES(qty_sugerida),
                    estado = VALUES(estado),
                    modelo_seleccionado = VALUES(modelo_seleccionado),
                    policy_min = VALUES(policy_min),
                    policy_max = VALUES(policy_max),
                    updated_at = NOW()
            """),
            {
                "run_id": self.run_id,
                "sku": sku,
                "qty": qty_sugerida,
                "modelo": modelo,
                "policy_min": policy["s"],
                "policy_max": policy["S"]
            }
        )
        
        return {
            "qty_sugerida": qty_sugerida,
            "estado": "PENDIENTE"
        }
