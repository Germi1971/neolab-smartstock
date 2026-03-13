
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def check():
    async with engine.connect() as conn:
        sku = 'Z899-1G'
        res = await conn.execute(text("""
            SELECT p.*, a.abc_class, a.xyz_class 
            FROM parametros_sku p 
            LEFT JOIN sku_abc_xyz a ON a.sku = p.sku 
            WHERE p.sku = :sku
        """), {"sku": sku})
        row = res.mappings().first()
        print(row)

if __name__ == "__main__":
    asyncio.run(check())
