@echo off
REM Pull en AWS Lightsail - actualiza neolab-smartstock y SCANNER_REPO
REM Uso: pull_aws.bat [ssh_target]
REM   ssh_target = ubuntu@IP o -i clave.pem ubuntu@IP
REM   Si no se pasa, usa AWS_SSH del env o pide configurar
REM
REM Para deploy completo (incl. graficos): deploy\deploy_aws_full.bat [ssh_target]

set SSH_TARGET=%1
if "%SSH_TARGET%"=="" set SSH_TARGET=%AWS_SSH%
if "%SSH_TARGET%"=="" (
  echo Configurar: set AWS_SSH=ubuntu@TU_IP
  echo O ejecutar: pull_aws.bat ubuntu@TU_IP
  exit /b 1
)

echo Pull en AWS (%SSH_TARGET%)...
ssh %SSH_TARGET% "cd /home/ubuntu/neolab-smartstock && git pull && cd /home/ubuntu/SCANNER_REPO && git pull"
echo Listo.
