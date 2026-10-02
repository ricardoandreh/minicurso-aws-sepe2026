# Encurtador de URL — app do hands-on no console

Aplicação de apoio do minicurso, usada **só na parte hands-on**, criada inteira
pelo AWS Management Console. Não tem relação com a Central de Chamados (que é
construída por código, com SST, na outra metade da aula) — a ideia aqui é
apresentar cada serviço isolado, numa aplicação pequena que fecha sozinha.

```
Browser ──POST /shorten──▶ API Gateway ──▶ Lambda create ──▶ DynamoDB
Browser ──GET  /{id}────▶ API Gateway ──▶ Lambda redirect ──▶ 301
                                              └──▶ SQS ──▶ Lambda contador ──▶ DynamoDB
Browser ──GET  /{id}/stats─▶ API Gateway ──▶ Lambda stats ──▶ DynamoDB
```

O contador de cliques fica **fora do caminho crítico** de propósito: o redirect
responde na hora e publica na fila; quem incrementa é outra Lambda, depois. É o
Queue-Based Load Leveling com motivo real, não exemplo forçado.

## Frontend

`index.html` é um arquivo só, sem build e sem dependência — é o que se sobe no
bucket S3. Estilo seguindo os tokens do Microsoft Fluent 2, tema claro e escuro.

Antes de subir, editar uma linha:

```js
const API_URL = "https://SEU-API-ID.execute-api.us-east-1.amazonaws.com";
```

## As duas Lambdas

Código em `lambdas/`. Runtime Python 3.13, um arquivo por função.

| Função | Gatilho | Rotas / origem |
|---|---|---|
| `api.py` | HTTP, síncrono | `POST /shorten`, `GET /urls`, `GET /{shortId}` |
| `contador.py` | fila SQS, assíncrono | mensagens publicadas pelo redirect |

Ambas usam `TABELA_NOME` e `FILA_URL`, e `def lambda_handler(...)` — que é o
que o console espera por padrão, então não há passo de trocar o Handler, onde o
primeiro teste costuma falhar.

**Por que as três rotas numa função só.** O critério para separar não é a URL,
é o **gatilho e o ciclo de vida**. As três rotas reagem ao mesmo gatilho (HTTP,
síncrono), escalam juntas e falham juntas — são uma função. O contador reage a
outro gatilho (fila, assíncrono), tem outro perfil de falha e pode ser retentado
sem ninguém esperando do outro lado — por isso é separado. Na prática isso
também corta pela metade o tempo de console no hands-on.

O despacho é por `routeKey`, não por método: `GET /urls` e `GET /{shortId}` são
os dois GET. O payload 2.0 entrega a rota inteira já resolvida
(`"GET /{shortId}"`, com as chaves), então o dicionário `ROTAS` no topo do
arquivo é um espelho literal das rotas da API.

### Decisões que valem ser explicadas em sala

- **302, não 301, no redirect.** O 301 é permanente e o navegador guarda em
  cache: o segundo clique no mesmo link não voltaria à API e o contador pararia
  de subir bem na hora de demonstrar que ele sobe.
- **`ADD clicks :um`** é o contador atômico do DynamoDB. Ler, somar em Python e
  gravar teria race condition, e `SET clicks = clicks + :um` quebra se o
  atributo ainda não existir.
- **Escrita condicional** (`attribute_not_exists(shortId)`) no `create` resolve
  colisão de ID sem precisar ler antes de escrever.
- **`int()` no `stats`.** Número no DynamoDB volta como `Decimal`, que o
  `json.dumps` não serializa — sem isso a rota devolve 500.
- **Nenhuma Lambda devolve cabeçalho de CORS.** Quem responde o preflight
  `OPTIONS` é o API Gateway, pela configuração de CORS da HTTP API. Cabeçalho
  posto na resposta da Lambda não resolve, porque o preflight nem chega nela.

## Bônus: parabéns aos 10 cliques

Cadeia opcional, **não coberta pelos scripts** — montada à mão no console:

```
contador ──update_item──▶ tabela
                           └─▶ Stream ──▶ EventBridge Pipe ──▶ SNS ──▶ discord.py
                                          (filtro: 9 → 10)
```

O filtro do Pipe é quem decide tudo, e por isso a Lambda do Discord não guarda
estado nenhum: ela só notifica.

```json
{
  "eventName": ["MODIFY"],
  "dynamodb": {
    "OldImage": { "clicks": { "N": ["9"]  } },
    "NewImage": { "clicks": { "N": ["10"] } }
  }
}
```

Duas igualdades exatas sobre strings — sem comparador numérico, que no registro
do stream não funcionaria porque o número vem como string (`{"N": "10"}`).

**Não ponha `eventSourceARN` no filtro.** O console sugere, mas o valor que
chega no registro é o ARN do **stream** (`.../table/X/stream/<timestamp>`), e
não o da tabela. Comparação exata com o ARN da tabela nunca casa, e o pipe
simplesmente nunca dispara — sem erro, sem log, sem nada.

A fragilidade honesta: isso depende de `clicks` subir de 1 em 1. Se alguém
agrupar o incremento no contador, o valor pula de 7 para 13, o par 9→10 nunca
existe e nada acontece. A versão à prova de salto troca os valores por
`OldImage` em `["0".."9"]` e `NewImage` com `anything-but` da mesma lista.

O webhook fica no **Parameter Store** como `SecureString` (criptografado com
KMS, gratuito no tier padrão), não em variável de ambiente — variável de
ambiente de Lambda aparece em texto puro para quem abre a função no console.
A `discord.py` guarda o valor em cache de módulo: a consulta acontece uma vez
por cold start, não uma por mensagem.

## Pontos em que a aula costuma travar

- **CORS.** O site é servido de `http://...s3-website...` e chama
  `https://...execute-api...`: é cross-origin. Sem CORS configurado na HTTP API,
  o navegador bloqueia e nada funciona. O frontend detecta esse caso e mostra a
  dica na tela, em vez de um erro genérico.
- **Nome do handler.** O console cria a função com `lambda_function.lambda_handler`.
  Se o código declara `def handler(...)`, é preciso mudar em
  Configuration → Runtime settings → Handler para `lambda_function.handler`.
- **Role no Learner Lab.** `iam:CreateRole` é negado, então na criação da função
  use "Change default execution role" → "Use an existing role" → `LabRole`.
- **Copiar para a área de transferência.** `navigator.clipboard` só existe em
  origem segura, e o S3 website hosting é HTTP puro. O botão já tem fallback via
  `document.execCommand`, senão não copiaria nada.
- **Stage da HTTP API.** Ela faz auto-deploy no stage `$default` e não tem o
  botão "Deploy" da REST API. Monte a URL curta só com `domainName`, sem stage:
  `f"https://{domain}/{short_id}"`.
