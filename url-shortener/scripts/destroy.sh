#!/usr/bin/env bash
# Remove tudo que o deploy.sh criou, para a aula começar do zero no console.
set -uo pipefail

REGIAO=${REGIAO:-us-east-1}
TABELA=${TABELA:-url-shortener-urls}
FILA=${FILA:-url-shortner-queue}
BUCKET=${BUCKET:-url-shortener-poc-3252343}
ROLE=${ROLE:-url-shortener-lambda-role}
API=${API:-url-shortener-api}

echo "Removendo o encurtador..."

API_ID=$(aws apigatewayv2 get-apis --query "Items[?Name=='$API'].ApiId" --output text 2>/dev/null)
[ -n "$API_ID" ] && aws apigatewayv2 delete-api --api-id "$API_ID" && echo "  API $API_ID"

for U in $(aws lambda list-event-source-mappings --query 'EventSourceMappings[?contains(FunctionArn,`url-shortener`)].UUID' --output text 2>/dev/null); do
  aws lambda delete-event-source-mapping --uuid "$U" >/dev/null 2>&1 && echo "  event source mapping $U"
done

for F in $(aws lambda list-functions --query 'Functions[?starts_with(FunctionName,`url-shortener`)].FunctionName' --output text 2>/dev/null); do
  aws lambda delete-function --function-name "$F" && echo "  lambda $F"
done

if aws iam get-role --role-name "$ROLE" >/dev/null 2>&1; then
  for P in $(aws iam list-role-policies --role-name "$ROLE" --query PolicyNames --output text); do
    aws iam delete-role-policy --role-name "$ROLE" --policy-name "$P"
  done
  for P in $(aws iam list-attached-role-policies --role-name "$ROLE" --query 'AttachedPolicies[].PolicyArn' --output text); do
    aws iam detach-role-policy --role-name "$ROLE" --policy-arn "$P"
  done
  aws iam delete-role --role-name "$ROLE" && echo "  role $ROLE"
fi

Q=$(aws sqs get-queue-url --queue-name "$FILA" --query QueueUrl --output text 2>/dev/null)
[ -n "$Q" ] && [ "$Q" != "None" ] && aws sqs delete-queue --queue-url "$Q" && echo "  fila $FILA"

aws dynamodb delete-table --table-name "$TABELA" >/dev/null 2>&1 && echo "  tabela $TABELA"

aws s3 rm "s3://$BUCKET" --recursive >/dev/null 2>&1
aws s3 rb "s3://$BUCKET" >/dev/null 2>&1 && echo "  bucket $BUCKET"

echo "Feito. Roles criadas pelo console (service-role/...) não são tocadas."
