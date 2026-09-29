# Central de Chamados — minicurso AWS + SST Ion

Central de Chamados serverless (S3 · CloudFront · API Gateway · Lambda Python ·
DynamoDB · SQS · SNS · Parameter Store · Strands Agents · Groq), construída em
duas etapas: primeiro manualmente pelo console/CLI da AWS (Parte 1), depois
recriada como infraestrutura como código com SST Ion (Parte 2).

```
.
├── sst.config.ts              # infra da Parte 2 (não builda o frontend)
├── pyproject.toml             # raiz do workspace uv
├── functions/src/functions/    # api.py, authorizer.py, agente.py, discord.py
├── layers/strands-openai/      # deps do agente (Strands + provider OpenAI-compatible), build antes da aula
├── scripts/deploy-frontend.sh # build + upload do frontend, roda depois do sst deploy
└── packages/frontend/          # Vite vanilla JS, consome VITE_API_URL (a chave é digitada no site)
```

## Pré-requisitos

- Node.js 20+ e npm
- [uv](https://docs.astral.sh/uv/) (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- AWS CLI configurado com as credenciais do **AWS Learner Lab** (`aws configure`,
  ou exportar `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_SESSION_TOKEN`)
- Docker (opcional, só para compilar a Lambda Layer no mesmo runtime do Lambda)
- Uma conta [Groq](https://console.groq.com) (chave grátis) e um webhook de um
  canal Discord

As credenciais do Learner Lab expiram (normalmente ~4h) — se o deploy começar a
falhar com erro de autenticação, é isso: abra o Lab de novo e re-exporte as
credenciais.

## Setup

```bash
# dependências JS (raiz + sst)
npm install

# dependências Python (workspace uv)
uv sync --all-packages

# layer do agente — rodar uma vez, não ao vivo
./layers/strands-openai/build.sh
```

## Parte 1 — hands-on manual (quatro serviços, só navegador)

Sem código de infra e sem nada instalado na máquina: a turma cria quatro
recursos direto no console — bucket S3 com website hosting servindo o frontend
já pronto, tabela DynamoDB, uma Lambda Python simples que grava um chamado, e
uma fila SQS ligada nessa Lambda como trigger. O resultado é um pedaço real e
funcionando (**SQS → Lambda → DynamoDB**) mais o site no ar.

O site carrega mas não lista nada, porque ainda não existe API — é essa falta
que a Parte 2 preenche. API Gateway, Lambda Authorizer, o agente com Strands,
SNS e o Discord **não** são hands-on: aparecem na Parte 2, por código.

A Lambda da Parte 1 usa um handler próprio e curto (está no `roteiro.md`), não
os handlers de `functions/src/functions/`, que já são a versão final com
`from sst import Resource`.

## Parte 2 — deploy com SST Ion

```bash
# segredos — uma vez por stage, nunca commitados
npx sst secret set GroqApiKey "gsk_..." --stage lab
npx sst secret set DiscordWebhook "https://discord.com/api/webhooks/..." --stage lab
npx sst secret set ApiKey "$(openssl rand -hex 24)" --stage lab

npx sst deploy --stage lab
./scripts/deploy-frontend.sh
```

`sst.config.ts` só declara o bucket do frontend — o build (`npm run build`)
e o upload (`aws s3 sync`) rodam à parte em `deploy-frontend.sh`, depois que
a infra (API, secrets) já existe. O script pega a URL da API e o bucket via
`sst state export`, e a `ApiKey` via `sst secret list` (não existe um
`sst output`/`sst secret get` prontos na CLI). A chave **não** entra no build:
o script só a imprime no fim, para colar no campo "Chave de acesso" do site.

Pra atualizar só o frontend depois de mudar o HTML/CSS/JS, rode o script de
novo — não precisa de `sst deploy`.

O output do deploy traz a URL do site (S3 website hosting) e da API. Para
desfazer tudo no fim da aula:

```bash
npx sst remove --stage lab
```

## Templates para testar

Chamados prontos pra colar no frontend (ou mandar via `curl`), variando a
prioridade que o agente classifica:

```
Crítico
Título:    Banco de dados de produção fora do ar
Descrição: Aplicação principal retornando erro 500 em todas as requisições
           desde as 14h. Impacto em todos os clientes.

Alto
Título:    Login não funciona para novos usuários
Descrição: Usuários cadastrados hoje não conseguem autenticar — erro
           "credenciais inválidas" mesmo com senha correta. Afeta só
           cadastros recentes.

Médio
Título:    Relatório mensal com valores incorretos
Descrição: O relatório de vendas de outubro está somando duplicado os
           pedidos cancelados. Não trava o sistema, mas os números saem
           errados.

Baixo
Título:    Botão de exportar CSV com texto cortado
Descrição: Na tela de relatórios, o botão "Exportar CSV" está com o texto
           cortado em telas menores que 1024px. Só estético.

Genérico (teste rápido)
Título:    Servidor fora do ar
Descrição: Queries levando mais de 30s desde as 10h
```

## Frontend em desenvolvimento local

```bash
cd packages/frontend
cp .env.example .env   # preencher com a URL da API (a chave vai no campo do site)
npm install
npm run dev
```

## Notas técnicas

- **`usarLabRole` no topo do `run()`**: o Learner Lab não permite `iam:CreateRole`,
  então lá as `Function` são fixadas na `LabRole` existente. Numa conta AWS
  normal deixe `false` (o padrão) e o SST cria uma role por Function com apenas
  o que o `link()` daquela função exige. Para rodar no Lab, troque para `true`.
- **HTTP API não tem API Key/Usage Plan** (isso é exclusivo da REST API v1) —
  por isso a autenticação é um Lambda Authorizer (`authorizer.py`) validando o
  header `x-api-key` contra o secret `ApiKey`.
- **Python no SST Ion é community-supported** e exige um workspace `uv` com
  `pyproject.toml` por pacote — já configurado em `pyproject.toml` (raiz) e
  `functions/pyproject.toml`.
