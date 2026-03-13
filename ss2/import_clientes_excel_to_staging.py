# import_clientes_excel_to_staging.py
# Lee BD1.xls (hoja "Clientes") y carga a MySQL en stg_clientes_excel
# Fix: headers en fila 3 (header=2) + autodetección robusta por "Cliente N°"

import os
import re
import sys
from typing import Optional, List, Tuple

import pandas as pd
import pymysql
from dotenv import load_dotenv

load_dotenv()

MYSQL_HOST = os.getenv("MYSQL_HOST", "190.228.29.65")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "neolab")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "CHANGE_ME")  # NO pegues el real
MYSQL_DB = os.getenv("MYSQL_DB", "neobd")


# -------------------------
# Limpieza / normalización
# -------------------------
def s(x) -> str:
    if x is None:
        return ""
    try:
        if isinstance(x, float) and pd.isna(x):
            return ""
        if pd.isna(x):
            return ""
    except Exception:
        pass
    return str(x).strip()


def norm_text(x, max_len: int) -> Optional[str]:
    v = s(x)
    return v[:max_len] if v else None


def norm_email(x) -> Optional[str]:
    v = s(x).lower()
    if not v or v in ("nan", "none", "null"):
        return None
    if "@" not in v:
        return None
    return v[:120]


def norm_phone(x) -> Optional[str]:
    v = s(x)
    if not v:
        return None
    v2 = re.sub(r"[^0-9+\-\s()]", "", v).strip()
    return v2[:50] if v2 else None


def norm_tax_id(x) -> Optional[str]:
    v = s(x)
    if not v:
        return None
    v = re.sub(r"\s+", "", v).replace(".", "")
    return v[:20] if v else None


def norm_vat_type(x) -> Optional[str]:
    v = s(x)
    return v[:40] if v else None


def to_int(x) -> Optional[int]:
    if x is None:
        return None
    try:
        if pd.isna(x):
            return None
    except Exception:
        pass
    if isinstance(x, int):
        return int(x)
    if isinstance(x, float):
        if x != x:
            return None
        return int(x)
    st = str(x).strip()
    if st == "":
        return None
    m = re.search(r"\d+", st)
    return int(m.group(0)) if m else None


def norm_colname(name: str) -> str:
    # normaliza espacios raros, dobles espacios, etc.
    n = (name or "").strip()
    n = re.sub(r"\s+", " ", n)
    return n


