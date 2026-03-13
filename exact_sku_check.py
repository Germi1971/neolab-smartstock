
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
        if row:
            errors = json.loads(row[0])
            for e in errors:
                sku = e['sku']
                print(f"\nANALYZING FAIL SKU: '{sku}'")
                print(f"  Python repr: {repr(sku)}")
                
                # Check in master
                res_m = await conn.execute(text("SELECT sku FROM ss_sku_master WHERE sku = :sku"), {"sku": sku})
                row_m = res_m.fetchone()
                if row_m:
                    print(f"  MATCH FOUND in ss_sku_master: '{row_m[0]}' (repr: {repr(row_m[0])})")
                else:
                    print(f"  NO MATCH in ss_sku_master for exact string.")
                    # Try partial
                    res_p = await conn.execute(text("SELECT sku FROM ss_sku_master WHERE sku LIKE :sku"), {"sku": f"%{sku}%"})
                    m_rows = res_p.fetchall()
                    if m_rows:
                        print(f"  PARTIAL MATCHES in master:")
                        for mr in m_rows:
                            print(f"    - '{mr[0]}' (repr: {repr(mr[0])})")

if __name__ == "__main__":
    asyncio.run(check())
