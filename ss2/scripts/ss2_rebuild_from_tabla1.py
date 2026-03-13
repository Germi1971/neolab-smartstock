# ss2_rebuild_from_tabla1.py
# SS2 - rebuild/cdc desde tabla1 + stock views + demand features (12m)
#
# ✅ Corrección clave: distinguir PO-lines (E/S='IMPO') vs item-lines (E/S='IMPO - ...')
# ✅ Guarda qty en ss2_inv_event (además de details_json)
#
# ✅ CAMBIO (OPCIÓN A - DEFINITIVO):
#    - NO se calculan features desde ss2_sales_fact / monthly.
#    - NO se hace recompute_q_event_stats parcial.
#    - Features 12m = 100% desde ss2_inv_event vía SP:
#         CALL sp_ss2_sku_features_12m_refresh(p_asof)
#
#    Esto elimina para siempre la inconsistencia de:
#      events_12m=0 / total_units_12m=0 con q_mean_event > 0.

import os
import json
import datetime as dt
from typing import Dict, Any, Optional, Tuple, List

import pymysql
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "190.228.29.65")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "neolab")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "CHANGE_ME")  # ⚠️ NO pegues el real
MYSQL_DB = os.getenv("MYSQL_DB", "neobd")

PREFIX = os.getenv("SS2_PREFIX", "ss2_")

T_TABLA1 = "tabla1"
T_CDC = f"{PREFIX}cdc_tabla1"
T_EVENT = f"{PREFIX}inv_event"
T_ITEM = f"{PREFIX}inv_item"
T_PO = f"{PREFIX}po_line"

V_IMPO_STALE = f"{PREFIX}v_impo_stale"
V_STOCK = f"{PREFIX}v_stock"

SP_FEATURES_REFRESH = "sp_ss2_sku_features_12m_refresh"


# -------------------------
# Helpers
# -------------------------
def now() -> dt.datetime:
    return dt.datetime.now()


def norm_str(x: Optional[str]) -> str:
    return (x or "").strip()


def norm_es(es: Optional[str]) -> str:
    return norm_str(es)


def es_upper(es: Optional[str]) -> str:
    return norm_str(es).upper()


def has_uid(uid: Optional[str]) -> bool:
    return bool(uid and str(uid).strip())


def is_po_line(row: Dict[str, Any]) -> bool:
    """
    PO line = orden de compra agregada al proveedor:
    - E/S exactamente 'IMPO'
    - no tiene UID (no es item individual)
    """
    return (es_upper(row.get("es")) == "IMPO") and (not has_uid(row.get("uid")))


def is_impo_family(es: str) -> bool:
    """
    Para status ON_ORDER: cualquier cosa que arranque con IMPO (IMPO, IMPO - R, IMPO - STOCK, etc.)
    """
    return es_upper(es).startswith("IMPO")


def safe_int(x: Any, default: int = 0) -> int:
    try:
        if x is None:
            return default
        if isinstance(x, (int, float)):
            return int(x)
        s = str(x).strip()
        if s == "":
            return default
        return int(float(s))
    except Exception:
        return default


def safe_dt(x: Any) -> Optional[dt.datetime]:
    if x is None:
        return None
    if isinstance(x, dt.datetime):
        return x
    if isinstance(x, dt.date):
        return dt.datetime.combine(x, dt.time.min)
    # si viene como string, lo deja pasar (pymysql suele parsear DATETIME/DATE)
    return None


def map_es_to_event(prev_es: str, new_es: str) -> str:
    """
    Esto aplica a item-lines (no PO-lines).
    """
    p = es_upper(prev_es)
    n = es_upper(new_es)

    # Excepciones
    if n in ("ANULADO", "ANULADA"):
        return "CANCEL"
    if n in ("V", "VENCIDO", "VENCIDA"):
        return "SCRAP"
    if n in ("EXTRAVIADO", "PERDIDO", "LOST"):
        return "LOST"

    # Flujo típico items
    # (cuando un item pasa de IMPO* a E => RECEIVE)
    if is_impo_family(p) and n == "E":
        return "RECEIVE"
    if n == "R" and p != "R":
        return "RESERVE"
    if p == "R" and n in ("E", "STOCK"):
        return "RELEASE"
    if n == "S":
        return "SHIP"

    return "INFO_CHANGE"


