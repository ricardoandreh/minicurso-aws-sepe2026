## AWS na prática: construindo uma aplicação web serverless com SST Ion (3h)

**Aplicação:** Central de Chamados cloud-native
**Stack:** S3 · API Gateway · Lambda Python · DynamoDB · SQS · SNS · Parameter Store · `sst.Secret` · Strands Agents · Groq · SST Ion · AWS Learner Labs

> **Formato.** A Parte 1 é hands-on de console em **quatro serviços** — S3,
> DynamoDB, Lambda e SQS. A turma faz, e só precisa do navegador: nenhuma
> instalação local até o intervalo. A Parte 2 é **acompanhada**: o instrutor
> percorre branches do repositório e a turma roda um comando (`sst deploy`)
> para ver a própria infraestrutura subir. Ninguém escreve TypeScript ao vivo —
> 30 pessoas digitando config é como se perde a Parte 2.
>
> **Sem CloudFront.** O Learner Lab não libera. O frontend fica em S3 website
> hosting, HTTP puro. Não entra no roteiro nem como "o que faltou" — está fora
> do escopo e ponto.

---

### Resumo de tempo

| Bloco | Horário | Duração | Quem faz |
|---|---|---|---|
| Abertura | 0:00–0:10 | 10 min | instrutor |
| Setup 1 — entrar no Learner Lab | 0:10–0:20 | 10 min | **turma** |
| S3 | 0:20–0:40 | 20 min | **turma** |
| DynamoDB | 0:40–1:00 | 20 min | **turma** |
| Lambda | 1:00–1:25 | 25 min | **turma** |
| SQS | 1:25–1:45 | 20 min | **turma** |
| **Intervalo + Setup 2 (ambiente local)** | 1:45–1:55 | 10 min | **turma** |
| O problema do manual | 1:55–2:05 | 10 min | instrutor |
| SST Ion — 5 passos por branch | 2:05–2:45 | 40 min | instrutor (+ 2 deploys da turma) |
| Demo final | 2:45–2:53 | 8 min | instrutor |
| Fechamento + sorteio | 2:53–3:00 | 7 min | instrutor |

**Marcos a defender:** 1:45 para o intervalo e 2:05 para começar o SST. Se a
Parte 1 estourar, corte profundidade do bloco de SQS — não o intervalo, que é
também o setup local da Parte 2.

---

### Antes da aula (checklist do instrutor)

- [ ] **Conferir o catálogo do Groq.** `model_id` fixo no código é bomba-relógio:
      o `llama-3.3-70b-versatile` foi retirado e o agente passou a dar 404.
      `curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $GROQ_KEY" | jq -r '.data[].id'`
      — hoje o roteiro usa `openai/gpt-oss-20b` (~600 ms de resposta).
- [ ] `./layers/strands-openai/build.sh` rodado (a layer **não** se monta ao vivo).
- [ ] Branches `passo-1-bucket` … `passo-5-fanout` e `main` criadas e testadas.
- [ ] Um canal de Discord da turma com webhook criado, para todos usarem o mesmo.
      Vira recurso didático: a sala vê os chamados de todo mundo chegando no
      mesmo canal, e o fan-out fica concreto. A alternativa (cada um cria o seu)
      custa 10 minutos de aula e não ensina nada a mais.
- [ ] Chaves do Groq distribuídas, ou uma chave da turma. Criar conta ao vivo
      não cabe no tempo.
- [ ] Gist de pré-requisitos enviado antes do evento (Node 20+, uv, AWS CLI).
- [ ] **Deploy gravado como fallback**, para o caso de a AWS travar.
- [ ] `npx sst remove --stage lab` rodado no ambiente de teste, para a aula
      começar do zero.

---

### Parte 1 — Fundamentos hands-on no console (0:00–1:45)

**Cada serviço segue o mesmo ritmo:** o que é → para que serve → hands-on →
como se encaixa na arquitetura.

Nesta parte a turma constrói um pedaço real e funcional: **SQS → Lambda →
DynamoDB**, mais o site estático no S3. O que falta (a API, o agente de AI, o
fan-out) é exatamente o que a Parte 2 vai montar — e a falta é visível, porque o
site sobe mas não consegue listar nada.

---

#### 0:00–0:10 — Abertura

Mostrar a aplicação funcionando ao vivo — o participante vê o destino antes de
começar:

