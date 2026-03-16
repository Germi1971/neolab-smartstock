@echo off
REM Deploy completo en AWS - pull + rebuild frontend + restart
REM Uso: deploy_aws_full.bat [ssh_target]
REM   ssh_target = ubuntu@IP (o usar AWS_SSH)

set SSH_TARGET=%1
if "%SSH_TARGET%"=="" set SSH_TARGET=%AWS_SSH%
if "%SSH_TARGET%"=="" (
  echo Configurar: set AWS_SSH=ubuntu@TU_IP
  echo O ejecutar: deploy_aws_full.bat ubuntu@TU_IP
  exit /b 1
)

echo Deploy en AWS (%SSH_TARGET%)...
echo.

REM Pull + ejecutar script de deploy en el servidor
ssh %SSH_TARGET% "cd /home/ubuntu/neolab-smartstock && git pull origin main && bash deploy/deploy_aws_full.sh /home/ubuntu/neolab-smartstock"

echo.
echo Listo. Los graficos de situacion SKU deberian estar disponibles.
pause
