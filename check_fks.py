
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def check_fks():
    async with engine.connect() as conn:
        tables = ["ml_suggestions", "ss_ml_suggestions", "ml_model_registry", "ss_ml_model_registry"]
        print("FOREIGN KEYS:")
        for t in tables:
            try:
                res = await conn.execute(text(f"""
                    SELECT 
                        COLUMN_NAME, 
                        REFERENCED_TABLE_NAME, 
                        REFERENCED_COLUMN_NAME
                    FROM
                        INFORMATION_SCHEMA.KEY_COLUMN_USAGE
                    WHERE
                        TABLE_NAME = :t
                        AND TABLE_SCHEMA = 'neobd'
                        AND REFERENCED_TABLE_NAME IS NOT NULL
                """), {"t": t})
                rows = res.fetchall()
                print(f"\nTable {t}:")
                for r in rows:
                    print(f"- {r[0]} -> {r[1]}({r[2]})")
            except Exception as e:
                print(f"Error {t}: {e}")

if __name__ == "__main__":
    asyncio.run(check_fks())
