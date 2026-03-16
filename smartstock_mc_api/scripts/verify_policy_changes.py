#!/usr/bin/env python
"""
Verificación rápida de los cambios en Policy Engine (P90 + cap_auto).
Ejecutar: python scripts/verify_policy_changes.py
"""
import sys
sys.path.insert(0, ".")

from app.policy_engine import (
    choose_base_demand_target,
    apply_cap_hist,
    calculate_policy_for_sku,
)

def main():
    errors = []
    
    # 1. CRITICO/ALTO usan P90 (no P97/P95)
    row = {"mc_enabled": 1, "criticidad": "CRITICO", "demand_p90": 25, "demand_p95": 35, "demand_p97": 40}
    val, src = choose_base_demand_target(row)
    assert src == "demand_p90" and val == 25, f"CRITICO debería usar P90=25, got {src}={val}"
    
    row = {"mc_enabled": 1, "criticidad": "ALTO", "demand_p90": 20, "demand_p95": 28}
    val, src = choose_base_demand_target(row)
    assert src == "demand_p90" and val == 20, f"ALTO debería usar P90=20, got {src}={val}"
    
    # 2. Cap automático: 1.5 × unidades_12m
    t, msg = apply_cap_hist(26, {"unidades_12m": 9})
    assert t == 14, f"Cap auto 9 uds: esperado 14, got {t}"
    assert "cap_hist" in (msg or ""), f"Debería indicar cap aplicado: {msg}"
    
    t, msg = apply_cap_hist(10, {"unidades_12m": 9})
    assert t == 10 and msg is None, f"Target 10 < cap 14: no recortar, got t={t} msg={msg}"
    
    # 3. Caso A102-100MG: 9 uds/año, stock 9
    row = {
        "sku": "A102-100MG",
        "mc_enabled": 1,
        "criticidad": "ALTO",
        "demand_p90": 15,
        "demand_p95": 26,
        "unidades_12m": 9,
        "stock_posicion": 9,
        "cap_objetivo": None,
        "moq": 1,
        "multiplo_compra": 1,
    }
    res = calculate_policy_for_sku(row)
    assert res["demand_target_source"] == "demand_p90", res["demand_target_source"]
    assert res["base_demand_target"] == 15, res["base_demand_target"]
    # cap_auto = 14, target 15 recortado a 14
    assert res["stock_objetivo_final"] == 14, res["stock_objetivo_final"]
    assert res["qty_recomendada_final"] == 5, res["qty_recomendada_final"]  # 14 - 9 = 5
    
    print("OK: Todas las verificaciones pasaron.")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except AssertionError as e:
        print(f"ERROR: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
