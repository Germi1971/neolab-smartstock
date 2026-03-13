
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
        sku = "1050212"
        for t in ["parametros_sku", "ss_sku_master"]:
            res = await conn.execute(text(f"SELECT sku FROM {t} WHERE sku LIKE :sku"), {"sku": f"%{sku}%"})
            rows = res.fetchall()
            print(f"Table {t} matches for {sku}:")
            for r in rows:
                print(f"  - '{r[0]}' (len: {len(r[0])})")

if __name__ == "__main__":
    asyncio.run(check())
