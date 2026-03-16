#!/bin/bash
# Pull en AWS Lightsail - actualiza neolab-smartstock y SCANNER_REPO
# Uso: ./pull_aws.sh [ssh_target]
#   ssh_target = ubuntu@IP (o con -i: ssh -i clave.pem ubuntu@IP "cd ... && git pull")
#   Si no se pasa, usa AWS_SSH del env
#
# Para deploy completo (pull + rebuild frontend + restart): ./deploy_aws_full.sh

SSH_TARGET="${1:-$AWS_SSH}"
if [ -z "$SSH_TARGET" ]; then
  echo "Configurar: export AWS_SSH=ubuntu@TU_IP"
  echo "O ejecutar: ./pull_aws.sh ubuntu@TU_IP"
  exit 1
fi

echo "Pull en AWS ($SSH_TARGET)..."
ssh "$SSH_TARGET" "cd /home/ubuntu/neolab-smartstock && git pull && cd /home/ubuntu/SCANNER_REPO && git pull"
echo "Listo."
echo ""
echo "Para rebuild frontend y restart: ssh $SSH_TARGET 'cd /home/ubuntu/neolab-smartstock && bash deploy/deploy_aws_full.sh'"
