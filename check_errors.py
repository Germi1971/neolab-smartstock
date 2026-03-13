
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine
import json

async def check_errors():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT error_log FROM ml_runs ORDER BY started_at DESC LIMIT 1"))
        row = res.fetchone()
        if row and row[0]:
            errors = json.loads(row[0])
            if errors:
                print(f"FIRST ERROR (SKU {errors[0]['sku']}):")
                print(errors[0]['error'])
                if len(errors) > 1:
                    print(f"\nSECOND ERROR (SKU {errors[1]['sku']}):")
                    print(errors[1]['error'])

if __name__ == "__main__":
    asyncio.run(check_errors())
