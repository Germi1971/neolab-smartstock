
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def get_view_def():
    async with engine.connect() as conn:
        res = await conn.execute(text("SHOW CREATE VIEW v_sku_event_features_12m"))
        row = res.fetchone()
        with open("view_events.sql", "w") as f:
            f.write(row[1])
        print("View definition saved to view_events.sql")

if __name__ == "__main__":
    asyncio.run(get_view_def())
