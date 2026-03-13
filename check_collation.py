
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
        for t in ["ss_sku_master", "ss_ml_suggestions", "ss_ml_model_registry"]:
            try:
                res = await conn.execute(text(f"""
                    SELECT COLUMN_NAME, CHARACTER_SET_NAME, COLLATION_NAME
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_NAME = :t AND COLUMN_NAME = 'sku' AND TABLE_SCHEMA = 'neobd'
                """), {"t": t})
                row = res.fetchone()
                print(f"Table {t} SKU Collation: {row[1]} / {row[2]}")
            except Exception as e:
                print(f"Error {t}: {e}")

if __name__ == "__main__":
    asyncio.run(check())
