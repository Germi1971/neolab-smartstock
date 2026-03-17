#!/bin/bash
# Deploy completo en AWS Lightsail - incluye gráficos de situación SKU
# Ejecutar EN el servidor AWS (o vía ssh)
#
# Uso local: ./pull_aws.sh  (hace pull) + ssh ... "bash -s" < deploy/deploy_aws_full.sh
# Uso en AWS: cd /home/ubuntu/neolab-smartstock && ./deploy/deploy_aws_full.sh

set -e

REPO_DIR="${1:-/home/ubuntu/neolab-smartstock}"
cd "$REPO_DIR"

echo "=== Deploy SmartStock en AWS ==="
echo "Repo: $REPO_DIR"

# 1. Pull
echo ""
echo "1. Git pull..."
git pull origin main || true

# 2. Rebuild frontend (gráficos, modal SKU)
echo ""
echo "2. Rebuild frontend..."
if [ -d "frontend" ]; then
  cd frontend
  npm ci --silent 2>/dev/null || npm install --silent
  npm run build
  cd ..
  echo "   Frontend build OK: frontend/dist/"
else
  echo "   (No frontend dir - skip)"
fi

# 2b. Permisos para cron (evitar Permission denied)
if [ -f "smartstock_mc_api/deploy/cron-daily.sh" ]; then
  chmod +x smartstock_mc_api/deploy/cron-daily.sh smartstock_mc_api/deploy/cron-daily-with-sync.sh
  echo "   Cron scripts: +x"
fi

# 3. Reiniciar servicios
echo ""
echo "3. Reiniciar servicios..."

if systemctl is-active --quiet smartstock-mc-api 2>/dev/null; then
  sudo systemctl restart smartstock-mc-api
  echo "   smartstock-mc-api: restarted"
fi

# Backend API (puerto 8000) - puede ser stock-hud o smartstock-backend
for svc in smartstock-backend stock-hud; do
  if systemctl is-active --quiet "$svc" 2>/dev/null; then
    sudo systemctl restart "$svc"
    echo "   $svc: restarted"
    break
  fi
done

echo ""
echo "=== Deploy listo ==="
echo "Verificar: curl http://localhost:8000/health  (backend)"
echo "           curl http://localhost:8001/health  (MC API)"
