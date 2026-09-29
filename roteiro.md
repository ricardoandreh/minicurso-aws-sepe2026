## AWS na prática: construindo uma aplicação web serverless com SST Ion (3h)

**Aplicação:** Central de Chamados cloud-native
**Stack:** S3 · CloudFront (conceitual) · API Gateway · Lambda Python · DynamoDB · SQS · SNS · Parameter Store · Strands Agents · Groq · SST Ion · AWS Learner Labs

> **Nota de ambiente:** este Learner Lab nega `cloudfront:CreateDistribution` (e OAC/OAI) para quem faz o deploy — não é uma questão de permissão específica, o CloudFront inteiro está fora do alcance nessa conta. O frontend usa S3 website hosting direto (sem CDN, sem HTTPS). CloudFront continua no roteiro como conceito — diagrama e explicação — mas sem hands-on. Se o Learner Lab da sua turma liberar CloudFront, reative o hands-on normalmente.

---

### Parte 1 — Fundamentos e hands-on no console (0:00–2:00)

**Cada serviço segue o mesmo ritmo:** o que é → para que serve → hands-on no console → como se encaixa na arquitetura.

---

#### 0:00–0:15 — Abertura

Mostrar a aplicação funcionando ao vivo — o participante vê o destino antes de começar:

> *"Essa é a Central de Chamados que vamos construir hoje. Frontend no browser, chamado criado, Discord recebe notificação com análise de AI em segundos. Tudo serverless, tudo na AWS. Vamos entender cada peça."*

Mostrar o diagrama completo da arquitetura:

```
Browser
    ↓
S3 (frontend, website hosting)      ← CloudFront iria aqui (bloqueado neste Lab)
    ↓
API Gateway (+ Lambda Authorizer) → Lambda Python (API)
    ↓                          ↓
DynamoDB                      SQS
(chamados)                      ↓
                          Lambda Python
                          Strands + Groq
                               ↓            ↓
                          SNS Topic      S3 (relatórios)
                               ↓
                          Lambda Python (Discord)
                               ↓              ↓
                           Discord        DynamoDB
                                         (histórico)

Parameter Store
├── /minicurso/groq-api-key
├── /minicurso/discord-webhook
└── /minicurso/api-key
```

Shared Responsibility Model — 3 minutos:

```
Você gerencia               AWS gerencia
────────────────────────────────────────
Código da função            Servidor físico
Dados                       Sistema operacional
IAM e permissões            Runtime do Lambda
Configuração                Escalabilidade
                            Disponibilidade
                            Patches de segurança
```

> *"Quanto mais managed o serviço, mais responsabilidade vai para a AWS. Lambda, DynamoDB, SQS — vocês gerenciam o código e as permissões. A AWS gerencia o resto. Isso é serverless."*

Design patterns que vão aparecer — nomear antes de ver:

- **Event-Driven Architecture** — o padrão guarda-chuva: nada chama nada diretamente, cada peça reage a um evento (mensagem na fila, publicação no tópico) e produz o próximo. Os três abaixo são formas concretas disso na nossa arquitetura.
- **Queue-Based Load Leveling** — SQS como buffer entre produtor e consumidor
- **Fan-out** — SNS entregando para múltiplos subscribers independentes
- **Pipes and Filters** — cada Lambda faz uma coisa só, passa o resultado adiante

**Aprendizado:** modelo mental completo antes de tocar no console. O participante sabe onde cada serviço se encaixa antes de vê-lo funcionar.

---

#### 0:15–0:30 — S3 e CloudFront

**O que é S3:**
> *"Storage de objetos. Qualquer arquivo, qualquer tamanho, qualquer formato. Backup, dataset, log, frontend — o S3 guarda tudo. É o serviço mais usado da AWS."*

**Hands-on:**
- Criar bucket S3
- Fazer upload do `index.html` do frontend já pronto no scaffold
- Habilitar website hosting
- Acessar via URL do S3 — sem HTTPS, sem CDN

**O que é CloudFront — conceitual, sem hands-on neste Lab:**
> *"CDN da AWS. Coloca o conteúdo mais perto do usuário, adiciona HTTPS automático e cache. Sem CloudFront o S3 serve de uma região só e sem HTTPS — é exatamente o que estamos vendo agora. Com CloudFront na frente, o bucket fica privado (via Origin Access Control) e o CDN serve do ponto de presença mais próximo do usuário no mundo, com HTTPS automático."*

> *"Esse Learner Lab especificamente nega `cloudfront:CreateDistribution` pra quem faz o deploy — não é uma permissão faltando, é o serviço inteiro fora do alcance dessa conta. Numa conta AWS normal, ou num Lab que libere CloudFront, os passos seriam: criar a distribuição apontando pro bucket S3, configurar Origin Access Control pra tirar o bucket do público, acessar via URL do CloudFront com HTTPS."*

**Aprendizado:** S3 como hosting estático, CloudFront como CDN — o conceito e por que ele importa, mesmo sem poder provisionar neste ambiente. O participante entende que o frontend não precisa de servidor, e que nem toda permissão que se espera numa conta AWS está disponível num ambiente de laboratório restrito.

---

