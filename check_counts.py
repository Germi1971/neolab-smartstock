
import asyncio
from sqlalchemy import text
import sys
import os
sys.path.append(os.getcwd())
from backend.db.database import engine

async def check_counts():
    async with engine.connect() as conn:
        tables = [
            "parametros_sku", 
            "sku_parameters", 
            "ss_sku_parameters", 
            "demand_history", 
            "ss_demand_history",
            "v_ml_sku_snapshot",
            "v_ml_eventos_50",
            "tablastock",
            "v_stock_estado"
        ]
        print("TABLE COUNTS:")
        for t in tables:
            try:
                res = await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
                cnt = res.scalar()
                print(f"- {t}: {cnt}")
            except Exception as e:
                print(f"- {t}: ERROR ({str(e).splitlines()[0]})")

if __name__ == "__main__":
    asyncio.run(check_counts())
