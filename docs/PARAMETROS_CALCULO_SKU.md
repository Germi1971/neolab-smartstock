# Parámetros del cálculo SmartStock por SKU

Listado completo de parámetros asociados al cálculo de sugerencias de compra, organizados por etapa del pipeline.

---

## 1. Parámetros de entrada (Features / Histórico)

| Parámetro | Origen | Descripción en el cálculo |
|----------|--------|----------------------------|
| **eventos_12m** | v_sku_features_12m / v_sku_classification_input | Número de transacciones (pedidos) en los últimos 12 meses. Define la frecuencia de demanda y alimenta λ (eventos/mes) para el Monte Carlo. |
| **unidades_12m** | v_sku_features_12m / v_sku_classification_input | Unidades vendidas en 12 meses. Base para Forecast_m y para calcular media por evento. |
| **q_mean_event** (mu_unidades_evento) | v_sku_features_12m | Media de unidades por transacción. Parámetro de la distribución Lognormal en la simulación MC. |
| **q_sd_event** (sigma_unidades_evento) | v_sku_features_12m | Desviación estándar del tamaño por evento. Define la variabilidad en la Lognormal. |
| **p_event** | Calculado: eventos_12m/12 | Probabilidad de que haya al menos un evento en un mes. Usado para inferir λ = -ln(1-p_event). |
| **Forecast_m** | unidades_12m/12 | Demanda mensual esperada. Cap para λ y base de criticidad automática. |
| **dias_observados** | v_sku_classification_input | Días con datos. Si < 180 → SKU NEW (lifecycle). |
| **days_since_last_sale** | v_sku_classification_input | Días desde última venta. Si > 180 y sin ventas 6m → DORMANT; si > 365 y sin ventas 12m → DEAD. |
| **unidades_6m** | v_sku_classification_input | Unidades vendidas en 6 meses. Usado en reglas de lifecycle (DORMANT). |
| **meses_con_venta_12m** | v_sku_features_12m | Meses con al menos una venta. Usado en ADI y para sku_activo. |
| **demanda_prom_mensual_12m** | v_sku_features_12m | Promedio mensual de demanda. Usado en Forecast_m y sku_activo. |
| **sigma_mensual_12m** | Vista MC-ready | Desviación estándar de demanda mensual. Usado en heurística de criticidad. |

---

## 2. Parámetros de clasificación (Demand Classification)

| Parámetro | Origen | Descripción en el cálculo |
|----------|--------|----------------------------|
| **ADI** (Average Demand Interval) | Calculado: meses_obs / meses_con_demanda | Mide regularidad de la demanda. ADI ≥ 1.32 → intermitente/lumpy. |
| **CV²** (Coeficiente de variación²) | Calculado: (std/mean)² por evento | Variabilidad del tamaño por evento. CV² ≥ 0.49 → erratic/lumpy. |
| **demand_class** | ss2_demand_classification | REGULAR, ERRATIC, INTERMITTENT, LUMPY. Define preferencia de modelo (analytic vs MC). |
| **lifecycle_state** | ss2_demand_classification | NEW, DORMANT, DEAD, ACTIVE. Prioridad sobre demand_class; DEAD/DORMANT excluyen de MC. |
| **cliente_dominante_flag** | ss2_demand_classification | 1 si top1_share ≥ 60%. Puede activar cap_cliente_dominante. |
| **accelerating_flag** | ss2_demand_classification | 1 si demanda 6m/24m ≥ 1.4. Usado en purchase scoring. |

---

## 3. Parámetros de Monte Carlo (Demand Engine)

