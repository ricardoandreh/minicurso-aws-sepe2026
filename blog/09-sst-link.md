# 9. Uma linha em vez de três passos

> Parte da série *construindo um encurtador de URL serverless na AWS*.
> [Voltar ao índice](README.md)

Volte ao artigo 3 por um instante. Para a função conseguir escrever na tabela,
você fez três coisas em três telas diferentes:

1. criou a variável de ambiente `TABELA_NOME` e colou o nome da tabela nela
2. abriu a role da função no IAM
3. anexou uma policy dando acesso ao DynamoDB

Três coisas que são, no fundo, a mesma informação dita três vezes: *esta função
usa aquela tabela*. Neste artigo essa frase é escrita uma vez.

## O que é o `link()`

Uma propriedade dos componentes do SST que conecta um recurso a outro. Quando
você escreve `link: [tabela]` numa função, acontecem duas coisas:

**A configuração é injetada.** O nome da tabela aparece no runtime da função, e
o código lê assim:

```python
from sst import Resource
tabela = boto3.resource("dynamodb").Table(Resource.Urls.name)
```

`Urls` é o nome lógico que você deu ao componente no `sst.config.ts`. Não há
variável de ambiente para configurar, nem nome para digitar errado.

**A permissão é escrita.** O SST gera na role da função uma policy com as ações
daquele serviço sobre aquele recurso, e nada além. Não é `AmazonDynamoDBFullAccess`,
não é `Resource: "*"`. É o ARN daquela tabela.

A segunda parte é a que vale mais, e é a mais fácil de não notar.

## Como funciona

Não tem mágica, e vale desmontar.

No deploy, o SST coloca na função uma variável de ambiente por recurso linkado,
com os valores em JSON. O pacote `sst-sdk` (que está no `functions/pyproject.toml`)
lê essas variáveis e expõe como atributo. `Resource.Urls.name` é uma leitura de
dicionário, resolvida no primeiro acesso, sem chamada de API e sem custo.

E a policy é derivada do componente, não do seu código. O `sst.aws.Dynamo` sabe
quais ações alguém que o usa vai precisar, e é isso que entra na role. Se amanhã
você linkar uma fila na mesma função, outra policy é somada.

Duas consequências que importam:

**Você não escreve ARN.** Nunca. Nem no código, nem na policy.

**A permissão acompanha o código.** Removeu o `link`, a policy sai junto no
próximo deploy. No console, a policy ficaria lá para sempre, e é assim que uma
conta vai acumulando acesso que ninguém usa e ninguém ousa remover.

## Onde entra no encurtador

A função das rotas HTTP, a mesma do artigo 3, agora com uma linha a mais no
config e uma linha diferente no Python.

## Hands-on

### 1. Trocar de passo e ler o diff

```bash
git checkout passo-2
git diff passo-1 passo-2 -- sst.config.ts
```

O que entrou:

```typescript
const encurtador = new sst.aws.Function("Encurtador", {
  handler: `${fnDir}/api.lambda_handler`,
  runtime,
  role,
  memory: "256 MB",
  timeout: "10 seconds",
  link: [tabela],
});
```

Reconheça cada campo: o handler, o runtime, a memória e o timeout são exatamente
os quatro campos que o console te pediu. O `link` é o que não tem equivalente
lá.

### 2. O diff que é a lição do minicurso

```bash
git diff passo-1 passo-2 -- functions/
```

O `api.py` é quase o mesmo arquivo do artigo 3. A diferença de verdade são
estas linhas:

```python
# antes, no console:
tabela = boto3.resource("dynamodb").Table(os.environ["TABELA_NOME"])

# agora:
from sst import Resource
tabela = boto3.resource("dynamodb").Table(Resource.Urls.name)
```

Uma linha. E ela carrega consigo as duas telas de IAM que você não vai mais
abrir.

> 📸 **Print:** o `git diff` lado a lado, mostrando as duas linhas.

### 3. Deployar

```bash
npx sst deploy --stage lab
```

Agora saem dois outputs, a tabela e a função. A tabela não foi recriada: ela já
estava do jeito declarado, e o SST só acrescentou o que faltava.

> 📸 **Print:** a saída do deploy, com a tabela intocada e a função criada.

### 4. Ver a role que você não escreveu