#### 0:30–0:45 — DynamoDB

**O que é DynamoDB:**
> *"Banco NoSQL serverless. Sem schema fixo, sem servidor para gerenciar, escala automaticamente. Pay-per-request — você paga por leitura e escrita, não por servidor ligado 24h."*

> *"Por que não RDS aqui? Chamados têm estrutura variável — cada um pode ter campos diferentes. E serverless combina com serverless — não faz sentido ter Lambda sem servidor chamando um banco que precisa de servidor rodando o tempo todo."*

**Hands-on:**
- Criar tabela `Chamados` com partition key `id` string
- Inserir um item manualmente via console
- Ver o item na tabela
- Fazer uma query pela partition key

**Aprendizado:** DynamoDB como banco serverless, quando usar NoSQL vs relacional, modelo de cobrança pay-per-request. Nota: `_listar_chamados` no scaffold faz um `scan()` na tabela inteira — ok pro volume da aula, mas em produção o padrão certo seria `Query` numa GSI (por `status` ou `timestamp`, por exemplo), não varrer a tabela toda.

---

#### 0:45–1:05 — Lambda e API Gateway

**O que é Lambda:**
> *"Função que roda sem servidor. Você escreve o código, a AWS executa quando precisa. Paga por execução — se não rodar, não paga. Escala de zero a milhares de execuções simultâneas automaticamente."*

**O que é API Gateway:**
> *"Porta de entrada da API REST. Recebe a requisição HTTP, chama o Lambda, devolve a resposta. O Lambda não sabe que veio do browser — só recebe um evento JSON com método, path, headers e body."*

**Como o API Gateway aciona a Lambda — mostrar explicitamente:**

Ao criar a rota no console, mostrar a tela de integração:

> *"Reparem que precisamos dizer explicitamente qual Lambda esta rota vai chamar. O API Gateway não descobre sozinho — precisamos configurar o ARN da função, o tipo de integração Lambda, e depois ainda dar permissão para o API Gateway invocar a Lambda. São três passos separados."*

O evento que chega na Lambda (payload format 2.0, o padrão de uma HTTP API):

```json
{
  "version": "2.0",
  "routeKey": "POST /chamados",
  "rawPath": "/chamados",
  "headers": { "content-type": "application/json", "x-api-key": "..." },
  "requestContext": {
    "http": { "method": "POST", "path": "/chamados" }
  },
  "body": "{\"titulo\": \"Servidor fora do ar\"}",
  "isBase64Encoded": false
}
```

**Protegendo a API — por que não é "API Key" aqui:**

> *"A API está pública agora — qualquer pessoa com a URL pode chamar. Em produção isso não é aceitável. Na REST API (v1) a AWS oferece um recurso pronto de API Key + Usage Plan. Só que a gente escolheu HTTP API — mais simples, mais barata — e HTTP API não tem esse recurso nativo. O equivalente aqui é um **Lambda Authorizer**: uma Lambda que roda antes da sua, olha o header `x-api-key` e decide se deixa passar."*

**Hands-on:**
- Criar função Lambda Python com o handler da API
- Configurar variáveis de ambiente: `TABELA_NOME` e `FILA_URL`
- Criar o parâmetro da chave no Parameter Store (voltamos nesse serviço com calma daqui a pouco):
  ```bash
  aws ssm put-parameter \
    --name "/minicurso/api-key" \
    --value "$(openssl rand -hex 24)" \
    --type SecureString
  ```
- Criar função Lambda Python `authorizer.py` — lê `x-api-key` do evento e compara com o parâmetro
- Criar API Gateway HTTP API com rotas `POST /chamados` e `GET /chamados`
- Criar integração Lambda em cada rota — mostrar o ARN sendo configurado
- Dar permissão para o API Gateway invocar cada Lambda (API e authorizer)
- Na aba **Authorization** de cada rota, anexar um Lambda Authorizer (tipo REQUEST, payload 2.0, "simple responses", fonte de identidade `$request.header.x-api-key`)
- Testar sem a key — recebe 401
- Testar com a key — funciona

```bash
# sem a key — 401
curl -X GET https://sua-api.execute-api.us-east-1.amazonaws.com/chamados

# com a key — funciona
curl -X GET https://sua-api.execute-api.us-east-1.amazonaws.com/chamados \
  -H "x-api-key: SuaApiKeyAqui"
```

**No frontend — como a key chega:**

```javascript
// src/api.js — a URL vem do build (não é segredo); a chave NÃO.
// Ela é digitada pela pessoa e guardada só no sessionStorage desta aba.
const API_URL = import.meta.env.VITE_API_URL;

function lerApiKey() {
  return sessionStorage.getItem("central-chamados:api-key") ?? "";
}

export async function criarChamado(titulo, descricao) {
  return fetch(`${API_URL}/chamados`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": lerApiKey(),
    },
    body: JSON.stringify({ titulo, descricao }),
  });
}
```

> *"Por que a chave não vem do build junto com a URL? Porque o Vite troca
> `import.meta.env.VITE_ALGO` por um literal dentro do bundle. Uma chave
> embutida assim está em texto puro num arquivo público — qualquer visitante
> lê no DevTools em 15 segundos. Isso não é falha do Vite: **nenhum segredo
> sobrevive dentro de código que roda no navegador.** Por isso o site pede a
> chave num campo em vez de já vir com ela."*