def map_es_to_status(es: str) -> str:
    e = es_upper(es)

    if e == "S":
        return "SHIPPED"
    if e == "R":
        return "RESERVED"
    if e in ("ANULADO", "ANULADA"):
        return "CANCELLED"
    if e in ("V", "VENCIDO", "VENCIDA"):
        return "SCRAPPED"
    if e in ("EXTRAVIADO", "PERDIDO", "LOST"):
        return "LOST"
    if is_impo_family(e):
        return "ON_ORDER"
    return "ON_HAND"


# -------------------------
# DDL (tablas ss2_)
# -------------------------
DDL_TABLES = {
    T_CDC: f"""
    CREATE TABLE IF NOT EXISTS `{T_CDC}` (
      `id_inventario` INT NOT NULL PRIMARY KEY,
      `last_hash` VARCHAR(64) DEFAULT NULL,
      `last_fecha_actualizacion` DATETIME DEFAULT NULL,
      `last_es` VARCHAR(30) DEFAULT NULL,
      `last_uid` VARCHAR(50) DEFAULT NULL,
      `updated_at` DATETIME NOT NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    """,
    T_EVENT: f"""
    CREATE TABLE IF NOT EXISTS `{T_EVENT}` (
      `event_id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      `event_ts` DATETIME NOT NULL,
      `uid` VARCHAR(50) DEFAULT NULL,
      `sku` VARCHAR(50) DEFAULT NULL,
      `event_type` ENUM('PO_CREATE','PO_UPDATE','RECEIVE','MARK_FREE','RESERVE','RELEASE','SHIP','CANCEL','SCRAP','LOST','ADJUST','INFO_CHANGE') NOT NULL,
      `qty` INT DEFAULT NULL,
      `from_es` VARCHAR(30) DEFAULT NULL,
      `to_es` VARCHAR(30) DEFAULT NULL,
      `id_inventario` INT DEFAULT NULL,
      `impo` VARCHAR(20) DEFAULT NULL,
      `fac` VARCHAR(20) DEFAULT NULL,
      `rem` VARCHAR(20) DEFAULT NULL,
      `customer_no` INT DEFAULT NULL,
      `lot` VARCHAR(50) DEFAULT NULL,
      `location` VARCHAR(20) DEFAULT NULL,
      `details_json` TEXT,
      KEY `idx_event_ts` (`event_ts`),
      KEY `idx_uid` (`uid`),
      KEY `idx_sku` (`sku`),
      KEY `idx_idinventario` (`id_inventario`),
      KEY `idx_event_type` (`event_type`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    """,
    T_ITEM: f"""
    CREATE TABLE IF NOT EXISTS `{T_ITEM}` (
      `uid` VARCHAR(50) NOT NULL PRIMARY KEY,
      `sku` VARCHAR(50) NOT NULL,
      `lot` VARCHAR(50) DEFAULT NULL,
      `location` VARCHAR(20) DEFAULT NULL,
      `status` ENUM('ON_ORDER','ON_HAND','RESERVED','SHIPPED','CANCELLED','SCRAPPED','LOST') NOT NULL,
      `customer_no` INT DEFAULT NULL,
      `fac` VARCHAR(20) DEFAULT NULL,
      `rem` VARCHAR(20) DEFAULT NULL,
      `impo` VARCHAR(20) DEFAULT NULL,
      `id_inventario` INT DEFAULT NULL,
      `first_seen_at` DATETIME NOT NULL,
      `last_seen_at` DATETIME NOT NULL,
      KEY `idx_sku` (`sku`),
      KEY `idx_status` (`status`),
      KEY `idx_customer` (`customer_no`),
      KEY `idx_impo` (`impo`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    """,
    T_PO: f"""
    CREATE TABLE IF NOT EXISTS `{T_PO}` (
      `po_line_id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
      `impo` VARCHAR(20) NOT NULL,
      `sku` VARCHAR(50) NOT NULL,
      `qty_ordered` INT NOT NULL,
      `qty_received` INT NOT NULL DEFAULT 0,
      `status` ENUM('OPEN','PARTIAL','CLOSED','CANCELLED') NOT NULL DEFAULT 'OPEN',
      `created_at` DATETIME NOT NULL,
      `updated_at` DATETIME NOT NULL,
      UNIQUE KEY `uk_impo_sku` (`impo`,`sku`),
      KEY `idx_sku` (`sku`),
      KEY `idx_status` (`status`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    """,
}


