
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def list_tables():
    async with engine.connect() as conn:
        res = await conn.execute(text('SHOW TABLES'))
        tables = [r[0] for r in res.fetchall()]
        print("TABLES FOUND:")
        for t in sorted(tables):
            print(f"- {t}")

if __name__ == "__main__":
    asyncio.run(list_tables())
