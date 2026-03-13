
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
        res = await conn.execute(text("SHOW CREATE PROCEDURE sp_auto_activate_skus"))
        row = res.fetchone()
        with open("sp_auto_activate_skus.sql", "w", encoding="utf-8") as f:
            f.write(row[2])
        print("Wrote sp_auto_activate_skus.sql")
        
        res = await conn.execute(text("SHOW CREATE PROCEDURE sp_refresh_abc_xyz"))
        row = res.fetchone()
        with open("sp_refresh_abc_xyz.sql", "w", encoding="utf-8") as f:
            f.write(row[2])
        print("Wrote sp_refresh_abc_xyz.sql")

if __name__ == "__main__":
    asyncio.run(check())
