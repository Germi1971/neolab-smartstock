"""
Tests del Policy Engine - Casos de validación funcional.

Caso 1 — Regular estable: MC apagado, analytic target, qty lógica
Caso 2 — Intermitente con historia: MC encendido, P95/P90, caps
Caso 3 — Intermitente sin historia: MC apagado por gate, fallback analítico
Caso 4 — Cliente dominante: target recortado por cap cliente
Caso 5 — Producto con vencimiento: target recortado por cap vencimiento
Caso 6 — MOQ alto: target redondeado correctamente
"""

import pytest
from app.policy_engine import (
    choose_service_level,
    choose_base_demand_target,
    apply_cap_hist,
    apply_cap_cliente,
    apply_cap_vencimiento,
    apply_caps,
    apply_moq_rounding,
    calculate_policy_for_sku,
)


# --- Caso 1: Regular estable, MC apagado ---
def test_caso1_regular_mc_apagado():
    row = {
        "sku": "SKU-REG-001",
        "stock_objetivo": 50,
        "stock_min": 10,
        "mc_enabled": 0,
        "criticidad": "MEDIO",
        "stock_posicion": 30,
        "cap_objetivo": None,
        "moq": 1,
        "multiplo_compra": 1,
        "q_cap": None,
    }
    res = calculate_policy_for_sku(row)
    assert res["demand_target_source"] == "analytic_target"
    assert res["base_demand_target"] == 50
    assert res["stock_objetivo_final"] == 50
    assert res["qty_recomendada_final"] == 20  # 50 - 30
    assert res["policy_reason"] == "ANALYTIC"


# --- Caso 2: Intermitente con historia, MC encendido ---
def test_caso2_intermitente_mc_encendido():
    row = {
        "sku": "SKU-INT-002",
        "stock_objetivo": 40,
        "stock_min": 8,
        "mc_enabled": 1,
        "criticidad": "ALTO",
        "demand_p50": 15,
        "demand_p80": 22,
        "demand_p90": 28,
        "demand_p95": 35,
        "demand_p99": 45,
        "stock_posicion": 10,
        "cap_objetivo": 50,
        "moq": 5,
        "multiplo_compra": 5,
        "q_cap": 30,
    }
    res = calculate_policy_for_sku(row)
    assert res["demand_target_source"] == "demand_p95"
    assert res["base_demand_target"] == 35
    assert res["stock_objetivo_final"] == 35
    assert res["qty_recomendada_final"] == 25  # 35-10, redondeado a múltiplo 5
    assert "MC:" in res["policy_reason"]


# --- Caso 3: Intermitente sin historia, MC apagado ---
def test_caso3_intermitente_sin_historia():
    row = {
        "sku": "SKU-NUEVO",
        "stock_objetivo": 20,
        "stock_min": 5,
        "mc_enabled": 0,
        "criticidad": "BAJO",
        "stock_posicion": 0,
        "cap_objetivo": None,
        "moq": 1,
        "multiplo_compra": 1,
    }
    res = calculate_policy_for_sku(row)
    assert res["demand_target_source"] == "analytic_target"
    assert res["base_demand_target"] == 20
    assert res["qty_recomendada_final"] == 20


# --- Caso 4: Cliente dominante (cap cliente) ---
def test_caso4_cap_cliente_dominante():
    row = {
        "sku": "SKU-CLIENTE",
        "stock_objetivo": 100,
        "stock_min": 20,
        "mc_enabled": 1,
        "criticidad": "ALTO",
        "demand_p95": 120,
        "stock_posicion": 0,
        "cap_objetivo": 200,
        "cap_cliente_dominante": 80,
        "moq": 10,
        "multiplo_compra": 10,
    }
    res = calculate_policy_for_sku(row)
    assert res["base_demand_target"] == 120
    assert res["stock_objetivo_final"] == 80
    assert "cap_cliente" in (res.get("applied_caps") or "")