# -------------------------
# Connection
# -------------------------
def get_conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8",
        autocommit=False,
        cursorclass=pymysql.cursors.DictCursor,
    )


def ensure_tables(conn):
    with conn.cursor() as cur:
        for ddl in DDL_TABLES.values():
            cur.execute(ddl)

        # si la tabla existía sin qty, lo agrega
        cur.execute(
            """
          SELECT COUNT(*) AS n
          FROM INFORMATION_SCHEMA.COLUMNS
          WHERE TABLE_SCHEMA = DATABASE()
            AND TABLE_NAME = %s
            AND COLUMN_NAME = 'qty'
        """,
            (T_EVENT,),
        )
        if int(cur.fetchone()["n"]) == 0:
            cur.execute(f"ALTER TABLE `{T_EVENT}` ADD COLUMN `qty` INT DEFAULT NULL AFTER `event_type`;")

        # Validación simple: que exista el SP que vamos a llamar (si no existe, falla temprano)
        cur.execute(
            """
          SELECT COUNT(*) AS n
          FROM information_schema.ROUTINES
          WHERE ROUTINE_SCHEMA = DATABASE()
            AND ROUTINE_TYPE='PROCEDURE'
            AND ROUTINE_NAME = %s
        """,
            (SP_FEATURES_REFRESH,),
        )
        if int(cur.fetchone()["n"]) == 0:
            raise RuntimeError(
                f"No existe el stored procedure {SP_FEATURES_REFRESH}. "
                f"Crealo en MySQL antes de correr este script."
            )


# -------------------------
# CDC fetch
# -------------------------
def fetch_changed_rows(conn, limit: int = 200000) -> List[Dict[str, Any]]:
    sql = f"""
    SELECT
      t.`ID inventario` AS id_inventario,
      t.`Hash` AS row_hash,
      t.`fecha_actualizacion` AS fecha_actualizacion,
      t.`E/S` AS es,
      t.`UID` AS uid,
      t.`Código` AS sku,
      t.`Lot` AS lot,
      t.`Location` AS location,
      t.`Cliente N°` AS customer_no,
      t.`IMPO` AS impo,
      t.`FAC` AS fac,
      t.`REM` AS rem,
      t.`Cantidad` AS cantidad,
      c.last_hash AS last_hash,
      c.last_es AS last_es,
      c.last_uid AS last_uid
    FROM `{T_TABLA1}` t
    LEFT JOIN `{T_CDC}` c ON c.id_inventario = t.`ID inventario`
    WHERE (c.id_inventario IS NULL)
       OR (IFNULL(c.last_hash,'') <> IFNULL(t.`Hash`,''))
    ORDER BY t.`fecha_actualizacion` ASC
    LIMIT %s
    """
    with conn.cursor() as cur:
        cur.execute(sql, (limit,))
        return list(cur.fetchall())


def upsert_cdc(conn, row: Dict[str, Any]):
    sql = f"""
    INSERT INTO `{T_CDC}`
      (id_inventario, last_hash, last_fecha_actualizacion, last_es, last_uid, updated_at)
    VALUES
      (%s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      last_hash=VALUES(last_hash),
      last_fecha_actualizacion=VALUES(last_fecha_actualizacion),
      last_es=VALUES(last_es),
      last_uid=VALUES(last_uid),
      updated_at=VALUES(updated_at)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                row["id_inventario"],
                row.get("row_hash"),
                row.get("fecha_actualizacion"),
                row.get("es"),
                row.get("uid"),
                now(),
            ),
        )


# -------------------------
# Writes: events, items, PO
# -------------------------
def insert_event(
    conn,
    *,
    event_ts: dt.datetime,
    uid: Optional[str],
    sku: Optional[str],
    event_type: str,
    qty: Optional[int],
    from_es: Optional[str],
    to_es: Optional[str],
    id_inventario: int,
    impo: Optional[str],
    fac: Optional[str],
    rem: Optional[str],
    customer_no: Optional[int],
    lot: Optional[str],
    location: Optional[str],
    details: Dict[str, Any],
):
    sql = f"""
    INSERT INTO `{T_EVENT}`
      (event_ts, uid, sku, event_type, qty, from_es, to_es, id_inventario, impo, fac, rem, customer_no, lot, location, details_json)
    VALUES
      (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                event_ts,
                uid,
                sku,
                event_type,
                qty,
                from_es,
                to_es,
                id_inventario,
                impo,
                fac,
                rem,
                customer_no,
                lot,
                location,
                json.dumps(details, ensure_ascii=False),
            ),
        )


