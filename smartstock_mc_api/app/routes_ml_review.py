import math
from typing import Any, Dict, Optional, List

import pymysql
from fastapi import APIRouter, Query

router = APIRouter()

DB_HOST = "190.228.29.65"
DB_USER = "neolab"
DB_PASS = "MYsql437626#"
DB_NAME = "neobd"


def get_db():
    return pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASS,
        database=DB_NAME,
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


def safe_float(x: Any, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def ceil_int(x: float) -> int:
    return int(math.ceil(x))


def round_to_multiple(qty: int, multiple: int) -> int:
    if multiple <= 1:
        return qty
    return int(math.ceil(qty / multiple) * multiple)


def service_default_by_criticidad(crit: Optional[str]) -> float:
    crit = (crit or "").upper()
    if crit == "ALTA":
        return 0.95
    if crit == "MEDIA":
        return 0.90
    if crit == "BAJA":
        return 0.85
    return 0.90


def months_cap_by_vencimiento(
    temp_storage: Optional[str],
    dias_min_antes_venc: Optional[int],
) -> Optional[int]:
    ts = (temp_storage or "").upper()
    if ts not in ("2-8", "-20"):
        return None

    d = dias_min_antes_venc
    if d is None:
        return 9
    if d <= 120:
        return 6
    if d <= 240:
        return 9
    return 12


def classify_and_recommend(row: Dict[str, Any]) -> Dict[str, Any]:
    sku = row["sku"]

    # flags
    activo = int(safe_float(row.get("activo"), 1.0)) == 1
    discontinuado = int(safe_float(row.get("discontinuado"), 0.0)) == 1

    clase = (row.get("clase_demanda") or "").upper()
    eventos_12m = safe_float(row.get("eventos_12m"))
    pct_meses = safe_float(row.get("pct_meses_con_venta_12m"))
    dem_prom = safe_float(row.get("demanda_prom_mensual_12m"))
    sig_m = safe_float(row.get("sigma_mensual_12m"))

    lead_time = safe_float(row.get("lead_time_dias"), 60.0)
    moq = int(safe_float(row.get("moq"), 1.0)) or 1
    mult = int(safe_float(row.get("multiplo_compra"), 1.0)) or 1

    criticidad = row.get("criticidad")
    temp_storage = row.get("temp_storage")
    dias_min_venc = row.get("dias_minimos_antes_vencimiento")

    unidades_24m = safe_float(row.get("unidades_totales_24m"))
    dom_share = safe_float(row.get("dominant_client_share"))

    cap_max_anual = safe_float(row.get("cap_max_anual"))
    tipo_demanda = (row.get("tipo_demanda") or "").upper()

    service = service_default_by_criticidad(criticidad)
    z = safe_float(row.get("z_servicio"), 1.65)

    # ========== Exclusiones ==========
    if (not activo) or discontinuado:
        return {
            "sku": sku,
            "modelo_recomendado": "NO_REPONER",
            "service_prob_usado": None,
            "cap_objetivo": None,
            "stock_min_recomendado": 0,
            "stock_objetivo_recomendado": 0,
            "debug": {"motivo": "inactivo/discontinuado"},
        }

    # ========== Régimen ==========
    if ("SIN_DATOS" in clase) or (eventos_12m < 2) or (unidades_24m < 2):
        modelo = "NEW_RULES"
        service = min(service, 0.85)
        cap_hist = max(moq, 2)

    else:
        # 1️⃣ REGULAR primero
        if ("REGULAR" in clase) and (pct_meses >= 0.50):
            modelo = "REGULAR_NORMAL"
            cap_hist = None

            # 🔁 Downgrade híbrido
            if (
                dom_share >= 0.70
                and tipo_demanda == "INTERMITENTE"
                and eventos_12m < 10
            ):
                modelo = "INTERMITENTE_CONTROLADO"
                service = min(service, 0.90)
                cap_hist = max(moq, ceil_int(unidades_24m * 0.80))

        # 2️⃣ Dominante no regular
        elif (dom_share >= 0.60) and (unidades_24m >= 6) and (eventos_12m >= 3):
            modelo = "INTERMITENTE_CONTROLADO"
            service = min(service, 0.90)
            cap_hist = max(moq, ceil_int(unidades_24m * 0.80))

        # 3️⃣ Intermitente estándar
        else:
            modelo = "INTERMITENTE_SBA"
            service = min(service, 0.90)
            cap_hist = (
                max(moq, ceil_int(unidades_24m * 0.90))
                if unidades_24m > 0
                else None
            )

    # ========== Objetivo base ==========
    LT_meses = max(0.5, lead_time / 30.0)
    E = dem_prom * LT_meses
    SD = sig_m * math.sqrt(LT_meses)

    if modelo == "REGULAR_NORMAL":
        target = ceil_int(E + z * SD)
    elif modelo in ("INTERMITENTE_CONTROLADO", "INTERMITENTE_SBA"):
        target = ceil_int(E + (z * SD) * 0.7)
    else:
        target = cap_hist if cap_hist is not None else max(moq, 2)

    # ========== Caps ==========
    cap_obj = cap_hist
    cap_cons_debug = None

    if dom_share >= 0.60 and tipo_demanda == "INTERMITENTE" and cap_max_anual > 0:
        cap_cons = int(math.floor(cap_max_anual * 0.80))
        cap_cons = max(cap_cons, moq)
        cap_cons = round_to_multiple(cap_cons, mult)
        cap_obj = cap_cons if cap_obj is None else min(cap_obj, cap_cons)
        cap_cons_debug = cap_cons

    mcap = months_cap_by_vencimiento(temp_storage, dias_min_venc)
    if mcap is not None and dem_prom > 0:
        cap_venc = max(moq, ceil_int(dem_prom * mcap))
        cap_venc = round_to_multiple(cap_venc, mult)
        cap_obj = cap_venc if cap_obj is None else min(cap_obj, cap_venc)

    if cap_obj is not None:
        target = min(target, int(cap_obj))

    target = max(target, moq)
    target = round_to_multiple(target, mult)
    stock_min = max(moq, round_to_multiple(ceil_int(E), mult))

    return {
        "sku": sku,
        "modelo_recomendado": modelo,
        "service_prob_usado": float(service),
        "cap_objetivo": int(cap_obj) if cap_obj is not None else None,
        "stock_min_recomendado": int(stock_min),
        "stock_objetivo_recomendado": int(target),
        "debug": {
            "criticidad": criticidad,
            "temp_storage": temp_storage,
            "dias_min_venc": dias_min_venc,
            "clase_demanda": row.get("clase_demanda"),
            "eventos_12m": eventos_12m,
            "pct_meses": pct_meses,
            "unidades_24m": unidades_24m,
            "dominant_share": dom_share,
            "tipo_demanda": tipo_demanda,
            "cap_max_anual": cap_max_anual,
            "cap_conservador_0_8": cap_cons_debug,
            "LT_meses": LT_meses,
            "E": E,
            "SD": SD,
            "z": z,
            "moq": moq,
            "multiplo": mult,
            "cap_hist": cap_hist,
            "cap_final": cap_obj,
        },
    }


@router.post("/ml/review/run")
def run_review(
    scope: str = Query("changed", pattern="^(changed|all)$"),
    dry_run: int = Query(0, ge=0, le=1),
    limit: int = Query(5000, ge=1, le=50000),
    response_limit: int = Query(50, ge=1, le=50000),
    sku: Optional[str] = Query(None),
):
    con = get_db()
    cur = con.cursor()

    if sku:
        cur.execute("SELECT sku, hash_actual FROM v_sku_review_hash WHERE sku=%s", (sku,))
        delta = cur.fetchall()
    else:
        if scope == "all":
            cur.execute("SELECT sku, hash_actual FROM v_sku_review_hash LIMIT %s", (limit,))
        else:
            cur.execute(
                """
                SELECT h.sku, h.hash_actual
                FROM v_sku_review_hash h
                LEFT JOIN sku_revision_state s ON s.sku = h.sku
                WHERE s.sku IS NULL OR s.hash_guardado <> h.hash_actual
                LIMIT %s
                """,
                (limit,),
            )
        delta = cur.fetchall()

    if not delta:
        return {"scope": scope, "dry_run": bool(dry_run), "reviewed": 0, "updated": 0, "items": []}

    hash_map = {d["sku"]: d["hash_actual"] for d in delta}
    items: List[Dict[str, Any]] = []
    updated = 0

    for sku_item in hash_map:
        cur.execute("SELECT * FROM v_sku_review_input_v3 WHERE sku=%s", (sku_item,))
        row = cur.fetchone()
        if not row:
            continue

        rec = classify_and_recommend(row)
        items.append(rec)

        if not dry_run:
            cur.execute(
                """
                UPDATE parametros_sku
                SET modelo_recomendado=%s,
                    service_prob_usado=%s,
                    cap_objetivo=%s,
                    stock_min=%s,
                    stock_objetivo=%s,
                    review_updated_at=NOW()
                WHERE sku=%s
                """,
                (
                    rec["modelo_recomendado"],
                    rec["service_prob_usado"],
                    rec["cap_objetivo"],
                    rec["stock_min_recomendado"],
                    rec["stock_objetivo_recomendado"],
                    sku_item,
                ),
            )

            cur.execute(
                """
                INSERT INTO sku_revision_state (sku, hash_guardado, last_review_at)
                VALUES (%s, %s, NOW())
                ON DUPLICATE KEY UPDATE
                  hash_guardado=VALUES(hash_guardado),
                  last_review_at=VALUES(last_review_at)
                """,
                (sku_item, hash_map[sku_item]),
            )
            updated += 1

    out = items[:response_limit]
    resp = {
        "scope": scope,
        "dry_run": bool(dry_run),
        "reviewed": len(items),
        "updated": updated,
        "items": out,
    }
    if len(items) > response_limit:
        resp["note"] = f"items truncado a {len(out)} (response_limit={response_limit})"
    return resp
