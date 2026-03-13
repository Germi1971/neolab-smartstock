
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def check():
    async with engine.connect() as conn:
        # active skus
        res = await conn.execute(text("SELECT COUNT(*) FROM parametros_sku WHERE activo = 1"))
        print(f"ACTIVE SKUS (activo=1): {res.scalar()}")
        
        # total skus
        res = await conn.execute(text("SELECT COUNT(*) FROM parametros_sku"))
        print(f"TOTAL SKUS: {res.scalar()}")
        
        # Check views definitions for LIMIT
        views = ["v_ml_sku_snapshot", "v_sku_features_12m", "v_sku_event_features_12m"]
        for v in views:
            try:
                res = await conn.execute(text(f"SHOW CREATE VIEW {v}"))
                row = res.fetchone()
                print(f"\nVIEW {v} DEFINITION:\n{row[1]}")
            except Exception as e:
                print(f"\nVIEW {v} ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(check())
