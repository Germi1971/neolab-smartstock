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
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

# -----------------------------
# Config & Logging
# -----------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
log = logging.getLogger("mc-api")

# CAP factor (default 1.35)
DEFAULT_CAP_FACTOR = float(os.getenv("MC_LAMBDA_CAP_FACTOR", "1.35"))

# Para evitar explosión por p_event≈1
P_EVENT_CLAMP_MAX = float(os.getenv("MC_PEVENT_CLAMP_MAX", "0.999999"))

# Umbral de forecast para aplicar CAP (REGULAR / baja demanda)
FORECAST_BAJO = float(os.getenv("MC_FORECAST_BAJO", "3.0"))

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
# Helpers: math & distributions
# -----------------------------
def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def service_prob_from_service_target(service_target: Optional[float]) -> float:
    """
    En tu setup ServiceTarget suele ser Z (ej. 1.65).
    Lo mapeamos a prob por CDF normal.
    """
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
    """
    Poisson sampler sin numpy (Knuth).
    Para lam grandes, usamos aproximación normal.
    """
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
# Monte Carlo simulation
# -----------------------------
def simulate_demand_horizon(
    lambda_eventos_mes: float,
    q_mean_event: float,
    q_sd_event: float,
    horizon_days: int,
    n_sims: int,
) -> List[float]:
    """
    Simula demanda total en horizonte H:
      N_eventos ~ Poisson(lambda_eventos_mes * H_meses)
      Qty_evento ~ LogNormal(mean, sd)
      Demanda = sum(Qty_evento)
    """
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

