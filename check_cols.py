
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def check():
    async with engine.connect() as conn:
        for t in ["ml_suggestions", "ss_ml_suggestions"]:
            try:
                res = await conn.execute(text(f"SELECT * FROM {t} LIMIT 0"))
                print(f"COLUMNS FOR {t}:")
                print(res.keys())
            except Exception as e:
                print(f"Table {t} error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
