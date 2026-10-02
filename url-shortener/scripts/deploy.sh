#!/usr/bin/env bash
# Sobe o encurtador inteiro numa conta AWS — SÓ PARA TESTAR.
#
# A aula faz tudo isso pelo AWS Management Console, clique a clique: é esse o
# ponto do hands-on. Este script existe para você validar que a aplicação
# funciona antes de ensinar, e para o `destroy.sh` poder desfazer tudo depois.
#
# Idempotente: pode rodar de novo em cima do que já existe.
set -euo pipefail
cd "$(dirname "$0")/.."

REGIAO=${REGIAO:-us-east-1}
TABELA=${TABELA:-url-shortener-urls}
FILA=${FILA:-url-shortner-queue}
BUCKET=${BUCKET:-url-shortener-poc-3252343}
ROLE=${ROLE:-url-shortener-lambda-role}
API=${API:-url-shortener-api}
CONTA=$(aws sts get-caller-identity --query Account --output text)

info() { printf '\n\033[1m%s\033[0m\n' "$*"; }
existe() { "$@" >/dev/null 2>&1; }

# ── DynamoDB ────────────────────────────────────────────────────────────────
info "DynamoDB: $TABELA"
if existe aws dynamodb describe-table --table-name "$TABELA"; then
  echo "  já existe"
else
  aws dynamodb create-table --table-name "$TABELA" \
    --attribute-definitions AttributeName=shortId,AttributeType=S \
    --key-schema AttributeName=shortId,KeyType=HASH \
    --billing-mode PAY_PER_REQUEST >/dev/null
  aws dynamodb wait table-exists --table-name "$TABELA"
  echo "  criada"
fi

# ── SQS ─────────────────────────────────────────────────────────────────────
info "SQS: $FILA"
FILA_URL=$(aws sqs create-queue --queue-name "$FILA" --query QueueUrl --output text)
FILA_ARN=$(aws sqs get-queue-attributes --queue-url "$FILA_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text)
echo "  $FILA_URL"

# ── IAM ─────────────────────────────────────────────────────────────────────
# Uma role para as quatro funções. Na aula cada função ganha a sua pelo console,
# e é esse trabalho manual que o link() do SST elimina na segunda metade.
info "IAM: $ROLE"
if ! existe aws iam get-role --role-name "$ROLE"; then
  aws iam create-role --role-name "$ROLE" --assume-role-policy-document '{
    "Version":"2012-10-17",
    "Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]
  }' >/dev/null
  aws iam attach-role-policy --role-name "$ROLE" \
    --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
  echo "  criada"
fi
aws iam put-role-policy --role-name "$ROLE" --policy-name AcessoAplicacao --policy-document "{
  \"Version\": \"2012-10-17\",
  \"Statement\": [
    {\"Effect\":\"Allow\",
     \"Action\":[\"dynamodb:GetItem\",\"dynamodb:PutItem\",\"dynamodb:UpdateItem\",\"dynamodb:Scan\"],
     \"Resource\":\"arn:aws:dynamodb:$REGIAO:$CONTA:table/$TABELA\"},
    {\"Effect\":\"Allow\",
     \"Action\":[\"sqs:SendMessage\",\"sqs:ReceiveMessage\",\"sqs:DeleteMessage\",\"sqs:GetQueueAttributes\"],
     \"Resource\":\"$FILA_ARN\"}
  ]
}"
ROLE_ARN=$(aws iam get-role --role-name "$ROLE" --query Role.Arn --output text)
echo "  permissões atualizadas"

# ── Lambdas ─────────────────────────────────────────────────────────────────
subir_lambda() {
  local nome=$1 arquivo=$2 timeout=$3
  local zip; zip=$(mktemp -d)/fn.zip
  # o console grava o código em lambda_function.py; espelhamos isso aqui
  cp "lambdas/$arquivo" "$(dirname "$zip")/lambda_function.py"
  (cd "$(dirname "$zip")" && zip -q fn.zip lambda_function.py)

  if existe aws lambda get-function --function-name "$nome"; then
    aws lambda update-function-code --function-name "$nome" --zip-file "fileb://$zip" >/dev/null
    aws lambda wait function-updated --function-name "$nome"
    aws lambda update-function-configuration --function-name "$nome" \
      --handler lambda_function.lambda_handler --role "$ROLE_ARN" --timeout "$timeout" \
      --environment "Variables={TABELA_NOME=$TABELA,FILA_URL=$FILA_URL}" >/dev/null
  else
    # Role recém-criada leva alguns segundos para o Lambda conseguir assumir.
    # O erro é "The role defined for the function cannot be assumed by Lambda"
    # e some sozinho — daí o retry em vez de um sleep fixo no escuro.
    local tentativa=0
    until aws lambda create-function --function-name "$nome" --runtime python3.13 \
      --handler lambda_function.lambda_handler --role "$ROLE_ARN" --timeout "$timeout" \
      --environment "Variables={TABELA_NOME=$TABELA,FILA_URL=$FILA_URL}" \
      --zip-file "fileb://$zip" >/dev/null 2>&1; do
      tentativa=$((tentativa + 1))
      [ $tentativa -ge 12 ] && { echo "  $nome: falhou após $tentativa tentativas"; return 1; }
      sleep 5
    done
  fi
  aws lambda wait function-updated --function-name "$nome"
  echo "  $nome"
}