def mc_metrics(
    demand_samples: List[float],
    stock_posicion: float,
    service_prob: float,
) -> Dict[str, float]:
    """
    Retorna percentiles + riesgo de quiebre bajo stock_posicion.
    """
    stock_pos = float(stock_posicion or 0.0)
    service_prob = clamp(float(service_prob), 0.50, 0.999)

    if not demand_samples:
        return {
            "demand_p50": 0.0, "demand_p90": 0.0, "demand_p95": 0.0, "demand_p97": 0.0, "demand_p99": 0.0,
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

    p_stockout = stockouts / len(demand_samples)
    exp_lost = lost_sum / len(demand_samples)

    return {
        "demand_p50": float(p50),
        "demand_p90": float(p90),
        "demand_p95": float(p95),
        "demand_p97": float(p97),
        "demand_p99": float(p99),
        "stock_objetivo_mc": float(objetivo),
        "p_stockout": float(p_stockout),
        "exp_lost_units": float(exp_lost),
    }

# -----------------------------
# Criterios MC (simple + fallback)
# -----------------------------
def decide_mc(row: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Si faltan campos (ej. dias_observados), hacemos fallback por señales:
      - tipo_demanda INTERMITENTE
      - p_event alto / PctZero bajo
      - LT >= 45
    """
    activo = int(row.get("activo") or 0)
    if activo != 1:
        return False, "SKU inactivo"

    # si existe dias_observados, aplico gating clásico
    dias_obs = row.get("dias_observados")
    eventos_12m = row.get("eventos_12m")
    unidades_12m = row.get("unidades_12m")

    tipo = (row.get("tipo_demanda") or row.get("model") or "").upper()
    lt_days = float(row.get("lt_days") or row.get("Mu_LT") or 0.0)

    if dias_obs is not None:
        try:
            d = float(dias_obs or 0.0)
            e = float(eventos_12m or 0.0)
            u = float(unidades_12m or 0.0)
            if d < 180:
                return False, f"Datos insuficientes: dias_observados={int(d)}"
            if e < 3:
                return False, f"Datos insuficientes: eventos_12m={int(e)}"
            if u <= 0:
                return False, "Sin consumo (unidades_12m=0)"
        except Exception:
            pass

    # Fallback: si no hay esas columnas en la vista, uso señales simples
    p_event = float(row.get("p_event") or 0.0)
    pct_zero = float(row.get("PctZero") or 0.0)

    if ("INTERMIT" in tipo) and (lt_days >= 45) and (p_event >= 0.90) and (pct_zero <= 0.20):
        return True, f"MC: INTERMITENTE(fallback) LT={int(lt_days)}d p_event={p_event:.2f} PctZero={pct_zero:.2f}"

    # Si es REGULAR pero hiper-volátil, igual dejamos MC por criterio suave
    if ("REGULAR" in tipo) and (lt_days >= 45) and (p_event >= 0.90):
        return True, f"MC: REGULAR(fallback) LT={int(lt_days)}d p_event={p_event:.2f}"

    return False, "No MC: no cumple criterios"

# -----------------------------
# Política de compra (MOQ / múltiplo / cap)
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
# Lambda inference (con CAP)
# -----------------------------
def infer_lambda_eventos_mes(row: Dict[str, Any]) -> Tuple[float, str, Dict[str, Any]]:
    """
    Devuelve (lambda_eventos_mes, lambda_mode, debug_dict).

    Si no existe lambda en la vista, deriva desde p_event mensual:
      lambda_base = -ln(1-p)

    CAP automático:
      si Forecast_m bajo y q_mean_event > 0:
         lambda_cap = (Forecast_m / q_mean_event) * CAP_FACTOR
      y usamos min(base, cap) o cap directo si p_event alto.

    NOTA: si NO existe Forecast_m, no capeamos.
    """

    model = (row.get("tipo_demanda") or row.get("model") or "").upper()

    # Inputs
    p_event = float(row.get("p_event") or 0.0)
    p_event_clamped = clamp(p_event, 0.0, P_EVENT_CLAMP_MAX)

    forecast_m = row.get("Forecast_m")
    try:
        forecast_m = float(forecast_m) if forecast_m is not None else 0.0
    except Exception:
        forecast_m = 0.0

    q_mean = float(row.get("q_mean_event") or row.get("mu_unidades_evento") or 0.0)

    # Base desde lambda_eventos_mes si existe
    lam_view = row.get("lambda_eventos_mes")
    lam_base = None
    base_mode = "BASE_PEVENT"

    if lam_view is not None:
        try:
            v = float(lam_view)
            if v >= 0:
                lam_base = v
                base_mode = "VIEW_LAMBDA"
        except Exception:
            lam_base = None

    if lam_base is None:
        if p_event_clamped <= 0:
            lam_base = 0.0
        else:
            lam_base = -math.log(1.0 - p_event_clamped)
        base_mode = "BASE_PEVENT"

    debug = {
        "p_event": p_event,
        "p_event_clamped": p_event_clamped,
        "forecast_m": forecast_m,
        "q_mean_event": q_mean,
        "cap_factor": DEFAULT_CAP_FACTOR,
        "lambda_base": float(lam_base),
        "base_mode": base_mode,
    }

    # CAP solo si hay forecast y q_mean positivo
    if forecast_m > 0 and q_mean > 0 and (forecast_m <= FORECAST_BAJO):
        lam_cap = max(0.0, (forecast_m / q_mean) * DEFAULT_CAP_FACTOR)
        debug["lambda_cap"] = float(lam_cap)

        # regla: si p_event muy alto -> usamos cap directo
        if p_event >= 0.90:
            return float(lam_cap), "CAP_FORECAST_OVER_Q", debug

        # si no, al menos no dejamos que base supere cap
        if lam_base > lam_cap:
            return float(lam_cap), "CAP_FORECAST_OVER_Q", debug

    return float(lam_base), base_mode, debug

# -----------------------------
# SQL (ajustado a tu vista actual)
#   - NO pedimos dias_observados / eventos_12m / q_cap si no existen
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
  a.multiplo_compra
FROM neobd.v_analisis_sku_excel a
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
  a.multiplo_compra
FROM neobd.v_analisis_sku_excel a
WHERE a.sku = %s
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

# -----------------------------
# API Models
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
    force: bool = Field(default=False, description="Si true, corre MC aunque mc_enabled sea False (debug)")

# -----------------------------
# FastAPI app
# -----------------------------
app = FastAPI(title="NeoLab SmartStock - Monte Carlo API", version="2.1.0")
cfg = load_db_config()

@app.get("/")
def root():
    return {
        "ok": True,
        "service": "smartstock_mc_api",
        "cap_factor": DEFAULT_CAP_FACTOR,
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
    row: Dict[str, Any],
    n_sims: int,
    review_days: int,
    service_prob_override: Optional[float],
    force: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    sku = row["sku"]
    stock_pos = float(row.get("stock_posicion") or 0.0)

    # lead time
    lt_days = float(row.get("lt_days") or row.get("Mu_LT") or 0.0)
    lt_months = float(row.get("lt_months") or 0.0)
    if lt_days <= 0 and lt_months > 0:
        lt_days = lt_months * 30.0
    if lt_days <= 0:
        lt_days = 30.0

    horizon_days = int(round(lt_days)) + int(review_days or 0)

    # service prob
    service_prob = float(service_prob_override) if service_prob_override is not None else service_prob_from_service_target(row.get("service_target"))

    # rounding rules
    moq = int(row.get("moq") or 1)
    multiplo = int(row.get("multiplo_compra") or 1)
    q_cap = None  # por ahora no viene en tu vista; lo dejamos NULL (la tabla cache lo acepta)

    # decidir MC
    mc_enabled, mc_reason = decide_mc(row)

    # infer lambda (con CAP)
    lam_m, lam_mode, lam_dbg = infer_lambda_eventos_mes(row)
    q_mean = float(row.get("q_mean_event") or row.get("mu_unidades_evento") or 0.0)
    q_sd = float(row.get("q_sd_event") or row.get("sigma_unidades_evento") or 0.0)

    # guardrails
    lam_m = max(0.0, float(lam_m))
    q_mean = max(0.0, float(q_mean))
    q_sd = max(0.0, float(q_sd))

    # Si no MC y no force, devolvemos fila sin simular (pero con lambda ya informada)
    if (not mc_enabled) and (not force):
        out = {
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
            "stock_posicion": float(stock_pos),
            "Forecast_m": float(row.get("Forecast_m") or 0.0),
            "demand_p50": 0.0, "demand_p90": 0.0, "demand_p95": 0.0, "demand_p97": 0.0, "demand_p99": 0.0,
            "stock_objetivo_mc": 0.0,
            "qty_recomendada_mc": 0.0,
            "p_stockout": 0.0,
            "exp_lost_units": 0.0,
            "moq": moq, "multiplo_compra": multiplo, "q_cap": q_cap,
        }
        return out, lam_dbg

    # simular
    samples = simulate_demand_horizon(
        lambda_eventos_mes=lam_m,
        q_mean_event=q_mean,
        q_sd_event=q_sd,
        horizon_days=horizon_days,
        n_sims=n_sims,
    )

    met = mc_metrics(samples, stock_posicion=stock_pos, service_prob=service_prob)

    # política de compra
    objetivo = float(met["stock_objetivo_mc"])
    qty_raw = max(0.0, objetivo - stock_pos)
    qty_final = apply_rounding(qty_raw, moq=moq, multiplo=multiplo, q_cap=q_cap)

    out = {
        "sku": sku,
        "mc_enabled": 1,
        "mc_reason": mc_reason if mc_reason.startswith("MC:") else f"MC: {mc_reason}",
        "n_sims": n_sims,
        "horizon_days": horizon_days,
        "lt_days": int(round(lt_days)),
        "review_days": int(review_days or 0),
        "lambda_eventos_mes": float(lam_m),
        "lambda_mode": lam_mode,
        "q_mean_event": float(q_mean),
        "q_sd_event": float(q_sd),
        "service_prob": float(service_prob),
        "stock_posicion": float(stock_pos),
        "Forecast_m": float(row.get("Forecast_m") or 0.0),
        **met,
        "qty_recomendada_mc": float(qty_final),
        "moq": moq, "multiplo_compra": multiplo, "q_cap": q_cap,
    }
    return out, lam_dbg

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
                        out, _dbg = compute_one(r, req.n_sims, req.review_days, req.service_prob_override, force=False)

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
                                int(out["mc_enabled"]),
                                str(out["mc_reason"])[:255] if out.get("mc_reason") else None,
                                float(out["demand_p50"]),
                                float(out["demand_p90"]),
                                float(out["demand_p95"]),
                                float(out["demand_p97"]),
                                float(out["demand_p99"]),
                                float(out["stock_objetivo_mc"]),
                                float(out["qty_recomendada_mc"]),
                                float(out["p_stockout"]),
                                float(out["exp_lost_units"]),
                                int(out["moq"]),
                                int(out["multiplo_compra"]),
                                out["q_cap"],
                            ),
                        )
                        updated += 1

                    except Exception as e:
                        errors.append({"sku": r.get("sku"), "error": str(e)})

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB/Run error: {str(e)}")

    return {
        "ok": True,
        "cap_factor": DEFAULT_CAP_FACTOR,
        "updated": updated,
        "simulated": simulated,
        "skipped": skipped,
        "errors_count": len(errors),
        "errors_sample": errors[:10],
        "elapsed_sec": round(time.time() - t0, 3),
    }

@app.post("/mc/sku/{sku}")
def mc_sku(sku: str, req: RunSkuRequest, debug: int = Query(default=0, ge=0, le=1)):
    if req.seed is not None:
        random.seed(req.seed)

    try:
        with get_conn(cfg) as conn:
            with conn.cursor() as cur:
                cur.execute(FETCH_ONE_SKU_SQL, (sku,))
                row = cur.fetchone()

            if not row:
                raise HTTPException(status_code=404, detail=f"SKU not found in v_analisis_sku_excel: {sku}")

            if int(row.get("activo") or 0) != 1:
                raise HTTPException(status_code=400, detail=f"SKU {sku} is not active (activo!=1).")

            out, lam_dbg = compute_one(row, req.n_sims, req.review_days, req.service_prob_override, force=req.force)

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
                        int(out["mc_enabled"]),
                        str(out["mc_reason"])[:255] if out.get("mc_reason") else None,
                        float(out["demand_p50"]),
                        float(out["demand_p90"]),
                        float(out["demand_p95"]),
                        float(out["demand_p97"]),
                        float(out["demand_p99"]),
                        float(out["stock_objetivo_mc"]),
                        float(out["qty_recomendada_mc"]),
                        float(out["p_stockout"]),
                        float(out["exp_lost_units"]),
                        int(out["moq"]),
                        int(out["multiplo_compra"]),
                        out["q_cap"],
                    ),
                )

        resp = {"ok": True, "cap_factor": DEFAULT_CAP_FACTOR, "model": row.get("model"), "tipo_demanda": row.get("tipo_demanda"), "result": out}
        if debug == 1:
            resp["lambda_debug"] = lam_dbg
        return resp

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

@app.get("/favicon.ico")
def favicon():
    return Response(status_code=204)
