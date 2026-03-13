
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def check():
    async with engine.connect() as conn:
        tables = ["ss_ml_run", "ss_ml_suggestions", "ss_ml_model_registry", "ml_model_registry"]
        for t in tables:
            try:
                res = await conn.execute(text(f"DESC {t}"))
                print(f"\n{t}:")
                for row in res.fetchall():
                    print(f"- {row[0]} ({row[1]})")
            except Exception as e:
                print(f"\n{t} error: {e}")

if __name__ == "__main__":
    asyncio.run(check())