**Aprendizado:** Lambda como compute serverless, API Gateway como proxy HTTP, integração explícita entre os dois, Lambda Authorizer como autenticação simples de uma HTTP API. O participante entende que cada conexão entre serviços é configurada — não acontece automaticamente.

---

#### 1:05–1:20 — SQS

**O que é SQS:**
> *"Fila de mensagens. Você coloca uma mensagem, alguém pega quando estiver pronto. Se o processador cair, a mensagem continua na fila. Nada se perde — e o processador não precisa estar disponível no momento do envio."*

**Queue-Based Load Leveling na prática:**
> *"A Lambda da API não vai esperar o agente processar o chamado com AI — isso pode levar segundos. Ela salva no DynamoDB, joga na fila e responde ao usuário imediatamente. O agente processa de forma assíncrona. Isso é Queue-Based Load Leveling."*

**Hands-on:**
- Criar fila SQS `ChamadosFila`
- Atualizar a Lambda da API para enviar mensagem para a fila após salvar no DynamoDB:

```python
sqs.send_message(
    QueueUrl=os.environ["FILA_URL"],
    MessageBody=json.dumps({
        "id":        id,
        "titulo":    body["titulo"],
        "descricao": body["descricao"],
    }),
)
```

- Criar um chamado via frontend e verificar a mensagem na fila no console
- Mostrar a mensagem em estado "In Flight" quando processando

**Aprendizado:** SQS como buffer assíncrono, desacoplamento entre produtor e consumidor, Queue-Based Load Leveling como pattern concreto. Nota: a fila do scaffold não tem Dead Letter Queue configurada — uma mensagem que falha repetidamente fica retentando até o fim da visibility timeout em vez de cair numa DLQ. Em produção, `sst.aws.Queue` aceita um `dlq` na config pra isso.

---

#### 1:20–1:33 — SNS

**O que é SNS:**
> *"Megafone. Você publica uma mensagem, todos os subscribers recebem simultaneamente. Um publisher, múltiplos consumers independentes. Fan-out pattern."*

**Por que SNS aqui e não chamar o Discord diretamente:**
> *"Se a Lambda do agente chamasse o Discord diretamente, estaria acoplada ao Discord. Se quiséssemos também notificar no Slack ou salvar num sistema de tickets, precisaríamos modificar a Lambda do agente. Com SNS, adicionamos um subscriber novo sem tocar no agente. Isso é fan-out — e é exatamente por que plataformas event-driven escalam bem."*

```
SNS Topic
├── Lambda Discord    ← provisionado hoje
├── Lambda Slack      ← poderia ser adicionado
└── Lambda Logging    ← poderia ser adicionado
```

**Hands-on:**
- Criar SNS Topic `ChamadosTopico`
- Criar subscription apontando para Lambda de teste
- Publicar mensagem manualmente no console
- Ver a mensagem chegando na Lambda subscriber via CloudWatch Logs

**Aprendizado:** SNS como fan-out, desacoplamento entre publisher e subscribers, extensibilidade sem modificar código existente.

---

#### 1:33–1:45 — Parameter Store e Strands Agents

**O que é Parameter Store:**
> *"Cofre de configurações da AWS. Credenciais seguras sem custo adicional. O tipo SecureString usa KMS para criptografar — o valor não aparece em texto puro no console. Diferente do Secrets Manager que cobra $0.40 por secret por mês, o Parameter Store é gratuito no tier padrão. Vocês já usaram um SecureString sem eu explicar — o `/minicurso/api-key` que criamos para o Lambda Authorizer. Agora fazemos o mesmo para o Groq e o Discord."*

**Hands-on — criar os parâmetros:**

```bash
aws ssm put-parameter \
  --name "/minicurso/groq-api-key" \
  --value "gsk_..." \
  --type SecureString

aws ssm put-parameter \
  --name "/minicurso/discord-webhook" \
  --value "https://discord.com/api/webhooks/..." \
  --type SecureString
```

**O que é Strands Agents:**
> *"Framework da AWS para agentes AI. Um agente pode raciocinar, usar ferramentas e tomar decisões em múltiplos passos. Aqui vai analisar o chamado, classificar a prioridade e sugerir uma ação. Usamos o Groq como provider — inferência rápida com modelos open source. O Groq expõe uma API compatível com a da OpenAI, então usamos o provider `OpenAIModel` nativo do Strands apontando o `base_url` para o Groq — sem precisar de uma camada de abstração extra."*

**Lambda Layer — por que precisa:**
> *"O Strands tem dependências que não cabem no zip padrão do Lambda. Lambda Layer é o mecanismo para compartilhar dependências entre funções — compiladas para linux, reutilizáveis por qualquer Lambda. A Layer já está criada no ambiente — vamos só atrelar à função."*

```
Lambda Layer: strands-openai
└── strands-agents[openai]

Lambda Function: agente.py
└── só o código — leve, rápido de deploy
```