> *"Essa é a Central de Chamados que vamos construir hoje. Frontend no browser,
> chamado criado, Discord recebe notificação com análise de AI em segundos.
> Tudo serverless, tudo na AWS. Vamos entender cada peça."*

Diagrama completo:

```
Browser
    ↓
S3 (frontend, website hosting)
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
```

Marcar no diagrama **o que a turma vai fazer à mão** (S3, DynamoDB, Lambda, SQS)
e o que vai aparecer por código na Parte 2. Isso evita a sensação de "só vi
metade".

Shared Responsibility Model — 2 minutos:

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

> *"Quanto mais managed o serviço, mais responsabilidade vai para a AWS. Lambda,
> DynamoDB, SQS — vocês gerenciam o código e as permissões. A AWS gerencia o
> resto. Isso é serverless."*

Design patterns que vão aparecer — nomear antes de ver:

- **Event-Driven Architecture** — o padrão guarda-chuva: nada chama nada
  diretamente, cada peça reage a um evento e produz o próximo.
- **Queue-Based Load Leveling** — SQS como buffer entre produtor e consumidor.
- **Fan-out** — SNS entregando para múltiplos subscribers independentes.
- **Pipes and Filters** — cada Lambda faz uma coisa só e passa adiante.

**Aprendizado:** modelo mental completo antes de tocar no console.

---

#### 0:10–0:20 — Setup 1: entrar no Learner Lab

Único requisito desta parte: **navegador**. Nada de instalar.

- Abrir o AWS Academy Learner Lab, iniciar o laboratório, aguardar o sinal verde
- Abrir o AWS Console pelo botão do Lab
- **Confirmar a região: `us-east-1`** — é o erro nº 1 da aula, criar recurso numa
  região e procurar em outra
- Localizar a barra de busca de serviços

> *"As credenciais do Lab expiram em algumas horas. Se mais tarde algo parar de
> funcionar com erro de permissão, é isso — abrimos o Lab de novo."*

Perguntar em voz alta quem **não** conseguiu entrar, e resolver agora. Um
participante travado aqui fica travado nas próximas duas horas.

**Aprendizado:** o ambiente é uma conta AWS real, com limites de laboratório.

---

#### 0:20–0:40 — S3

**O que é:**
> *"Storage de objetos. Qualquer arquivo, qualquer tamanho, qualquer formato.
> Backup, dataset, log, frontend — o S3 guarda tudo. É o serviço mais usado
> da AWS."*

**Hands-on:**
- Criar bucket (nome é global — precisa ser único no mundo; ótimo momento para
  explicar por quê)
- Desmarcar o Block Public Access e aceitar o aviso
- Upload do `index.html` e da pasta `assets/` do frontend já pronto
- Propriedades → Static website hosting → habilitar, index document `index.html`
- Adicionar a bucket policy de leitura pública
- Abrir a URL do website

O site carrega, mostra o formulário… e **não lista nada**. Isso é o esperado, e é
o gancho da aula inteira:

> *"O site está no ar, servido pela AWS, sem nenhum servidor. Mas ele não tem com
> quem falar — não existe API, não existe banco. Guardem essa tela: é ela que
> vamos completar."*

**Aprendizado:** S3 como storage e como hosting estático. Frontend não precisa de
servidor. Bucket policy e Block Public Access como controles de acesso
explícitos.

---

#### 0:40–1:00 — DynamoDB

**O que é:**
> *"Banco NoSQL serverless. Sem schema fixo, sem servidor para gerenciar, escala
> automaticamente. Pay-per-request — você paga por leitura e escrita, não por
> servidor ligado 24h."*

> *"Por que não RDS aqui? Chamados têm estrutura variável. E serverless combina
> com serverless — não faz sentido ter Lambda sem servidor chamando um banco que
> precisa de servidor rodando o tempo todo."*

**Hands-on:**
- Criar tabela `Chamados`, partition key `id` (String)
- Inserir um item pelo console: `id`, `titulo`, `status`
- Inserir um **segundo** item com um campo a mais, por exemplo `prioridade`
- Ver os dois na tabela, com formatos diferentes, convivendo
- Query pela partition key

> *"Repare que o segundo item tem um campo que o primeiro não tem, e o banco não
> reclamou. Num banco relacional você precisaria ter declarado essa coluna antes
> de inserir qualquer linha. Isso é schemaless — e é um dos motivos pelos quais
> DynamoDB combina tão bem com arquitetura event-driven, onde o mesmo registro
> vai ganhando campos conforme atravessa o fluxo."*

