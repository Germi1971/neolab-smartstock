
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine
import json

async def check():
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT error_log FROM ss_ml_run WHERE error_log IS NOT NULL ORDER BY started_at DESC LIMIT 1"))
        row = res.fetchone()
        if row and row[0]:
            errors = json.loads(row[0])
            failing_skus = [e['sku'] for e in errors]
            print(f"Total failing SKUs in log snippet: {len(failing_skus)}")
            
            for sku in failing_skus[:10]:
                res_master = await conn.execute(text("SELECT sku FROM ss_sku_master WHERE sku = :sku"), {"sku": sku})
                m_row = res_master.fetchone()
                exists = m_row is not None
                print(f"SKU '{sku}' (len {len(sku)}) exists in master? {exists}")
                if exists:
                     print(f"  Master SKU: '{m_row[0]}' (len {len(m_row[0])})")

if __name__ == "__main__":
    asyncio.run(check())
