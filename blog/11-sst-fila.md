# 11. A fila, e o que o `subscribe` esconde

> Parte da série *construindo um encurtador de URL serverless na AWS*.
> [Voltar ao índice](README.md)

No artigo 5 você tirou a contagem de cliques do caminho do usuário. Deu para
sentir quantas peças isso exigiu: criar a fila, criar a segunda função, criar o
trigger ligando as duas, voltar no IAM para dar permissão de ler da fila, voltar
no IAM de novo para dar permissão de escrever na tabela, e acrescentar a variável
de ambiente com a URL da fila na primeira função.

Seis passos. Aqui são duas declarações.

## O componente

```typescript
const fila = new sst.aws.Queue("Cliques", { visibilityTimeout: "60 seconds" });

fila.subscribe({
  handler: `${fnDir}/contador.lambda_handler`,
  runtime,
  role,
  memory: "128 MB",
  timeout: "15 seconds",
  link: [tabela],
});
```

E na função das rotas, o `link` ganha um item:

```typescript
link: [tabela, fila],
```

## O que o `subscribe` faz

Três recursos, de uma vez:

**A função consumidora.** Mesma coisa que um `sst.aws.Function`, com os mesmos
campos.

**O event source mapping.** É o recurso que fica perguntando à fila se tem
mensagem e invocando a função quando tem. No console ele aparece com o nome
*trigger*, e é a peça que mais confunde quem está começando, porque ela não é
nem da fila nem da função: é um terceiro recurso que liga as duas.

**As permissões, dos dois lados.** A função consumidora ganha
`ReceiveMessage`, `DeleteMessage` e `GetQueueAttributes` naquela fila. E a
função que publica, por causa do `link: [tabela, fila]`, ganha `SendMessage`.

Nenhum ARN foi escrito, e nenhuma dessas permissões foi decidida por você.

## O `visibilityTimeout`, que é a única coisa que você precisa pensar

Essa é a configuração que o SST deixa na sua mão de propósito, porque ela depende
de uma coisa que só você sabe: quanto tempo o seu consumidor demora.

A regra é simples e dói quando esquecida: **`visibilityTimeout` tem que ser maior
que o `timeout` da função que consome**. Aqui são 60 segundos para uma função de
15, com folga de sobra.

Se for menor, acontece isto: a mensagem fica invisível por 10 segundos, a função
demora 15, e no segundo 10 a mensagem reaparece na fila e é entregue a uma
segunda invocação. A primeira ainda está rodando. As duas processam o mesmo
clique, e o contador sobe dois.

E o sintoma não é um erro. É um número errado, de vez em quando, sob carga. Dos
piores de diagnosticar.

## A outra ponta: `Resource.Cliques.url`

No `api.py`:

```python
sqs = boto3.client("sqs")
FILA_URL = Resource.Cliques.url
```

`Cliques` é o nome lógico da fila no config. A URL dela chega resolvida. No
artigo 5 isso era uma variável de ambiente que você copiou e colou da tela do
SQS, e se colasse o ARN em vez da URL, o `send_message` falhava com uma mensagem
pouco amigável.

E repare no `try` em volta do `send_message`:

```python
try:
    sqs.send_message(QueueUrl=FILA_URL, MessageBody=json.dumps({"shortId": short_id}))
except Exception as erro:
    print(f"falha ao enfileirar clique de {short_id}: {erro}")
```

Isso é uma decisão de projeto, não descuido: se o SQS estiver com problema, o
usuário ainda é redirecionado. Perder uma contagem é aceitável; perder o redirect
não é. O log fica para alguém olhar depois.

## Hands-on

### 1. Trocar de passo e ler o diff

```bash
git checkout passo-4
git diff passo-3 passo-4
```

No `sst.config.ts` entraram a fila e o `subscribe`, e o `link` do encurtador
ganhou a fila. No `api.py`, o diff é o refactor que interessa:

```diff
-    tabela.update_item(
-        Key={"shortId": short_id},
-        UpdateExpression="ADD clicks :um",
-        ExpressionAttributeValues={":um": 1},
-    )
+    try:
+        sqs.send_message(QueueUrl=FILA_URL, MessageBody=json.dumps({"shortId": short_id}))
+    except Exception as erro:
+        print(f"falha ao enfileirar clique de {short_id}: {erro}")
```

A escrita saiu do redirect e virou mensagem. Quem escreve agora é o
`contador.py`, que é um arquivo novo de trinta linhas.

> 📸 **Print:** esse diff do `api.py`.

### 2. Deployar

```bash
BUCKET_SITE=url-shortener-site-SEUNUMERO npx sst deploy --stage lab
```

### 3. Clicar e cronometrar

Abra o site, clique num link curto, e volte. O número sobe, mas não na hora.