# -------------------------
# DB
# -------------------------
def get_conn():
    return pymysql.connect(
        host=MYSQL_HOST,
        port=MYSQL_PORT,
        user=MYSQL_USER,
        password=MYSQL_PASSWORD,
        database=MYSQL_DB,
        charset="utf8",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def ensure_staging(conn):
    # MySQL 5.5: DEFAULT CURRENT_TIMESTAMP ok para TIMESTAMP (no para DATETIME)
    ddl = """
    CREATE TABLE IF NOT EXISTS stg_clientes_excel (
      account_code INT,
      legal_name VARCHAR(150),
      vat_type VARCHAR(40),
      tax_id VARCHAR(20),
      email VARCHAR(120),
      telefono VARCHAR(50),
      atencion VARCHAR(160),
      contacto_1 VARCHAR(160),
      contacto_2 VARCHAR(160),
      contacto_3 VARCHAR(160),
      created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8;
    """
    with conn.cursor() as cur:
        cur.execute(ddl)


def clear_staging(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE stg_clientes_excel;")


def insert_rows(conn, rows: List[Tuple]):
    sql = """
    INSERT INTO stg_clientes_excel (
      account_code, legal_name, vat_type, tax_id, email, telefono, atencion,
      contacto_1, contacto_2, contacto_3
    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    with conn.cursor() as cur:
        cur.executemany(sql, rows)


# -------------------------
# Lectura Excel (autodetect header row)
# -------------------------
def find_header_row_xls(path_xls: str, sheet_name: str) -> int:
    """
    Devuelve índice 0-based del row que contiene headers reales.
    Busca 'Cliente N°' en las primeras 30 filas.
    """
    raw = pd.read_excel(path_xls, sheet_name=sheet_name, engine="xlrd", header=None)
    max_scan = min(len(raw), 30)

    for r in range(max_scan):
        vals = [norm_colname(s(v)) for v in raw.iloc[r].tolist()]
        if any(v.lower() == "cliente n°" or v.lower() == "cliente n°." or v.lower() == "cliente n° " for v in vals):
            return r

    # fallback típico: headers en fila 3 => índice 2
    return 2


def load_clientes_xls(path_xls: str, sheet_name: str = "Clientes") -> pd.DataFrame:
    hdr = find_header_row_xls(path_xls, sheet_name)
    df = pd.read_excel(path_xls, sheet_name=sheet_name, engine="xlrd", header=hdr)
    df.columns = [norm_colname(str(c)) for c in df.columns]
    return df


def pick_col(df: pd.DataFrame, *names: str) -> Optional[str]:
    """
    Devuelve el nombre de columna existente en df (primera coincidencia).
    """
    cols = {c.lower(): c for c in df.columns}
    for n in names:
        if n is None:
            continue
        key = norm_colname(n).lower()
        if key in cols:
            return cols[key]
    return None


def build_staging_rows(df: pd.DataFrame) -> List[Tuple]:
    c_cliente = pick_col(df, "Cliente N°", "Cliente N° ", "Cliente N°.")
    if not c_cliente:
        print("ERROR: No encuentro columna 'Cliente N°' aun con header autodetectado.")
        print("Columnas detectadas:", df.columns.tolist())
        return []

    c_facturar = pick_col(df, "Facturar a:", "Facturar a")
    c_enviar = pick_col(df, "Enviar a:", "Enviar a")
    c_iva = pick_col(df, "IVA Tipo", "IVA")
    c_cuit = pick_col(df, "CUIT N°", "CUIT", "Tax ID")
    c_email = pick_col(df, "email", "Email", "E-mail")
    c_tel = pick_col(df, "Telefono", "Teléfono", "Telefono ")
    c_at = pick_col(df, "Atención", "Atencion", "Atencion ")
    c_c1 = pick_col(df, "Contacto 1")
    c_c2 = pick_col(df, "Contacto 2")
    c_c3 = pick_col(df, "Contacto 3")

    rows: List[Tuple] = []
    skipped = 0

    for _, r in df.iterrows():
        account_code = to_int(r.get(c_cliente))
        if account_code is None:
            skipped += 1
            continue

        legal_name = norm_text(r.get(c_facturar) if c_facturar else None, 150)
        if not legal_name:
            legal_name = norm_text(r.get(c_enviar) if c_enviar else None, 150)

        vat_type = norm_vat_type(r.get(c_iva) if c_iva else None)
        tax_id = norm_tax_id(r.get(c_cuit) if c_cuit else None)

        email = norm_email(r.get(c_email) if c_email else None)
        telefono = norm_phone(r.get(c_tel) if c_tel else None)

        atencion = norm_text(r.get(c_at) if c_at else None, 160)

        contacto_1 = norm_text(r.get(c_c1) if c_c1 else None, 160)
        contacto_2 = norm_text(r.get(c_c2) if c_c2 else None, 160)
        contacto_3 = norm_text(r.get(c_c3) if c_c3 else None, 160)

        rows.append((
            account_code,
            legal_name,
            vat_type,
            tax_id,
            email,
            telefono,
            atencion,
            contacto_1,
            contacto_2,
            contacto_3,
        ))

    print(f"Rows skipped (no Cliente N°): {skipped}")
    return rows


# -------------------------
# Main
# -------------------------
def main():
    if len(sys.argv) < 2:
        print("Uso: python import_clientes_excel_to_staging.py BD1.xls [SheetName]")
        sys.exit(1)

    path_xls = sys.argv[1]
    sheet = sys.argv[2] if len(sys.argv) >= 3 else "Clientes"

    print(f"Reading Excel: {path_xls} | sheet={sheet}")
    df = load_clientes_xls(path_xls, sheet_name=sheet)
    print(f"Rows read: {len(df)} | cols={len(df.columns)}")
    print("Columnas (primeras 20):", df.columns.tolist()[:20])

    rows = build_staging_rows(df)
    print(f"Rows to insert (with Cliente N°): {len(rows)}")

    conn = get_conn()
    try:
        ensure_staging(conn)
        clear_staging(conn)
        if rows:
            insert_rows(conn, rows)
        conn.commit()
        print("OK: staging loaded.")

        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS n FROM stg_clientes_excel;")
            n = cur.fetchone()["n"]
            print("stg_clientes_excel count =", n)

        print("\nSiguiente paso (en MySQL):")
        print("  CALL sp_crm_import_contacts_from_stg();")

    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()