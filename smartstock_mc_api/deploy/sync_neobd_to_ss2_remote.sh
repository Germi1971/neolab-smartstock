#!/bin/bash
# =============================================================================
# Clonar neobd (remoto) → ss2_staging (Lightsail local)
# =============================================================================
# neobd:  190.228.29.65:3306
# ss2_staging: 127.0.0.1:3307 (o localhost)
#
# Uso: ./sync_neobd_to_ss2_remote.sh
# O con variables de entorno:
#   NEOBD_HOST=190.228.29.65 NEOBD_USER=neolab NEOBD_PASS=xxx \
#   SS2_HOST=127.0.0.1 SS2_PORT=3307 SS2_USER=ss2 SS2_PASS=xxx \
#   ./sync_neobd_to_ss2_remote.sh
# =============================================================================

NEOBD_HOST="${NEOBD_HOST:-190.228.29.65}"
NEOBD_PORT="${NEOBD_PORT:-3306}"
NEOBD_USER="${NEOBD_USER:-neolab}"
NEOBD_PASS="${NEOBD_PASS:-}"
NEOBD_DB="${NEOBD_DB:-neobd}"

SS2_HOST="${SS2_HOST:-127.0.0.1}"
SS2_PORT="${SS2_PORT:-3307}"
SS2_USER="${SS2_USER:-ss2}"
SS2_PASS="${SS2_PASS:-}"
SS2_DB="${SS2_DB:-ss2_staging}"

TABLES="parametros_sku tablaprecios sku_mc_cache"
TMP="/tmp/sync_neobd_ss2_$$.sql"

echo ">>> Exportando desde $NEOBD_HOST:$NEOBD_PORT ($NEOBD_DB)..."
> "$TMP"
for t in $TABLES; do
  echo "  - $t"
  mysqldump -h "$NEOBD_HOST" -P "$NEOBD_PORT" -u "$NEOBD_USER" -p"$NEOBD_PASS" \
    --no-create-info --complete-insert "$NEOBD_DB" "$t" 2>/dev/null >> "$TMP" || echo "    (omitida)"
done

if [ ! -s "$TMP" ]; then
  echo "Error: no se exportó nada. Verifica credenciales y conectividad a neobd."
  rm -f "$TMP"
  exit 1
fi

echo ">>> Vaciar tablas destino y importar en $SS2_HOST:$SS2_PORT ($SS2_DB)..."
mysql -h "$SS2_HOST" -P "$SS2_PORT" -u "$SS2_USER" -p"$SS2_PASS" "$SS2_DB" -e "
  SET FOREIGN_KEY_CHECKS=0;
  DELETE FROM parametros_sku;
  DELETE FROM tablaprecios;
  DELETE FROM sku_mc_cache;
  SET FOREIGN_KEY_CHECKS=1;
" 2>/dev/null || true

mysql -h "$SS2_HOST" -P "$SS2_PORT" -u "$SS2_USER" -p"$SS2_PASS" "$SS2_DB" < "$TMP" 2>/dev/null || {
  echo "Error: no se pudo importar. Verifica que las tablas existan en ss2_staging."
  rm -f "$TMP"
  exit 1
}

rm -f "$TMP"
echo ">>> Sync completado."
