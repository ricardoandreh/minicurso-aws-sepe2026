from sst import Resource


def _chave_esperada():
    return Resource.ApiKey.value


def handler(event, context):
    # HTTP API (v2) não suporta API Key + Usage Plan nativo (só a REST API);
    # este authorizer é o substituto: valida x-api-key manualmente.
    chave_recebida = event.get("headers", {}).get("x-api-key")
    autorizado = chave_recebida is not None and chave_recebida == _chave_esperada()
    return {"isAuthorized": autorizado}
