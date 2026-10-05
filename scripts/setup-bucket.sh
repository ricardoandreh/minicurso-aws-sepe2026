#!/bin/bash
# Cria o bucket do site se não existir, evitando o SCP do Learner Lab.
# O SCP bloqueia GetBucketObjectLockConfiguration, então usamos --no-wait
# e criamos via boto3 que não faz essa verificação.

set -e

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
BUCKET_NAME="minicurso-chamados-${ACCOUNT_ID}"
REGION="us-east-1"

echo "📦 Setup: Preparando bucket S3 para a Central de Chamados"
echo "   Account: $ACCOUNT_ID"
echo "   Bucket: $BUCKET_NAME"
echo "   Region: $REGION"
echo

# Verifica se o bucket já existe
if aws s3 ls "s3://$BUCKET_NAME" --region "$REGION" >/dev/null 2>&1; then
    echo "✓ Bucket já existe"
    export BUCKET_SITE="$BUCKET_NAME"
    exit 0
fi

echo "▶ Criando bucket..."
python3 - <<PYEOF
import boto3
import sys

s3 = boto3.client('s3', region_name='$REGION')
bucket_name = '$BUCKET_NAME'
region = '$REGION'

try:
    if region == 'us-east-1':
        s3.create_bucket(Bucket=bucket_name)
    else:
        s3.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': region}
        )
    print(f'✓ Bucket criado: {bucket_name}')
except s3.exceptions.BucketAlreadyExists:
    print(f'✓ Bucket já existe: {bucket_name}')
except s3.exceptions.BucketAlreadyOwnedByYou:
    print(f'✓ Você já é dono: {bucket_name}')
except Exception as e:
    print(f'✗ Erro ao criar bucket: {e}', file=sys.stderr)
    sys.exit(1)
PYEOF

export BUCKET_SITE="$BUCKET_NAME"
echo "✓ Pronto para deploy"
