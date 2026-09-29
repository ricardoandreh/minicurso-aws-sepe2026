import json
from datetime import datetime, timezone

import boto3
from strands import Agent
from strands.models.openai import OpenAIModel
from sst import Resource

GROQ_BASE_URL = "https://api.groq.com/openai/v1"

s3 = boto3.client("s3")
sns = boto3.client("sns")

SYSTEM_PROMPT = (
    "Você é um assistente de central de chamados. Leia o título e a "
    "descrição do chamado e responda em português com: 1) uma "
    "classificação de prioridade (baixa, média, alta ou crítica) e "
    "2) uma sugestão objetiva de próxima ação para a equipe de suporte. "
    "Seja direto, no máximo 4 linhas."
)


def _groq_api_key():
    return Resource.GroqApiKey.value


def _topico_arn():
    return Resource.ChamadosTopico.arn


def _bucket_nome():
    return Resource.Relatorios.name


def _analisar(chamado):
    model = OpenAIModel(
        client_args={"api_key": _groq_api_key(), "base_url": GROQ_BASE_URL},
        model_id="openai/gpt-oss-120b",
        params={"max_tokens": 300, "temperature": 0.3},
    )
    agente = Agent(model=model, system_prompt=SYSTEM_PROMPT)
    resposta = agente(
        f"Título: {chamado['titulo']}\nDescrição: {chamado.get('descricao', '')}"
    )
    return str(resposta)


def _salvar_relatorio(chamado_id, chamado, analise):
    corpo = json.dumps(
        {
            "id": chamado_id,
            "chamado": chamado,
            "analise": analise,
            "gerado_em": datetime.now(timezone.utc).isoformat(),
        }
    )
    s3.put_object(
        Bucket=_bucket_nome(),
        Key=f"relatorios/{chamado_id}.json",
        Body=corpo,
        ContentType="application/json",
    )


def handler(event, context):
    for registro in event["Records"]:
        chamado = json.loads(registro["body"])
        chamado_id = chamado["id"]

        analise = _analisar(chamado)
        _salvar_relatorio(chamado_id, chamado, analise)

        sns.publish(
            TopicArn=_topico_arn(),
            Message=json.dumps(
                {
                    "id": chamado_id,
                    "chamado": chamado,
                    "analise": analise,
                }
            ),
        )