**Aprendizado:** banco serverless, NoSQL vs relacional, pay-per-request,
schemaless na prática.

> **Nota honesta a dizer:** o `_listar_chamados` do scaffold faz `scan()` na
> tabela inteira. Serve para o volume da aula; em produção o padrão é `Query`
> numa GSI (por `status` ou `timestamp`), não varrer a tabela toda.

---

#### 1:00–1:25 — Lambda

**O que é:**
> *"Função que roda sem servidor. Você escreve o código, a AWS executa quando
> precisa. Paga por execução — se não rodar, não paga. Escala de zero a milhares
> de execuções simultâneas automaticamente."*

**Hands-on** — uma função simples, escrita para este bloco, que grava um chamado
na tabela:

- Criar função `GravaChamado`, runtime Python 3.13
- Colar o código:

```python
import os, uuid, boto3
from datetime import datetime, timezone

tabela = boto3.resource("dynamodb").Table(os.environ["TABELA_NOME"])

def handler(evento, contexto):
    item = {
        "id": str(uuid.uuid4()),
        "titulo": evento.get("titulo", "sem título"),
        "descricao": evento.get("descricao", ""),
        "status": "aberto",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    tabela.put_item(Item=item)
    return item
```

- Configuration → Environment variables → `TABELA_NOME` = `Chamados`
- Configuration → Permissions → abrir a role → **anexar permissão de escrita no
  DynamoDB**. Parar aqui e explicar:

> *"Essa função não tem permissão para nada por padrão. Se eu tentar rodar agora,
> tomo AccessDenied. Toda permissão na AWS é explícita — e guardem esse trabalho
> de abrir a role e anexar política, porque na Parte 2 ele desaparece."*

- Test → criar evento de teste `{"titulo": "Servidor fora do ar"}` → Invoke
- Ver o retorno, ver o item na tabela, abrir os **CloudWatch Logs**

> *"CloudWatch é onde todos os logs da AWS vão parar automaticamente. Vocês não
> configuraram nada — a Lambda já loga."*

**Aprendizado:** compute serverless, handler e evento, variável de ambiente,
**permissão IAM explícita**, observabilidade automática. O trabalho manual de
IAM aqui é o que dá impacto ao `link()` na Parte 2.

---

#### 1:25–1:45 — SQS

**O que é:**
> *"Fila de mensagens. Você coloca uma mensagem, alguém pega quando estiver
> pronto. Se o processador cair, a mensagem continua na fila. Nada se perde — e o
> produtor não precisa que o consumidor esteja disponível na hora do envio."*

**Queue-Based Load Leveling:**
> *"Na aplicação final, a Lambda da API não vai esperar o agente de AI processar
> o chamado — isso leva segundos. Ela salva, joga na fila e responde na hora. O
> agente processa depois, no ritmo dele. Isso é Queue-Based Load Leveling."*

**Hands-on:**
- Criar fila `ChamadosFila` (Standard)
- Send and receive messages → enviar `{"titulo": "Banco de dados lento"}` → ver a
  mensagem na fila
- Voltar na Lambda `GravaChamado` → Add trigger → SQS → `ChamadosFila`
- Notar que o trigger pede **mais uma permissão na role** (ler da fila)
- Ajustar o handler para ler do envelope do SQS:

```python
import json
# dentro do handler, o evento agora vem embrulhado:
#   {"Records": [{"body": "{\"titulo\": \"...\"}"}]}
for registro in evento["Records"]:
    dados = json.loads(registro["body"])
```

- Enviar outra mensagem pela fila e **não invocar nada**: o item aparece na
  tabela sozinho
- Mostrar a mensagem em *In Flight* durante o processamento

> *"Ninguém chamou a Lambda. Ela reagiu a um evento. Acabamos de montar o primeiro
> pedaço event-driven da aplicação: SQS → Lambda → DynamoDB, sem nada chamando
> nada diretamente."*

**Aprendizado:** fila como buffer assíncrono, desacoplamento, Queue-Based Load
Leveling, trigger como configuração explícita (fila + permissão + mapeamento).

> **Nota honesta a dizer:** esta fila não tem Dead Letter Queue. Uma mensagem que
> falha sempre fica retentando até expirar. Em produção se configura uma DLQ —
> no SST é um argumento (`dlq`) no `sst.aws.Queue`.

---

### Intervalo — 1:45–1:55 (e Setup 2)

Dez minutos de intervalo que são também o setup local da Parte 2. O instrutor
circula ajudando. No telão:

```bash
git clone <url-do-repo> && cd minicurso-poc
npm install
uv sync --all-packages

# credenciais do Learner Lab: botão "AWS Details" → copiar o bloco e colar
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...

aws sts get-caller-identity   # tem que responder com um ARN
```

> *"Quem conseguir, vai fazer deploy da própria infraestrutura junto comigo. Quem
> não conseguir, acompanha na tela — ninguém fica atrás por causa disso."*

O sucesso da aula não pode depender de 30 ambientes locais. Mas quem tiver
ambiente vive o argumento central do minicurso em vez de ouvi-lo.

---

### Parte 2 — Do manual ao IaC (1:55–3:00)

---

#### 1:55–2:05 — O problema do manual

Listar ao vivo, na ordem em que a turma fez:

```
✓ Bucket S3 criado manualmente
✓ Block Public Access desmarcado manualmente
✓ Bucket policy escrita manualmente
✓ Website hosting habilitado manualmente
✓ Tabela DynamoDB criada manualmente
✓ Função Lambda criada manualmente
✓ Código colado manualmente
✓ Variável de ambiente configurada manualmente
✓ Permissão de DynamoDB anexada manualmente na role
✓ Fila SQS criada manualmente
✓ Trigger SQS → Lambda configurado manualmente
✓ Permissão de leitura da fila anexada manualmente
```

> *"Doze passos. Nenhum versionado. Nenhum reproduzível com segurança. Se um
> segundo dev precisar do mesmo ambiente, refaz tudo do zero e reza para não
> esquecer um clique. Se algo mudar, atualiza à mão em cada lugar. O problema não
> é o esforço — é a rastreabilidade: ninguém sabe dizer qual é o estado correto."*

> *"E foi só isso: **quatro serviços**. A aplicação completa tem doze peças. Agora
> eu vou construir as doze na frente de vocês, em menos de 150 linhas, e vocês
> vão rodar um comando para elas existirem na conta de vocês."*

**Aprendizado:** o problema do manual é rastreabilidade, reprodutibilidade e
consistência — não volume de trabalho.

---

#### 2:05–2:45 — SST Ion, cinco passos por branch

**O que é IaC:**
> *"Infrastructure as Code. Infra declarada em código, versionada no Git,
> reproduzível em qualquer conta. Se deletar tudo e rodar de novo, fica idêntico."*

**O que é SST Ion:**
> *"IaC moderno em TypeScript. Abstrai o Pulumi por baixo — você não precisa
> saber que o Pulumi existe. O `sst deploy` declara o que você quer e garante
> que está no estado correto."*

**Como este bloco funciona:** cada passo é uma branch. O instrutor faz
`git checkout`, mostra o **diff** em relação ao passo anterior, explica, e segue.
A turma não digita. Dois deploys ao longo do bloco: um no passo 1 (rápido, o
momento "funciona") e um no fim (a aplicação completa).

> *"Vou trocar de branch a cada passo. O `git diff` entre duas branches mostra
> exatamente as linhas que mudaram — é a melhor forma de ver uma arquitetura
> crescer sem se perder no arquivo inteiro."*

---

**`passo-1-bucket` — o menor `sst.config.ts` possível** *(6 min, deploy da turma)*

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
    const bucket = new sst.aws.Bucket("Relatorios");
    return { bucket: bucket.name };
  },
});
```

Explicar: `app()` (identidade e região), `run()` (os recursos), **stage** como
ambiente isolado, `return` como output. E que `aws` e `sst` são globais — o
`/// <reference>` no topo é o que faz isso, não precisa importar nada.

**A turma roda:**
```bash
npx sst secret set ApiKey "$(openssl rand -hex 24)" --stage lab   # usado no passo 3
npx sst deploy --stage lab
```

Enquanto o deploy roda (~1 min), explicar que o SST está criando um bucket de
estado na conta para saber o que já existe. Ao terminar: cada um abre o próprio
console e vê **o próprio bucket**.

> *"Trinta pessoas, trinta contas AWS diferentes, um comando, o mesmo resultado.
> Isso é o que 'reproduzível' significa na prática."*

Mostrar também `npx sst remove --stage lab` — e não rodar.

---

**`passo-2-link` — a ideia central do SST** *(8 min)*

Diff: entram `sst.aws.Dynamo` e `sst.aws.Function`, com `link`.