No Learner Lab a cadeia inteira, do clique ao número novo na tela, leva de 900
milissegundos a pouco mais de um segundo. É por isso que o `index.html` recarrega
a lista um segundo depois do clique, e de novo em 2,5 segundos como repescagem:

```javascript
function agendarAtualizacao(){
  clearTimeout(timerClique);
  timerClique=setTimeout(()=>{carregar();timerClique=setTimeout(()=>carregar(),1500)},1000);
}
```

Esse atraso é a coisa mais importante do artigo, e é um atraso que você escolheu.
O usuário recebeu o 302 em poucos milissegundos; o número na tela chegou depois.
Consistência eventual, bem na frente dos seus olhos.

> 📸 **Print:** a lista com o contador antes e depois, nas duas recargas.

### 4. Ver a fila trabalhando

Console → **SQS** → a fila → **Monitoring**. `NumberOfMessagesSent` e
`NumberOfMessagesDeleted` sobem juntos. Se o segundo ficar atrás do primeiro,
tem mensagem encalhada.

Em **Lambda** → função do contador → **Monitor** → **Logs**, cada invocação tem
a linha `clique contado para ...`.

> 📸 **Print:** o gráfico do SQS com as duas métricas.

### 5. Provar que a fila protege

Aqui vale desligar o consumidor de propósito. Console → Lambda → função do
contador → **Configuration** → **Triggers** → desabilite o trigger do SQS.

Clique em links algumas vezes. Os redirects continuam instantâneos, e o contador
não se move. Vá no SQS: as mensagens estão lá, em
*Messages available*.

Reabilite o trigger. Em segundos o contador pula para o valor certo, de uma vez.

> 📸 **Print:** o SQS com mensagens acumuladas e o contador parado.

Isso é *Queue-Based Load Leveling*, e é a melhor demonstração dele que a
aplicação oferece: o consumidor esteve fora do ar e o usuário não percebeu.

## O que deu errado (e por quê)

**`KeyError: 'longUrl'` na listagem, depois de apagar um link.** Esse aconteceu
de verdade na preparação desta série, e é bonito.

Apaguei um item na tabela enquanto ainda havia cliques dele na fila. O contador
leu a mensagem e fez `update_item` com `ADD clicks`. E o `update_item` do
DynamoDB, num item que não existe, **cria o item**. A tabela ficou com um
registro de `shortId` e `clicks`, sem `longUrl`, e a listagem estourou.

A correção está no `_listar`: `.get("longUrl", "")` em vez de `["longUrl"]`, e um
filtro descartando itens sem URL. A lição não é "use `.get()`". É que num banco
sem schema, qualquer escrita parcial é um item válido, e quem lê precisa estar
preparado.

**O contador conta dois.** Entrega *at-least-once*: o SQS garante que a mensagem
chega, não que chega uma vez só. `ADD` é atômico, então duas Lambdas concorrentes
não perdem contagem, mas se a **mesma** mensagem for entregue duas vezes, ela
conta duas. Causas comuns: `visibilityTimeout` curto, ou a função terminando com
erro depois de já ter escrito.

Deixei assim de propósito, porque é um gancho honesto: contador de cliques
suporta imprecisão. Se fosse saldo bancário, você precisaria de uma chave de
idempotência, um registro de "esta mensagem já foi processada", e uma escrita
condicional. Vale saber que esse trabalho existe, e que você está escolhendo não
fazê-lo.

**503 ao clicar em vários links ao mesmo tempo.** O limite de concorrência da
conta. Conta nova de AWS começa com **10** execuções simultâneas, não 1000, e o
Learner Lab também é baixo. Com três pessoas testando ao mesmo tempo dá para
bater nisso.

**A mensagem foi parar na Dead Letter Queue, e não tem DLQ.** Sem DLQ, uma
mensagem que falha fica sendo retentada até expirar, e você vê a mesma invocação
quebrando a cada minuto nos logs. Para uma aula está bem; em produção, DLQ não é
opcional.

## Como isso sustenta event-driven

Olhe o `contador.py` e repare no que ele não sabe: não sabe que existe um API
Gateway, não sabe que existe um site, não sabe quem publicou a mensagem. Ele sabe
ler `{"shortId": "..."}` de um `event["Records"]`.

Isso é desacoplamento no sentido forte. Amanhã o clique pode vir de um app
mobile, de um QR code, de um script. O contador não muda. E se amanhã você quiser
um segundo consumidor dos mesmos cliques, para alimentar um painel, ele não
precisa avisar ninguém: é só mais um assinante.

Essa última frase é o próximo artigo.

## O que ainda não dá para fazer

Você quer comemorar quando um link bater 10 cliques. O contador sabe o número,
então a tentação é colocar um `if` nele.

Não faça. O próximo artigo mostra por quê, e o que fazer em vez disso.

**Próximo:** [12. Reagindo ao dado, não ao código](12-sst-stream-pipe-sns.md)