def upsert_inv_item(conn, row: Dict[str, Any]):
    uid = norm_str(row.get("uid"))
    if not uid:
        return

    status = map_es_to_status(norm_es(row.get("es")))
    ts = row.get("fecha_actualizacion") or now()

    sql = f"""
    INSERT INTO `{T_ITEM}`
      (uid, sku, lot, location, status, customer_no, fac, rem, impo, id_inventario, first_seen_at, last_seen_at)
    VALUES
      (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    ON DUPLICATE KEY UPDATE
      sku=VALUES(sku),
      lot=VALUES(lot),
      location=VALUES(location),
      status=VALUES(status),
      customer_no=VALUES(customer_no),
      fac=VALUES(fac),
      rem=VALUES(rem),
      impo=VALUES(impo),
      id_inventario=VALUES(id_inventario),
      last_seen_at=VALUES(last_seen_at)
    """
    with conn.cursor() as cur:
        cur.execute(
            sql,
            (
                uid,
                row.get("sku"),
                row.get("lot"),
                row.get("location"),
                status,
                row.get("customer_no"),
                row.get("fac"),
                row.get("rem"),
                row.get("impo"),
                row.get("id_inventario"),
                ts,  # first_seen_at (si ya existe, no cambia)
                ts,  # last_seen_at
            ),
        )


def upsert_po_line_from_impo(conn, row: Dict[str, Any], *, is_new: bool):
    """
    SOLO PO line: E/S='IMPO' y sin UID.
    """
    if not is_po_line(row):
        return

    impo = norm_str(row.get("impo"))
    sku = norm_str(row.get("sku"))
    qty = safe_int(row.get("cantidad"), 0)

    if not impo or not sku or qty <= 0:
        return

    ts = row.get("fecha_actualizacion") or now()

    sql = f"""
    INSERT INTO `{T_PO}` (impo, sku, qty_ordered, qty_received, status, created_at, updated_at)
    VALUES (%s, %s, %s, 0, 'OPEN', %s, %s)
    ON DUPLICATE KEY UPDATE
      qty_ordered=VALUES(qty_ordered),
      updated_at=VALUES(updated_at)
    """
    with conn.cursor() as cur:
        cur.execute(sql, (impo, sku, qty, ts, ts))


def process_changes(conn, changed_rows: List[Dict[str, Any]]) -> Tuple[int, int]:
    n_events, n_items = 0, 0

    for r in changed_rows:
        prev_es = norm_es(r.get("last_es"))
        new_es = norm_es(r.get("es"))

        is_new = r.get("last_hash") is None

        # 1) PO line upsert si corresponde
        upsert_po_line_from_impo(conn, r, is_new=is_new)

        # 2) determinar evento + qty
        event_ts = r.get("fecha_actualizacion") or now()

        # qty raw de tabla1 (solo relevante para PO line)
        cantidad_raw = safe_int(r.get("cantidad"), 0)

        if is_po_line(r):
            # PO event: CREATE vs UPDATE
            event_type = "PO_CREATE" if is_new else "PO_UPDATE"
            event_qty = max(1, cantidad_raw)  # qty real de la orden
        else:
            # item event: qty siempre 1 (item individual)
            es_changed = es_upper(prev_es) != es_upper(new_es)
            event_type = map_es_to_event(prev_es, new_es) if es_changed else "INFO_CHANGE"
            event_qty = 1

        insert_event(
            conn,
            event_ts=event_ts,
            uid=(norm_str(r.get("uid")) or None),
            sku=(norm_str(r.get("sku")) or None),
            event_type=event_type,
            qty=event_qty,
            from_es=(prev_es or None),
            to_es=(new_es or None),
            id_inventario=int(r["id_inventario"]),
            impo=r.get("impo"),
            fac=r.get("fac"),
            rem=r.get("rem"),
            customer_no=r.get("customer_no"),
            lot=r.get("lot"),
            location=r.get("location"),
            details={
                "cantidad": r.get("cantidad"),
                "note": "Generated from tabla1 change detection",
                "is_po_line": bool(is_po_line(r)),
            },
        )
        n_events += 1

        # 3) estado actual por UID (solo si hay UID)
        if has_uid(r.get("uid")):
            upsert_inv_item(conn, r)
            n_items += 1

        # 4) CDC
        upsert_cdc(conn, r)

    return n_events, n_items


