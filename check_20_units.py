import sys
sys.path.append('backend')
from database import SessionLocal
from sqlalchemy import text

session = SessionLocal()

skus = ('A175-5KG', 'G3251-5KG', 'G434-5KG', 'M481-10G')

# Check parametros_sku
result = session.execute(
    text('SELECT sku, stock_objetivo, modelo_recomendado, cap_objetivo FROM parametros_sku WHERE sku IN :skus'),
    {'skus': skus}
).fetchall()

print('=== PARAMETROS_SKU ===')
for r in result:
    print(f'{r[0]}: obj={r[1]}, modelo={r[2]}, cap={r[3]}')

# Check ML suggestions
result2 = session.execute(
    text('SELECT sku, policy_max, modelo_seleccionado FROM ss_ml_suggestions WHERE sku IN :skus ORDER BY created_at DESC LIMIT 10'),
    {'skus': skus}
).fetchall()

print('\n=== ML SUGGESTIONS ===')
for r in result2:
    print(f'{r[0]}: policy_max={r[1]}, modelo={r[2]}')

# Check features
result3 = session.execute(
    text('SELECT sku, dias_observados_total, eventos_venta_total, unidades_vendidas_total FROM ss_ml_sku_features WHERE sku IN :skus'),
    {'skus': skus}
).fetchall()

print('\n=== FEATURES ===')
for r in result3:
    print(f'{r[0]}: dias={r[1]}, eventos={r[2]}, unidades={r[3]}')

session.close()
