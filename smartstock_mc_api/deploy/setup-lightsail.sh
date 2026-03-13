#!/bin/bash
# Setup SmartStock Monte Carlo API en AWS Lightsail (Ubuntu)
# Ejecutar desde smartstock_mc_api: cd .../smartstock_mc_api && bash deploy/setup-lightsail.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "=== SmartStock Monte Carlo API - Setup Lightsail ==="
echo "Directorio: $WORK_DIR"

# 1. Instalar dependencias del sistema
echo ">>> Instalando Python..."
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# 2. Venv y dependencias Python
echo ">>> Creando venv e instalando dependencias..."
cd "$WORK_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# 3. Verificar .env
if [ ! -f .env ]; then
  echo ">>> Crear .env con: cp deploy/env.lightsail.example .env && nano .env"
  echo ">>> Completar MYSQL_HOST, MYSQL_USER, MYSQL_PASSWORD, MYSQL_DB"
  exit 1
fi

# 4. Verificar conexión a BD
echo ">>> Verificando conexión a MySQL..."
cd "$WORK_DIR" && source venv/bin/activate
python3 -c "
import os
from dotenv import load_dotenv
load_dotenv()
import pymysql
conn = pymysql.connect(
    host=os.getenv('MYSQL_HOST','127.0.0.1'),
    port=int(os.getenv('MYSQL_PORT','3306')),
    user=os.getenv('MYSQL_USER'),
    password=os.getenv('MYSQL_PASSWORD'),
    database=os.getenv('MYSQL_DB','neobd'),
)
conn.cursor().execute('SELECT 1')
conn.close()
print('MySQL OK')
" || { echo "Error: no se pudo conectar a MySQL. Revisar .env y que v_analisis_sku_excel_mc exista"; exit 1; }

# 5. Instalar servicio systemd
echo ">>> Instalando servicio systemd..."
sudo cp "$SCRIPT_DIR/smartstock-mc-api.service" /etc/systemd/system/
sudo sed -i "s|__WORK_DIR__|$WORK_DIR|g" /etc/systemd/system/smartstock-mc-api.service
sudo systemctl daemon-reload
sudo systemctl enable smartstock-mc-api
sudo systemctl start smartstock-mc-api

echo ""
echo "=== Listo ==="
echo "API:  sudo systemctl status smartstock-mc-api"
echo "Logs: sudo journalctl -u smartstock-mc-api -f"
echo "Health: curl http://localhost:8001/health"
echo ""
echo "Abrí el puerto 8001 en Lightsail Networking."
echo "URL para Stock HUD: SMARTSTOCK_MC_API_URL=http://TU_IP:8001"
echo ""
echo "Poblar cache: curl -X POST http://localhost:8001/mc/run"
