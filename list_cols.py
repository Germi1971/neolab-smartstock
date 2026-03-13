
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
        for t in ["ml_suggestions", "ss_ml_suggestions", "ml_runs", "ss_ml_run"]:
            try:
                res = await conn.execute(text(f"DESCRIBE {t}"))
                print(f"\nCOLUMNS FOR {t}:")
                for row in res.fetchall():
                    print(f"- {row[0]} ({row[1]})")
            except Exception as e:
                print(f"\nTable {t} error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
