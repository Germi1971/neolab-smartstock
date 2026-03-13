
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
try:
    from backend.db.database import engine
except ImportError:
    sys.path.append(os.path.join(os.getcwd(), ".."))
    from backend.db.database import engine

async def check():
    async with engine.connect() as conn:
        tables = ["sku_master", "ss_sku_master", "parametros_sku", "v_ml_sku_snapshot"]
        for t in tables:
            try:
                res = await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
                print(f"{t}: {res.scalar()}")
            except Exception as e:
                print(f"Error {t}: {e}")

if __name__ == "__main__":
    asyncio.run(check())
