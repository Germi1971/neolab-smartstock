#!/bin/bash
# Crea las vistas en ss2_staging para que el Stock HUD muestre datos de Policy Engine.
# Ejecutar DESPUÉS del sync (parametros_sku, tablaprecios, tabla1, ss2_* ya deben existir).
#
# Uso en AWS:
#   cd /home/ubuntu/neolab-smartstock/smartstock_mc_api
#   bash deploy/setup_ss2_staging_views.sh
#
# Requiere: mysql client. Variables de .env o pasar por argumentos:
#   MYSQL_HOST=127.0.0.1 MYSQL_USER=ss2 MYSQL_PASSWORD=xxx mysql ...

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MC_API_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Cargar .env si existe
if [ -f "$MC_API_DIR/.env" ]; then
  set -a
  source <(grep -v '^#' "$MC_API_DIR/.env" | grep -E '^(AWS_)?MYSQL_' | sed 's/^/export /')
  set +a
fi

# Usar AWS_MYSQL_* para ss2_staging (destino)
HOST="${AWS_MYSQL_HOST:-127.0.0.1}"
PORT="${AWS_MYSQL_PORT:-3306}"
USER="${AWS_MYSQL_USER:-ss2}"
PASS="${AWS_MYSQL_PASSWORD:-}"
DB="${AWS_MYSQL_DB:-ss2_staging}"

if [ -z "$USER" ]; then
  echo "Configurar AWS_MYSQL_USER (y AWS_MYSQL_PASSWORD) en .env"
  exit 1
fi

MYSQL_CMD="mysql -h $HOST -P $PORT -u $USER"
if [ -n "$PASS" ]; then
  MYSQL_CMD="$MYSQL_CMD -p$PASS"
fi

echo "=== Creando vistas en $DB ==="

# 1. v_sku_features_12m (desde ss2_sku_features_12m)
echo ">>> v_sku_features_12m..."
$MYSQL_CMD "$DB" < "$SCRIPT_DIR/ddl_v_sku_features_12m_from_ss2.sql" || echo "  (puede fallar si ss2_sku_features_12m vacía)"

# 2. v_stock_estado_unidades (desde tabla1)
echo ">>> v_stock_estado_unidades..."
$MYSQL_CMD "$DB" < "$SCRIPT_DIR/ddl_v_stock_estado_unidades_neobd.sql" || echo "  WARN"

# 3. ss2_v_purchase_suggestions_v2 (vista principal para HUD)
echo ">>> ss2_v_purchase_suggestions_v2..."
$MYSQL_CMD "$DB" < "$SCRIPT_DIR/ddl_ss2_v_purchase_suggestions_v2.sql" || { echo "  ERROR: revisar dependencias"; exit 1; }

echo ""
echo "=== Vistas creadas. Verificar: ==="
$MYSQL_CMD -e "SELECT COUNT(*) AS filas FROM $DB.ss2_v_purchase_suggestions_v2" 2>/dev/null || true
