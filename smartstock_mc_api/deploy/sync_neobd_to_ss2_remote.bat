@echo off
REM =============================================================================
REM Clonar neobd (remoto) -> ss2_staging (local/tunnel)
REM Ejecutar desde tu PC donde tienes acceso a ambas DBs (HeidiSQL)
REM =============================================================================

set NEOBD_HOST=190.228.29.65
set NEOBD_PORT=3306
set NEOBD_USER=neolab
set NEOBD_PASS=TU_PASS_NEOBD
set NEOBD_DB=neobd

set SS2_HOST=127.0.0.1
set SS2_PORT=3307
set SS2_USER=ss2
set SS2_PASS=TU_PASS_SS2
set SS2_DB=ss2_staging

set TMP=%TEMP%\sync_neobd_ss2_%RANDOM%.sql

REM Edita NEOBD_PASS y SS2_PASS con tus contraseñas reales.
REM Si sku_mc_cache no existe en neobd: cambia "parametros_sku tablaprecios sku_mc_cache" por "parametros_sku tablaprecios"

echo Exportando desde %NEOBD_HOST%:%NEOBD_PORT%...
mysqldump -h %NEOBD_HOST% -P %NEOBD_PORT% -u %NEOBD_USER% -p%NEOBD_PASS% --no-create-info --complete-insert %NEOBD_DB% parametros_sku tablaprecios sku_mc_cache > "%TMP%" 2>nul

echo Importando en %SS2_HOST%:%SS2_PORT%...
mysql -h %SS2_HOST% -P %SS2_PORT% -u %SS2_USER% -p%SS2_PASS% %SS2_DB% -e "SET FOREIGN_KEY_CHECKS=0; DELETE FROM parametros_sku; DELETE FROM tablaprecios; DELETE FROM sku_mc_cache; SET FOREIGN_KEY_CHECKS=1;" 2>nul
mysql -h %SS2_HOST% -P %SS2_PORT% -u %SS2_USER% -p%SS2_PASS% %SS2_DB% < "%TMP%" 2>nul
if errorlevel 1 (
  echo Error al importar. Verifica credenciales de ss2_staging.
)

del "%TMP%" 2>nul
echo Sync completado.
pause
