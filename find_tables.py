
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def find_tables():
    async with engine.connect() as conn:
        res = await conn.execute(text("SHOW TABLES"))
        tables = [r[0] for r in res.fetchall()]
        
        targets = ["param", "sku", "ventas", "sale", "mov", "stock", "hist", "demand"]
        found = []
        for t in tables:
            if any(target in t.lower() for target in targets):
                found.append(t)
        
        print("INTERESTING TABLES FOUND:")
        for t in sorted(found):
            print(f"- {t}")

if __name__ == "__main__":
    asyncio.run(find_tables())