| Parámetro | Origen | Descripción en el cálculo |
|----------|--------|----------------------------|
| **lambda_eventos_mes** | Inferido: -ln(1-p_event) o Forecast_m/q_mean | Tasa de eventos por mes. λ_total = λ × (horizon_days/30) para Poisson. |
| **horizon_days** | lt_days + review_days | Días de la simulación (LT + período hasta próxima revisión). |
| **lt_days** (LT) | parametros_sku.lead_time_days o LT_OPERATIVO_DEFAULT (60) | Lead time en días. Parte del horizonte. |
| **review_days** | parametros_sku o MC_REVIEW_DAYS_DEFAULT (120) | Días hasta próxima revisión. horizon = LT + review. |
| **n_sims** | MC_N_SIMS (default 8000) | Número de simulaciones Monte Carlo. |
| **demand_p50, demand_p80, demand_p90, demand_p95, demand_p97, demand_p99** | ss2_demand_cache | Percentiles de demanda en el horizonte. Política: CRITICO/ALTO/MEDIO → P90; BAJO → P80. |
| **p_stockout_at_current_stock** | ss2_demand_cache | P(demanda > stock actual). Usado en purchase scoring. |
| **mc_enabled** | Decisión: decide_mc() | 1 si se usa Monte Carlo; 0 → analytic_target (stock_objetivo paramétrico). |
| **regimen** | MC / classification | REGULAR, INTERMITENTE, NUEVO. Trazabilidad. |

---

## 4. Parámetros de criticidad y service level

| Parámetro | Origen | Descripción en el cálculo |
|----------|--------|----------------------------|
| **criticidad** | Heurística automática o parametros_sku | CRITICO, ALTO, MEDIO, BAJO. Política unificada: CRITICO/ALTO/MEDIO usan P90; BAJO usa P80. |
| **service_prob_usado** | Override o auto por criticidad | 0.97 (CRITICO), 0.95 (ALTO), 0.90 (MEDIO), 0.80 (BAJO). Nivel de servicio objetivo. |
| **SERVICE_CRITICO** | Env: 0.95 | Service level para SKUs críticos. |
| **SERVICE_IMPORTANTE** | Env: 0.90 | Service level para SKUs importantes. |
| **SERVICE_NO_CRITICO** | Env: 0.50 | Service level para SKUs no críticos. |

---

## 5. Parámetros del Policy Engine (decisión de stock objetivo)

| Parámetro | Origen | Descripción en el cálculo |
|----------|--------|----------------------------|
| **stock_objetivo** | parametros_sku | Objetivo paramétrico. Usado si mc_enabled=0 (analytic_target). |
| **demand_target_source** | Elegido por criticidad | demand_p90 (CRITICO/ALTO/MEDIO), demand_p80 (BAJO) o analytic_target. |
| **demand_target_value** | Percentil elegido | Valor del target antes de caps. |
| **cap_objetivo** (cap_hist) | parametros_sku | Límite máximo de stock objetivo. Si null, se usa cap_auto = ceil(CAP_AUTO_FACTOR × unidades_12m). |
| **cap_cliente_dominante** | parametros_sku | Cap adicional si cliente_dominante_flag=1. |
| **cap_vencimiento** | parametros_sku | Cap por vencimiento (productos perecederos). |
| **stock_posicion** (oferta_total) | v_stock_estado_unidades | stock_libre_deposito + impo_libre. Base para qty_recomendada = objetivo - oferta. |
| **stock_min** | parametros_sku | Stock mínimo. Usado en riesgo (BAJO_MIN) y estado operativo. |

---

## 6. Parámetros de compra (MOQ, múltiplo, caps)

| Parámetro | Origen | Descripción en el cálculo |
|----------|--------|----------------------------|
| **moq** (Minimum Order Quantity) | parametros_sku / sku_mc_cache | Cantidad mínima por orden. La qty_recomendada se redondea hacia arriba al MOQ. |
| **multiplo_compra** | parametros_sku / sku_mc_cache | Múltiplo de compra (ej. cajas de 6). La qty se redondea al múltiplo. |
| **q_cap** | parametros_sku / sku_mc_cache / auto | Límite máximo de unidades a recomendar por orden. Si no hay valor, puede calcularse como Q_CAP_MULTIPLE × Forecast_m. |
| **Q_CAP_MULTIPLE** | Env: 3 | Factor para q_cap automático: ceil(3 × Forecast_m). |

---

## 7. Parámetros de stock (estado actual)

