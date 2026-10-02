"""url-shortener-api — as três rotas HTTP numa função só

    POST /shorten       cria um link curto
    GET  /urls          lista os links
    GET  /{shortId}     redireciona e enfileira o clique

Por que uma só: separar função por rota é tentador, mas o critério que importa
é **o gatilho e o ciclo de vida**, não a URL. As três reagem ao mesmo gatilho
(HTTP, síncrono), escalam juntas e falham juntas — então são uma função. O
contador fica separado porque reage a outro gatilho (fila, assíncrono), tem
outro perfil de falha e pode ser retentado sem ninguém esperando.

Variáveis de ambiente: TABELA_NOME, FILA_URL
"""
import json
import os
import secrets
import string
from datetime import datetime, timezone

import boto3

tabela = boto3.resource("dynamodb").Table(os.environ["TABELA_NOME"])
sqs = boto3.client("sqs")
FILA_URL = os.environ["FILA_URL"]

ALFABETO = string.ascii_letters + string.digits
TAMANHO_ID = 6
TENTATIVAS = 5


def _resposta(status, corpo):
    # Sem cabeçalhos de CORS aqui de propósito: quem responde o preflight
    # OPTIONS é o próprio API Gateway, pela configuração de CORS da HTTP API.
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(corpo),
    }


def _criar(event):
    corpo = json.loads(event.get("body") or "{}")
    url_longa = (corpo.get("url") or "").strip()

    if not url_longa.startswith(("http://", "https://")):
        return _resposta(400, {"error": "Envie uma url começando com http:// ou https://"})

    agora = int(datetime.now(timezone.utc).timestamp())

    for _ in range(TENTATIVAS):
        short_id = "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO_ID))
        try:
            # A escrita condicional garante que não sobrescrevemos um ID
            # existente, sem precisar ler antes.
            tabela.put_item(
                Item={"shortId": short_id, "longUrl": url_longa,
                      "createdAt": agora, "clicks": 0},
                ConditionExpression="attribute_not_exists(shortId)",
            )
        except tabela.meta.client.exceptions.ConditionalCheckFailedException:
            continue

        dominio = event["requestContext"]["domainName"]
        stage = event["requestContext"]["stage"]
        # A HTTP API faz auto-deploy no stage "$default", que NÃO entra no
        # caminho da URL. Só um stage nomeado vira prefixo.
        prefixo = "" if stage == "$default" else f"/{stage}"

        return _resposta(201, {
            "shortId": short_id,
            "shortUrl": f"https://{dominio}{prefixo}/{short_id}",
            "longUrl": url_longa,
        })

    return _resposta(503, {"error": "Não foi possível gerar um ID livre, tente de novo"})


def _listar(event):
    # Scan varre a tabela inteira
    itens = tabela.scan().get("Items", [])

    # Número no DynamoDB volta como Decimal, e json.dumps não serializa
    # Decimal, sem os int() aqui a resposta quebra com TypeError e vira 500.
    links = sorted(
        ({"shortId": i["shortId"], "longUrl": i["longUrl"],
          "clicks": int(i.get("clicks", 0)), "createdAt": int(i.get("createdAt", 0))}
         for i in itens),
        key=lambda link: link["createdAt"],
        reverse=True,
    )
    return _resposta(200, {"links": links})


def _redirecionar(event):
    short_id = (event.get("pathParameters") or {}).get("shortId")
    item = tabela.get_item(Key={"shortId": short_id}).get("Item") if short_id else None

    if not item:
        return _resposta(404, {"error": "Link não encontrado"})

    # Fire-and-forget: se o SQS falhar, o usuário ainda é redirecionado.
    # Perder uma contagem é aceitável; perder o redirect não é.
    try:
        sqs.send_message(QueueUrl=FILA_URL, MessageBody=json.dumps({"shortId": short_id}))
    except Exception as erro:  # noqa: BLE001
        print(f"falha ao enfileirar clique de {short_id}: {erro}")

    # 302, não 301. O 301 é permanente e o navegador guarda em cache: o
    # segundo clique no mesmo link não voltaria à API e o contador pararia
    # de subir, exatamente o que queremos demonstrar.
    return {"statusCode": 302, "headers": {"Location": item["longUrl"]}}


# O routeKey do payload 2.0 vem com a rota inteira ("GET /{shortId}"), então
# este dicionário é um espelho literal das rotas da API. Método sozinho não
# serviria: /urls e /{shortId} são os dois GET.
ROTAS = {
    "POST /shorten": _criar,
    "GET /urls": _listar,
    "GET /{shortId}": _redirecionar,
}


def handler(event, ctx):
    tratar = ROTAS.get(event.get("routeKey"))
    if not tratar:
        return _resposta(404, {"error": f"Rota não tratada: {event.get('routeKey')}"})
    return tratar(event)
