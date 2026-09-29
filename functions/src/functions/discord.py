import json
import urllib.request
from datetime import datetime, timezone

import boto3
from sst import Resource

dynamodb = boto3.resource("dynamodb")


def _webhook_url():
    return Resource.DiscordWebhook.value


def _tabela():
    return dynamodb.Table(Resource.Chamados.name)


def handler(event, context):
    dados = json.loads(event["Records"][0]["Sns"]["Message"])
    chamado = dados["chamado"]
    analise = dados["analise"]

    mensagem = (
        f"🎫 **Novo Chamado #{dados['id'][:8]}**\n\n"
        f"**Título:** {chamado['titulo']}\n"
        f"**Análise:** {analise}"
    )

    payload = json.dumps({"content": mensagem}).encode()
    requisicao = urllib.request.Request(
        _webhook_url(),
        data=payload,
        # sem User-Agent, o Cloudflare do Discord bloqueia a requisição
        # (erro 1010) — o User-Agent padrão do urllib é reconhecido como bot
        headers={
            "Content-Type": "application/json",
            "User-Agent": "central-chamados-bot/1.0",
        },
        method="POST",
    )
    urllib.request.urlopen(requisicao)

    _tabela().put_item(
        Item={
            "id": dados["id"],
            "titulo": chamado["titulo"],
            "descricao": chamado.get("descricao", ""),
            "analise": analise,
            "status": "notificado",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