| Parámetro | Origen | Descripción en el cálculo |
|----------|--------|----------------------------|
| **stock_libre_deposito** | v_stock_estado_unidades | Stock disponible en depósito. |
| **impo_libre** | v_stock_estado_unidades | Unidades en tránsito (importación) disponibles. |
| **oferta_total** | Calculado | stock_libre_deposito + impo_libre. Es el stock_posicion usado en el cálculo. |
| **stock_reservado_deposito** | v_stock_estado_unidades | Reservado (no disponible). |
| **impo_reservada** | v_stock_estado_unidades | Importación reservada. |

---

## 8. Parámetros de purchase scoring (priorización)

| Parámetro | Origen | Descripción en el cálculo |
|----------|--------|----------------------------|
| **priority_score** | purchase_scoring | Score 0-100. Combina: stockout (30%), criticidad (20%), LT (15%), acceleration (10%), margen (10%), backlog (10%), overstock (-10%), cliente (-5%). |
| **priority_band** | purchase_scoring | URGENTE (85-100), ALTA (70-84), MEDIA (55-69), BAJA (40-54), MUY_BAJA (<40). |
| **priority_reason** | purchase_scoring | Explicación textual de la prioridad. |

---

## 9. Variables de entorno (configuración global)

| Variable | Default | Descripción |
|---------|---------|-------------|
| **LT_OPERATIVO_DEFAULT** | 60 | Lead time por defecto (días) si no hay valor por SKU. |
| **MC_REVIEW_DAYS** | 120 | Días de revisión para horizonte MC. horizon = LT + review. |
| **MC_N_SIMS** | 8000 | Simulaciones Monte Carlo. |
| **SERVICE_CRITICO** | 0.95 | Service level para CRITICO. |
| **SERVICE_IMPORTANTE** | 0.90 | Service level para ALTO/IMPORTANTE. |
| **SERVICE_NO_CRITICO** | 0.50 | Service level para BAJO. |
| **Q_CAP_MULTIPLE** | 3 | Múltiplo para q_cap automático. |
| **SKU_OVERRIDE_TABLE** | sku_service_override | Tabla de overrides de service level por SKU. |
| **CAP_AUTO_FACTOR** | 1.5 | Factor para cap automático: stock objetivo ≤ ceil(factor × unidades_12m). |

---

## 10. Fórmula resumida de qty_recomendada

```
1. base_target = demand_p90 (CRITICO/ALTO/MEDIO) o demand_p80 (BAJO) o stock_objetivo (si mc_enabled=0)
2. cap_hist = cap_objetivo o ceil(CAP_AUTO_FACTOR × unidades_12m) si null
3. target_capped = min(base_target, cap_hist, cap_cliente, cap_vencimiento)
4. stock_objetivo_final = redondear(target_capped) con MOQ/múltiplo
5. qty_raw = max(0, stock_objetivo_final - oferta_total)
6. qty_recomendada = redondear(qty_raw) con MOQ/múltiplo, limitado por q_cap
```

---

## 11. Tablas/vistas que alimentan el cálculo

| Tabla/Vista | Rol |
|-------------|-----|
| **parametros_sku** | stock_min, stock_objetivo, cap_objetivo, cap_cliente_dominante, cap_vencimiento, moq, multiplo_compra, lead_time_days |
| **v_sku_features_12m** | eventos_12m, unidades_12m, q_mean_event, q_sd_event, p_event, Forecast_m |
| **v_sku_classification_input** | Input para demand_classification (eventos, unidades, mu, sigma, dias_obs, etc.) |
| **v_stock_estado_unidades** | stock_libre_deposito, impo_libre, oferta_total |
| **ss2_demand_classification** | demand_class, lifecycle_state, ADI, CV² |
| **ss2_demand_cache** | demand_p50/p80/p90/p95/p97/p99, mc_enabled, criticidad |
| **ss2_policy_results** | stock_objetivo_final, qty_recomendada_final, demand_target_source |
| **sku_mc_cache** | moq, multiplo_compra, q_cap (legacy/compatibilidad) |
| **ss2_purchase_scores** | priority_score, priority_band |
| **tablaprecios** | costo_unit (para impacto_usd) |
