#!/usr/bin/env bash
# Builda e sobe o frontend pro S3 — roda depois de `sst deploy --stage lab`.
# Separado do deploy da infra de propósito: build de frontend e infra têm
# ciclos de vida diferentes, e não existe um comando `sst output`/`sst secret
# get` pronto — pegamos tudo via `sst state export` + `sst secret list`.
set -euo pipefail
cd "$(dirname "$0")/.."

state=$(npx sst state export --stage lab)
outputs() { echo "$state" | jq -r ".latest.resources[] | select(.type==\"pulumi:pulumi:Stack\") | .outputs.$1"; }

api_url=$(outputs api)
bucket=$(outputs bucket)
site_url=$(outputs site)

# A ApiKey NÃO entra no build: o site pede a chave num campo e guarda no
# sessionStorage. Se ela fosse embutida via VITE_*, o Vite a gravaria como
# literal no bundle e qualquer visitante a leria no DevTools. Aqui só a
# imprimimos para a pessoa colar no site (num pipeline real um segredo
# nunca sairia impresso no log).
api_key=$(npx sst secret list --stage lab | grep '^ApiKey=' | cut -d= -f2)

cd packages/frontend
VITE_API_URL="$api_url" npm run build
aws s3 sync dist "s3://$bucket" --delete --region us-east-1

echo
echo "  Site:   $site_url"
echo "  API:    $api_url"
echo "  ApiKey: $api_key"
echo
echo "Cole a ApiKey no campo \"Chave de acesso\" do site para criar chamados."
