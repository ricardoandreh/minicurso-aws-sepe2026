"""url-shortener-redirect — GET /{shortId}

Busca a URL longa e redireciona. A contagem de cliques NÃO acontece aqui:
vai para uma fila SQS e é processada por outra Lambda. O redirect é o caminho
crítico — quem clicou está esperando — e contar clique não pode atrasá-lo.
Isso é Queue-Based Load Leveling.

Variáveis de ambiente: TABELA_NOME, FILA_URL
Permissões necessárias na role: leitura no DynamoDB, envio no SQS
"""
import json
import os

import boto3

tabela = boto3.resource("dynamodb").Table(os.environ["TABELA_NOME"])
sqs = boto3.client("sqs")
FILA_URL = os.environ["FILA_URL"]


def lambda_handler(event, context):
    short_id = (event.get("pathParameters") or {}).get("shortId")

    item = tabela.get_item(Key={"shortId": short_id}).get("Item") if short_id else None
    if not item:
        return {
            "statusCode": 404,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": "Link não encontrado"}),
        }

    # Fire-and-forget: se o SQS falhar, o usuário ainda é redirecionado.
    # Perder uma contagem é aceitável; perder o redirect não é.
    try:
        sqs.send_message(QueueUrl=FILA_URL, MessageBody=json.dumps({"shortId": short_id}))
    except Exception as erro:  # noqa: BLE001
        print(f"falha ao enfileirar clique de {short_id}: {erro}")

    # 302, não 301. O 301 é permanente e o navegador guarda em cache: o
    # segundo clique no mesmo link não voltaria à API e o contador pararia
    # de subir — exatamente o que queremos demonstrar.
    return {"statusCode": 302, "headers": {"Location": item["longUrl"]}}
