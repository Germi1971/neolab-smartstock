from typing import Dict, Any, Tuple

def decide_mc(row: Dict[str, Any]) -> Tuple[bool, str]:
    """Criterio MC usando campos disponibles en v_analisis_sku_excel_plus."""
    if int(row.get("activo") or 0) != 1:
        return False, "SKU inactivo"

    model = (row.get("Model") or "").upper()
    tipo_demanda = (row.get("tipo_demanda") or "").upper()
    pct_zero = row.get("PctZero")
    p_event = float(row.get("p_event") or 0.0)
    q_mean = float(row.get("q_mean_event") or 0.0)
    lt_days = float(row.get("Mu_LT") or 0.0)

    # mínimos de datos para simular
    if p_event <= 0 or q_mean <= 0:
        return False, f"Datos insuficientes p_event={p_event:.3f} q_mean={q_mean:.3f}"
    if lt_days <= 0:
        return False, "Datos insuficientes: Mu_LT<=0"

    # volatilidad mensual (si existe)
    forecast_m = float(row.get("Forecast_m") or 0.0)
    sigma_m = float(row.get("sigma_mensual_12m") or 0.0)
    cv_m = (sigma_m / forecast_m) if forecast_m > 0 else 0.0

    # riesgo por criticidad + prioridad
    criticidad = (row.get("criticidad") or "").upper()
    priority = float(row.get("PriorityScore") or 0.0)

    riesgo_ok = (lt_days >= 45) or (criticidad == "ALTA") or (priority >= 8)

    pct_zero_val = float(pct_zero) if pct_zero is not None else None
    intermitente_proxy = (
        ("INTERMIT" in model) or ("INTERMIT" in tipo_demanda)
        or (pct_zero_val is not None and pct_zero_val >= 0.40)
        or (p_event <= 0.40)
    )

    # REGULAR: MC solo si muy variable + riesgo
    if "REGULAR" in model or "NORMAL" in model:
        if cv_m >= 0.8 and riesgo_ok:
            return True, f"MC: REGULAR volátil CVm={cv_m:.2f} LT={int(lt_days)}d"
        return False, f"No MC: REGULAR CVm={cv_m:.2f}"

    # Intermitente: MC si hay riesgo
    if intermitente_proxy:
        if riesgo_ok:
            return True, f"MC: intermitencia (p={p_event:.2f} pct0={pct_zero_val}) + riesgo"
        return False, "No MC: intermitente pero riesgo bajo"

    return False, f"No MC: Model={model or 'N/A'}"