**Hands-on:**
- Criar Lambda `AgenteProcessador` com trigger na fila SQS
- Atrelar a Layer `strands-openai`
- Configurar variáveis de ambiente: `GROQ_PARAM_NAME`, `TOPICO_ARN`, `BUCKET_NOME`
- Configurar a role — mostrar que precisa de permissão para `ssm:GetParameter`
- Testar enviando uma mensagem na fila e ver o agente processando no CloudWatch Logs

**Aprendizado:** Parameter Store para credenciais seguras e gratuitas, Strands como framework de agente, Lambda Layer para dependências pesadas, permissões IAM explícitas.

---

#### 1:45–2:00 — Conectando tudo e Lambda Discord

**Criar a Lambda Discord com trigger no SNS:**

> *"A Lambda do Discord é o subscriber do SNS. Ela recebe a análise do agente, envia para o Discord via webhook e salva o histórico no DynamoDB. Note que ela não sabe nada sobre SQS ou sobre o agente — só sabe que recebeu uma mensagem do SNS."*

```python
# functions/src/functions/discord.py — versão manual
import json, os, boto3, urllib.request
from datetime import datetime

ssm      = boto3.client("ssm")
dynamodb = boto3.resource("dynamodb")

def get_webhook():
    return ssm.get_parameter(
        Name=os.environ["DISCORD_PARAM_NAME"],
        WithDecryption=True
    )["Parameter"]["Value"]

def handler(event, context):
    dados   = json.loads(event["Records"][0]["Sns"]["Message"])
    chamado = dados["chamado"]
    analise = dados["analise"]

    mensagem = (
        f"🎫 **Novo Chamado #{dados['id'][:8]}**\n\n"
        f"**Título:** {chamado['titulo']}\n"
        f"**Análise:** {analise}"
    )

    payload = json.dumps({"content": mensagem}).encode()
    req = urllib.request.Request(
        get_webhook(),
        data=payload,
        # sem User-Agent, o Cloudflare do Discord bloqueia a requisição
        # (erro 1010) — o User-Agent padrão do urllib é reconhecido como bot
        headers={
            "Content-Type": "application/json",
            "User-Agent": "central-chamados-bot/1.0",
        },
        method="POST",
    )
    urllib.request.urlopen(req)

    dynamodb.Table(os.environ["TABELA_NOME"]).put_item(Item={
        "id":        dados["id"],
        "titulo":    chamado["titulo"],
        "descricao": chamado.get("descricao", ""),
        "analise":   analise,
        "status":    "notificado",
        "timestamp": datetime.utcnow().isoformat(),
    })
```

> *"Reparem no que o DynamoDB está fazendo aqui. A Lambda da API criou o item com quatro campos — `id`, `titulo`, `descricao`, `status`. Agora a Lambda do Discord está gravando o mesmo item com campos a mais: `analise`, `timestamp`. Num banco relacional precisaríamos ter definido todas essas colunas antes de inserir qualquer dado. No DynamoDB, cada item pode ter campos diferentes. O mesmo `id` vai ganhando campos ao longo do fluxo. Isso é schemaless na prática — e é um dos motivos pelos quais DynamoDB combina tão bem com arquiteturas event-driven."*

**Testar o fluxo completo end-to-end:**
- Criar chamado pelo frontend
- Acompanhar cada etapa no console — SQS, CloudWatch Logs do agente, SNS, CloudWatch Logs do Discord
- Ver a notificação chegar no Discord com análise da AI
- Ver o histórico salvo no DynamoDB

> *"CloudWatch é onde todos os logs da AWS vão parar automaticamente. Vocês já usaram sem perceber — cada Lambda que rodou gerou logs aqui."*

**Aprendizado:** Pipes and Filters com as três Lambdas em sequência, fluxo completo end-to-end funcionando, CloudWatch como observabilidade automática. É a primeira vez que o Event-Driven Architecture completo aparece de ponta a ponta — API → SQS → Agente → SNS → Discord, cada peça reagindo a um evento, nenhuma chamando a outra diretamente.

**Menção honrosa — DynamoDB Streams:**
> *"Dava pra levar esse event-driven ainda mais longe com DynamoDB Streams: em vez da Lambda da API mandar explicitamente pra fila, o Stream da tabela dispararia sozinho a cada `put_item` — o evento nasceria da própria mudança no dado, não de uma chamada explícita pra publicar. Não fizemos isso hoje porque ter duas fontes de evento ao mesmo tempo (SQS explícito e Stream implícito) ia confundir mais do que ensinar — mas é o próximo passo natural se quiser eliminar de vez o 'dual write' entre banco e fila."*

---

### Parte 2 — O problema, SST Ion, demo e fechamento (2:00–3:00)

---

#### 2:00–2:10 — O problema do manual

Listar ao vivo tudo que foi feito:

