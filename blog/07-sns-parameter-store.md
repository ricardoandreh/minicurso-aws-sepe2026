# 7. Avisando o mundo

> Série: construindo um encurtador de URL serverless na AWS — [índice](README.md)

O pipe entrega no tópico, mas ninguém está ouvindo. Vamos fechar a cadeia.

## O que é o SNS

Um megafone. Alguém publica uma mensagem no **tópico** e todos os **assinantes**
recebem, cada um na sua cópia, independentes entre si.

## Como funciona

**Um publica, N recebem.** O publicador não sabe quem são os assinantes nem
quantos existem. Adicionar um não exige tocar em quem publica.

**A entrega é assíncrona.** Para uma Lambda, o SNS invoca e não espera resposta.
Se a função falhar, o SNS **tenta de novo** sozinho, com intervalo crescente.

**Isso é fan-out.** A diferença para a fila: na fila, uma mensagem é consumida
por **um**; no tópico, a mesma mensagem vai para **todos**.

## O que é o Parameter Store

Um cofre de configuração do AWS Systems Manager. Guarda valores por nome, e o
tipo `SecureString` cifra com KMS.

No tier padrão é **gratuito** — diferente do Secrets Manager, que cobra por
segredo por mês.

## Onde entram no encurtador

O SNS fica entre o pipe e o Discord. E o Parameter Store guarda a URL do webhook.

**Por que não uma variável de ambiente para o webhook?** Porque variável de
ambiente de Lambda aparece **em texto puro** para qualquer um que abra a função
no console. É o mesmo erro de embutir uma chave no JavaScript do frontend, só que
no backend.

**E por que o SNS, se há um assinante só?** Honestamente: com um assinante, é
investimento, não necessidade. A função de marco já existe e poderia postar
direto. O ganho aparece no dia em que você quiser avisar também no Slack ou
alimentar um ranking: adiciona um assinante e **não toca** em nada que já
funciona. Fingir que é indispensável seria desonesto; o argumento verdadeiro é o
custo de mudança no futuro.

## Hands-on

### 1. Guardar o webhook

Crie um webhook num canal do Discord (*Configurações do canal → Integrações →
Webhooks → Novo webhook → Copiar URL*).

Console → **Systems Manager** → **Parameter Store** → **Create parameter**:

| Campo | Valor |
|---|---|
| Name | `/labs/discord-webhook` |
| Type | **SecureString** |
| KMS key source | My current account (deixe `alias/aws/ssm`) |
| Value | a URL do webhook |

**Create parameter.**

> 📸 **Print:** o parâmetro criado na lista, mostrando o tipo SecureString —
> sem revelar o valor.

### 2. Criar a função de aviso

**Lambda → Create function**:

- **Name:** `url-shortener-alert`
- **Runtime:** Python 3.13
- No Learner Lab: **Use an existing role → LabRole**

Cole [`url-shortener/lambdas/discord.py`](../url-shortener/lambdas/discord.py) →
**Deploy**.

**Configuration → Environment variables:** `WEBHOOK_PARAM` = `/labs/discord-webhook`
(o nome ou o ARN completo; `get_parameter` aceita os dois).

**Configuration → General configuration → Timeout: 10 s.** O padrão de 3 s é
curto: há uma consulta ao Parameter Store **e** um POST externo.

No Learner Lab não é preciso mexer em permissão. Fora dele, a role precisa de
`ssm:GetParameter` e `kms:Decrypt`.

### 3. Assinar o tópico

Na `url-shortener-alert` → **Configuration → Triggers → Add trigger** → **SNS** →
tópico `congrats-urls` → **Add**.

> 📸 **Print:** o diagrama da função com o SNS à esquerda como gatilho.

### 4. Testar

No DynamoDB, ponha `clicks` de um link em `9`. Clique uma vez no link curto.

> 📸 **Print:** a mensagem de parabéns chegando no canal do Discord.

## Dois detalhes do código que valem explicação

**O cache do segredo.**

```python
_webhook = None

def _webhook_url():
    global _webhook
    if _webhook is None:
        _webhook = ssm.get_parameter(Name=PARAMETRO, WithDecryption=True)["Parameter"]["Value"]
    return _webhook
```

