# 5. Tirando trabalho do caminho crítico

> Parte da série *construindo um encurtador de URL serverless na AWS*.
> [Voltar ao índice](README.md)

O encurtador funciona. Agora vamos melhorá-lo e, de quebra, encontrar o primeiro
pedaço genuinamente event-driven da aplicação.

## O problema

Hoje o redirect faz tudo de uma vez:

```
GET /{id} → busca a URL → incrementa o contador → responde 302
                          └── o usuário está esperando por isto
```

Contar clique não interessa a quem clicou. Ninguém espera para saber que virou
o décimo visitante. Mas, do jeito que está, a pessoa espera mesmo assim.

A ideia é separar o que é urgente do que não é:

```
GET /{id} → busca a URL → responde 302        (rápido)
                    └──→ joga na fila          (e esquece)
                            └──→ outra função conta, no ritmo dela
```

## O que é o SQS

Uma fila de mensagens gerenciada. Alguém publica, alguém consome depois. Os dois
lados não precisam estar disponíveis ao mesmo tempo.

## Como funciona

**A mensagem espera.** Se o consumidor estiver fora do ar, ela fica na fila até
alguém ler, por até 14 dias.

**A mensagem não some ao ser lida.** Ela fica *invisível* por um tempo (o
*visibility timeout*). Se o consumidor terminar, ele a apaga. Se cair no meio,
ela reaparece e outro tenta. É isso que garante que nada se perde.

**A entrega é pelo menos uma vez.** Em caso raro, a mesma mensagem pode ser
processada duas vezes. Seu consumidor precisa aguentar isso.

**O consumidor recebe um lote.** O evento sempre traz uma lista `Records`, mesmo
com uma mensagem só.

Esse conjunto tem nome: **Queue-Based Load Leveling**. O produtor não espera o
consumidor, e um pico no produtor vira fila, não erro.

## Onde entra no encurtador

O redirect publica `{"shortId": "aK3x9p"}` e responde imediatamente. Uma segunda
função lê da fila e incrementa o contador.

**Agora o critério de separação fica visível.** No artigo 3 as três rotas HTTP
ficaram numa função só porque compartilhavam gatilho e ciclo de vida. O contador
é outra função porque:

- reage a outro gatilho (fila, não HTTP)
- é assíncrono, pode demorar que ninguém está esperando
- pode ser repetido sem prejuízo
- se falhar, a mensagem volta para a fila em vez de virar erro na cara do usuário

Em resumo: separe por **gatilho e ciclo de vida**, não por URL.

## Hands-on

### 1. Criar a fila

Console → **SQS** → **Create queue**.

- **Type:** Standard
- **Name:** `url-shortener-queue`
- Resto no padrão → **Create queue**

Copie a **URL** da fila.

> 📸 **Print:** a fila criada, com a URL visível.

### 2. Apontar a função HTTP para a fila

Na `url-shortener-api` → **Configuration → Environment variables → Edit**:

| Chave | Valor |
|---|---|
| `FILA_URL` | a URL que você copiou |

E dê à role permissão de envio: **Permissions** → role → **Attach policies** →
`AmazonSQSFullAccess`.

> ⚠️ **No Learner Lab**, pule este segundo passo: a `LabRole` já cobre.

O código do redirect publica assim:

```python
try:
    sqs.send_message(QueueUrl=FILA_URL, MessageBody=json.dumps({"shortId": short_id}))
except Exception as erro:
    print(f"falha ao enfileirar clique de {short_id}: {erro}")

return {"statusCode": 302, "headers": {"Location": item["longUrl"]}}
```

O `try/except` é deliberado: **perder uma contagem é aceitável, perder o
redirect não é**. Se a fila estiver indisponível, o usuário ainda chega onde
queria.

### 3. Criar a função do contador

**Lambda → Create function**:

- **Name:** `url-shortener-counter`
- **Runtime:** Python 3.13
- No Learner Lab: **Use an existing role → LabRole**

Cole o conteúdo de
[`url-shortener/lambdas/contador.py`](../url-shortener/lambdas/contador.py) →
**Deploy**.

Variável de ambiente: `TABELA_NOME` = `url-shortener-urls`.

