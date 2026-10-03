"""url-shortener-discord — assina o tópico SNS de marcos

Recebe o aviso de que um link bateu 10 cliques e posta no Discord.
Não decide nada: quem decidiu foi o filtro do EventBridge Pipe, que só deixa
passar o registro em que `clicks` cruzou de 9 para 10. Esta função notifica,
e é só isso que ela faz.

Variável de ambiente: WEBHOOK_PARAM, nome ou ARN do parâmetro
    (ex.: /labs/discord-webhook, ou o ARN completo; get_parameter aceita os dois)
Permissão necessária na role: ssm:GetParameter (e kms:Decrypt, para SecureString)
"""
import json
import os
import urllib.request

import boto3

ssm = boto3.client("ssm")
PARAMETRO = os.environ["WEBHOOK_PARAM"]

# Cache entre invocações: o módulo só é carregado no cold start, então a
# consulta ao Parameter Store acontece uma vez por ambiente de execução, não
# uma vez por mensagem. O Parameter Store tem limite de requisições por
# segundo, e buscar o mesmo valor a cada invocação é a forma mais comum de
# esbarrar nele sem perceber.
_webhook = None


def _webhook_url():
    global _webhook
    if _webhook is None:
        _webhook = ssm.get_parameter(Name=PARAMETRO, WithDecryption=True)["Parameter"]["Value"]
    return _webhook


def _postar(mensagem):
    requisicao = urllib.request.Request(
        _webhook_url(),
        data=json.dumps({"content": mensagem}).encode(),
        # sem User-Agent, o Cloudflare do Discord bloqueia a requisição
        # (erro 1010) — o User-Agent padrão do urllib é reconhecido como bot
        headers={
            "Content-Type": "application/json",
            "User-Agent": "url-shortener-bot/1.0",
        },
        method="POST",
    )
    urllib.request.urlopen(requisicao)


def lambda_handler(event, context):
    for registro in event["Records"]:
        # O SNS entrega o corpo como string. Sem input transformer no Pipe,
        # o que vem aqui é o registro cru do DynamoDB Stream, com os atributos
        # tipados ({"S": "..."}, {"N": "..."}).
        dados = json.loads(registro["Sns"]["Message"])
        imagem = dados["dynamodb"]["NewImage"]

        short_id = imagem["shortId"]["S"]
        url_longa = imagem["longUrl"]["S"]
        cliques = imagem["clicks"]["N"]

        # A URL vai entre crases para o Discord não montar o cartão de
        # preview: sem isso uma mensagem de duas linhas vira meia tela. De
        # quebra ela deixa de ser clicável, o que aqui é desejável, já que o
        # destino é digitado por quem usa o encurtador e ninguém auditou.
        _postar(
            f"🎉 **O link `{short_id}` bateu {cliques} cliques!**\n"
            f"Destino: `{url_longa}`"
        )
        print(f"parabéns postado para {short_id}")