```typescript
const tabela = new sst.aws.Dynamo("Chamados", {
  fields: { id: "string" },
  primaryIndex: { hashKey: "id" },
});

const chamadosApi = new sst.aws.Function("ChamadosApi", {
  handler: "functions/src/functions/api.handler",
  runtime: "python3.13",
  memory: "256 MB",
  timeout: "10 seconds",
  link: [tabela],
});
```

E no Python, a única mudança:

```python
# antes (Parte 1, feito à mão)
dynamodb.Table(os.environ["TABELA_NOME"])
# depois
dynamodb.Table(Resource.Chamados.name)
```

Este é o passo mais importante do bloco. Cobrar o contraste:

> *"Na Parte 1 vocês fizeram três coisas para a Lambda alcançar a tabela: criaram
> a variável de ambiente, abriram a role e anexaram a política. Aqui eu escrevi
> `link: [tabela]`. O SST injetou o nome da tabela no runtime e criou uma role
> com exatamente as permissões que essa função precisa — nem uma a mais. E eu não
> escrevi um ARN, não escrevi um nome de tabela, não escrevi uma policy."*

Abrir no console a role gerada, se o tempo permitir — ver a policy mínima que
ninguém escreveu.

> **Nota do Learner Lab:** o Lab nega `iam:CreateRole`, então o `sst.config.ts`
> tem um interruptor `usarLabRole` que fixa as Functions na `LabRole` existente.
> Dizer isso e explicar o custo: com uma role pronta, o SST para de gerenciar as
> permissões dela — perdemos justamente o privilégio mínimo que acabamos de
> elogiar. Em conta normal o interruptor fica `false` e o SST cuida de tudo.

> **Python no SST:** suporte mantido pela comunidade, espera um workspace `uv`
> com um `pyproject.toml` por pacote. Já vem pronto no scaffold — é o que o
> `uv sync --all-packages` do intervalo resolveu.

---

**`passo-3-api` — a porta de entrada e o segredo** *(7 min)*

Diff: `sst.aws.ApiGatewayV2`, duas rotas, `sst.Secret` e o Lambda Authorizer.

```typescript
const apiKey = new sst.Secret("ApiKey");

const api = new sst.aws.ApiGatewayV2("Api", {
  cors: { allowOrigins: ["*"], allowMethods: ["GET", "POST"],
          allowHeaders: ["content-type", "x-api-key"] },
});

const apiAuth = api.addAuthorizer({
  name: "ApiKeyAuthorizer",
  lambda: {
    function: { handler: `${fnDir}/authorizer.handler`, runtime,
                memory: "128 MB", timeout: "5 seconds", link: [apiKey] },
    identitySources: ["$request.header.x-api-key"],
    payload: "2.0", response: "simple", ttl: "5 minutes",
  },
});

const auth = { auth: { lambda: apiAuth.id } };
api.route("POST /chamados", chamadosApi.arn, auth);
api.route("GET /chamados", chamadosApi.arn, auth);
```

Três coisas a dizer:

**1. Segredo nunca no código.** O valor foi setado uma vez por CLI, no passo 1.
> *"`sst.Secret` guarda o valor fora do repositório, por stage. É o papel que o
> Parameter Store cumpre na AWS — mesma função, mecanismo diferente por baixo: o
> SST guarda num bucket dele, não no Parameter Store. Se esquecerem o valor:
> `npx sst secret list --stage lab`. Não existe `sst secret get`."*

**2. Por que um Lambda Authorizer e não "API Key".**
> *"A REST API v1 da AWS tem API Key + Usage Plan prontos. A HTTP API, que é mais
> simples e mais barata e é a que estamos usando, **não tem** esse recurso. Muita
> gente descobre isso procurando no console uma opção que não existe. O
> equivalente aqui é uma Lambda que roda antes da sua e decide se deixa passar."*

**3. Uma Function, duas rotas.** As duas `.route()` recebem `chamadosApi.arn`, não
o caminho do handler.
> *"Se eu passasse a mesma string de handler nas duas rotas, o SST criaria duas
> Lambdas idênticas — uma por rota, sem avisar. Passando o ARN de uma Function que
> eu construí antes, as duas rotas compartilham a mesma função."*

Demonstrar `401` vs `403` com `curl`:

```bash
curl -s -o /dev/null -w '%{http_code}\n' $API/chamados                        # 401
curl -s -o /dev/null -w '%{http_code}\n' -H 'x-api-key: errada' $API/chamados  # 403
```

> *"401 significa que nenhuma credencial chegou ao authorizer. 403 significa que
> chegou e foi recusada. Os dois estão certos, e a diferença ajuda muito a
> depurar."*