info "Lambdas"
# Duas funções, não quatro: as três rotas HTTP compartilham a mesma (despacham
# por routeKey lá dentro), e o contador fica separado porque o gatilho é outro.
subir_lambda url-shortener-api      api.py      10
subir_lambda url-shortener-contador contador.py 15

# gatilho da fila no contador
if [ -z "$(aws lambda list-event-source-mappings --function-name url-shortener-contador \
            --query "EventSourceMappings[?EventSourceArn=='$FILA_ARN'].UUID" --output text)" ]; then
  aws lambda create-event-source-mapping --function-name url-shortener-contador \
    --event-source-arn "$FILA_ARN" --batch-size 1 >/dev/null
  echo "  gatilho SQS -> contador"
fi

# ── API Gateway (HTTP API) ──────────────────────────────────────────────────
info "API Gateway: $API"
API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='$API'].ApiId" --output text)
SITE="http://$BUCKET.s3-website-$REGIAO.amazonaws.com"
if [ -z "$API_ID" ]; then
  API_ID=$(aws apigatewayv2 create-api --name "$API" --protocol-type HTTP \
    --cors-configuration "AllowOrigins=$SITE,AllowMethods=GET,POST,OPTIONS,AllowHeaders=content-type" \
    --query ApiId --output text)
  echo "  criada"
else
  aws apigatewayv2 update-api --api-id "$API_ID" \
    --cors-configuration "AllowOrigins=$SITE,AllowMethods=GET,POST,OPTIONS,AllowHeaders=content-type" >/dev/null
  echo "  atualizada"
fi

rota() {
  local chave=$1 fn=$2
  local arn="arn:aws:lambda:$REGIAO:$CONTA:function:$fn"
  local integ
  integ=$(aws apigatewayv2 create-integration --api-id "$API_ID" \
    --integration-type AWS_PROXY --integration-uri "$arn" --payload-format-version 2.0 \
    --query IntegrationId --output text)
  # Se a rota já existe, APONTA ela para a integração nova. Só criar quando
  # falta deixaria a rota velha presa numa integração órfã — e o sintoma é um
  # 500 do API Gateway sem nenhum log na Lambda, porque ela nem é invocada.
  local id_rota
  id_rota=$(aws apigatewayv2 get-routes --api-id "$API_ID" --query "Items[?RouteKey=='$chave'].RouteId" --output text)
  if [ -z "$id_rota" ]; then
    aws apigatewayv2 create-route --api-id "$API_ID" --route-key "$chave" \
      --target "integrations/$integ" >/dev/null
  else
    aws apigatewayv2 update-route --api-id "$API_ID" --route-id "$id_rota" \
      --target "integrations/$integ" >/dev/null
  fi
  # o API Gateway precisa de permissão explícita para invocar a função
  aws lambda add-permission --function-name "$fn" --statement-id "apigw-$(echo "$chave" | tr -cd '[:alnum:]')" \
    --action lambda:InvokeFunction --principal apigateway.amazonaws.com \
    --source-arn "arn:aws:execute-api:$REGIAO:$CONTA:$API_ID/*/*" >/dev/null 2>&1 || true
  echo "  $chave -> $fn"
}
rota "POST /shorten"          url-shortener-api
rota "GET /urls"              url-shortener-api
rota "GET /{shortId}"         url-shortener-api

# a HTTP API faz auto-deploy no stage $default, que não entra no caminho da URL
if ! existe aws apigatewayv2 get-stage --api-id "$API_ID" --stage-name '$default'; then
  aws apigatewayv2 create-stage --api-id "$API_ID" --stage-name '$default' --auto-deploy >/dev/null
fi
API_URL="https://$API_ID.execute-api.$REGIAO.amazonaws.com"

# ── S3 ──────────────────────────────────────────────────────────────────────
info "S3: $BUCKET"
existe aws s3api head-bucket --bucket "$BUCKET" || aws s3 mb "s3://$BUCKET" --region "$REGIAO" >/dev/null
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
aws s3api put-bucket-policy --bucket "$BUCKET" --policy "{
  \"Version\":\"2012-10-17\",
  \"Statement\":[{\"Sid\":\"PublicReadGetObject\",\"Effect\":\"Allow\",\"Principal\":\"*\",
    \"Action\":\"s3:GetObject\",\"Resource\":\"arn:aws:s3:::$BUCKET/*\"}]
}"
aws s3api put-bucket-website --bucket "$BUCKET" \
  --website-configuration '{"IndexDocument":{"Suffix":"index.html"}}'

# injeta a URL da API numa cópia — o index.html do repositório fica com o
# placeholder, que é o que o aluno edita à mão na aula
TMP=$(mktemp -d)
sed "s|https://SEU-API-ID.execute-api.us-east-1.amazonaws.com|$API_URL|" index.html > "$TMP/index.html"
aws s3 cp "$TMP/index.html" "s3://$BUCKET/index.html" --content-type text/html >/dev/null
echo "  index.html publicado"

info "Pronto"
echo "  Site: $SITE"
echo "  API:  $API_URL"
