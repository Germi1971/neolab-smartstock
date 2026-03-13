
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

async def alter():
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE ss_ml_run ADD COLUMN status VARCHAR(16) AFTER duracion_segundos"))
            print("Column 'status' added to 'ss_ml_run'")
        except Exception as e:
            if "Duplicate column name" in str(e):
                print("Column 'status' already exists in 'ss_ml_run'")
            else:
                print(f"Error adding column: {e}")

if __name__ == "__main__":
    asyncio.run(alter())
