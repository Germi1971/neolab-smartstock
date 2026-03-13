
import os

path = r'c:\Users\germa\Documents\NEOLAB\DATO_SOLUTIONS\neolab_smartstock\backend\routers\api.py'
content = open(path, 'r', encoding='utf-8').read()

old_code = """    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "items": items,
    }"""

# Note: The above old_code is the same as the one used in the previous patch.
# I need to find the one inside api_purchase_suggestions.
# It's better to find a more unique anchor for this specific function.

anchor = "        ORDER BY sc.impacto_usd DESC, sc.qty_recomendada DESC, sc.sku"

new_code_fragment = """
    # STATS para KPIs del frontend (Compras)
    stats_sql = text(\"\"\"
        SELECT 
            COUNT(*) as total_sugerencias,
            SUM(CASE WHEN COALESCE(sc.aprobado, 0) = 0 THEN 1 ELSE 0 END) as pendientes,
            SUM(CASE WHEN COALESCE(sc.aprobado, 0) = 1 THEN 1 ELSE 0 END) as aprobadas,
            SUM(COALESCE(sc.qty_recomendada, 0)) as total_qty_sugerida
        FROM v_sugerencias_compra sc
    \"\"\")
    stats_res = await db.execute(stats_sql)
    stats_row = stats_res.mappings().first()

    return {
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "items": items,
        "stats": {
            "total_sugerencias": int(stats_row["total_sugerencias"] or 0),
            "pendientes": int(stats_row["pendientes"] or 0),
            "aprobadas": int(stats_row["aprobadas"] or 0),
            "total_qty_sugerida": float(stats_row["total_qty_sugerida"] or 0)
        }
    }"""

# Find the next return block after the anchor
import re
pattern = re.escape(anchor) + r".*?return \{.*?\} " # simplified, need to handle newlines
# Let's just find the return block that comes after sc.sku

# Actually, I can just find the one at lines 594-600
# But file line numbers might have shifted after the previous patch.

# Let's count them or use a more robust regex.
lines = content.splitlines()
target_line = -1
for i, line in enumerate(lines):
    if "return {" in line and i > 520 and i < 650: # Range for api_purchase_suggestions
        target_line = i
        break

if target_line != -1:
    old_return_block = "\n".join(lines[target_line:target_line+7])
    # The return block is 7 lines long in the original
    print(f"Found return block at line {target_line+1}")
    
    new_content = content.replace(old_return_block, new_code_fragment)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SUCCESS")
else:
    print("RETURN BLOCK NOT FOUND IN RANGE")
