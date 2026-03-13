
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
        tables = [
            "ml_run", "ss_ml_run", 
            "ml_suggestions", "ss_ml_suggestions", 
            "ml_model_registry", "ss_ml_model_registry",
            "parametros_sku", "sku_abc_xyz"
        ]
        with open("schemas.sql", "w") as f:
            for t in tables:
                try:
                    res = await conn.execute(text(f"SHOW CREATE TABLE {t}"))
                    row = res.fetchone()
                    f.write(f"\n-- TABLE: {t}\n{row[1]};\n")
                except Exception as e:
                    f.write(f"\n-- Table {t} error: {e}\n")
        print("Schemas saved to schemas.sql")

if __name__ == "__main__":
    asyncio.run(check())
