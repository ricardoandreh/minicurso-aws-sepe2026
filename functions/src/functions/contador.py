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
        # Mensagem malformada nunca vai dar certo numa retentativa, então
        # descartar é melhor que levantar. Sem DLQ, uma mensagem envenenada
        # volta a cada visibility timeout até a retenção expirar: com os
        # padrões do console, 30s e 4 dias, são 11.520 invocações com o mesmo
        # erro. E numa invocação em lote ela ainda derruba junto os cliques
        # bons que vieram com ela, que seriam reprocessados e contados de novo.
        try:
            corpo = json.loads(registro["body"])
            short_id = corpo["shortId"]
            if not isinstance(short_id, str) or not short_id:
                raise ValueError("shortId ausente ou vazio")
        except (ValueError, KeyError, TypeError) as erro:
            print(f"mensagem descartada: {erro} | corpo={registro['body'][:200]!r}")
            continue

        # ADD é o contador atômico do DynamoDB: duas Lambdas incrementando ao
        # mesmo tempo não perdem contagem, e funciona mesmo se o atributo
        # ainda não existir. Ler, somar em Python e gravar teria race condition.
        #
        # A condição não é detalhe. Sem ela o ADD CRIA o item quando a chave
        # não existe, e qualquer mensagem na fila vira linha na tabela: basta
        # publicar {"shortId": "abc"} pelo console do SQS. Quem valida o link é
        # o redirect, que devolve 404, mas quem escreve é esta função, e entre
        # as duas há uma fila que aceita mensagem de qualquer origem. Validar
        # no produtor não protege o consumidor.
        try:
            tabela.update_item(
                Key={"shortId": short_id},
                UpdateExpression="ADD clicks :um",
                ConditionExpression="attribute_exists(shortId)",
                ExpressionAttributeValues={":um": 1},
            )
        except tabela.meta.client.exceptions.ConditionalCheckFailedException:
            # O link não existe, ou foi apagado enquanto o clique esperava na
            # fila. Descartar é o certo: contar clique de link que não existe
            # não significa nada, e levantar aqui faria a mensagem voltar para
            # a fila e repetir para sempre.
            print(f"clique de {short_id} descartado: link inexistente")
            continue

        print(f"clique contado para {short_id}")
