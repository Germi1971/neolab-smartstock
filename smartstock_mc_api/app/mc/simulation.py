import math
import random
from typing import List, Tuple, Dict

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))

def service_prob_from_z(z: float) -> float:
    if z is None:
        return 0.95
    z = float(z)
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

def lambda_from_p_event(p_event: float) -> float:
    p = clamp(float(p_event or 0.0), 0.0, 0.999999)
    if p <= 0:
        return 0.0
    return -math.log(1.0 - p)

def simulate_demand_horizon(lambda_eventos_mes: float, q_mean_event: float, q_sd_event: float, horizon_days: int, n_sims: int) -> List[float]:
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

def compute_metrics(demand_samples: List[float], stock_posicion: float, service_prob: float) -> Dict[str, float]:
    stock_pos = float(stock_posicion or 0.0)
    service_prob = clamp(float(service_prob), 0.50, 0.999)

    if not demand_samples:
        return {
            "demand_p50": 0.0, "demand_p90": 0.0, "demand_p95": 0.0, "demand_p97": 0.0, "demand_p99": 0.0,
            "stock_objetivo_mc": 0.0, "p_stockout": 0.0, "exp_lost_units": 0.0,
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
