from typing import Any
from fastapi import APIRouter, HTTPException, Query
import pymysql

router = APIRouter()


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


@router.get("/sku/{sku}/eventos")
def sku_eventos(sku: str, limit: int = Query(50, ge=1, le=500)):
    """
    Lista de eventos (FAC) por SKU, basado en v_hist_ventas (FAC+SKU).
    """
    from app.main import cfg, get_conn  # import tardío para evitar circularidad

    sql = """
    SELECT
      Fecha,
      FAC,
      ClienteN,
      ClienteNombre,
      Qty,
      UnitPrice_USD,
      UnitCost_USD,
      Revenue_USD,
      Margin_USD
    FROM v_hist_ventas
    WHERE SKU = %s
    ORDER BY Fecha DESC
    LIMIT %s;
    """
    try:
        with get_conn(cfg) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (sku, limit))
                rows = cur.fetchall() or []
        # Normalizamos numéricos
        for r in rows:
            r["Qty"] = safe_float(r.get("Qty"))
            r["UnitPrice_USD"] = safe_float(r.get("UnitPrice_USD"))
            r["UnitCost_USD"] = safe_float(r.get("UnitCost_USD"))
            r["Revenue_USD"] = safe_float(r.get("Revenue_USD"))
            r["Margin_USD"] = safe_float(r.get("Margin_USD"))
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"sku/{sku}/eventos error: {str(e)}")


@router.get("/sku/{sku}/demanda_mensual")
def sku_demanda_mensual(sku: str, months: int = Query(24, ge=1, le=120)):
    """
    Serie mensual (YearMonth) para chart, basado en v_hist_ventas.
    Devuelve orden ASC para graficar (antiguo -> reciente).
    """
    from app.main import cfg, get_conn

    sql = """
    SELECT
      YearMonth,
      SUM(Qty) AS Qty
    FROM v_hist_ventas
    WHERE SKU = %s
    GROUP BY YearMonth
    ORDER BY YearMonth DESC
    LIMIT %s;
    """
    try:
        with get_conn(cfg) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (sku, months))
                rows = cur.fetchall() or []
        for r in rows:
            r["Qty"] = safe_float(r.get("Qty"))
        # Para charts conviene ASC
        return list(reversed(rows))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"sku/{sku}/demanda_mensual error: {str(e)}")


@router.get("/sku/{sku}/top_clientes")
def sku_top_clientes(sku: str, limit: int = Query(10, ge=1, le=100)):
    """
    Top clientes por SKU (ranking por unidades), basado en v_hist_ventas.
    """
    from app.main import cfg, get_conn

    sql = """
    SELECT
      ClienteN,
      ClienteNombre,
      COUNT(DISTINCT FAC) AS N_FAC,
      SUM(Qty) AS Units,
      SUM(Revenue_USD) AS Revenue_USD,
      SUM(Margin_USD) AS Margin_USD,
      MAX(Fecha) AS UltimaCompra
    FROM v_hist_ventas
    WHERE SKU = %s
    GROUP BY ClienteN, ClienteNombre
    ORDER BY Units DESC
    LIMIT %s;
    """
    try:
        with get_conn(cfg) as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cur:
                cur.execute(sql, (sku, limit))
                rows = cur.fetchall() or []
        for r in rows:
            r["N_FAC"] = int(r.get("N_FAC") or 0)
            r["Units"] = safe_float(r.get("Units"))
            r["Revenue_USD"] = safe_float(r.get("Revenue_USD"))
            r["Margin_USD"] = safe_float(r.get("Margin_USD"))
        return rows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"sku/{sku}/top_clientes error: {str(e)}")