```
✓ Bucket S3 criado manualmente
✓ Website hosting habilitado manualmente
✓ DynamoDB criado manualmente
✓ Lambda API criada manualmente
✓ Variáveis de ambiente configuradas manualmente
✓ Role IAM configurada manualmente em cada Lambda
✓ API Gateway criado manualmente
✓ Integração API Gateway → Lambda configurada manualmente
✓ Permissão de invocação configurada manualmente
✓ Lambda Authorizer criada e anexada manualmente às rotas
✓ SQS criada manualmente
✓ Lambda Agente criada manualmente
✓ Trigger SQS → Lambda configurado manualmente
✓ Layer atachada manualmente
✓ Parameter Store configurado manualmente
✓ SNS Topic criado manualmente
✓ Subscription SNS → Lambda configurada manualmente
✓ Lambda Discord criada manualmente
```

> *"18 passos. Nenhum versionado. Nenhum reproduzível com segurança. Se um segundo dev precisar do mesmo ambiente, refaz tudo do zero. Se algo mudar, atualiza manualmente em cada lugar. O problema não é a quantidade de passos — é a rastreabilidade."*

> *"O SST Ion resolve isso. Você descreve o que quer, ele garante que existe. Versionado no Git, reproduzível em qualquer conta."*

**Aprendizado:** o problema do manual não é esforço — é rastreabilidade, reprodutibilidade e consistência.

---

#### 2:10–2:35 — SST Ion

**O que é IaC:**
> *"Infrastructure as Code. Infra declarada em código, versionada no Git, reproduzível em qualquer conta. Se deletar tudo e rodar de novo, fica idêntico."*

**O que é SST Ion:**
> *"IaC moderno em TypeScript. Abstrai o Pulumi por baixo — você não precisa saber que o Pulumi existe. O `sst deploy` declara os recursos e garante que estão no estado correto."*

**No Learner Labs — por que a LabRole é explícita:**
> *"O SST por padrão cria uma role IAM específica para cada Lambda com as permissões mínimas necessárias — o que é mais seguro. No Learner Labs, não podemos criar roles. Por isso usamos a LabRole que já existe no ambiente. Em uma conta AWS normal, o SST gerenciaria as roles automaticamente. Detalhe técnico: quando você passa uma role pronta, o SST não atualiza mais as permissões dela sozinho — mas a LabRole já é bem permissiva, então funciona."*

**Python no SST — um pré-requisito antes de codar:**
> *"Suporte a Python no SST Ion é mantido pela comunidade, não pela AWS. Ele espera um workspace `uv` — cada pacote Python precisa de um `pyproject.toml`. Isso já está pronto no scaffold: `pyproject.toml` na raiz declara o workspace, `functions/pyproject.toml` declara as dependências (`boto3`, `sst-sdk`). Só rodem `uv sync --all-packages` uma vez antes do deploy."*

**Construir o `sst.config.ts` ao vivo:**

> *"`aws` e `sst` já vêm como globais dentro do `sst.config.ts` — é o `/// <reference>` no topo do arquivo que faz isso. O SST também expõe uns atalhos globais pra não precisar importar o Pulumi direto: `$asset()` empacota um arquivo ou diretório, `$interpolate` monta strings com valores que só existem depois do deploy. Com isso, esse `sst.config.ts` não precisa de nenhum import — nem do Pulumi, nem de nada."*

> *"Nota técnica: `sst.Secret` armazena os valores num bucket S3 interno do SST, não no Parameter Store. A analogia com Parameter Store é conceitual — mesma função de guardar segredos com segurança, mecanismo diferente por baixo."*