O módulo só é carregado no cold start, então a consulta acontece uma vez por
ambiente de execução, não uma por mensagem. Buscar o mesmo parâmetro a cada
invocação é a forma mais comum de esbarrar no limite de requisições do Parameter
Store sem entender por quê.

**A função não decide nada.** Quem decidiu foi o filtro do pipe. Ela recebe,
formata e posta. Uma responsabilidade só — e por isso não precisa de nenhum
campo de controle na tabela.

## O que deu errado (e por quê)

**`Runtime.HandlerNotFound: Handler 'lambda_handler' missing`.** O mesmo do
artigo 3: o console espera `lambda_function.lambda_handler`. Renomeie a função
no código.

**A Lambda é invocada três vezes com o mesmo RequestId.** Não é bug, é o SNS
reentregando porque a função falhou. Invocação assíncrona tem retry automático —
e esse é o contraste com o API Gateway, que teria devolvido 500 na cara do
usuário sem tentar de novo.

**`403 Forbidden` do Discord, sem detalhe.** O Cloudflare do Discord bloqueia o
`User-Agent` padrão do `urllib` (erro 1010). Por isso o código manda um próprio:

```python
headers={"Content-Type": "application/json", "User-Agent": "url-shortener-bot/1.0"}
```

**Timeout de 3 s.** Consulta ao SSM mais POST externo passam disso no cold
start.

## Como isso sustenta event-driven

Olhe a cadeia inteira, de ponta a ponta:

```
clique no link
  → Lambda responde 302 e publica na fila        (assíncrono no tempo)
  → fila entrega ao contador                     (desacoplado do produtor)
  → contador escreve no banco
  → Stream registra a mudança                    (o dado vira evento)
  → Pipe filtra a transição 9 → 10               (decisão sem código)
  → SNS distribui                                (um para N)
  → Lambda posta no Discord
```

Sete passos, e **nenhum deles chama o seguinte**. Cada um reage a um fato e
produz outro. Você pode derrubar qualquer peça do meio que as anteriores
continuam funcionando — as mensagens esperam.

E a extensibilidade é concreta, não teórica. Quer avisar no Slack? Assina o
tópico. Quer um painel de marcos? Assina o tópico. Quer contar cliques de outro
jeito? Mais um consumidor. Em nenhum caso você abre o código do que já existe.

Isso é o que serverless e event-driven entregam juntos: **peças pequenas que não
se conhecem, que escalam sozinhas e que você só paga quando acontecem.**

## Limpeza

Para não deixar nada cobrando, remova na ordem inversa da construção:

```
1. EventBridge → Pipes → congrats-pipe-urls → Delete
2. Lambda → url-shortener-alert, url-shortener-counter, url-shortener-api → Delete
3. SNS → congrats-urls → Delete
4. SQS → url-shortener-queue → Delete
5. API Gateway → url-shortener-api-gtw → Delete
6. DynamoDB → url-shortener-urls → Delete
7. Systems Manager → Parameter Store → /labs/discord-webhook → Delete
8. S3 → esvazie o bucket e depois apague
```

O pipe primeiro, para ele não reagir às deleções seguintes. O bucket por último,
porque o S3 exige que esteja vazio.

## O que você construiu

Nove serviços, uma aplicação funcionando, zero servidores:

| Serviço | Papel |
|---|---|
| S3 | hospedagem do site |
| DynamoDB | armazenamento |
| Lambda | execução do código |
| API Gateway | porta HTTP |
| IAM | permissões |
| CloudWatch | logs |
| SQS | fila, desacoplamento no tempo |
| DynamoDB Streams | o dado virando evento |
| EventBridge Pipes | conexão filtrada, sem código |
| SNS | fan-out |
| Parameter Store | segredo fora do código |

E um incômodo que ficou pelo caminho: **todo esse trabalho foi feito a cliques**.
Nada está versionado, nada é reproduzível com segurança, e refazer numa segunda
conta significa repetir tudo torcendo para não esquecer um passo.

É esse problema que a infraestrutura como código resolve — mas isso é outra
série.