O núcleo é uma linha:

```python
tabela.update_item(
    Key={"shortId": short_id},
    UpdateExpression="ADD clicks :um",
    ConditionExpression="attribute_exists(shortId)",
    ExpressionAttributeValues={":um": 1},
)
```

`ADD` é o **contador atômico** do DynamoDB. Duas execuções simultâneas não
perdem contagem, e funciona mesmo se o atributo ainda não existir. Ler, somar em
Python e gravar de volta teria condição de corrida, e dois cliques simultâneos
virariam um só.

A `ConditionExpression` está aí por um motivo que vale testar na mão daqui a
pouco: sem ela, o `ADD` numa chave que não existe **cria** o item. O artigo 11
mostra o estrago, e o `except` que acompanha essa condição está no código
completo em [`../url-shortener/lambdas/contador.py`](../url-shortener/lambdas/contador.py).

### 4. Ligar a fila na função

Na `url-shortener-counter` → **Configuration → Triggers → Add trigger** →
**SQS** → `url-shortener-queue` → **Add**.

> 📸 **Print:** o diagrama da função mostrando o SQS como gatilho à esquerda.

### 5. Testar

Clique num link curto algumas vezes e acompanhe:

1. **SQS → Monitoring:** as mensagens entrando e saindo
2. **CloudWatch Logs do contador:** `clique contado para ...`
3. **DynamoDB:** o `clicks` subindo
4. **O site:** clique em **Atualizar** e veja o número

> 📸 **Print:** o gráfico de mensagens do SQS com o pico de envio e consumo.

Repare numa coisa: **ninguém invocou o contador**. Ele simplesmente reagiu.

### 6. As duas colunas da fila

Console → **SQS** → a fila. No topo há dois números, e entender a diferença
entre eles vale mais do que parece:

| Rótulo no console | Atributo na API | O que significa |
|---|---|---|
| **Messages available** | `ApproximateNumberOfMessages` | esperando alguém pegar |
| **Messages in flight** | `ApproximateNumberOfMessagesNotVisible` | alguém pegou e ainda não apagou |

Aquilo da seção "Como funciona", que a mensagem não some ao ser lida, é isto
aqui em números. Ela não sai da fila quando alguém a recebe: **troca de coluna**.
Fica *in flight* enquanto durar o visibility timeout. Se o consumidor apagar,
some de vez. Se o consumidor falhar ou demorar demais, o relógio expira e ela
volta para *available*.

Dá para ver os dois números trocando de lugar:

1. Na `url-shortener-counter` → **Configuration → Triggers**, **desabilite** o
   gatilho do SQS
2. Clique num link curto três vezes
3. Volte na fila: **Messages available: 3**, **in flight: 0**. O contador na
   tela do site não se move, e o redirect continua instantâneo
4. **Send and receive messages → Poll for messages**: as três estão lá, e dá
   para abrir e ler o corpo de cada uma
5. Reabilite o gatilho. Em segundos *available* volta a 0 e o contador pula de
   três de uma vez

> 📸 **Print:** a fila com 3 em *available* e 0 em *in flight*, ao lado do
> contador parado no site.

Na tela do Poll repare na coluna **Receive count**. É quantas vezes aquela
mensagem já foi entregue. Numa fila saudável é 1.

### 7. Por que uma mensagem com defeito não aparece no Poll

Esse é o caso que confunde, e é melhor encontrá-lo agora do que na primeira vez
que algo quebrar de verdade.

Com o gatilho **ligado**, publique na fila, pelo próprio console, uma mensagem
que o contador não consiga processar: escreva `teste01` cru, sem aspas e sem
JSON.

O contador vai falhar, porque `json.loads` não lê isso. Agora tente dar Poll
para ver a mensagem. Você não vai conseguir, e a fila vai mostrar
**available: 0, in flight: 1**.

O motivo é uma corrida que você sempre perde. A Lambda recebe a mensagem, falha
em milissegundos, e a mensagem fica invisível pelos 30 segundos do visibility
timeout. Quando ela reaparece, o poller da Lambda está esperando em long
polling e a pega de novo, antes de qualquer clique seu. Ela passa a vida
inteira *in flight*.

