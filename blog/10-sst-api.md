# 10. A API, agora em três linhas

> Parte da série *construindo um encurtador de URL serverless na AWS*. [Voltar ao índice](README.md)

No artigo 4 a API deu trabalho. Criar a HTTP API, criar três rotas, apontar cada uma para a função, configurar CORS em outra aba, descobrir que o preflight estava faltando um cabeçalho. Agora são três linhas e um bloco de CORS.

## O componente

```typescript
const api = new sst.aws.ApiGatewayV2("Api", {
  cors: {
    allowOrigins: [siteUrl],
    allowMethods: ["GET", "POST"],
    allowHeaders: ["content-type"],
  },
});

api.route("POST /shorten", encurtador.arn);
api.route("GET /urls", encurtador.arn);
api.route("GET /{shortId}", encurtador.arn);
```

Quatro coisas estão acontecendo aqui que não são óbvias, e cada uma delas foi um erro que alguém já cometeu.

## 1. O `.arn`, e por que não o objeto

Repare que `api.route()` recebe `encurtador.arn`, não `encurtador`. Isso é deliberado.

Se você passar o caminho do handler direto na rota, assim:

```typescript
api.route("POST /shorten", `${fnDir}/api.lambda_handler`);
api.route("GET /urls", `${fnDir}/api.lambda_handler`);
```

o SST cria **duas funções Lambda idênticas**, sem avisar, e cada rota chama a sua. Do ponto de vista dele faz sentido: você pediu uma função por rota. Do seu ponto de vista, você acabou de duplicar cold starts, logs e configuração.

Construir a função antes e passar o ARN para as três rotas é o que faz as três compartilharem a mesma Lambda. É o mesmo arranjo do artigo 4, onde você apontou as três rotas para a mesma função na lista.

## 2. A permissão de invocação, que você não escreve

No artigo 4, se você criou a rota antes de associar a função, teve um 500 sem nenhum log na Lambda. A causa é que o API Gateway precisa de permissão explícita para invocar aquela função, e essa permissão não vive na role da função: é uma *resource policy* na própria Lambda, uma por rota.

O console adiciona isso quando você usa o assistente, e não adiciona quando você faz na ordem errada. O `api.route()` sempre adiciona. Você não tem como errar essa ordem.

Esse é o tipo de coisa que o console te deixa fazer pela metade e a IaC não.

## 3. A precedência das rotas não é sua

```
GET /urls
GET /{shortId}
```

As duas casam com `GET /urls`. Quem decide é o API Gateway, e a regra é que **rota literal vence rota com variável**. Então `/urls` lista, e qualquer outro caminho cai no redirect.

Você não controla isso pela ordem em que escreveu as linhas. Se fosse pela ordem, trocar duas linhas de lugar faria a listagem virar uma tentativa de redirecionar um link de id `urls`, que daria 404. Vale saber que a regra existe, porque quando ela te morder, o sintoma vai ser estranho.

## 4. O `content-type` no `allowHeaders`

Essa custou tempo de verdade.

```typescript
allowHeaders: ["content-type"],
```

Sem essa linha o preflight responde **204, com sucesso, e sem nenhum cabeçalho `Access-Control-*`**. O navegador então cancela o POST silenciosamente, e a API não registra erro algum, porque do ponto de vista dela nada deu errado.

E o detalhe cruel: `curl` não mostra o problema. `curl` não faz preflight. Você testa pelo terminal, funciona, testa pelo navegador, não funciona, e passa meia hora olhando o lugar errado.

Por que o `content-type` especificamente? Porque é justamente ele que faz a requisição deixar de ser "simples" aos olhos do navegador e exigir preflight. O frontend manda `Content-Type: application/json` no POST, então todo POST do encurtador passa por essa porta.

## O bucket do site, que fica de fora

