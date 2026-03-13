import sys
sys.path.append('backend')
from database import SessionLocal
from sqlalchemy import text

session = SessionLocal()

# Check how many SKUs have suggestions but no sales history
query = text("""
    SELECT 
        COUNT(*) as total_unfounded,
        SUM(sc.qty_recomendada) as total_qty
    FROM v_sugerencias_compra sc
    LEFT JOIN ss_ml_sku_features f ON f.sku = sc.sku
    WHERE COALESCE(f.eventos_venta_total, 0) = 0
      AND COALESCE(sc.qty_recomendada, 0) > 0
""")

result = session.execute(query).fetchone()
print(f"=== UNFOUNDED SUGGESTIONS ===")
print(f"Total SKUs with suggestions but no sales: {result[0]}")
print(f"Total quantity suggested: {result[1]}")

# Check specific SKUs
skus = ('A175-5KG', 'G3251-5KG', 'G434-5KG', 'M481-10G')
query2 = text("""
    SELECT 
        sc.sku,
        COALESCE(f.eventos_venta_total, 0) as eventos,
        COALESCE(f.unidades_vendidas_total, 0) as unidades,
        COALESCE(f.clasificacion_demanda, 'N/A') as clasificacion,
        sc.qty_recomendada,
        p.stock_objetivo as param_obj,
        sc.stock_objetivo_capeado as ml_obj
    FROM v_sugerencias_compra sc
    LEFT JOIN ss_ml_sku_features f ON f.sku = sc.sku
    LEFT JOIN parametros_sku p ON p.sku = sc.sku
    WHERE sc.sku IN :skus
""")

result2 = session.execute(query2, {'skus': skus}).fetchall()
print(f"\n=== SPECIFIC SKUs ===")
for r in result2:
    print(f"{r[0]}: eventos={r[1]}, unidades={r[2]}, clase={r[3]}, qty_sug={r[4]}, param_obj={r[5]}, ml_obj={r[6]}")

session.close()
