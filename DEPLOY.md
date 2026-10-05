# Deploy: Central de Chamados

Branch: `chamados-pronto` — tudo pronto para deploy, sem atrito.

## Quick Start

```bash
# 1. Cria os buckets do S3 (necessário no Learner Lab)
scripts/setup-bucket.sh

# 2. Seta os secrets
npx sst secret set GroqApiKey "sk-..." --stage lab
npx sst secret set DiscordWebhook "https://discord.com/api/webhooks/..." --stage lab
npx sst secret set ApiKey "sua-chave-api" --stage lab

# 3. Deploy
npx sst deploy --stage lab
```

## O que o `setup-bucket.sh` faz

1. Detecta seu Account ID
2. Cria dois buckets com nomes padrão:
   - `minicurso-relatorios-{ACCOUNT_ID}` (para geração de relatórios)
   - `minicurso-site-{ACCOUNT_ID}` (para o frontend public)
3. Se os buckets já existem, não faz nada (idempotent)
4. Exporta as variáveis de ambiente para o deploy

## Customização

Se você quer buckets com nomes específicos:

```bash
RELATORIOS_BUCKET=meu-bucket-relatorios \
FRONTEND_BUCKET=meu-bucket-site \
npx sst deploy --stage lab
```

Ou edite o `sst.config.ts` direto e mude os defaults nas linhas:
```typescript
const relatoriosBucket = process.env.RELATORIOS_BUCKET || "minicurso-relatorios";
const frontendBucketName = process.env.FRONTEND_BUCKET || process.env.BUCKET_SITE || "minicurso-site";
```

## Por que é assim

O AWS Learner Lab tem uma SCP que bloqueia `s3:GetBucketObjectLockConfiguration`, impedindo criação de S3 via Pulumi (que verifica a config ao criar **e** ao referenciar um bucket).

A solução: criar via boto3 (que não faz essa verificação) no script, e passar referências já existentes ao SST.

## Layers

O projeto usa `layers/strands-openai/build` para Groq + OpenAI. Se não existe, crie:

```bash
mkdir -p layers/strands-openai/build/python
pip install -t layers/strands-openai/build/python groq -q
```

## Stack

- **DynamoDB:** Tabela `Chamados` com registros de tickets
- **SQS:** Fila de processamento de mensagens
- **SNS:** Fan-out para notificações
- **Lambda:** Agente (Groq LLM) + Notificador Discord
- **S3:** Buckets para relatórios e frontend

## Troubleshooting

**"Informe o bucket do site"**
```bash
scripts/setup-bucket.sh && npx sst deploy --stage lab
```

**"NoSuchBucket: The specified bucket does not exist"**
Rode `scripts/setup-bucket.sh` de novo, ou confirme os nomes:
```bash
aws s3 ls | grep minicurso
```

**"Access Denied" em SSM GetParameter**
Confirme que os secrets foram setados:
```bash
npx sst secret list --stage lab
```
