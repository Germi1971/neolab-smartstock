
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
        try:
            res = await conn.execute(text("SHOW CREATE VIEW v_ml_sku_snapshot"))
            row = res.fetchone()
            print(f"VIEW v_ml_sku_snapshot DEFINITION:\n{row[1]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