---

**`passo-4-fila` — o agente de AI atrás da fila** *(8 min)*

Diff: SQS, bucket de relatórios, a layer do Strands, o secret do Groq e o
`fila.subscribe()`.

```typescript
const fila = new sst.aws.Queue("ChamadosFila", { visibilityTimeout: "90 seconds" });
const bucket = new sst.aws.Bucket("Relatorios");
const groqApiKey = new sst.Secret("GroqApiKey");

const strandsLayer = new aws.lambda.LayerVersion("StrandsLayer", {
  layerName: "strands-openai",
  code: $asset("layers/strands-openai/build"),
  compatibleRuntimes: [runtime],
  compatibleArchitectures: ["x86_64"],
});

fila.subscribe({
  handler: `${fnDir}/agente.handler`,
  runtime, layers: [strandsLayer.arn],
  memory: "512 MB", timeout: "30 seconds",
  link: [topico, bucket, groqApiKey],
});
```

> *"SQS vocês criaram à mão, com trigger e permissão. Aqui é `fila.subscribe()`
> — uma linha, e o SST cria a função, o mapeamento de evento e as permissões de
> leitura da fila."*

**O que é Strands Agents:**
> *"Framework da AWS para agentes de AI. Aqui ele lê o chamado, classifica a
> prioridade e sugere uma ação. Usamos o Groq como provider — inferência rápida
> com modelos open source. O Groq expõe uma API compatível com a da OpenAI, então
> o provider `OpenAIModel` nativo do Strands serve, só apontando o `base_url`."*

**Lambda Layer — por que precisa:**
> *"O Strands tem dependências grandes demais para o zip da função. Layer é o
> mecanismo para compartilhar dependências, compiladas para linux. Já está pronta
> — não se monta layer ao vivo."*

> **Pegadinha que vale contar:** `$asset()` zipa o **conteúdo** do diretório. O
> Lambda exige uma pasta `python/` na raiz do zip, então aponta-se para
> `build/` (que contém `python/`), não para `build/python/`. Errar isso dá
> `No module named 'strands'` em runtime — erro que parece qualquer outra coisa.

**Memória e timeout medidos, não chutados** — mostrar a tabela:

| Lambda | memória | timeout | duração medida | memória usada |
|---|---|---|---|---|
| `authorizer` | 128 MB | 5s | ~2 ms | 44 MB |
| `api` | 256 MB | 10s | 28–283 ms | 94 MB |
| `discord` | 256 MB | 15s | ~420 ms | 94 MB |
| `agente` | 512 MB | 30s | ~5,1 s | ~193 MB |

> *"Memória no Lambda também é CPU. Quando cortei o agente de 1024 para 512 MB, a
> memória usada não mudou — continuou em ~193 MB. Mas o tempo de execução mais que
> dobrou, porque o processamento do Strands é sensível a CPU. Não é economia de
> graça, e não se descobre isso chutando: são 30 segundos de CloudWatch."*

E lembrar: `visibilityTimeout` da fila tem que ser **maior ou igual** ao timeout
da Lambda que consome, senão a mensagem volta para a fila enquanto ainda está
sendo processada.

---

**`passo-5-fanout` — SNS e o Discord** *(6 min)*

Diff: o tópico e o subscriber.

```typescript
const topico = new sst.aws.SnsTopic("ChamadosTopico");

topico.subscribe("DiscordNotifier", {
  handler: `${fnDir}/discord.handler`,
  runtime, memory: "256 MB", timeout: "15 seconds",
  link: [tabela, discordWebhook],
});
```

**Por que SNS e não chamar o Discord direto do agente:**
> *"Se o agente chamasse o Discord, estaria acoplado ao Discord. Para também
> avisar no Slack ou abrir um ticket, eu teria que mexer no agente. Com SNS eu
> adiciono um subscriber novo e não toco em nada do que já funciona."*

```
SNS Topic
├── Lambda Discord    ← provisionado hoje
├── Lambda Slack      ← poderia ser adicionado
└── Lambda Logging    ← poderia ser adicionado
```

> **Detalhe fácil de confundir:** `Queue.subscribe()` **não** recebe nome (uma
> fila tem um consumidor). `SnsTopic.subscribe()` **recebe** (um tópico tem
> vários).

E a peça que fecha o event-driven:

> *"Repare no que o DynamoDB faz aqui. A Lambda da API criou o item com quatro
> campos. A Lambda do Discord grava o mesmo `id` com campos a mais: `analise`,
> `timestamp`. O mesmo registro foi ganhando campos ao longo do fluxo — é o
> schemaless que vocês viram no bloco de DynamoDB, agora em movimento."*

---

**`main` — o frontend e o deploy completo** *(5 min, deploy da turma)*

Diff: o bucket do frontend, o website config e o CORS travado.

```typescript
const frontendBucket = new sst.aws.Bucket("Frontend", {
  access: "public",
  // website hosting do S3 serve só em HTTP puro, e a policy padrão do
  // componente nega acesso sem HTTPS — o que bloquearia o próprio site
  enforceHttps: false,
});

new aws.s3.BucketWebsiteConfiguration("FrontendWebsite", {
  bucket: frontendBucket.name,
  indexDocument: { suffix: "index.html" },
  errorDocument: { key: "index.html" },
});
```

> *"O `sst.config.ts` declara o bucket, e nada mais sobre o frontend. O build e o
> upload ficam num script separado, `deploy-frontend.sh`, rodado depois. Infra e
> aplicação têm ciclos de vida diferentes — num pipeline de CI/CD real seriam dois
> jobs distintos."*

**A turma roda:**
```bash
npx sst secret set GroqApiKey "gsk_..." --stage lab
npx sst secret set DiscordWebhook "https://discord.com/api/webhooks/..." --stage lab
npx sst deploy --stage lab
./scripts/deploy-frontend.sh
```

Enquanto o deploy roda, o beat da chave de acesso:

> *"O script imprime a URL do site e a ApiKey no fim. Reparem que a chave **não**
> vai para dentro do site: o site pede num campo. Se ela fosse embutida no build,
> estaria em texto puro dentro de um arquivo JavaScript público — qualquer
> visitante leria no DevTools em quinze segundos. E isso não é limitação do Vite:
> **nenhum segredo sobrevive dentro de código que roda no navegador.** Autenticação
> de verdade seria login por usuário, com cada um recebendo o próprio token. O que
> temos aqui é uma barreira contra robô, e é honesto chamar pelo nome."*

> *"18 passos manuais viraram menos de 150 linhas. Versionado no Git. Reproduzível
> em qualquer conta."*

**Aprendizado do bloco:** IaC resolve rastreabilidade e reprodutibilidade.
`link()` elimina configuração manual de IAM e variável de ambiente. `Resource` é
a experiência do dev: sem ARN, sem hardcode, sem `os.environ`. `sst.Secret` é o
Parameter Store do SST. HTTP API não tem API Key nativa — Lambda Authorizer é o
caminho. E memória/timeout se medem, não se chutam.

---

#### 2:45–2:53 — Demo final

Abrir o site, colar a ApiKey, criar um chamado:

```
Título:    Banco de dados de produção fora do ar
Descrição: Aplicação retornando erro 500 em todas as requisições desde as 14h.
```

Mostrar em sequência, cada uma no console:

1. Chamado aparece na lista — API Gateway + Lambda + DynamoDB
2. Mensagem na SQS — Queue-Based Load Leveling
3. CloudWatch Logs do agente — Strands + Groq processando
4. Relatório no S3
5. SNS entregou ao subscriber — fan-out
6. **Discord recebeu a notificação com a análise da AI**
7. DynamoDB com o histórico e o `status` atualizado

Outros chamados prontos, para variar a prioridade que o agente classifica:

```
Alto     Login não funciona para novos usuários
         Usuários cadastrados hoje não conseguem autenticar — erro de
         credenciais inválidas mesmo com senha correta.

Médio    Relatório mensal com valores incorretos
         O relatório de outubro está somando duplicado os pedidos cancelados.
         Não trava o sistema, mas os números saem errados.

Baixo    Botão de exportar CSV com texto cortado
         Na tela de relatórios o botão está com o texto cortado em telas
         menores que 1024px. Só estético.
```

---

#### 2:53–3:00 — Fechamento + sorteio

**O que vimos:**

```
S3               → storage e hosting estático
DynamoDB         → banco NoSQL serverless, schemaless
Lambda           → compute serverless, pay-per-execution
SQS              → fila assíncrona, Queue-Based Load Leveling
API Gateway      → porta de entrada HTTP
Lambda Authorizer → autenticação simples numa HTTP API
SNS              → fan-out de eventos
Parameter Store / sst.Secret → segredo fora do código
Lambda Layer     → dependências compartilhadas
Strands + Groq   → agente de AI dentro da arquitetura
CloudWatch       → observabilidade automática
SST Ion          → IaC, do manual ao cloud-native
```

