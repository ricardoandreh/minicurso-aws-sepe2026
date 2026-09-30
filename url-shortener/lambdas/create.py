"""url-shortener-create — POST /shorten

Recebe uma URL longa, gera um ID curto e grava no DynamoDB.

Variável de ambiente: TABELA_NOME
Permissão necessária na role: escrita no DynamoDB
"""
import json
import os
import secrets
import string
from datetime import datetime, timezone

import boto3

tabela = boto3.resource("dynamodb").Table(os.environ["TABELA_NOME"])

ALFABETO = string.ascii_letters + string.digits
TAMANHO_ID = 6
TENTATIVAS = 5


def _resposta(status, corpo):
    # Sem cabeçalhos de CORS aqui de propósito: quem responde o preflight
    # OPTIONS é o próprio API Gateway, pela configuração de CORS da HTTP API.
    # Cabeçalho devolvido pela Lambda não resolve CORS — o preflight nem chega.
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(corpo),
    }


def _url_curta(event, short_id):
    dominio = event["requestContext"]["domainName"]
    stage = event["requestContext"]["stage"]
    # A HTTP API faz auto-deploy no stage "$default", que NÃO entra no caminho
    # da URL. Só um stage nomeado vira prefixo.
    prefixo = "" if stage == "$default" else f"/{stage}"
    return f"https://{dominio}{prefixo}/{short_id}"


def lambda_handler(event, context):
    corpo = json.loads(event.get("body") or "{}")
    url_longa = (corpo.get("url") or "").strip()

    if not url_longa.startswith(("http://", "https://")):
        return _resposta(400, {"error": "Envie uma url começando com http:// ou https://"})

    agora = int(datetime.now(timezone.utc).timestamp())

    for _ in range(TENTATIVAS):
        short_id = "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO_ID))
        try:
            # A condição é o que garante que não sobrescrevemos um ID existente.
            # Uma escrita condicional resolve isso sem precisar ler antes.
            tabela.put_item(
                Item={
                    "shortId": short_id,
                    "longUrl": url_longa,
                    "createdAt": agora,
                    "clicks": 0,
                },
                ConditionExpression="attribute_not_exists(shortId)",
            )
        except tabela.meta.client.exceptions.ConditionalCheckFailedException:
            continue  # colidiu, sorteia outro

        return _resposta(201, {
            "shortId": short_id,
            "shortUrl": _url_curta(event, short_id),
            "longUrl": url_longa,
        })

    return _resposta(503, {"error": "Não foi possível gerar um ID livre, tente de novo"})