```typescript
/// <reference path="./.sst/platform/config.d.ts" />

export default $config({
  app(input) {
    return {
      name: "central-chamados",
      removal: input?.stage === "production" ? "retain" : "remove",
      home: "aws",
      providers: { aws: { region: "us-east-1" } },
    };
  },

  async run() {
    // LabRole — necessária no Learner Labs, onde não dá pra criar roles novas.
    // Em conta normal, deixe `false`: o SST cria uma role por Lambda com só o
    // que o link() daquela função exige
    const usarLabRole = true;
    const role = usarLabRole
      ? `arn:aws:iam::${(await aws.getCallerIdentity()).accountId}:role/LabRole`
      : undefined;
    const runtime = "python3.13";
    const fnDir = "functions/src/functions";

    // banco — reconhecem do bloco DynamoDB
    const tabela = new sst.aws.Dynamo("Chamados", {
      fields: { id: "string" },
      primaryIndex: { hashKey: "id" },
    });

    // segredos — reconhecem do bloco Parameter Store
    // o valor real NUNCA vai no código — é setado uma vez via CLI:
    //   npx sst secret set GroqApiKey "gsk_..." --stage lab
    //   npx sst secret set DiscordWebhook "https://discord.com/api/webhooks/..." --stage lab
    //   npx sst secret set ApiKey "$(openssl rand -hex 24)" --stage lab
    const groqApiKey = new sst.Secret("GroqApiKey");
    const discordWebhook = new sst.Secret("DiscordWebhook");
    const apiKey = new sst.Secret("ApiKey");

    // layer — reconhecem do bloco Strands. $asset() zipa o diretório na
    // hora do deploy — aponta pro "build/" (que só tem a pasta "python/"
    // dentro), porque o Lambda exige essa pasta "python/" na raiz do zip
    const strandsLayer = new aws.lambda.LayerVersion("StrandsLayer", {
      layerName: "strands-openai",
      code: $asset("layers/strands-openai/build"),
      compatibleRuntimes: [runtime],
      compatibleArchitectures: ["x86_64"],
    });

    // fila, tópico e bucket — reconhecem dos blocos SQS, SNS
    // visibilityTimeout precisa ser >= timeout da Lambda que consome a fila
    const fila = new sst.aws.Queue("ChamadosFila", { visibilityTimeout: "90 seconds" });
    const topico = new sst.aws.SnsTopic("ChamadosTopico");
    const bucket = new sst.aws.Bucket("Relatorios");

    // lambda agente — reconhecem do bloco Strands
    // role explícita + link() injeta Resource no handler
    // Queue.subscribe() não recebe nome — só um subscriber por fila.
    // SnsTopic.subscribe() recebe (já que um tópico tem vários subscribers)
    //
    // memory/timeout explícitos nas quatro Lambdas do app, em vez de
    // deixar no default do SST (1024MB/20s) — dimensionados pelo que cada
    // uma realmente faz, medido no CloudWatch (Max Memory Used/Duration):
    //   agente:     mais pesada — Strands+Groq (LLM externo) e a layer
    //               mais lenta pra carregar no cold start
    //   discord:    DynamoDB + um POST externo pro webhook
    //   api:        só DynamoDB + SQS, chamadas internas rápidas
    //   authorizer: uma comparação de string, sem I/O nenhum
    // memória também é CPU na Lambda — cortar pela metade (1024→512MB)
    // não reduziu a memória USADA (ficou ~193MB antes e depois), mas mais
    // que dobrou o tempo de execução (2.4s→5.1s), porque o processamento
    // do Strands é sensível a CPU, não só a espera de rede do Groq. Ainda
    // sobra bastante margem pro timeout (~6x), mas não é economia de graça
    fila.subscribe({
      handler: `${fnDir}/agente.handler`,
      runtime,
      role,
      layers: [strandsLayer.arn],
      memory: "512 MB",
      timeout: "30 seconds",
      link: [topico, bucket, groqApiKey],
    });

    // lambda discord — reconhecem do bloco final
    topico.subscribe("DiscordNotifier", {
      handler: `${fnDir}/discord.handler`,
      runtime,
      role,
      memory: "256 MB",
      timeout: "15 seconds",
      link: [tabela, discordWebhook],
    });

    // frontend — sem CloudFront. Esse Learner Lab nega até
    // cloudfront:CreateDistribution pra quem faz o deploy — não é uma
    // permissão específica faltando, o serviço inteiro está fora do
    // alcance dessa conta. Sem CDN, sem HTTPS: S3 com website hosting
    // público direto. Numa conta AWS normal, CloudFront + OAC na frente
    // (ver Parte 1) é o caminho certo — aí sst.aws.StaticSite cuidaria de
    // tudo isso sozinho.
    //
    // O sst.config.ts só declara o bucket. O build (`npm run build`) e o
    // upload (`aws s3 sync`) não entram aqui — viram um script separado
    // (scripts/deploy-frontend.sh) rodado depois do `sst deploy`. Dá pra
    // automatizar isso com um `command.local.Command`, mas o Pulumi só
    // re-executa esse comando quando os "triggers" mudam — e usar hash de
    // arquivo como trigger, só pra isso, é complexidade que não ajuda a
    // aula. Infra e frontend têm ciclos de vida diferentes; num pipeline
    // de CI/CD real, seriam dois jobs separados de qualquer forma.
    const frontendBucket = new sst.aws.Bucket("Frontend", {
      access: "public",
      // website hosting do S3 só serve em HTTP puro (sem CloudFront não
      // tem HTTPS) — a política padrão do Bucket nega acesso sem HTTPS,
      // o que bloquearia o próprio endpoint de website
      enforceHttps: false,
    });

    new aws.s3.BucketWebsiteConfiguration("FrontendWebsite", {
      bucket: frontendBucket.name,
      indexDocument: { suffix: "index.html" },
      errorDocument: { key: "index.html" },
    });

    // criado antes da API pra poder travar o CORS nele — ver comentário abaixo
    const siteUrl = $interpolate`http://${frontendBucket.name}.s3-website-us-east-1.amazonaws.com`;

    // api gateway — reconhecem do bloco Lambda e API Gateway
    // allowOrigins trava no nosso próprio bucket em vez de "*": CORS é
    // aplicado pelo navegador, não pelo servidor — isso impede JS de outro
    // site de LER a resposta da nossa API, mas não substitui o authorizer
    // (curl/Postman ignoram CORS completamente). Ainda assim, "*" só fazia
    // sentido enquanto não sabíamos a URL final do bucket.
    const api = new sst.aws.ApiGatewayV2("Api", {
      cors: {
        allowOrigins: [siteUrl],
        allowMethods: ["GET", "POST"],
        allowHeaders: ["content-type", "x-api-key"],
      },
    });

    // lambda authorizer — mesmo papel do que fizemos manualmente:
    // HTTP API não tem API Key + Usage Plan nativo, então validamos
    // o header x-api-key numa Lambda que roda antes da rota
    const apiAuth = api.addAuthorizer({
      name: "ApiKeyAuthorizer",
      lambda: {
        function: {
          handler: `${fnDir}/authorizer.handler`,
          runtime,
          role,
          memory: "128 MB",
          timeout: "5 seconds",
          link: [apiKey],
        },
        identitySources: ["$request.header.x-api-key"],
        payload: "2.0",
        response: "simple",
        ttl: "5 minutes",
      },
    });

    const auth = { auth: { lambda: apiAuth.id } };

    // GET e POST batem no mesmo handler (api.py despacha por método) —
    // criar a Function uma vez e passar pras duas rotas evita subir duas
    // Lambdas idênticas, uma por rota
    const chamadosApi = new sst.aws.Function("ChamadosApi", {
      handler: `${fnDir}/api.handler`,
      runtime,
      role,
      memory: "256 MB",
      timeout: "10 seconds",
      link: [tabela, fila],
    });
    api.route("POST /chamados", chamadosApi.arn, auth);
    api.route("GET /chamados", chamadosApi.arn, auth);

    return {
      site: siteUrl,
      api: api.url,
      bucket: frontendBucket.name,
    };
  },
});
```

**Ajuste nos handlers — o `from sst import Resource`:**

> *"O handler muda no mesmo ponto em todo lugar: a função `_algo()` que hoje lê `os.environ` ou chama `ssm.get_parameter()` passa a devolver `Resource.Algo.valor`. Isso já está marcado com `# TODO (Parte 2)` em cada arquivo do scaffold — não escrevemos do zero, só trocamos a linha. O `link()` injetou tudo automaticamente: sem variável de ambiente manual, sem `ssm:GetParameter` configurado à mão."*

