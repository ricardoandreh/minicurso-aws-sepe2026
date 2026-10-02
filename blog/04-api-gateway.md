# 4. A porta de entrada

> Série: construindo um encurtador de URL serverless na AWS — [índice](README.md)

A função existe mas ninguém alcança. Falta o endereço.

## O que é o API Gateway

A porta HTTP da sua aplicação. Ele recebe a requisição, decide qual Lambda
chamar, converte a resposta de volta em HTTP e devolve ao navegador.

## Como funciona

Três conceitos, e vale separá-los porque o console os mistura:

**Rota** é o par método + caminho: `POST /shorten`, `GET /{shortId}`. O trecho
entre chaves é variável e chega à função em `pathParameters`.

**Integração** é para onde a rota aponta — no nosso caso, uma Lambda.

**Permissão** é o direito do API Gateway de invocar aquela função. Fica na
*resource policy* da Lambda, não na role. É um terceiro elemento, invisível na
tela de rotas, e é a causa de erro mais frequente deste artigo.

Existem dois tipos de API: **REST API** (v1, mais recursos, mais cara) e **HTTP
API** (v2, mais simples, mais barata, mais rápida). Vamos de HTTP API — e
registre uma diferença que importa: **HTTP API não tem API Key nem Usage Plan**.
Esses são exclusivos da REST API. Muita gente perde tempo procurando no console
uma opção que não existe ali.

## Onde entra no encurtador

Ele transforma a função do artigo 3 numa aplicação de verdade:

```
POST /shorten        → cria o link
GET  /urls           → lista
GET  /{shortId}      → redireciona
```

As três apontam para a **mesma** Lambda, que despacha pelo `routeKey`.

## Hands-on

### 1. Criar a API

Console → **API Gateway** → **Create API** → em **HTTP API**, clique **Build**.

- **API name:** `url-shortener-api-gtw`
- **Add integration** → **Lambda** → escolha `url-shortener-api`
- **Next**

### 2. Criar as rotas

Na etapa de rotas, configure as três apontando para a mesma integração:

| Method | Resource path |
|---|---|
| POST | `/shorten` |
| GET | `/urls` |
| GET | `/{shortId}` |

**Next** → deixe o stage `$default` com *Auto-deploy* → **Create**.

> 📸 **Print:** a lista das três rotas, todas com a mesma Lambda como destino.

**Atenção à ordem conceitual:** `/urls` e `/{shortId}` competem pelo mesmo
formato de caminho. O API Gateway resolve isso dando precedência ao **segmento
literal**: `/urls` cai na listagem, não no redirect. Se você esquecer de criar a
rota `/urls`, o caminho `/urls` casa com `/{shortId}` e sua função vai procurar
um link chamado "urls" no banco — devolvendo 404 por um motivo completamente
diferente do que parece.

### 3. Configurar o CORS

**Develop → CORS → Configure CORS**:

| Campo | Valor |
|---|---|
| Access-Control-Allow-Origin | `http://url-shortener-site-SEUNUMERO.s3-website-us-east-1.amazonaws.com` |
| Access-Control-Allow-Methods | `GET`, `POST` |
| **Access-Control-Allow-Headers** | **`content-type`** |

**Save.**

> 📸 **Print:** a tela de CORS preenchida, destacando o campo de headers.

Não adicione `OPTIONS` aos métodos: a HTTP API responde o preflight sozinha.

### 4. Apontar o frontend para a API

Copie a **Invoke URL** (algo como `https://abc123.execute-api.us-east-1.amazonaws.com`).

No `index.html`, troque:

```js
const API_URL = "https://SEU-API-ID.execute-api.us-east-1.amazonaws.com";
```

Suba o arquivo de novo no S3 (**Upload**, sobrescrevendo) e recarregue o site com
**Ctrl+Shift+R**.

> 📸 **Print:** o site com um link já encurtado na lista, mostrando o contador
> em zero.

### 5. Testar o fluxo

Cole uma URL longa, clique em **Encurtar** e depois no link curto que apareceu.
Você deve ser redirecionado.

## O que deu errado (e por quê)

Este artigo tem quatro erros clássicos, e **o jeito de distingui-los é olhar se
a Lambda gerou log**. Se não gerou, o problema está antes dela.

| Resposta | Tem log na Lambda? | Causa |
|---|---|---|
| `{"message":"Not Found"}` | não | a rota não existe |
| `{"message":"Internal Server Error"}` | **não** | falta permissão de invocação |
| nada, e erro de CORS no console do navegador | não | preflight bloqueado |
| `{"error":"..."}` | sim | é o seu código respondendo |

**O 500 sem log** merece destaque. Quando você cria uma rota e **seleciona uma
integração já existente**, o console não adiciona a permissão de invocação para
aquela rota. O API Gateway tenta chamar a função, toma `AccessDenied` e devolve
o 500 genérico dele. Sua função nunca roda, então não há log nenhum para
consultar — o que faz você procurar no lugar errado.

Para corrigir: apague a rota e recrie usando **Create and attach an
integration**, que adiciona a permissão.

**O erro de CORS** tem uma armadilha própria: **testar com `curl` não revela o
problema**. O `curl` não faz preflight. A API responde 201 lindamente na linha de
comando e o site continua sem funcionar, o que leva você a culpar o JavaScript.

E ele é sutil porque o CORS pode estar *quase* certo. Com origem e métodos
configurados mas **sem `content-type` nos headers**, o preflight devolve 204 —
sucesso — mas sem nenhum cabeçalho `Access-Control-*`, e o navegador cancela.
Como o frontend manda `Content-Type: application/json`, é justamente esse header
que obriga o preflight.

**A URL curta sai com `$default` no meio.** A HTTP API faz auto-deploy num stage
chamado `$default`, que **não** aparece no caminho da URL. Se o código montar
`https://{domínio}/{stage}/{id}`, o resultado é `.../$default/abc123`, quebrado.
Por isso a função verifica:

```python
prefixo = "" if stage == "$default" else f"/{stage}"
```

## Como isso sustenta serverless

O API Gateway é o tradutor que permite que a sua função **não saiba o que é
HTTP**. Ela recebe um dicionário e devolve um dicionário. Quem converte isso de
e para a web é outro serviço, gerenciado, que escala sozinho.

É desacoplamento real, não metáfora: a mesma função poderia ser acionada por uma
fila amanhã, sem mudar a lógica — só o formato do evento. E é por isso que o
próximo artigo consegue acrescentar um caminho totalmente assíncrono sem
reescrever nada do que já existe.

## O que ainda não dá para fazer

O encurtador funciona. Mas repare no redirect: ele busca a URL, conta o clique e
só então responde. Quem clicou está esperando o banco ser atualizado para ser
redirecionado — e contar clique não é urgente para ninguém.

**Próximo:** [5. Tirando trabalho do caminho crítico](05-sqs.md)
