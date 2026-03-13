# Queries for neobd.v_analisis_sku_excel_plus (vista base)

FETCH_ACTIVE_SKUS_SQL = """
SELECT
  sku,
  producto,
  category,
  sub_category,
  marca,
  fob_ref_usd,
  ServiceTarget,
  z,
  Mu_LT,
  Sigma_LT,
  LT_mean_m,
  LT_min_m,
  LT_max_m,
  PctZero,
  p_event,
  q_mean_event,
  q_sd_event,
  Forecast_m,
  sigma_mensual_12m,
  Model,
  stock_posicion,
  stock_min,
  stock_objetivo,
  moq,
  multiplo_compra,
  criticidad,
  tipo_demanda,
  activo,
  ABC_Class,
  XYZ_Class,
  PriorityScore
FROM neobd.v_analisis_sku_excel_plus
WHERE activo = 1;
"""

FETCH_ONE_SKU_SQL = """
SELECT
  sku,
  producto,
  category,
  sub_category,
  marca,
  fob_ref_usd,
  ServiceTarget,
  z,
  Mu_LT,
  Sigma_LT,
  LT_mean_m,
  LT_min_m,
  LT_max_m,
  PctZero,
  p_event,
  q_mean_event,
  q_sd_event,
  Forecast_m,
  sigma_mensual_12m,
  Model,
  stock_posicion,
  stock_min,
  stock_objetivo,
  moq,
  multiplo_compra,
  criticidad,
  tipo_demanda,
  activo,
  ABC_Class,
  XYZ_Class,
  PriorityScore
FROM neobd.v_analisis_sku_excel_plus
WHERE sku = %s
LIMIT 1;
"""

UPSERT_CACHE_SQL = """
INSERT INTO neobd.sku_mc_cache
(sku, n_sims, horizon_days, lt_days, review_days, lambda_eventos_mes, q_mean_event, q_sd_event, service_prob,
 mc_enabled, mc_reason,
 demand_p50, demand_p90, demand_p95, demand_p97, demand_p99,
 stock_objetivo_mc, qty_recomendada_mc, p_stockout, exp_lost_units,
 moq, multiplo_compra, q_cap, updated_at)
VALUES
(%s,%s,%s,%s,%s,%s,%s,%s,%s,
 %s,%s,
 %s,%s,%s,%s,%s,
 %s,%s,%s,%s,
 %s,%s,%s, NOW())
ON DUPLICATE KEY UPDATE
n_sims=VALUES(n_sims),
horizon_days=VALUES(horizon_days),
lt_days=VALUES(lt_days),
review_days=VALUES(review_days),
lambda_eventos_mes=VALUES(lambda_eventos_mes),
q_mean_event=VALUES(q_mean_event),
q_sd_event=VALUES(q_sd_event),
service_prob=VALUES(service_prob),
mc_enabled=VALUES(mc_enabled),
mc_reason=VALUES(mc_reason),
demand_p50=VALUES(demand_p50),
demand_p90=VALUES(demand_p90),
demand_p95=VALUES(demand_p95),
demand_p97=VALUES(demand_p97),
demand_p99=VALUES(demand_p99),
stock_objetivo_mc=VALUES(stock_objetivo_mc),
qty_recomendada_mc=VALUES(qty_recomendada_mc),
p_stockout=VALUES(p_stockout),
exp_lost_units=VALUES(exp_lost_units),
moq=VALUES(moq),
multiplo_compra=VALUES(multiplo_compra),
q_cap=VALUES(q_cap),
updated_at=NOW();
"""

FETCH_CACHE_SQL = """
SELECT *
FROM neobd.sku_mc_cache
WHERE sku = %s
LIMIT 1;
"""

TOP_STOCKOUT_SQL = """
SELECT sku, mc_enabled, p_stockout, exp_lost_units, qty_recomendada_mc, stock_objetivo_mc, mc_reason, updated_at
FROM neobd.sku_mc_cache
ORDER BY p_stockout DESC, exp_lost_units DESC
LIMIT %s;
"""