**Para quem quiser ir além — o próximo passo está numa branch:**

> *"Tem um problema na nossa arquitetura que eu não consertei. A Lambda da API
> grava no DynamoDB e depois publica no SQS: dois sistemas, duas chamadas, sem
> atomicidade. Se ela morrer entre as duas linhas, o chamado existe e nunca é
> analisado. Isso tem nome: **dual write problem**. A solução clássica é o
> **transactional outbox pattern** — gravar o evento numa tabela `Outbox` na mesma
> transação e drenar depois. No DynamoDB dá para fazer melhor: o **Stream** da
> tabela já é esse log, então não precisa de tabela de outbox nenhuma. Está
> implementado na branch `outbox-streams` — clonem e comparem."*

**Onde continuar praticando:**

```
AWS Builder Center Sandbox   → builder.aws
                               gratuito, sem cartão de crédito, conta AWS real

AWS Free Tier                → aws.amazon.com/pt/free
                               créditos + serviços sempre gratuitos
                               tudo que fizemos hoje está coberto

AWS Learner Labs             → via AWS Academy, o ambiente de hoje
```

**Certificações:**

```
AWS Serverless Demonstrated  → skillbuilder.aws
                               gratuito, hands-on em ambiente real
                               sem múltipla escolha, badge no Credly
                               valida exatamente o que fizemos hoje

Cloud Practitioner           → certificação formal
                               Skill Builder (curso oficial gratuito)
                               4 a 6 semanas com a base de hoje
```

**Não esquecer:** pedir para todos rodarem `npx sst remove --stage lab`. Numa
conta própria isso é a diferença entre centavos e uma surpresa na fatura.

**Fala de fechamento:**
> *"Vocês saem sabendo o que é serverless na prática, não na teoria. Quatro
> serviços construídos com as próprias mãos, e a aplicação inteira subindo com um
> comando na conta de cada um. Para continuar: Builder Center Sandbox para
> praticar sem cartão, Free Tier para projetos próprios, Serverless Demonstrated
> para validar o que aprenderam hoje.*
>
> *Antes de encerrar — o sorteio."*

**Sorteio.**

---

### Princípios de execução

- **Mostrar a aplicação funcionando no início.** O participante precisa saber o
  destino antes de começar a jornada.
- **Ritmo fixo por serviço:** o que é → hands-on → como se encaixa.
- **O bloco "problema do manual" é curto e obrigatório.** Sem sentir a dor, o
  SST Ion não tem impacto.
- **Na Parte 1 a turma faz; na Parte 2 a turma acompanha.** Não tentar as duas
  coisas ao mesmo tempo, e dizer isso explicitamente no começo para ninguém se
  sentir deixado de fora.
- **Cobrar o contraste sempre que aparecer.** Cada `link()` deve ser cobrado
  contra a role que eles abriram à mão; cada `subscribe()` contra o trigger que
  eles configuraram.
- **Nomear o que é atalho didático.** `scan()` em vez de GSI, fila sem DLQ,
  chave compartilhada em vez de login. Dizer é mais forte que silenciar.
- **Defender 1:45 e 2:05.** Se a Parte 1 atrasar, cortar profundidade — nunca o
  intervalo, que é o setup local da Parte 2.
- **Perguntar "quem não conseguiu?" em voz alta** ao fim de cada hands-on, em vez
  de "todos conseguiram?". A primeira pergunta tem resposta honesta.

---

### Plano B

| Se… | Então… |
|---|---|
| A AWS/console travar | Seguir com o deploy gravado; a narrativa continua. |
| Credenciais do Lab expirarem | Reabrir o Lab, re-exportar, `npx sst unlock --stage lab` antes de deployar de novo (o deploy morto deixa lock). |
| Groq fora do ar ou modelo retirado | Conferir `GET /v1/models`; se necessário, mostrar a análise de um chamado já processado antes da aula. |
| Discord bloquear o webhook | Mostrar o relatório no S3 e o item no DynamoDB — o fluxo é o mesmo, sem a notificação. |
| Ninguém conseguir ambiente local | A Parte 2 vira 100% demonstração; nada do conteúdo se perde. |
| Faltar tempo na Parte 2 | Cortar o `passo-5-fanout` (SNS) e ir direto ao `main`; explicar fan-out pelo diagrama. |