# -------------------------
# Autocorrección PO: qty_received + status
# -------------------------
def recompute_po_received(conn):
    """
    Como tus UIDs mantienen IMPO, calculamos qty_received real desde ss2_inv_item.
    """
    sql = f"""
    UPDATE `{T_PO}` p
    LEFT JOIN (
      SELECT
        impo,
        sku,
        COUNT(*) AS qty_received_calc
      FROM `{T_ITEM}`
      WHERE COALESCE(impo,'') <> ''
        AND status IN ('ON_HAND','RESERVED','SHIPPED')
      GROUP BY impo, sku
    ) r ON r.impo = p.impo AND r.sku = p.sku
    SET
      p.qty_received = IFNULL(r.qty_received_calc, 0),
      p.status = CASE
        WHEN IFNULL(r.qty_received_calc,0) <= 0 THEN 'OPEN'
        WHEN IFNULL(r.qty_received_calc,0) < p.qty_ordered THEN 'PARTIAL'
        ELSE 'CLOSED'
      END,
      p.updated_at = NOW()
    """
    with conn.cursor() as cur:
        cur.execute(sql)


# -------------------------
# Views: stale + stock definitivo (MySQL 5.5 safe)
# -------------------------
def ensure_views(conn):
    with conn.cursor() as cur:
        # 1) ss2_v_impo_stale
        cur.execute(f"DROP VIEW IF EXISTS `{V_IMPO_STALE}`")
        cur.execute(
            f"""
        CREATE VIEW `{V_IMPO_STALE}` AS
        SELECT
          t.`IMPO` AS impo,
          t.`Código` AS sku,
          COUNT(*) AS n_lines,
          SUM(CASE WHEN COALESCE(t.`UID`, '') = '' THEN 1 ELSE 0 END) AS lines_without_uid,
          MIN(t.`Fecha`) AS first_date,
          MAX(t.`Fecha`) AS last_date
        FROM `{T_TABLA1}` t
        WHERE UPPER(TRIM(t.`E/S`)) = 'IMPO'
          AND COALESCE(t.`IMPO`, '') <> ''
          AND COALESCE(t.`Código`, '') <> ''
        GROUP BY t.`IMPO`, t.`Código`
        HAVING MAX(t.`Fecha`) < DATE_SUB(CURDATE(), INTERVAL 60 DAY)
        """
        )

        # 2) items agregados por sku
        cur.execute("DROP VIEW IF EXISTS ss2_v_item_agg")
        cur.execute(
            f"""
        CREATE VIEW ss2_v_item_agg AS
        SELECT
          i.sku,
          SUM(CASE WHEN i.status IN ('ON_HAND','RESERVED') THEN 1 ELSE 0 END) AS on_hand,
          SUM(CASE WHEN i.status = 'RESERVED' THEN 1 ELSE 0 END) AS reserved
        FROM `{T_ITEM}` i
        GROUP BY i.sku
        """
        )

        # 3) on_order por sku
        cur.execute("DROP VIEW IF EXISTS ss2_v_po_on_order")
        cur.execute(
            f"""
        CREATE VIEW ss2_v_po_on_order AS
        SELECT
          p.sku,
          SUM(
            CASE
              WHEN p.status IN ('OPEN','PARTIAL') THEN (p.qty_ordered - p.qty_received)
              ELSE 0
            END
          ) AS on_order
        FROM `{T_PO}` p
        GROUP BY p.sku
        """
        )

        # 4) cantidad de POs abiertas por sku
        cur.execute("DROP VIEW IF EXISTS ss2_v_po_open_count")
        cur.execute(
            f"""
        CREATE VIEW ss2_v_po_open_count AS
        SELECT
          p.sku,
          SUM(CASE WHEN p.status IN ('OPEN','PARTIAL') THEN 1 ELSE 0 END) AS impo_open_count
        FROM `{T_PO}` p
        GROUP BY p.sku
        """
        )

        # 5) flag stale por sku
        cur.execute("DROP VIEW IF EXISTS ss2_v_impo_stale_sku")
        cur.execute(
            f"""
        CREATE VIEW ss2_v_impo_stale_sku AS
        SELECT
          sku,
          1 AS impo_stale_flag
        FROM `{V_IMPO_STALE}`
        GROUP BY sku
        """
        )

        # 6) universo de skus (items + po_line + catálogo)
        cur.execute("DROP VIEW IF EXISTS ss2_v_sku_universe")
        cur.execute(
            f"""
        CREATE VIEW ss2_v_sku_universe AS
        SELECT sku FROM ss2_v_item_agg
        UNION
        SELECT sku FROM `{T_PO}`
        UNION
        SELECT tp.`Product Number` AS sku FROM tablaprecios tp WHERE COALESCE(tp.`Product Number`,'') <> ''
        """
        )

        # 7) ss2_v_stock definitivo
        cur.execute(f"DROP VIEW IF EXISTS `{V_STOCK}`")
        cur.execute(
            f"""
        CREATE VIEW `{V_STOCK}` AS
        SELECT
          u.sku,
          IFNULL(i.on_hand, 0) AS on_hand,
          IFNULL(i.reserved, 0) AS reserved,
          (IFNULL(i.on_hand, 0) - IFNULL(i.reserved, 0)) AS available,
          IFNULL(o.on_order, 0) AS on_order,
          ((IFNULL(i.on_hand, 0) - IFNULL(i.reserved, 0)) + IFNULL(o.on_order, 0)) AS virtual_available,
          IFNULL(oc.impo_open_count, 0) AS impo_open_count,
          IFNULL(st.impo_stale_flag, 0) AS impo_stale_flag
        FROM ss2_v_sku_universe u
        LEFT JOIN ss2_v_item_agg i ON i.sku = u.sku
        LEFT JOIN ss2_v_po_on_order o ON o.sku = u.sku
        LEFT JOIN ss2_v_po_open_count oc ON oc.sku = u.sku
        LEFT JOIN ss2_v_impo_stale_sku st ON st.sku = u.sku
        """
        )

        # 8) stock enriched (catálogo + stock)
        cur.execute("DROP VIEW IF EXISTS ss2_v_stock_enriched")
        cur.execute(
            """
        CREATE VIEW ss2_v_stock_enriched AS
        SELECT
          s.sku,
          tp.`Item Description`        AS item_description,
          tp.`Marca`                   AS marca,
          tp.`Category`                AS category,
          tp.`Sub-Category`            AS sub_category,
          s.on_hand,
          s.reserved,
          s.available,
          s.on_order,
          s.virtual_available,
          s.impo_open_count,
          s.impo_stale_flag
        FROM ss2_v_stock s
        LEFT JOIN tablaprecios tp
          ON tp.`Product Number` = s.sku
        """
        )

        # 9) vista API friendly (con flags)
        cur.execute("DROP VIEW IF EXISTS ss2_v_stock_api")
        cur.execute(
            """
        CREATE VIEW ss2_v_stock_api AS
        SELECT
          s.sku,
          s.item_description,
          s.marca,
          s.category,
          s.sub_category,
          s.on_hand,
          s.reserved,
          s.available,
          s.on_order,
          s.virtual_available,
          s.impo_open_count,
          s.impo_stale_flag,
          CASE
            WHEN s.available <= 0 AND s.on_order > 0 THEN 'STOCKOUT_ONORDER'
            WHEN s.available <= 0 THEN 'STOCKOUT'
            WHEN s.available <= 2 THEN 'LOW'
            ELSE 'OK'
          END AS stock_status,
          CASE
            WHEN s.impo_stale_flag = 1 THEN 'STALE'
            WHEN s.on_order > 0 THEN 'ON_ORDER'
            ELSE 'NONE'
          END AS supply_status,
          CASE
            WHEN (s.available <= 0) OR (s.impo_stale_flag = 1) THEN 1
            ELSE 0
          END AS needs_attention
        FROM ss2_v_stock_enriched s
        """
        )


