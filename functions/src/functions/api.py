import json
import uuid
from datetime import datetime, timezone

import boto3
from sst import Resource

dynamodb = boto3.resource("dynamodb")
sqs = boto3.client("sqs")


def _tabela():
    return dynamodb.Table(Resource.Chamados.name)


def _fila_url():
    return Resource.ChamadosFila.url


def _resposta(status, body):
    return {
        "statusCode": status,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _criar_chamado(body):
    dados = json.loads(body or "{}")
    titulo = dados.get("titulo")
    descricao = dados.get("descricao", "")

    if not titulo:
        return _resposta(400, {"erro": "titulo é obrigatório"})

    chamado_id = str(uuid.uuid4())
    item = {
        "id": chamado_id,
        "titulo": titulo,
        "descricao": descricao,
        "status": "aberto",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    _tabela().put_item(Item=item)

    sqs.send_message(
        QueueUrl=_fila_url(),
        MessageBody=json.dumps(
            {
                "id": chamado_id,
                "titulo": titulo,
                "descricao": descricao,
            }
        ),
    )

    return _resposta(201, item)


def _listar_chamados():
    resultado = _tabela().scan()
    itens = sorted(
        resultado.get("Items", []),
        key=lambda i: i.get("timestamp", ""),
        reverse=True,
    )
    return _resposta(200, {"chamados": itens})


def handler(event, context):
    metodo = event["requestContext"]["http"]["method"]

    if metodo == "POST":
        return _criar_chamado(event.get("body"))

    if metodo == "GET":
        return _listar_chamados()

    return _resposta(405, {"erro": "método não suportado"})