Para conseguir olhar, tire a Lambda da disputa: **desabilite o gatilho, espere
o visibility timeout expirar** (30 segundos) e só então dê Poll. A mensagem
aparece, e o **Receive count** vai mostrar um número alto, uma entrega para cada
tentativa que falhou.

> 📸 **Print:** a mensagem finalmente visível no Poll, com o Receive count alto.

Deixe essa mensagem aí por enquanto, ou apague, tanto faz. O que ela causa, e
como o código se defende, é assunto do artigo 11.

## O que deu errado (e por quê)

**O contador não dispara.** Confira se o gatilho é o SQS. É fácil, montando
vários serviços, ligar uma função no gatilho errado. E o sintoma é silêncio
total, não erro, o que torna a procura mais difícil.

**`Records` sempre com uma mensagem só.** O `for` no código parece inútil. Não
é: o Lambda agrupa quando a fila acumula. Mas isso depende de duas coisas,
**ambas necessárias**: `BatchSize` maior que 1 **e** uma janela de agrupamento
(`MaximumBatchingWindowInSeconds`). Sem a janela, o Lambda entrega o que achar
no instante da leitura, que é quase sempre uma.

E mesmo com as duas, só agrupa sob acúmulo de verdade. Testando com 20 cliques
disparados em paralelo, os lotes foram de 1 e 2. Jogando 30 mensagens de uma vez
direto na fila, apareceu um lote de 6. **Lote é sintoma de fila acumulando.** Em
volume baixo você vai ver sempre uma mensagem, e o `for` continua sendo o certo a
escrever desde o começo.

**Erro 503 quando você testa com muitos cliques de uma vez.** Esse merece um parágrafo
próprio, porque parece que a aplicação quebrou e não é bem isso.

Toda conta tem um limite de execuções simultâneas do Lambda, e contas novas
começam com **10**, não com os 1000 do padrão antigo. Disparando 40 cliques em
paralelo, 25 voltaram 503: as funções `api` e `counter` disputam as mesmas 10
vagas, e o excedente é recusado.

Confira o seu em **Service Quotas → AWS Lambda → Concurrent executions** antes
de demonstrar carga para alguém.

E repare no detalhe bonito que o throttling revela: os cliques recusados **não
se perderam**. As mensagens continuaram na fila, voltaram e foram processadas
quando houve vaga. Num desenho síncrono, cada 503 seria um clique perdido para
sempre. É a fila fazendo exatamente o trabalho que justifica a existência dela.

**Mensagem presa, voltando sem parar.** Se a função falha sempre com a mesma
mensagem, ela reaparece indefinidamente. É para isso que existe a **Dead Letter
Queue**: depois de N tentativas, a mensagem vai para uma fila separada e para de
atrapalhar. Nossa fila não tem DLQ, mas em produção teria.

## Como isso sustenta event-driven

Aqui aparece a primeira peça realmente orientada a eventos da aplicação.

Repare na diferença em relação ao artigo 4. API Gateway → Lambda é **síncrono**:
alguém chama e espera a resposta. É desacoplado no *código*, mas acoplado no
*tempo*.

A fila desacopla no tempo. O redirect não sabe quem vai contar, nem quando, nem
se vai dar certo na primeira tentativa. Ele publica um fato, *"este link foi
clicado"*, e segue a vida. Quem se interessa, reage.

E isso tem consequência prática: se o contador ficar fora do ar por dez minutos,
nenhum usuário percebe. As mensagens esperam, e quando ele voltar, processa
tudo. Num desenho síncrono, dez minutos de contador fora seriam dez minutos de
redirect quebrado.

## O que ainda não dá para fazer

O contador escreve no banco. E se a gente quisesse reagir a *isso*, comemorando
quando um link bate 10 cliques?

A tentação é acrescentar o `if` dentro do contador. Mas aí ele deixa de ter uma
responsabilidade só, e para avisar em mais um canal amanhã seria preciso mexer
nele de novo.

Dá para fazer melhor: reagir à **mudança no banco** sem tocar em quem escreveu.

**Próximo:** [6. Reagindo a mudanças no banco](06-streams-pipes.md)