```python
# api.py e discord.py — trocar
dynamodb.Table(os.environ["TABELA_NOME"])
# por
dynamodb.Table(Resource.Chamados.name)
```

```python
# api.py — trocar
os.environ["FILA_URL"]
# por
Resource.ChamadosFila.url
```

```python
# agente.py — trocar as três
ssm.get_parameter(Name=os.environ["GROQ_PARAM_NAME"], WithDecryption=True)["Parameter"]["Value"]
# por
Resource.GroqApiKey.value

os.environ["TOPICO_ARN"]
# por
Resource.ChamadosTopico.arn

os.environ["BUCKET_NOME"]
# por
Resource.Relatorios.name
```

```python
# discord.py — trocar
ssm.get_parameter(Name=os.environ["DISCORD_PARAM_NAME"], WithDecryption=True)["Parameter"]["Value"]
# por
Resource.DiscordWebhook.value
```

```python
# authorizer.py — trocar
ssm.get_parameter(Name=os.environ["API_KEY_PARAM_NAME"], WithDecryption=True)["Parameter"]["Value"]
# por
Resource.ApiKey.value
```

E no topo dos quatro arquivos, um único import novo: `from sst import Resource`.

**Deploy ao vivo:**

```bash
uv sync --all-packages
npx sst secret set GroqApiKey "gsk_..." --stage lab
npx sst secret set DiscordWebhook "https://discord.com/api/webhooks/..." --stage lab
npx sst secret set ApiKey "$(openssl rand -hex 24)" --stage lab
npx sst deploy --stage lab
./scripts/deploy-frontend.sh
```

> *"O `sst deploy` cuida da infraestrutura — Lambda, DynamoDB, SQS, SNS, API Gateway. O frontend é buildado e sobe pro S3 num passo separado, o `deploy-frontend.sh`. Essa separação é intencional: infra e código de aplicação têm ciclos de vida diferentes. Num pipeline de CI/CD real, seriam dois jobs distintos."*

> *"18 passos manuais. Menos de 150 linhas de código. Versionado no Git. Reproduzível em qualquer conta."*

**Step Functions — menção rápida:**
> *"Um serviço que não vimos hoje mas que apareceria naturalmente aqui é o Step Functions — orquestrador de workflows serverless. Quando precisar coordenar múltiplas Lambdas em sequência com retry automático e tratamento de erro, ele entra. Daria um minicurso inteiro — e é exatamente o que fizemos no minicurso anterior."*

**Aprendizado:** IaC como solução para rastreabilidade e reprodutibilidade. `link()` eliminando configuração manual de IAM e variáveis de ambiente. `Resource` como experiência do dev — sem ARN, sem hardcode, sem `os.environ`. `sst.Secret` como o equivalente do SST para o Parameter Store — segredo versionável por stage, nunca no código. Role explícita necessária no Learner Labs. HTTP API não tem API Key/Usage Plan — Lambda Authorizer é o caminho, e o SST tem suporte nativo com `api.addAuthorizer()`. `memory`/`timeout` explícitos em vez do default (1024MB/20s) em todas as Lambdas — dimensionados pelo que cada uma mede no CloudWatch, não chutados: a memória na Lambda também é CPU, então cortar memória de uma função com trabalho de CPU de verdade (como o agente, que roda o Strands) mede em dobro de tempo de execução, não é economia de graça. E nem tudo é abstração perfeita: `StaticSite` seria o caminho natural para o frontend, mas cria CloudFront por baixo — e esse Learner Lab não libera CloudFront pra ninguém. Frontend fica em S3 com website hosting público, sem CDN, sem HTTPS — a mesma limitação da Parte 1, agora em código.

