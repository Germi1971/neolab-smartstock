
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

async def sync_all():
    async with engine.begin() as conn:
        print("Syncing sku_master and ss_sku_master...")
        
        # Populate sku_master
        sql_sku = """
            INSERT IGNORE INTO sku_master (sku, descripcion, activo, created_at)
            SELECT p.sku, COALESCE(NULLIF(tp.`Item Description`,''), p.sku), p.activo, NOW()
            FROM parametros_sku p
            LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(p.sku)
        """
        res1 = await conn.execute(text(sql_sku))
        print(f"sku_master: {res1.rowcount} new rows.")
        
        # Populate ss_sku_master
        sql_ss = """
            INSERT IGNORE INTO ss_sku_master (sku, descripcion, activo, created_at)
            SELECT p.sku, COALESCE(NULLIF(tp.`Item Description`,''), p.sku), p.activo, NOW()
            FROM parametros_sku p
            LEFT JOIN tablaprecios tp ON TRIM(tp.`Product Number`) = TRIM(p.sku)
        """
        res2 = await conn.execute(text(sql_ss))
        print(f"ss_sku_master: {res2.rowcount} new rows.")
        
        # Check if ss_ml_sku_features exists
        try:
            await conn.execute(text("SELECT 1 FROM ss_ml_sku_features LIMIT 1"))
            print("Table ss_ml_sku_features exists.")
        except Exception:
            print("Table ss_ml_sku_features DOES NOT exist. Creating it based on ml_sku_features...")
            try:
                await conn.execute(text("CREATE TABLE ss_ml_sku_features LIKE ml_sku_features"))
                print("Table ss_ml_sku_features created.")
            except Exception as e:
                print(f"Error creating ss_ml_sku_features: {e}")

if __name__ == "__main__":
    asyncio.run(sync_all())