Console → **Lambda** → a função nova → **Configuration** → **Permissions**.

Aqui o Learner Lab atrapalha, e vale explicar por quê. No Lab o SST não pode
criar role nenhuma, porque `iam:CreateRole` é negado, então o `sst.config.ts`
passa a `LabRole` explicitamente para todas as funções. E a `LabRole` já pode
quase tudo. Ou seja: a policy mínima que o `link()` geraria não aparece, porque
no Lab ele não tem onde escrever.

Em conta AWS comum você omite o campo `role`, e aí sim: cada função ganha uma
role sua, com a policy derivada dos links dela. Se você tem uma conta pessoal,
vale rodar `npx sst deploy --stage pessoal` nela depois da aula e comparar as
duas roles. É o print que convence.

### 5. Chamar a função sem API

Não existe API Gateway ainda, e é isso que faz este passo interessante: a função
existe, está linkada, e dá para exercitá-la direto.

```bash
aws lambda invoke --profile labs \
  --function-name NOME-DA-FUNCAO \
  --cli-binary-format raw-in-base64-out \
  --payload '{"routeKey":"GET /urls"}' \
  /dev/stdout
```

O nome da função é o output do deploy. A resposta é um JSON com `statusCode` 200
e a lista de links, vazia, porque esta é uma tabela nova.

Crie um link:

```bash
aws lambda invoke --profile labs \
  --function-name NOME-DA-FUNCAO \
  --cli-binary-format raw-in-base64-out \
  --payload '{"routeKey":"POST /shorten","body":"{\"url\":\"https://ifc.edu.br\"}"}' \
  /dev/stdout
```

Volta um `201` com o `shortId`. Liste de novo e ele está lá.

Esse payload com `routeKey` é o que o API Gateway vai mandar a partir do próximo
artigo. Você está fazendo o papel dele na mão.

> 📸 **Print:** as duas invocações no terminal, criar e listar.

## O que deu errado (e por quê)

**`Runtime.HandlerNotFound`.** O console da Lambda sugere `lambda_function.lambda_handler`
e muita gente deixa assim. Aqui o caminho vem do `handler` no config, e precisa
bater com o arquivo e a função de verdade: `api.lambda_handler` significa
`api.py` com uma função chamada `lambda_handler` dentro. Vale conferir qual
nome você usou no artigo 3, porque se não for `lambda_handler`, a versão em
código não roda e você vai procurar no lugar errado.

**`ModuleNotFoundError: No module named 'sst'`.** O `sst-sdk` precisa estar nas
dependências de `functions/pyproject.toml`. O SST instala as dependências de lá
no pacote da função no momento do deploy. Se você acrescentou algo depois do
último deploy, precisa deployar de novo.

**`AccessDeniedException` no DynamoDB, em conta comum.** Quer dizer que o
`link` não está onde você pensa que está. Confira se é a função certa, e se o
deploy que acrescentou o link realmente passou.

**`KeyError: 'longUrl'` na listagem.** Essa é mais sutil e vai aparecer mais
tarde, então já fica o aviso: o `update_item` com `ADD` **cria** o item se ele
não existir. Se você apagar um link e ainda houver clique dele na fila, a tabela
ganha um item com `shortId` e `clicks` e nada mais. A listagem no `api.py` usa
`.get()` com valor padrão e filtra itens sem `longUrl` por causa disso. Num
banco sem schema, código defensivo na leitura não é paranoia.

## Como isso sustenta serverless

O princípio do menor privilégio é fácil de defender e difícil de praticar. A
razão é econômica: escrever a policy mínima para cada função custa tempo, e
`FullAccess` custa zero. Quem está com prazo escolhe o zero.

O que o `link()` faz é mudar esse preço. A policy mínima passa a ser o caminho
mais curto, não o mais longo. Você não ganha segurança por disciplina, ganha
porque o jeito preguiçoso virou o jeito certo.

E tem um efeito colateral bom: lendo o `sst.config.ts`, a lista de `link` de cada
função é o mapa de quem fala com quem na sua aplicação. Essa informação, no
console, está espalhada por doze telas.

## O que ainda não dá para fazer

A função funciona, mas só para quem tem a AWS CLI. Falta a porta de entrada.

**Próximo:** [10. A API, agora em três linhas](10-sst-api.md)