# -------------------------
# Daily snapshot table (API-friendly)
# -------------------------
def ensure_daily_table(conn):
    sql = """
    CREATE TABLE IF NOT EXISTS ss2_stock_daily (
      snapshot_date DATE NOT NULL,
      sku VARCHAR(50) NOT NULL,

      item_description VARCHAR(255) DEFAULT NULL,
      marca VARCHAR(60) DEFAULT NULL,
      category VARCHAR(100) DEFAULT NULL,
      sub_category VARCHAR(100) DEFAULT NULL,

      on_hand INT NOT NULL,
      reserved INT NOT NULL,
      available INT NOT NULL,
      on_order INT NOT NULL,
      virtual_available INT NOT NULL,

      impo_open_count INT NOT NULL,
      impo_stale_flag TINYINT(1) NOT NULL,

      stock_status VARCHAR(20) NOT NULL,
      supply_status VARCHAR(20) NOT NULL,
      needs_attention TINYINT(1) NOT NULL,

      created_at DATETIME NOT NULL,

      PRIMARY KEY (snapshot_date, sku),
      KEY idx_sku (sku),
      KEY idx_snapshot_date (snapshot_date),
      KEY idx_attention (needs_attention)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    """
    with conn.cursor() as cur:
        cur.execute(sql)


