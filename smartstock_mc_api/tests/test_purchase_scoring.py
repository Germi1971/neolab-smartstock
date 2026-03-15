"""
Tests del Smart Replenishment Score (SRS).
"""

import pytest
from app.purchase_scoring import (
    score_stockout,
    score_criticidad,
    score_lead_time,
    score_acceleration,
    score_backlog,
    penalty_overstock,
    penalty_cliente,
    calculate_priority_score,
)


def test_score_stockout_from_p_stockout():
    row = {"p_stockout_at_current_stock": 0.78}
    assert score_stockout(row) == 78.0


def test_score_stockout_fallback_stock_zero():
    row = {"stock_posicion": 0, "stock_min": 10, "stock_objetivo": 50}
    assert score_stockout(row) >= 90


def test_score_criticidad():
    assert score_criticidad({"criticidad": "CRITICO"}) == 100.0
    assert score_criticidad({"criticidad": "ALTO"}) == 80.0
    assert score_criticidad({"criticidad": "MEDIO"}) == 50.0
    assert score_criticidad({"criticidad": "BAJO"}) == 20.0


def test_score_lead_time():
    assert score_lead_time({"lt_days": 150}) == 100.0
    assert score_lead_time({"lt_days": 75}) == 70.0
    assert score_lead_time({"lt_days": 45}) == 45.0
    assert score_lead_time({"lt_days": 20}) == 20.0


def test_score_acceleration_with_ratio():
    row = {"demand_6m": 18, "demand_24m": 10}  # ratio 1.8
    assert score_acceleration(row) == 100.0

    row = {"demand_6m": 11, "demand_24m": 10}  # ratio 1.1
    assert score_acceleration(row) == 60.0


def test_score_backlog():
    row = {"backlog_qty": 50, "stock_posicion": 30}
    assert score_backlog(row) == 100.0

    row = {"backlog_qty": 0, "stock_posicion": 10}
    assert score_backlog(row) == 0.0


def test_penalty_overstock():
    row = {"stock_posicion": 200, "stock_objetivo_final": 100}
    assert penalty_overstock(row) == 100.0


def test_penalty_cliente():
    row = {"top1_share_12m": 0.90}
    assert penalty_cliente(row) == 50.0


def test_calculate_priority_score_m524_example():
    """Ejemplo conceptual M524-100L según especificación."""
    row = {
        "sku": "M524-100L",
        "p_stockout_at_current_stock": 0.78,
        "criticidad": "ALTO",
        "lt_days": 75,
        "demand_6m": 15.5,
        "demand_24m": 10.0,
        "stock_posicion": 10,
        "stock_objetivo_final": 50,
        "stock_min": 5,
        "backlog_qty": 2,
        "top1_share_12m": 0.68,
    }
    res = calculate_priority_score(row)
    assert res["sku"] == "M524-100L"
    assert res["stockout_score"] == 78.0
    assert res["criticidad_score"] == 80.0
    assert res["lead_time_score"] == 70.0
    assert res["acceleration_score"] == 80.0  # 15.5/10 = 1.55
    assert res["cliente_penalty"] == 20.0
    assert 50 <= res["priority_score"] <= 85
    assert res["priority_band"] in ("URGENTE", "ALTA", "MEDIA", "BAJA", "MUY_BAJA")


def test_priority_band_urgente():
    row = {
        "sku": "X",
        "p_stockout_at_current_stock": 0.95,
        "criticidad": "CRITICO",
        "lt_days": 120,
        "stock_posicion": 0,
        "stock_objetivo_final": 100,
    }
    res = calculate_priority_score(row)
    assert res["priority_band"] == "URGENTE"
    assert res["priority_score"] >= 85
