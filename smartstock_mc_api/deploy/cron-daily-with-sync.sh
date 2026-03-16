#!/bin/bash
# Pipeline SS2 diario + sync a ss2_staging local (para AWS).
# Usar en AWS: pipeline escribe en neobd, luego sync copia a ss2_staging para el HUD local.
# Crontab: 0 2 * * * /home/ubuntu/neolab-smartstock/smartstock_mc_api/deploy/cron-daily-with-sync.sh >> /var/log/smartstock-mc-cron.log 2>&1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MC_API_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Ejecutar pipeline (igual que cron-daily.sh)
bash "$SCRIPT_DIR/cron-daily.sh"

# Sync neobd → ss2_staging (local en AWS)
echo "$(date '+%Y-%m-%d %H:%M:%S') Sincronizando neobd → ss2_staging..."
cd "$MC_API_DIR"
"$MC_API_DIR/venv/bin/python" deploy/sync_neobd_to_aws.py || { echo "WARN sync (verificar AWS_MYSQL_* en .env)"; }
echo "$(date '+%Y-%m-%d %H:%M:%S') === Cron con sync finalizado ==="