def upsert_daily_snapshot(conn):
    sql = """
    INSERT INTO ss2_stock_daily (
      snapshot_date, sku,
      item_description, marca, category, sub_category,
      on_hand, reserved, available, on_order, virtual_available,
      impo_open_count, impo_stale_flag,
      stock_status, supply_status, needs_attention,
      created_at
    )
    SELECT
      CURDATE() AS snapshot_date,
      sku,
      item_description, marca, category, sub_category,
      on_hand, reserved, available, on_order, virtual_available,
      impo_open_count, impo_stale_flag,
      stock_status, supply_status, needs_attention,
      NOW() AS created_at
    FROM ss2_v_stock_api
    ON DUPLICATE KEY UPDATE
      item_description=VALUES(item_description),
      marca=VALUES(marca),
      category=VALUES(category),
      sub_category=VALUES(sub_category),
      on_hand=VALUES(on_hand),
      reserved=VALUES(reserved),
      available=VALUES(available),
      on_order=VALUES(on_order),
      virtual_available=VALUES(virtual_available),
      impo_open_count=VALUES(impo_open_count),
      impo_stale_flag=VALUES(impo_stale_flag),
      stock_status=VALUES(stock_status),
      supply_status=VALUES(supply_status),
      needs_attention=VALUES(needs_attention),
      created_at=VALUES(created_at);
    """
    with conn.cursor() as cur:
        cur.execute(sql)


# -------------------------
# Demand Features (12m) - SP (SS2 puro)
# -------------------------
def refresh_features_12m(conn, asof: Optional[dt.date] = None):
    """
    ✅ ÚNICA fuente de verdad: ss2_inv_event.
    Llama al stored procedure sp_ss2_sku_features_12m_refresh(p_asof).
    """
    asof_date = asof or dt.date.today()
    with conn.cursor() as cur:
        cur.execute(f"CALL {SP_FEATURES_REFRESH}(%s);", (asof_date,))


# -------------------------
# Main
# -------------------------
def main():
    conn = get_conn()
    try:
        ensure_tables(conn)

        changed = fetch_changed_rows(conn, limit=200000)
        n_events = n_items = 0
        if changed:
            n_events, n_items = process_changes(conn, changed)

        # Autocorrección PO (clave para que on_order sea confiable)
        recompute_po_received(conn)

        # Views definitivas (stock)
        ensure_views(conn)

        # ✅ Features 12m (SS2 puro): SOLO SP desde ss2_inv_event
        refresh_features_12m(conn, asof=dt.date.today())

        # Daily snapshot
        ensure_daily_table(conn)
        upsert_daily_snapshot(conn)

        conn.commit()
        print(f"OK. Changes={len(changed)}  events={n_events}  items_upserted={n_items}")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()