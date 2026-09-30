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
