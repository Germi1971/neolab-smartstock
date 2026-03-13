-- Vista base (sin filtrar por fecha ni qty)
CREATE OR REPLACE VIEW ss2_v_suggested_purchases AS
SELECT
    r.asof_date AS asof_date,
    r.sku AS sku,
    e.item_description AS item_description,
    e.marca AS marca,
    e.category AS category,
    e.sub_category AS sub_category,
    r.model_code AS model_code,
    r.z AS z,
    r.lead_time_days AS lead_time_days,
    r.review_days AS review_days,
    r.stock_on_hand AS stock_on_hand,
    r.stock_reserved AS stock_reserved,
    r.stock_available AS stock_available,
    r.stock_on_order AS stock_on_order,
    r.stock_virtual AS stock_virtual,
    r.backlog_open_qty AS backlog_open_qty,
    r.effective_virtual AS effective_virtual,
    r.reorder_point AS reorder_point,
    r.target_level AS target_level,
    (r.effective_virtual - r.reorder_point) AS risk_gap,
    r.suggested_qty_rounded AS qty_to_buy,
    e.impo_open_count AS impo_open_count,
    e.impo_stale_flag AS impo_stale_flag,
    r.reason AS reason
FROM ss2_replenishment_plan r
LEFT JOIN ss2_v_stock_enriched e
    ON e.sku = r.sku;