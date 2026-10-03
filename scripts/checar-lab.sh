#!/usr/bin/env bash
# Depois de todo Start do Learner Lab: as assinaturas de fila voltam Disabled e
# os pipes voltam Stopped, e nenhuma das duas falhas aparece como erro.
# Com --corrigir, religa tudo.
set -uo pipefail
P=labs
CORRIGIR=0
for a in "$@"; do
  case "$a" in --corrigir) CORRIGIR=1;; --profile=*) P="${a#*=}";; esac
done

aws sts get-caller-identity --profile $P --query Account --output text >/dev/null 2>&1 || {
  echo "credenciais do perfil '$P' invalidas ou expiradas. Renove o lab."; exit 1; }

problemas=0

echo "== assinaturas de fila =="
aws lambda list-event-source-mappings --profile $P \
  --query 'EventSourceMappings[].[State,UUID,EventSourceArn]' --output text |
while read -r estado uuid origem; do
  printf "  %-9s %s\n" "$estado" "$(basename "$origem")"
done
paradas=$(aws lambda list-event-source-mappings --profile $P \
  --query 'EventSourceMappings[?State!=`Enabled`].UUID' --output text)
if [ -n "$paradas" ]; then
  problemas=1
  for u in $paradas; do
    if [ $CORRIGIR -eq 1 ]; then
      aws lambda update-event-source-mapping --profile $P --uuid "$u" --enabled >/dev/null && echo "  religando $u"
    else
      echo "  PARADA: $u   (rode com --corrigir)"
    fi
  done
fi

echo
echo "== pipes =="
aws pipes list-pipes --profile $P --query 'Pipes[].[CurrentState,Name]' --output text |
while read -r estado nome; do printf "  %-9s %s\n" "$estado" "$nome"; done
parados=$(aws pipes list-pipes --profile $P --query 'Pipes[?CurrentState!=`RUNNING`].Name' --output text)
if [ -n "$parados" ]; then
  problemas=1
  for n in $parados; do
    if [ $CORRIGIR -eq 1 ]; then
      aws pipes start-pipe --profile $P --name "$n" >/dev/null && echo "  iniciando $n"
    else
      echo "  PARADO: $n   (rode com --corrigir)"
    fi
  done
fi

echo
echo "== filas com mensagem represada =="
for q in $(aws sqs list-queues --profile $P --query 'QueueUrls' --output text 2>/dev/null); do
  n=$(aws sqs get-queue-attributes --profile $P --queue-url "$q" \
      --attribute-names ApproximateNumberOfMessages \
      --query 'Attributes.ApproximateNumberOfMessages' --output text)
  [ "$n" != "0" ] && { echo "  $(basename "$q"): $n"; problemas=1; }
done
[ $problemas -eq 0 ] && echo "  nenhuma"

echo
[ $problemas -eq 0 ] && echo "tudo no lugar." || \
  { [ $CORRIGIR -eq 1 ] && echo "corrigido. Reconfira em 1 minuto." || echo "ha o que corrigir. Rode: $0 --corrigir"; }
