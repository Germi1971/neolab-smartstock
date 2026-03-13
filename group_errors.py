
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine
import json
from collections import Counter

async def group_errors():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT error_log FROM ss_ml_run WHERE error_log IS NOT NULL ORDER BY started_at DESC LIMIT 1"))
        row = res.fetchone()
        if row and row[0]:
            errors = json.loads(row[0])
            print(f"Total errors in log: {len(errors)}")
            
            # Group by error message (removing the SKU part)
            messages = [e['error'] for e in errors]
            counts = Counter(messages)
            
            print("\nERROR SUMMARY:")
            for msg, count in counts.items():
                print(f"- {count} SKUs: {msg[:200]}...")

if __name__ == "__main__":
    asyncio.run(group_errors())
