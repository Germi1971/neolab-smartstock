
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def check_view():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT * FROM v_stock_estado LIMIT 1"))
        print("COLUMNS for v_stock_estado:")
        print(res.keys())

if __name__ == "__main__":
    asyncio.run(check_view())
