
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
        procs = ["sp_auto_activate_skus", "sp_refresh_abc_xyz"]
        for p in procs:
            try:
                res = await conn.execute(text(f"SHOW CREATE PROCEDURE {p}"))
                row = res.fetchone()
                print(f"PROCEDURE {p} DEFINITION:\n{row[2]}")
            except Exception as e:
                print(f"Error {p}: {e}")

if __name__ == "__main__":
    asyncio.run(check())
