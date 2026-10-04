# 3. O código que roda sem servidor

> Parte da série *construindo um encurtador de URL serverless na AWS*. [Voltar ao índice](README.md)

Temos um site e uma tabela. Falta o que fica no meio.

## O que é o Lambda

Um serviço que executa a sua função quando algo acontece. Você entrega o código; a AWS decide onde rodar, quantas cópias subir e quando desligar.

## Como funciona

Sua função recebe dois argumentos: o **evento** (um dicionário com o que aconteceu) e o **contexto** (dados da execução). Ela processa e retorna.

Três ideias que mudam como você escreve código:

**A função não sabe quem a chamou.** Para o Lambda, tudo é um dicionário. Requisição HTTP, mensagem de fila, alteração no banco, tudo chega como JSON. É quem configura o gatilho que define o formato.

**Ela não guarda nada entre execuções.** Variável global às vezes sobrevive, às vezes não. Estado vai para o banco.

**Permissão é explícita e não vem de graça.** Toda função executa com uma **role** do IAM. Sem permissão declarada, qualquer chamada à AWS falha com `AccessDenied`.

## Onde entra no encurtador

Uma função trata as três rotas HTTP:

| Rota | O que faz |
|---|---|
| `POST /shorten` | gera um ID curto e grava na tabela |
| `GET /urls` | lista os links |
| `GET /{shortId}` | busca a URL longa e redireciona |

**Por que uma função e não três.** O critério para separar não é a URL, é o **gatilho e o ciclo de vida**. As três reagem ao mesmo gatilho (HTTP, síncrono), escalam juntas e falham juntas. São uma função.

No artigo 5 você vai criar a segunda função, e aí o critério fica visível: ela é separada porque reage a *outro* gatilho, tem outro perfil de falha e pode ser repetida sem ninguém esperando do outro lado.

## Hands-on

### 1. Criar a função

Console → **Lambda** → **Create function**.

- **Author from scratch**
- **Function name:** `url-shortener-api`
- **Runtime:** Python 3.13
- **Create function**

> ⚠️ **No AWS Academy Learner Lab**, abra **Change default execution role** e escolha **Use an existing role → LabRole**. O Lab nega `iam:CreateRole`, então a criação padrão falha. Veja a nota ao final deste artigo.

> 📸 **Print:** a tela de criação com runtime e nome preenchidos.

### 2. Colar o código

Aba **Code** → abra `lambda_function.py` → apague tudo → cole o conteúdo de [`url-shortener/lambdas/api.py`](../url-shortener/lambdas/api.py) → **Deploy**.

O despacho fica no topo do arquivo:

```python
ROTAS = {
    "POST /shorten":  _criar,
    "GET /urls":      _listar,
    "GET /{shortId}": _redirecionar,
}

def lambda_handler(event, context):
    tratar = ROTAS.get(event.get("routeKey"))
    ...
```

É um espelho literal das rotas que você vai criar no artigo 4. **Método HTTP sozinho não serviria:** `/urls` e `/{shortId}` são os dois GET. O que separa sem ambiguidade é o `routeKey`, que o API Gateway entrega já resolvido.

### 3. Variáveis de ambiente

**Configuration → Environment variables → Edit → Add**:

| Chave | Valor |
|---|---|
| `TABELA_NOME` | `url-shortener-urls` |
| `FILA_URL` | deixe em branco por enquanto, ela entra no artigo 5 |

Nome de tabela não vai hardcoded no código: muda por ambiente, e código que muda por ambiente não é código, é configuração.

### 4. Dar permissão de DynamoDB

**Configuration → Permissions** → clique no nome da role → abre o IAM em outra aba → **Add permissions → Attach policies** → procure `AmazonDynamoDBFullAccess` → **Add permissions**.

> 📸 **Print:** a role do IAM com a policy recém-anexada na lista.

Vale parar um segundo aqui. A `FullAccess` dá mais de cinquenta ações em **todas** as tabelas da conta a uma função que precisa de três ações numa tabela só. Em produção seria:

```json
{
  "Effect": "Allow",
  "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Scan"],
  "Resource": "arn:aws:dynamodb:us-east-1:SEU-ID:table/url-shortener-urls"
}
```

Guarde esse incômodo. Ele tem solução, e não é escrever JSON à mão.

### 5. Testar

Aba **Test** → **Create new event** → nome `CriarLink` → cole:

```json
{
  "routeKey": "POST /shorten",
  "body": "{\"url\": \"https://aws.amazon.com\"}",
  "requestContext": {
    "domainName": "exemplo.execute-api.us-east-1.amazonaws.com",
    "stage": "$default"
  }
}
```

**Test.** Você deve ver `statusCode: 201` e um `shortId`. Confira na tabela: o item está lá.

> 📸 **Print:** o resultado do teste, com o corpo da resposta expandido.

### 6. Ver os logs

Aba **Monitor → View CloudWatch logs**. Cada execução gerou um registro, e você não configurou nada para isso.

## O que deu errado (e por quê)

**`Runtime.HandlerNotFound: Handler 'lambda_handler' missing`.** O console cria a função esperando `lambda_function.lambda_handler`. Se o seu código define `def handler(...)`, não bate. Duas saídas: renomear a função no código (melhor, porque não acrescenta passo) ou mudar em **Runtime settings → Handler**.

**`AccessDenied` no DynamoDB mesmo depois de anexar a policy.** O IAM demora alguns segundos para propagar, às vezes quase um minuto. E a mensagem não ajuda: ela diz *"no identity-based policy allows"*, que soa como "você anexou a policy errada". Na dúvida, vale **esperar um minuto antes de concluir que errou**. É o tipo de coisa que faz a gente desfazer o que já estava certo.

**`Object of type Decimal is not JSON serializable`.** É o tipo numérico do DynamoDB chegando no `json.dumps`. Por isso o código converte com `int()` antes de responder. Sem isso, sua rota de listagem devolve 500.

**Timeout de 3 segundos.** É o padrão, e é pouco quando há chamada externa. O sintoma é `Task timed out after 3.00 seconds` nos logs.

## Como isso sustenta serverless

Uma função que não é chamada custa zero. Não há processo ocioso, nem instância reservada "por garantia". O custo nasce no evento e morre com ele.

E o escalonamento não é seu problema: se chegarem mil requisições ao mesmo tempo, a AWS sobe mil execuções. Você não configurou nada, e não existe um número máximo que você precise estimar com antecedência.

O preço disso é alguma disciplina: **sem estado e sem permissão implícita**. As duas coisas que mais incomodam no começo acabam sendo as que permitem o resto.

## Nota: IAM no AWS Academy Learner Lab

No Learner Lab, `iam:CreateRole` e `iam:AttachRolePolicy` são **negados**, inclusive na própria `LabRole`. Ou seja, o passo 4 não é possível ali.

O caminho é escolher **Use an existing role → LabRole** na criação, e a função já funciona, porque a `LabRole` é bastante permissiva.

Isso acaba mudando a lição, e para melhor: em vez de sentir o trabalho de anexar permissão, você vê o outro extremo. Abra a `LabRole` no IAM e repare em quantas policies ela tem. Uma role compartilhada que pode quase tudo é cômoda e é exatamente o que você não quer em produção, onde cada função teria a sua, com o mínimo necessário.

## O que ainda não dá para fazer

A função existe, mas só você consegue executá-la, pelo botão Test. O navegador não tem como chegar até ela: não há endereço, não há HTTP, não há porta de entrada.

**Próximo:** [4. A porta de entrada](04-api-gateway.md)
