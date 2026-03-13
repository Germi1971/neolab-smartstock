#!/bin/bash
# Ejecutar diariamente vía cron para mantener sku_obs_12m y cache Monte Carlo actualizados
# Crontab: 0 2 * * * /home/ubuntu/neolab-smartstock/smartstock_mc_api/deploy/cron-daily.sh >> /var/log/smartstock-mc-cron.log 2>&1

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MC_API_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "$(date '+%Y-%m-%d %H:%M:%S') === SmartStock MC cron iniciado ==="

# 1. Refrescar sku_obs_12m (desde tabla1)
echo "$(date '+%Y-%m-%d %H:%M:%S') Refrescando sku_obs_12m..."
cd "$MC_API_DIR"
"$MC_API_DIR/venv/bin/python" tools/refresh_sku_obs_12m.py || { echo "ERROR refresh_sku_obs_12m"; exit 1; }

# 2. Poblar cache Monte Carlo
echo "$(date '+%Y-%m-%d %H:%M:%S') Ejecutando mc/run..."
curl -s -X POST http://localhost:8001/mc/run -H "Content-Type: application/json" -d '{}' || { echo "ERROR mc/run"; exit 1; }
echo ""

echo "$(date '+%Y-%m-%d %H:%M:%S') === SmartStock MC cron finalizado ==="
