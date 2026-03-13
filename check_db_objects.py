
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
        print("STORED PROCEDURES:")
        res = await conn.execute(text("SHOW PROCEDURE STATUS WHERE Db = 'neobd'"))
        for row in res:
            print(f"- {row[1]}")
        
        print("\nVIEWS:")
        res = await conn.execute(text("SHOW FULL TABLES WHERE Table_type = 'VIEW'"))
        for row in res:
            print(f"- {row[0]}")

if __name__ == "__main__":
    asyncio.run(check())
