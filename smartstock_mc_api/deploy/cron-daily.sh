#!/bin/bash
# Pipeline SS2 diario: refresh_sku_obs_12m -> MC -> Policy -> Scoring
# Crontab: 0 2 * * * /home/ubuntu/neolab_smartstock/smartstock_mc_api/deploy/cron-daily.sh >> /var/log/smartstock-mc-cron.log 2>&1

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MC_API_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "$(date '+%Y-%m-%d %H:%M:%S') === SmartStock MC cron iniciado ==="

# 1. Refrescar sku_obs_12m (desde tabla1)
echo "$(date '+%Y-%m-%d %H:%M:%S') Refrescando sku_obs_12m..."
cd "$MC_API_DIR"
"$MC_API_DIR/venv/bin/python" tools/refresh_sku_obs_12m.py || { echo "ERROR refresh_sku_obs_12m"; exit 1; }

# 2. Demand Engine: Monte Carlo → ss2_demand_cache
echo "$(date '+%Y-%m-%d %H:%M:%S') Ejecutando mc/run..."
curl -s -X POST http://localhost:8001/mc/run -H "Content-Type: application/json" -d '{}' || { echo "ERROR mc/run"; exit 1; }
echo ""

# 3. Policy Engine → ss2_policy_results
echo "$(date '+%Y-%m-%d %H:%M:%S') Ejecutando policy/run..."
curl -s -X POST http://localhost:8001/policy/run -H "Content-Type: application/json" -d '{}' || { echo "ERROR policy/run"; exit 1; }
echo ""

# 4. Purchase Scoring → ss2_purchase_scores
echo "$(date '+%Y-%m-%d %H:%M:%S') Ejecutando scoring/run..."
curl -s -X POST http://localhost:8001/scoring/run -H "Content-Type: application/json" -d '{}' || { echo "ERROR scoring/run"; exit 1; }
echo ""

echo "$(date '+%Y-%m-%d %H:%M:%S') === SmartStock SS2 pipeline diario finalizado ==="
