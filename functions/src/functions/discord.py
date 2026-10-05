"""url-shortener-discord — assina o tópico SNS de marcos

Recebe o aviso de que um link bateu 10 cliques e posta no Discord.
Não decide nada: quem decidiu foi o filtro do EventBridge Pipe, que só deixa
passar o registro em que `clicks` cruzou de 9 para 10. Esta função notifica,
e é só isso que ela faz.

Variável de ambiente: WEBHOOK_URL (injetada pelo SST)
"""
import json
import os
import urllib.request

WEBHOOK_URL = os.environ["WEBHOOK_URL"]


def _webhook_url():
    return WEBHOOK_URL


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
