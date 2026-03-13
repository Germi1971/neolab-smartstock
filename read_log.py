
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine
import json

async def check():
    async with engine.connect() as conn:
        run_id = 'RUN-20260211210934-cebaa0'
        res = await conn.execute(text("SELECT error_log FROM ss_ml_run WHERE run_id = :rid"), {"rid": run_id})
        row = res.fetchone()
        if row and row[0]:
            print(row[0])

if __name__ == "__main__":
    asyncio.run(check())
