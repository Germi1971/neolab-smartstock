import os
from dotenv import load_dotenv

load_dotenv()

import math
import time
import random
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple

import pymysql
from fastapi import FastAPI, HTTPException


from pydantic import BaseModel, Field

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("mc-api")

# -----------------------------
# DB Config
# -----------------------------
@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


def load_db_config() -> DBConfig:
    return DBConfig(
        host=os.getenv("MYSQL_HOST", "190.228.29.65"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "neolab"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DB", "neobd"),
    )


def get_conn(cfg: DBConfig):
    return pymysql.connect(
        host=cfg.host,
        port=cfg.port,
        user=cfg.user,
        password=cfg.password,
        database=cfg.database,
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=True,
    )


# -----------------------------
# Helpers
# -----------------------------

# -----------------------------
# Politica operativa (ajustable)
# -----------------------------
LT_OPERATIVO_DEFAULT = float(os.getenv('LT_OPERATIVO_DEFAULT', '60'))  # dias

SERVICE_CRITICO = float(os.getenv('SERVICE_CRITICO', '0.95'))
SERVICE_IMPORTANTE = float(os.getenv('SERVICE_IMPORTANTE', '0.90'))
SERVICE_NO_CRITICO = float(os.getenv('SERVICE_NO_CRITICO', '0.50'))

# Tabla simple para overrides manuales por SKU
OVERRIDE_TABLE = os.getenv('SKU_OVERRIDE_TABLE', 'sku_service_override')

def fetch_override(conn, sku: str) -> float | None:
    """Devuelve override (0.50-0.999) para el SKU o None si no hay.
    Fuente: tabla OVERRIDE_TABLE(sku, service_prob_override).
    """
    if not sku:
        return None
    try:
        with conn.cursor() as cur:
            cur.execute(f"SELECT service_prob_override FROM {OVERRIDE_TABLE} WHERE sku=%s LIMIT 1;", (sku,))
            r = cur.fetchone() or {}
        v = r.get('service_prob_override')
        if v is None:
            return None
        v = float(v)
        if 0.5 <= v <= 0.999:
            return v
        return None
    except Exception:
        # Si la tabla no existe o hay error, no bloqueamos la corrida
        return None

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def service_prob_from_service_target(service_target: Optional[float]) -> float:
    if service_target is None:
        return 0.95
    z = float(service_target)
    if z < 0:
        return 0.50
    if z > 5:
        return 0.999
    return clamp(normal_cdf(z), 0.50, 0.999)


def lognorm_mu_sigma_from_mean_sd(mean: float, sd: float) -> Tuple[float, float]:
    if mean <= 0:
        return (0.0, 0.0)
    if sd <= 0:
        return (math.log(mean), 1e-12)
    var = sd * sd
    sigma2 = math.log(1.0 + var / (mean * mean))
    mu = math.log(mean) - 0.5 * sigma2
    sigma = math.sqrt(sigma2)
    return mu, sigma


def sample_lognormal(mean: float, sd: float) -> float:
    mean = float(mean or 0.0)
    sd = float(sd or 0.0)
    if mean <= 0:
        return 0.0
    mu, sigma = lognorm_mu_sigma_from_mean_sd(mean, sd)
    if sigma < 1e-10:
        return max(0.0, mean)
    return max(0.0, random.lognormvariate(mu, sigma))


def poisson_sample(lam: float) -> int:
    lam = max(0.0, float(lam or 0.0))
    if lam <= 0.0:
        return 0
    if lam > 60:
        n = int(round(random.gauss(lam, math.sqrt(lam))))
        return max(0, n)

    L = math.exp(-lam)
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


def quantile_sorted(vals_sorted: List[float], q: float) -> float:
    if not vals_sorted:
        return 0.0
    q = clamp(float(q), 0.0, 1.0)
    idx = int(math.floor((len(vals_sorted) - 1) * q))
    return float(vals_sorted[idx])


# -----------------------------
# Monte Carlo
# -----------------------------
def simulate_demand_horizon(
    lambda_eventos_mes: float,
    q_mean_event: float,
    q_sd_event: float,
    horizon_days: int,
    n_sims: int,
) -> List[float]:
    horizon_days = int(horizon_days or 0)
    if horizon_days <= 0:
        horizon_days = 30
    H_meses = horizon_days / 30.0
    lam_total = max(0.0, float(lambda_eventos_mes or 0.0)) * H_meses

    out: List[float] = []
    for _ in range(int(n_sims)):
        n_events = poisson_sample(lam_total)
        d = 0.0
        for _e in range(n_events):
            d += sample_lognormal(q_mean_event, q_sd_event)
        out.append(d)
    return out


def mc_metrics(demand_samples: List[float], stock_posicion: float, service_prob: float) -> Dict[str, float]:
    stock_pos = float(stock_posicion or 0.0)
    service_prob = clamp(float(service_prob), 0.50, 0.999)

    if not demand_samples:
        return {
            "demand_p50": 0.0,
            "demand_p90": 0.0,
            "demand_p95": 0.0,
            "demand_p97": 0.0,
            "demand_p99": 0.0,
            "stock_objetivo_mc": 0.0,
            "p_stockout": 0.0,
            "exp_lost_units": 0.0,
        }

    srt = sorted(demand_samples)
    p50 = quantile_sorted(srt, 0.50)
    p90 = quantile_sorted(srt, 0.90)
    p95 = quantile_sorted(srt, 0.95)
    p97 = quantile_sorted(srt, 0.97)
    p99 = quantile_sorted(srt, 0.99)

    objetivo = quantile_sorted(srt, service_prob)

    stockouts = 0
    lost_sum = 0.0
    for d in demand_samples:
        if d > stock_pos:
            stockouts += 1
            lost_sum += (d - stock_pos)

    return {
        "demand_p50": float(p50),
        "demand_p90": float(p90),
        "demand_p95": float(p95),
        "demand_p97": float(p97),
        "demand_p99": float(p99),
        "stock_objetivo_mc": float(objetivo),
        "p_stockout": float(stockouts / len(demand_samples)),
        "exp_lost_units": float(lost_sum / len(demand_samples)),
    }


# -----------------------------
# Decide MC (usa sku_obs_12m ya unido)
# -----------------------------
def decide_mc(row: Dict[str, Any]) -> Tuple[bool, str]:
    activo = int(row.get("activo") or 0)
    if activo != 1:
        return False, "SKU inactivo"

    dias_obs = float(row.get("dias_observados") or 0.0)
    eventos_12m = float(row.get("eventos_12m") or 0.0)
    unidades_12m = float(row.get("unidades_12m") or 0.0)
    tipo = (row.get("tipo_demanda") or row.get("Model") or row.get("model") or "").upper()

    # Gates mínimos de datos
    if dias_obs < 180:
        return False, f"Datos insuficientes: dias_observados={int(dias_obs)}"
    if eventos_12m < 3:
        return False, f"Datos insuficientes: eventos_12m={int(eventos_12m)}"
    if unidades_12m <= 0:
        return False, "Sin consumo (unidades_12m=0)"

    # Señales de incertidumbre (U)
    mu_gap = float(row.get("mu_gap_dias") or 0.0)
    mu_q = float(row.get("mu_unidades_evento") or row.get("q_mean_event") or 0.0)
    sigma_q = float(row.get("sigma_unidades_evento") or row.get("q_sd_event") or 0.0)

    cv_evento = (sigma_q / mu_q) if (mu_q and mu_q > 0) else 0.0
    I = clamp(mu_gap / 90.0, 0.0, 1.0)
    V = clamp((cv_evento / 1.2), 0.0, 1.0)
    U = 0.5 * I + 0.5 * V

    # Riesgo operativo (tu regla)
    lt_days = float(row.get("Mu_LT") or row.get("lt_days") or 0.0)
    riesgo_ok = (lt_days >= 45)

    # Inputs para fallback
    p_event = float(row.get("p_event") or 0.0)
    forecast_m = float(row.get("Forecast_m") or row.get("forecast_m") or 0.0)
    pct_zero = float(row.get("PctZero") or 0.0)

    if "INTERMIT" in tipo:
        # Regla principal
        if U >= 0.60 and riesgo_ok:
            return True, f"MC: INTERMITENTE U={U:.2f} LT={int(lt_days)}d"

        # ✅ Fallback controlado (para forzar CAP de lambda)
        if riesgo_ok and (p_event >= 0.90) and (forecast_m > 0.0) and (forecast_m <= 5.0):
            return True, f"MC: INTERMITENTE(fallback) LT={int(lt_days)}d p_event={p_event:.2f} PctZero={pct_zero:.2f}"

        return False, f"No MC: INTERMITENTE pero U={U:.2f} o riesgo bajo"

    if "REGULAR" in tipo:
        if (cv_evento >= 0.9) and riesgo_ok:
            return True, f"MC: REGULAR volátil CVevt={cv_evento:.2f} LT={int(lt_days)}d"
        return False, f"No MC: REGULAR (CVevt={cv_evento:.2f})"

    return False, f"No MC: tipo_demanda={tipo or 'N/A'}"


# -----------------------------
# Rounding
# -----------------------------
def apply_rounding(qty: float, moq: int, multiplo: int, q_cap: Optional[int]) -> float:
    q = max(0.0, float(qty or 0.0))
    moq = int(moq or 1)
    multiplo = int(multiplo or 1)
    if moq < 1:
        moq = 1
    if multiplo < 1:
        multiplo = 1
    if q <= 0:
        return 0.0
    q = max(q, float(moq))
    q = math.ceil(q / multiplo) * multiplo
    if q_cap is not None:
        cap = int(q_cap)
        if cap > 0:
            q = min(q, float(cap))
    return float(q)


# -----------------------------
# Lambda inference (desde p_event) + CAP
# -----------------------------
def infer_lambda_eventos_mes(row: Dict[str, Any]) -> Tuple[float, str]:
    """
    Base: lambda = -ln(1 - p_event)

    Problema típico: cuando p_event≈1, -ln(1-p) explota y genera lambdas absurdas.
    Solución: acotar lambda usando el forecast mensual observado.

    Reglas:
      1) lam_base = -ln(1-p_event)
      2) lam_cap  = Forecast_m / q_mean_event  (si tenemos ambos)
      3) Si p_event >= 0.90 => usamos CAP (lam_cap)
      4) Guard-rail general: lambda no puede implicar una media > 2x Forecast_m
         => lambda <= 2*Forecast_m / q_mean_event
    """
    p_event = float(row.get("p_event") or 0.0)
    forecast_m = float(row.get("Forecast_m") or row.get("forecast_m") or 0.0)
    q_mean = float(row.get("q_mean_event") or row.get("mu_unidades_evento") or 0.0)

    p = clamp(p_event, 0.0, 0.999999)
    lam_base = 0.0 if p <= 0 else -math.log(1.0 - p)
    base_mode = "BASE_PEVENT"

    if forecast_m > 0.0 and q_mean > 0.0:
        lam_cap = max(0.0, forecast_m / max(q_mean, 1e-6))

        # CAP fuerte si p_event es muy alto
        if p_event >= 0.90:
            return float(lam_cap), "CAP_FORECAST_OVER_Q"

        # Si no es tan alto, igual no dejamos que supere el cap
        if lam_base > lam_cap:
            lam_base = lam_cap

        # Guard-rail final: media mensual <= 2x forecast
        lam_guard = 2.0 * forecast_m / max(q_mean, 1e-6)
        lam_base = min(lam_base, lam_guard)

    return float(lam_base), base_mode



# -----------------------------
# SQL (lee vista MC-ready)
# -----------------------------
FETCH_ACTIVE_SKUS_SQL = """
SELECT
  a.sku,
  a.activo,
  a.Model AS model,
  a.tipo_demanda,

  a.PctZero,
  a.p_event AS p_event,
  a.q_mean_event AS q_mean_event,
  a.q_sd_event AS q_sd_event,
  a.Forecast_m AS Forecast_m,
  a.sigma_mensual_12m AS sigma_mensual_12m,

  a.stock_posicion AS stock_posicion,

  a.LT_mean_m AS lt_months,
  a.Mu_LT AS lt_days,
  a.ServiceTarget AS service_target,

  a.moq,
  a.multiplo_compra,
  NULL AS q_cap,

  /* obs 12m (desde sku_obs_12m) */
  a.dias_observados,
  a.eventos_12m,
  a.unidades_12m,
  a.mu_unidades_evento,
  a.sigma_unidades_evento,
  a.mu_gap_dias,
  a.sigma_gap_dias

FROM v_analisis_sku_excel_mc a
WHERE a.activo = 1;
"""

FETCH_ONE_SKU_SQL = """
SELECT
  a.sku,
  a.activo,
  a.Model AS model,
  a.tipo_demanda,

  a.PctZero,
  a.p_event AS p_event,
  a.q_mean_event AS q_mean_event,
  a.q_sd_event AS q_sd_event,
  a.Forecast_m AS Forecast_m,
  a.sigma_mensual_12m AS sigma_mensual_12m,

  a.stock_posicion AS stock_posicion,

  a.LT_mean_m AS lt_months,
  a.Mu_LT AS lt_days,
  a.ServiceTarget AS service_target,

  a.moq,
  a.multiplo_compra,
  NULL AS q_cap,

  a.dias_observados,
  a.eventos_12m,
  a.unidades_12m,
  a.mu_unidades_evento,
  a.sigma_unidades_evento,
  a.mu_gap_dias,
  a.sigma_gap_dias

FROM v_analisis_sku_excel_mc a
WHERE a.sku = %s
LIMIT 1;
"""

UPSERT_CACHE_SQL = """
INSERT INTO sku_mc_cache
(sku, n_sims, horizon_days, lt_days, review_days, lambda_eventos_mes, q_mean_event, q_sd_event,
 service_prob, service_prob_usado, service_prob_auto, service_prob_override,
 mc_enabled, mc_reason,
 demand_p50, demand_p90, demand_p95, demand_p97, demand_p99,
 stock_objetivo_mc, qty_recomendada_mc, p_stockout, exp_lost_units,
 moq, multiplo_compra, q_cap,
 criticidad,
 updated_at)
VALUES
(%s,%s,%s,%s,%s,%s,%s,%s,
 %s,%s,%s,%s,
 %s,%s,
 %s,%s,%s,%s,%s,
 %s,%s,%s,%s,
 %s,%s,%s,
 %s,
 NOW())
ON DUPLICATE KEY UPDATE
n_sims=VALUES(n_sims),
horizon_days=VALUES(horizon_days),
lt_days=VALUES(lt_days),
review_days=VALUES(review_days),
lambda_eventos_mes=VALUES(lambda_eventos_mes),
q_mean_event=VALUES(q_mean_event),
q_sd_event=VALUES(q_sd_event),
service_prob=VALUES(service_prob),
service_prob_usado=VALUES(service_prob_usado),
service_prob_auto=VALUES(service_prob_auto),
/* no pises override manual */
service_prob_override=COALESCE(sku_mc_cache.service_prob_override, VALUES(service_prob_override)),
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
criticidad=VALUES(criticidad),
updated_at=NOW();
"""

FETCH_CACHE_SQL = """
SELECT *
FROM sku_mc_cache
WHERE sku = %s
LIMIT 1;
"""

TOP_STOCKOUT_SQL = """
SELECT sku, mc_enabled, p_stockout, exp_lost_units, qty_recomendada_mc, stock_objetivo_mc, mc_reason, updated_at
FROM sku_mc_cache
ORDER BY p_stockout DESC, exp_lost_units DESC
LIMIT %s;
"""


# -----------------------------
# API
# -----------------------------
class RunBatchRequest(BaseModel):
    n_sims: int = Field(default=8000, ge=500, le=50000)
    review_days: int = Field(default=30, ge=0, le=180)
    service_prob_override: Optional[float] = Field(default=None, ge=0.5, le=0.999)
    seed: Optional[int] = Field(default=None)


class RunSkuRequest(BaseModel):
    n_sims: int = Field(default=8000, ge=500, le=50000)
    review_days: int = Field(default=30, ge=0, le=180)
    service_prob_override: Optional[float] = Field(default=None, ge=0.5, le=0.999)
    seed: Optional[int] = None
    force: bool = Field(default=False)


app = FastAPI(title="NeoLab SmartStock - Monte Carlo API", version="2.1.0")
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


from app.routes_ml_review import router as ml_review_router
app.include_router(ml_review_router, prefix="/ml", tags=["ML Review"])

from app.routes_sku_history import router as sku_history_router
app.include_router(sku_history_router)



# ✅ NUEVO: router dashboard compatible con BOLT
from app.routes_dashboard import router as dashboard_router
app.include_router(dashboard_router, tags=["Dashboard"])

cfg = load_db_config()


@app.get("/")
def root():
    return {
        "ok": True,
        "service": "smartstock_mc_api",
        "endpoints": ["/health", "/docs", "/mc/run", "/mc/sku/{sku}", "/mc/cache/{sku}", "/mc/top_stockout"],
    }


@app.get("/health")
def health():
    try:
        with get_conn(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 AS ok;")
                row = cur.fetchone()
        return {"ok": True, "db": True, "row": row}
    except Exception as e:
        return {"ok": False, "db": False, "error": str(e)}


def compute_one(
    conn,
    row: Dict[str, Any],
    n_sims: int,
    review_days: int,
    service_prob_override: Optional[float],
    force: bool,
) -> Dict[str, Any]:
    sku = row["sku"]
    stock_pos = float(row.get("stock_posicion") or 0.0)

    # -----------------------------
    # Lead Time y horizonte
    # -----------------------------
    lt_days_raw = float(row.get("lt_days") or 0.0)
    lt_months = float(row.get("lt_months") or 0.0)
    if lt_days_raw <= 0 and lt_months > 0:
        lt_days_raw = lt_months * 30.0

    # ✅ Política operativa: si todos los SKUs reponen con el mismo lead time, usamos ESTE valor.
    lt_days = float(LT_OPERATIVO_DEFAULT) if float(LT_OPERATIVO_DEFAULT or 0) > 0 else float(lt_days_raw or 0.0)
    if lt_days <= 0:
        lt_days = 60.0

    horizon_days = int(round(lt_days)) + int(review_days or 0)

    # Pasamos el LT operativo al resto del pipeline (decide_mc / mensajes)
    row_local = dict(row)
    row_local["lt_days"] = lt_days
    row_local["Mu_LT"] = lt_days

    # -------------------------------------------------
    # Override por SKU (cargado por vos en MySQL)
    # - Si el POST trae override => gana el POST
    # - Si no, si hay override en DB => gana DB
    # - Si no, usamos el auto por criticidad
    # -------------------------------------------------
    override_db = fetch_override(conn, sku)

    # -------------------------------------------------
    # Criticidad automática (por DEMANDA / VARIABILIDAD)
    # -------------------------------------------------
    tipo = str(row.get("tipo_demanda") or row.get("model") or "").upper()

    forecast_m = float(row.get("Forecast_m") or 0.0)
    p_event = float(row.get("p_event") or 0.0)
    q_mean = float(row.get("q_mean_event") or 0.0)
    q_sd = float(row.get("q_sd_event") or 0.0)
    sigma_m = float(row.get("sigma_mensual_12m") or 0.0)

    cv_evento = (q_sd / q_mean) if q_mean > 1e-9 else 0.0

    # Heurística "a pedido" (si PctZero no es confiable, nos apoyamos en p_event + forecast)
    es_a_pedido = (p_event <= 0.20) and (forecast_m <= 0.50)

    if (not es_a_pedido) and (
        forecast_m >= 3.0
        or q_mean >= 3.0
        or (p_event >= 0.70 and forecast_m >= 1.5)
    ):
        criticidad = "CRITICO"
        service_prob_auto = SERVICE_CRITICO

    elif (not es_a_pedido) and (
        forecast_m >= 1.0
        or p_event >= 0.35
        or ("INTERMIT" in tipo and cv_evento >= 0.70)
        or sigma_m >= 1.0
    ):
        criticidad = "IMPORTANTE"
        service_prob_auto = SERVICE_IMPORTANTE

    else:
        criticidad = "NO_CRITICO"
        service_prob_auto = SERVICE_NO_CRITICO

    # ✅ override final (POST > DB > AUTO)
    service_prob_override_final = (
        float(service_prob_override) if service_prob_override is not None else override_db
    )

    service_prob_usado = (
        float(service_prob_override_final)
        if service_prob_override_final is not None
        else float(service_prob_auto)
    )
    service_prob = service_prob_usado

    # -----------------------------
    # Parámetros de compra
    # -----------------------------
    moq = int(row.get("moq") or 1)
    multiplo = int(row.get("multiplo_compra") or 1)
    q_cap = None  # hoy lo dejamos NULL hasta que lo tengas en dim/vista

    # -----------------------------
    # Decisión MC
    # -----------------------------
    mc_enabled, mc_reason = decide_mc(row_local)

    # -----------------------------
    # SIN MC → solo cacheo
    # -----------------------------
    if (not mc_enabled) and (not force):
        lam_m, lam_mode = infer_lambda_eventos_mes(row_local)
        return {
            "sku": sku,
            "mc_enabled": 0,
            "mc_reason": mc_reason,
            "n_sims": n_sims,
            "horizon_days": horizon_days,
            "lt_days": int(round(lt_days)),
            "review_days": int(review_days or 0),
            "lambda_eventos_mes": float(lam_m),
            "lambda_mode": lam_mode,
            "q_mean_event": float(q_mean),
            "q_sd_event": float(q_sd),
            "service_prob": float(service_prob),
            "service_prob_usado": float(service_prob_usado),
            "service_prob_auto": float(service_prob_auto),
            "service_prob_override": service_prob_override_final,
            "criticidad": criticidad,
            "stock_posicion": stock_pos,
            "Forecast_m": forecast_m,
            "demand_p50": 0.0,
            "demand_p90": 0.0,
            "demand_p95": 0.0,
            "demand_p97": 0.0,
            "demand_p99": 0.0,
            "stock_objetivo_mc": 0.0,
            "qty_recomendada_mc": 0.0,
            "p_stockout": 0.0,
            "exp_lost_units": 0.0,
            "moq": moq,
            "multiplo_compra": multiplo,
            "q_cap": q_cap,
        }

    # -----------------------------
    # MONTE CARLO
    # -----------------------------
    lam_m, lam_mode = infer_lambda_eventos_mes(row_local)
    samples = simulate_demand_horizon(lam_m, q_mean, q_sd, horizon_days, n_sims)
    met = mc_metrics(samples, stock_posicion=stock_pos, service_prob=service_prob)

    objetivo = float(met["stock_objetivo_mc"])
    qty_raw = max(0.0, objetivo - stock_pos)
    qty_final = apply_rounding(qty_raw, moq=moq, multiplo=multiplo, q_cap=q_cap)

    return {
        "sku": sku,
        "mc_enabled": 1,
        "mc_reason": mc_reason if str(mc_reason).startswith("MC:") else f"MC: {mc_reason}",
        "n_sims": n_sims,
        "horizon_days": horizon_days,
        "lt_days": int(round(lt_days)),
        "review_days": int(review_days or 0),
        "lambda_eventos_mes": float(lam_m),
        "lambda_mode": lam_mode,
        "q_mean_event": float(q_mean),
        "q_sd_event": float(q_sd),
        "service_prob": float(service_prob),
        "service_prob_usado": float(service_prob_usado),
        "service_prob_auto": float(service_prob_auto),
        "service_prob_override": service_prob_override_final,
        "criticidad": criticidad,
        "stock_posicion": stock_pos,
        "Forecast_m": forecast_m,
        **met,
        "qty_recomendada_mc": float(qty_final),
        "moq": moq,
        "multiplo_compra": multiplo,
        "q_cap": q_cap,
    }


@app.post("/mc/run")
def mc_run(req: RunBatchRequest):
    if req.seed is not None:
        random.seed(req.seed)

    t0 = time.time()
    updated = 0
    simulated = 0
    skipped = 0
    errors: List[Dict[str, Any]] = []

    try:
        with get_conn(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(FETCH_ACTIVE_SKUS_SQL)
                rows = cur.fetchall()

            log.info(f"MC batch: fetched {len(rows)} active SKUs.")

            with conn.cursor() as cur:
                for r in rows:
                    try:
                        out = compute_one(conn, r, req.n_sims, req.review_days, req.service_prob_override, force=False)

                        if int(out["mc_enabled"]) == 1:
                            simulated += 1
                        else:
                            skipped += 1

                        cur.execute(
                            UPSERT_CACHE_SQL,
                            (
                                out["sku"],
                                int(out["n_sims"]),
                                int(out["horizon_days"]),
                                int(out["lt_days"]),
                                int(out["review_days"]),
                                float(out["lambda_eventos_mes"]),
                                float(out["q_mean_event"]),
                                float(out["q_sd_event"]),

                                float(out["service_prob"]),
                                float(out.get("service_prob_usado", out["service_prob"])),

                                float(out.get("service_prob_auto", out.get("service_prob_usado", out["service_prob"]))),
                                out.get("service_prob_override"),

                                int(out["mc_enabled"]),
                                str(out["mc_reason"])[:255] if out.get("mc_reason") else None,

                                float(out.get("demand_p50", 0.0)),
                                float(out.get("demand_p90", 0.0)),
                                float(out.get("demand_p95", 0.0)),
                                float(out.get("demand_p97", 0.0)),
                                float(out.get("demand_p99", 0.0)),

                                float(out.get("stock_objetivo_mc", 0.0)),
                                float(out.get("qty_recomendada_mc", 0.0)),
                                float(out.get("p_stockout", 0.0)),
                                float(out.get("exp_lost_units", 0.0)),

                                int(out.get("moq", 1)),
                                int(out.get("multiplo_compra", 1)),
                                out.get("q_cap"),

                                out.get("criticidad"),
                            ),
                        )
                        updated += 1
                    except Exception as e:
                        errors.append({"sku": r.get("sku"), "error": str(e)})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB/Run error: {str(e)}")

    return {
        "ok": True,
        "updated": updated,
        "simulated": simulated,
        "skipped": skipped,
        "errors_count": len(errors),
        "errors_sample": errors[:10],
        "elapsed_sec": round(time.time() - t0, 3),
    }


@app.post("/mc/sku/{sku}")
def mc_sku(sku: str, req: RunSkuRequest):
    if req.seed is not None:
        random.seed(req.seed)

    try:
        with get_conn(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(FETCH_ONE_SKU_SQL, (sku,))
                row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"SKU not found: {sku}")

            if int(row.get("activo") or 0) != 1:
                raise HTTPException(status_code=400, detail=f"SKU {sku} is not active (activo!=1).")

            out = compute_one(conn, row, req.n_sims, req.review_days, req.service_prob_override, force=req.force)

            with conn.cursor() as cur:
                cur.execute(
                    UPSERT_CACHE_SQL,
                    (
                        out["sku"],
                        int(out["n_sims"]),
                        int(out["horizon_days"]),
                        int(out["lt_days"]),
                        int(out["review_days"]),
                        float(out["lambda_eventos_mes"]),
                        float(out["q_mean_event"]),
                        float(out["q_sd_event"]),

                        float(out["service_prob"]),
                        float(out.get("service_prob_usado", out["service_prob"])),

                        float(out.get("service_prob_auto", out.get("service_prob_usado", out["service_prob"]))),
                        out.get("service_prob_override"),

                        int(out["mc_enabled"]),
                        str(out["mc_reason"])[:255] if out.get("mc_reason") else None,

                        float(out.get("demand_p50", 0.0)),
                        float(out.get("demand_p90", 0.0)),
                        float(out.get("demand_p95", 0.0)),
                        float(out.get("demand_p97", 0.0)),
                        float(out.get("demand_p99", 0.0)),

                        float(out.get("stock_objetivo_mc", 0.0)),
                        float(out.get("qty_recomendada_mc", 0.0)),
                        float(out.get("p_stockout", 0.0)),
                        float(out.get("exp_lost_units", 0.0)),

                        int(out.get("moq", 1)),
                        int(out.get("multiplo_compra", 1)),
                        out.get("q_cap"),

                        out.get("criticidad"),
                    ),
                )

        return {"ok": True, "model": row.get("model"), "tipo_demanda": row.get("tipo_demanda"), "result": out}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"MC SKU error: {str(e)}")


@app.get("/mc/cache/{sku}")
def mc_cache_get(sku: str):
    try:
        with get_conn(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(FETCH_CACHE_SQL, (sku,))
                row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"No cache row for SKU: {sku}")
        return {"ok": True, "cache": row}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cache read error: {str(e)}")


@app.get("/mc/top_stockout")
def mc_top_stockout(limit: int = 25):
    limit = max(1, min(200, int(limit)))
    try:
        with get_conn(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(TOP_STOCKOUT_SQL, (limit,))
                rows = cur.fetchall()
        return {"ok": True, "limit": limit, "rows": rows}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Top stockout error: {str(e)}")
