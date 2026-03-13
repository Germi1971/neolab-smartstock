
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
        res = await conn.execute(text("SELECT error_log, skus_exitosos, skus_fallidos FROM ss_ml_run WHERE run_id = :rid"), {"rid": run_id})
        row = res.fetchone()
        if row:
            print(f"Stats: {row[1]} success, {row[2]} failed")
            errors = json.loads(row[0])
            for e in errors:
                if 'A102-100MG' in e['sku']:
                    print(f"Error for {e['sku']}:")
                    print(e['error'])
                    break
            
            # Successful SKUs sample
            res_ok = await conn.execute(text("SELECT sku FROM ss_ml_suggestions WHERE run_id = :rid LIMIT 5"), {"rid": run_id})
            print(f"\nSample Success SKUs: {[r[0] for r in res_ok.fetchall()]}")

if __name__ == "__main__":
    asyncio.run(check())