---

#### 2:35–2:45 — Demo final

Abrir o frontend via URL do S3 (website hosting). Criar um chamado:

```
Título:    Banco de dados com lentidão crítica
Descrição: Queries levando mais de 30s desde as 10h
```

**Outras opções de chamado pra testar** (variam a prioridade que o agente classifica — bom pra mostrar a análise da AI mudando):

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
```

Mostrar em sequência:

1. Chamado aparece na lista — DynamoDB + API Gateway + Lambda funcionando
2. SQS recebeu a mensagem — Queue-Based Load Leveling visível
3. Lambda do Agente processou com Strands — CloudWatch Logs
4. Relatório salvo no S3
5. SNS entregou para o subscriber — Fan-out visível
6. Discord recebeu a notificação com análise da AI
7. DynamoDB registrou o histórico

> *"Frontend no S3 — CloudFront seria o próximo passo natural numa conta sem essa restrição. API no API Gateway com Lambda. Banco no DynamoDB. Fila no SQS. Agente com Strands e Groq. Fan-out no SNS. Notificação no Discord. Relatório no S3. Histórico no DynamoDB. Tudo serverless. Tudo que vocês construíram hoje."*

---

#### 2:45–3:00 — Fechamento

**O que aprendemos:**

```
S3              → storage e hosting estático
CloudFront      → CDN e HTTPS automático
API Gateway     → porta de entrada da API REST
Lambda Authorizer → autenticação simples de uma HTTP API
Lambda          → compute serverless, pay-per-execution
DynamoDB        → banco NoSQL serverless
SQS             → fila assíncrona, Queue-Based Load Leveling
SNS             → fan-out de eventos
Parameter Store → credenciais seguras e gratuitas
Strands + Groq  → agente AI integrado à arquitetura
Lambda Layer    → dependências compartilhadas
SST Ion         → IaC moderno, do manual ao cloud-native
```

**Onde continuar praticando:**

```
AWS Builder Center Sandbox   → builder.aws
                               gratuito, sem cartão de crédito
                               conta AWS real, sessões de workshops
                               lançado em julho de 2026

AWS Free Tier                → aws.amazon.com/pt/free
                               $200 em créditos
                               serviços sempre gratuitos
                               tudo que fizemos está coberto

AWS Learner Labs              → via AWS Academy
                               ambiente que usamos hoje
```

**Certificações e credenciais:**

```
AWS Serverless Demonstrated  → skillbuilder.aws
                               gratuito, sem assinatura
                               hands-on em ambiente AWS real
                               sem múltipla escolha
                               valida exatamente o que fizemos hoje
                               badge Credly → LinkedIn

Cloud Practitioner           → certificação formal AWS
                               Skill Builder → curso oficial gratuito
                               Udemy Stephane Maarek → o que estou usando
                               4 a 6 semanas com a base de hoje
```

**Fala de fechamento:**
> *"Vocês saem de hoje sabendo o que é serverless na prática — não na teoria. S3, CloudFront, API Gateway, Lambda, DynamoDB, SQS, SNS, Parameter Store, Strands Agents e SST Ion. Tudo construído, tudo funcionando.*
>
> *Para continuar: Builder Center Sandbox para praticar sem cartão, Free Tier para projetos próprios, Serverless Demonstrated para validar o que aprenderam hoje, Cloud Practitioner para a certificação formal — estou usando o Stephane Maarek na Udemy para tirar a minha.*
>
> *Antes de encerrar — o sorteio."*

**Sorteio.**

---

### Resumo de tempo

| Bloco | Horário | Duração |
|---|---|---|
| Abertura e contexto | 0:00–0:15 | 15 min |
| S3 e CloudFront | 0:15–0:30 | 15 min |
| DynamoDB | 0:30–0:45 | 15 min |
| Lambda e API Gateway | 0:45–1:05 | 20 min |
| SQS | 1:05–1:20 | 15 min |
| SNS | 1:20–1:33 | 13 min |
| Parameter Store e Strands | 1:33–1:45 | 12 min |
| Conectando tudo | 1:45–2:00 | 15 min |
| O problema do manual | 2:00–2:10 | 10 min |
| SST Ion | 2:10–2:35 | 25 min |
| Demo final | 2:35–2:45 | 10 min |
| Fechamento + sorteio | 2:45–3:00 | 15 min |

---

### Princípios de execução

Mostrar a aplicação funcionando no início — o participante sabe o destino antes de começar a jornada. Cada serviço segue o mesmo ritmo: o que é, hands-on, como se encaixa. O bloco "O problema do manual" é curto mas obrigatório — sem sentir a dor, o SST Ion não tem impacto. O `sst.config.ts` é construído ao vivo com o participante reconhecendo cada recurso. A Layer já vem criada antes da aula — não fazer ao vivo. Os handlers Python já vêm com os TODOs do `from sst import Resource` marcados no scaffold. O frontend já vem pronto — foco é na arquitetura, não no HTML. Ter o deploy gravado como fallback — se a AWS travar, a narrativa continua.
