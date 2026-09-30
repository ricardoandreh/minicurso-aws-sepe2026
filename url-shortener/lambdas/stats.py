"""url-shortener-stats — GET /{shortId}/stats

Devolve os dados de um link curto, incluindo o contador de cliques.

Variável de ambiente: TABELA_NOME
Permissão necessária na role: leitura no DynamoDB
"""
import json
import os

import boto3

tabela = boto3.resource("dynamodb").Table(os.environ["TABELA_NOME"])


def _resposta(status, corpo):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(corpo),
    }


def lambda_handler(event, context):
    short_id = (event.get("pathParameters") or {}).get("shortId")

    item = tabela.get_item(Key={"shortId": short_id}).get("Item") if short_id else None
    if not item:
        return _resposta(404, {"error": "Link não encontrado"})

    # Número no DynamoDB volta como Decimal, e json.dumps não sabe serializar
    # Decimal — sem o int() aqui a resposta quebra com TypeError e vira 500.
    return _resposta(200, {
        "shortId": short_id,
        "longUrl": item["longUrl"],
        "clicks": int(item.get("clicks", 0)),
        "createdAt": int(item.get("createdAt", 0)),
    })
