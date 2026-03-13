
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def get_view_def():
    async with engine.connect() as conn:
        views = ["v_ml_eventos_50", "v_ml_sku_snapshot"]
        for v in views:
            try:
                res = await conn.execute(text(f"SHOW CREATE VIEW {v}"))
                row = res.fetchone()
                print(f"VIEW {v} DEFINITION:\n{row[1]}\n")
            except Exception as e:
                print(f"VIEW {v} ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(get_view_def())