# --- Caso 5: Producto con vencimiento ---
def test_caso5_cap_vencimiento():
    row = {
        "sku": "SKU-VENC",
        "stock_objetivo": 60,
        "stock_min": 10,
        "mc_enabled": 1,
        "criticidad": "MEDIO",
        "demand_p90": 70,
        "stock_posicion": 5,
        "cap_vencimiento": 40,
        "moq": 5,
        "multiplo_compra": 5,
    }
    res = calculate_policy_for_sku(row)
    assert res["base_demand_target"] == 70
    assert res["stock_objetivo_final"] == 40
    assert "cap_vencimiento" in (res.get("applied_caps") or "")


# --- Caso 6: MOQ alto ---
def test_caso6_moq_alto():
    row = {
        "sku": "SKU-MOQ",
        "stock_objetivo": 25,
        "stock_min": 5,
        "mc_enabled": 0,
        "criticidad": "BAJO",
        "stock_posicion": 8,
        "moq": 20,
        "multiplo_compra": 20,
        "q_cap": None,
    }
    res = calculate_policy_for_sku(row)
    # stock_objetivo_final = redondear(25) con MOQ 20 -> ceil(25/20)*20 = 40
    assert res["stock_objetivo_final"] == 40
    # qty = 40 - 8 = 32, redondeado a múltiplo 20 -> 40
    assert res["qty_recomendada_final"] == 40


# --- Helpers ---
def test_choose_service_level():
    assert choose_service_level("CRITICO") == 0.97
    assert choose_service_level("ALTO") == 0.95
    assert choose_service_level("MEDIO") == 0.90
    assert choose_service_level("BAJO") == 0.80
    assert choose_service_level("") == 0.80


def test_apply_cap_hist():
    t, msg = apply_cap_hist(100, {"cap_objetivo": 80})
    assert t == 80
    assert "cap_hist" in (msg or "")

    t, msg = apply_cap_hist(50, {"cap_objetivo": 80})
    assert t == 50
    assert msg is None


def test_apply_cap_cliente():
    t, msg = apply_cap_cliente(100, {"cap_cliente_dominante": 60})
    assert t == 60
    assert "cap_cliente" in (msg or "")


def test_apply_cap_vencimiento():
    t, msg = apply_cap_vencimiento(100, {"cap_vencimiento": 50})
    assert t == 50
    assert "cap_vencimiento" in (msg or "")


def test_apply_moq_rounding():
    row = {"moq": 10, "multiplo_compra": 10, "q_cap": 50}
    assert apply_moq_rounding(7, row) == 10
    assert apply_moq_rounding(23, row) == 30
    assert apply_moq_rounding(55, row) == 50  # q_cap


# --- Caso 7: CRITICO con demand_p97 ---
def test_caso7_critico_demand_p97():
    row = {
        "sku": "SKU-CRIT-97",
        "stock_objetivo": 30,
        "stock_min": 5,
        "mc_enabled": 1,
        "criticidad": "CRITICO",
        "demand_p90": 25,
        "demand_p95": 32,
        "demand_p97": 38,
        "demand_p99": 45,
        "stock_posicion": 10,
        "cap_objetivo": 100,
        "moq": 1,
        "multiplo_compra": 1,
    }
    res = calculate_policy_for_sku(row)
    assert res["demand_target_source"] == "demand_p97"
    assert res["base_demand_target"] == 38
    assert res["stock_objetivo_final"] == 38
    assert res["qty_recomendada_final"] == 28


def test_critico_fallback_p95_sin_p97():
    """CRITICO sin demand_p97 usa demand_p95 como fallback."""
    row = {
        "sku": "SKU-CRIT-FB",
        "mc_enabled": 1,
        "criticidad": "CRITICO",
        "demand_p95": 30,
        "stock_posicion": 0,
        "moq": 1,
        "multiplo_compra": 1,
    }
    res = calculate_policy_for_sku(row)
    assert res["demand_target_source"] == "demand_p95"
    assert res["base_demand_target"] == 30
