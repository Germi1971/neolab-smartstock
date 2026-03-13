
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine
import re

async def find_base_table():
    async with engine.connect() as conn:
        res = await conn.execute(text("SHOW CREATE VIEW v_hist_ventas"))
        row = res.fetchone()
        sql = row[1]
        # Match FROM or JOIN
        matches = re.findall(r"FROM\s+`?(\w+)`?|JOIN\s+`?(\w+)`?", sql, re.IGNORECASE)
        print("BASE TABLES FOR v_hist_ventas:")
        for m in matches:
            table = m[0] or m[1]
            print(f"- {table}")

if __name__ == "__main__":
    asyncio.run(find_base_table())
