
import asyncio
from sqlalchemy import text
from backend.db.database import get_db, init_db, close_db
import json

async def check():
    await init_db()
    async for db in get_db():
        # Check sku_parameters
        res = await db.execute(text("SELECT COUNT(*), SUM(activo) FROM sku_parameters"))
        count, active = res.fetchone()
        print(f"SKUs in parameters: {count}, Active: {active}")
        
        # Check if views exist and have data
        try:
            res = await db.execute(text("SELECT COUNT(*) FROM v_ml_sku_snapshot"))
            snapshots = res.scalar()
            print(f"Rows in v_ml_sku_snapshot: {snapshots}")
        except Exception as e:
            print(f"Error checking v_ml_sku_snapshot: {e}")

        try:
            res = await db.execute(text("SELECT COUNT(*) FROM v_ml_eventos_50"))
            eventos = res.scalar()
            print(f"Rows in v_ml_eventos_50: {eventos}")
        except Exception as e:
            print(f"Error checking v_ml_eventos_50: {e}")
            
        break
    await close_db()

if __name__ == "__main__":
    asyncio.run(check())
