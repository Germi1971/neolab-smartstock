
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def check():
    async with engine.connect() as conn:
        views = ['v_sugerencias_compra', 'v_stock_semaforo_ui']
        for v in views:
            res = await conn.execute(text(f"SHOW CREATE VIEW {v}"))
            row = res.fetchone()
            with open(f"{v}.sql", "w") as f:
                f.write(row[1])
            print(f"Wrote {v}.sql")

if __name__ == "__main__":
    asyncio.run(check())
