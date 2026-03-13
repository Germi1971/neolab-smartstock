
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

async def populate():
    async with engine.begin() as conn:
        print("Populating ss_sku_master from parametros_sku...")
        sql = """
            INSERT IGNORE INTO ss_sku_master (sku, descripcion, activo, created_at)
            SELECT 
                p.sku, 
                COALESCE(NULLIF(tp.`Item Description`,''), p.sku) as descripcion,
                p.activo,
                NOW()
            FROM parametros_sku p
            LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(p.sku)
        """
        res = await conn.execute(text(sql))
        print(f"Inserted {res.rowcount} records into ss_sku_master.")

if __name__ == "__main__":
    asyncio.run(populate())
