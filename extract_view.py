
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
try:
    from backend.db.database import engine
except ImportError:
    # If run from backend dir
    sys.path.append(os.path.join(os.getcwd(), ".."))
    from backend.db.database import engine

async def get_view_def():
    async with engine.connect() as conn:
        res = await conn.execute(text("SHOW CREATE VIEW v_ml_sku_snapshot"))
        row = res.fetchone()
        with open("view_snapshot.sql", "w") as f:
            f.write(row[1])
        print("View definition saved to view_snapshot.sql")

if __name__ == "__main__":
    asyncio.run(get_view_def())
