"""url-shortener-contador — disparada pela fila SQS

Lê os cliques da fila e incrementa o contador no DynamoDB.

Variável de ambiente: TABELA_NOME
Permissão necessária na role: escrita no DynamoDB (o gatilho do SQS já pede
a permissão de leitura da fila quando você o cria pelo console)
"""
import json
import os

import boto3

tabela = boto3.resource("dynamodb").Table(os.environ["TABELA_NOME"])


def lambda_handler(event, context):
    # "Records" é sempre uma lista, mesmo com uma mensagem só: se vários
    # cliques chegarem juntos, o SQS agrupa tudo numa invocação.
    for registro in event["Records"]:
        short_id = json.loads(registro["body"])["shortId"]

        # ADD é o contador atômico do DynamoDB: duas Lambdas incrementando ao
        # mesmo tempo não perdem contagem, e funciona mesmo se o atributo
        # ainda não existir. Ler, somar em Python e gravar teria race condition.
        tabela.update_item(
            Key={"shortId": short_id},
            UpdateExpression="ADD clicks :um",
            ExpressionAttributeValues={":um": 1},
        )
        print(f"clique contado para {short_id}")
