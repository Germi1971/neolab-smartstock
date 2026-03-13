
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

new_code = """    # STATS para KPIs del frontend
    stats_sql = text(\"\"\"
        SELECT 
            COUNT(*) as total_skus,
            SUM(CASE WHEN COALESCE(p.activo, 1) = 1 THEN 1 ELSE 0 END) as activos,
            SUM(CASE WHEN COALESCE(vs.estado, 'OK') IN ('QUIEBRE', 'BAJO') THEN 1 ELSE 0 END) as stock_bajo,
            SUM(CASE WHEN p.moq > 0 THEN 1 ELSE 0 END) as con_moq
        FROM parametros_sku p
        LEFT JOIN v_stock_semaforo_ui vs ON vs.sku = p.sku
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
            "total_skus": int(stats_row["total_skus"] or 0),
            "activos": int(stats_row["activos"] or 0),
            "stock_bajo": int(stats_row["stock_bajo"] or 0),
            "con_moq": int(stats_row["con_moq"] or 0)
        }
    }"""

if old_code in content:
    new_content = content.replace(old_code, new_code)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SUCCESS")
else:
    # Try with CRLF
    old_code_crlf = old_code.replace('\n', '\r\n')
    if old_code_crlf in content:
        new_content = content.replace(old_code_crlf, new_code.replace('\n', '\r\n'))
        with open(path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("SUCCESS CRLF")
    else:
        print("OLD CODE NOT FOUND")