```typescript
const bucketSite = process.env.BUCKET_SITE;
if (!bucketSite) {
  throw new Error("Informe o bucket do site, criado no hands-on da Parte 1: ...");
}
const siteUrl = `http://${bucketSite}.s3-website-us-east-1.amazonaws.com`;
```

O `allowOrigins` do CORS precisa da URL do site, e o site é o bucket que você criou no artigo 1. Em conta AWS comum esse bucket seria um `sst.aws.Bucket` aqui mesmo, e o `siteUrl` sairia dele. No Learner Lab não dá, pelo motivo que o artigo 8 explica: a SCP que nega `s3:GetBucketObjectLockConfiguration` impede o Pulumi até de referenciar um bucket existente.

Então passamos só o nome, por variável de ambiente, e o config monta a URL. O `throw` ali é para falhar com uma mensagem útil em vez de deployar um CORS com `undefined` no meio.

## Hands-on

### 1. Trocar de passo

```bash
git checkout passo-3
git diff passo-2 passo-3
```

Dois arquivos mudaram. No `sst.config.ts` entrou o bloco da API; no `api.py` entrou a rota de redirect, que no passo anterior não tinha onde existir.

### 2. Deployar, com o nome do bucket

```bash
BUCKET_SITE=url-shortener-site-SEUNUMERO npx sst deploy --stage lab
```

Use o nome exato do bucket do artigo 1. No fim, três outputs: `site`, `api` e `tabela`.

> 📸 **Print:** a saída do deploy com a URL da API.

### 3. Testar pelo terminal

```bash
curl -X POST https://SEU-API-ID.execute-api.us-east-1.amazonaws.com/shorten \
  -H 'content-type: application/json' \
  -d '{"url":"https://ifc.edu.br"}'
```

Volta um `201` com `shortId` e `shortUrl`. Siga o link curto:

```bash
curl -i https://SEU-API-ID.execute-api.us-east-1.amazonaws.com/SEU-SHORTID
```

`302`, com `Location` apontando para o destino.

Note que a URL não tem stage no caminho. A HTTP API faz auto-deploy num stage chamado `$default`, e esse nome não entra na URL. Só um stage nomeado viraria prefixo. É por isso que o `api.py` calcula:

```python
prefixo = "" if stage == "$default" else f"/{stage}"
```

### 4. Apontar o frontend para a API nova

Edite `url-shortener/index.html`, a linha do `API_URL`, e coloque a URL que saiu no output. Suba de novo para o bucket:

```bash
aws s3 cp url-shortener/index.html s3://url-shortener-site-SEUNUMERO/index.html \
  --profile labs --content-type "text/html; charset=utf-8"
```

Abra o site. Encurte um link. Clique nele.

> 📸 **Print:** o site funcionando, com um link criado pela API nova.

A aplicação está no ar de novo, e desta vez ela cabe num arquivo que você pode ler em dois minutos.

### 5. O teste que mostra o CORS

Vale fazer o erro de propósito, porque é o que mais aparece. No `sst.config.ts`, apague `"content-type"` do `allowHeaders`, deploy, e tente encurtar pelo site. O console do navegador reclama de CORS; a aba Network mostra o OPTIONS com 204 e sem cabeçalho nenhum; o CloudWatch da Lambda não tem log, porque ela nunca foi chamada.

Depois devolve a linha e deploya de novo.

> 📸 **Print:** a aba Network com o OPTIONS 204 sem cabeçalhos de CORS.

## O que deu errado (e por quê)

**404 em `GET /urls`.** A rota não existe com esse nome exato. No payload 2.0 o `routeKey` chega inteiro (`"GET /urls"`), e o dicionário `ROTAS` do `api.py` é um espelho literal das rotas do config. Se um lado tem `/urls` e o outro `/links`, dá 404 e o erro vem da sua própria função, não do API Gateway.

**500 sem log nenhum na Lambda.** Permissão de invocação, explicada acima. Com `api.route()` isso não deveria acontecer, mas se você estiver comparando com a API que fez a mão no artigo 4, é lá que está.

**O site continua batendo na API velha.** O `index.html` é um arquivo estático no S3. Trocar o `API_URL` localmente não muda o que está no bucket, e o navegador ainda pode ter o antigo em cache. Suba de novo e recarregue com Ctrl+Shift+R.

**`CORS` reclamando de `http` versus `https`.** O `allowOrigins` tem que casar exatamente com a origem do navegador, esquema incluído. O site do S3 é `http://` sem CloudFront, e `https://` ali não vale.

## Como isso sustenta serverless

A HTTP API tem uma propriedade que vale notar: ela não tem servidor para você dimensionar, e também não tem nada para você deixar ligado. Zero requisição, zero custo.

E o jeito como ela se liga à função é o padrão que se repete no resto da aplicação: o gatilho é configuração, não código. A função não sabe que existe uma API na frente dela. No próximo artigo, o mesmo código vai ser acionado por uma fila, e continua sem saber.

## O que ainda não dá para fazer

Vá no site, clique num link várias vezes, e olhe o contador. Ele sobe, mas sobe no caminho do usuário: o redirect espera a escrita no DynamoDB terminar antes de responder. Dá para fazer melhor.

**Próximo:** [11. A fila, e o que o `subscribe` esconde](11-sst-fila.md)
