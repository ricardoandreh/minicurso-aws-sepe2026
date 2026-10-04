# 12. Reagindo ao dado, não ao código

> Parte da série *construindo um encurtador de URL serverless na AWS*. [Voltar ao índice](README.md)

Último passo. Entram quatro coisas: o stream da tabela, um EventBridge Pipe com filtro, um tópico SNS e a função que posta no Discord. É a parte mais interessante da aplicação, e também a única em que o SST não tem componente para tudo.

## Primeiro, o `if` que não vamos escrever

O contador já sabe o número. Seria uma linha:

```python
novo = tabela.update_item(..., ReturnValues="UPDATED_NEW")
if novo["Attributes"]["clicks"] == 10:
    postar_no_discord(short_id)
```

Funciona, e é a solução errada por quatro motivos que vale enumerar:

**O contador passa a conhecer o Discord.** Uma função cujo trabalho é somar um agora tem dependência de uma integração externa, de um segredo, e de rede.

**Toda mudança no festejo mexe no contador.** Quer comemorar em 100 também? Quer mandar por e-mail? Você edita, testa e deploya a função que está no caminho da contagem de todos os links.

**A entrega at-least-once vira notificação duplicada.** Se a mensagem for reprocessada quando `clicks` já é 10, o `if` dispara de novo. Para evitar, você precisa de um campo `jaComemorou` na tabela, e de uma escrita condicional para não ter corrida. Virou estado.

**Se o Discord estiver fora, a contagem falha.** A função vai dar erro depois de já ter escrito, a mensagem volta para a fila, e o contador conta de novo. Um serviço externo indisponível passou a corromper o seu dado.

A alternativa é não acoplar: deixar a mudança no dado ser o aviso.

## Como funciona

```
contador → update_item → tabela
                           └─▶ Stream ──▶ Pipe (filtro) ──▶ SNS ──▶ Lambda ──▶ Discord
```

Você viu isso no artigo 6, e o que muda aqui é só a forma de declarar. Os conceitos que importam continuam os mesmos:

**O stream carrega as duas imagens.** `OldImage` e `NewImage` chegam juntas, o que permite expressar uma *transição*, e não um estado. Por isso o `stream` é `new-and-old-images`, e não qualquer outro valor: o filtro compara o antes com o depois.

**O filtro roda no serviço, antes do destino.** Registro que não casa é descartado pelo Pipes, e o destino nem é acionado.

**O "já aconteceu?" deixa de ser estado.** A transição de 9 para 10 ocorre exatamente uma vez na vida de um item. Não precisa de campo, nem de escrita de volta, nem de risco de laço.

## O filtro

```json
{
  "eventName": ["MODIFY"],
  "dynamodb": {
    "OldImage": { "clicks": { "N": ["9"]  } },
    "NewImage": { "clicks": { "N": ["10"] } }
  }
}
```

Duas igualdades exatas sobre **strings**, e isso não é descuido. No registro do stream, número vem no formato nativo do DynamoDB, `{"N": "10"}`, com o valor como string. O comparador numérico do EventBridge (`{"numeric": [">=", 10]}`) espera um número JSON de verdade, então ele não serve aqui. Igualdade de string é o que funciona.

## O que o SST não tem, e o que fazer

O SST v4 tem `sst.aws.Bus`, que é o barramento do EventBridge. Não tem componente para Pipes.

E isso não é um problema, porque o Pulumi está logo abaixo:

```typescript
new aws.pipes.Pipe("Parabens10", {
  roleArn: role,
  source: tabela.nodes.table.streamArn,
  target: topico.arn,
  sourceParameters: {
    dynamodbStreamParameters: { startingPosition: "LATEST", batchSize: 1 },
    filterCriteria: { filters: [{ pattern: JSON.stringify({ /* o filtro acima */ }) }] },
  },
});
```

Duas coisas valem o destaque:

**Não há `import`.** O `aws` é global dentro do `run()`, e o provedor `@pulumi/aws` já vem embutido no SST. Você não instalou nada.

**`tabela.nodes.table.streamArn`.** O `nodes` é a saída de emergência dos componentes do SST: por ele você alcança os recursos Pulumi crus que o componente criou. `tabela` é um `sst.aws.Dynamo`; `tabela.nodes.table` é a tabela do Pulumi lá dentro, com todos os atributos dela, incluindo o ARN do stream.

Esse par, componente para o comum e `nodes` para o resto, é o que faz uma camada de abstração ser útil em vez de ser uma gaiola. Você não fica refém do que ela cobre.

## O tópico e o segredo

```typescript
const webhook = new sst.Secret("DiscordWebhook");

const topico = new sst.aws.SnsTopic("Parabens");

topico.subscribe("Discord", {
  handler: `${fnDir}/discord.lambda_handler`,
  runtime, role,
  memory: "128 MB",
  timeout: "10 seconds",
  link: [webhook],
});
```

O `sst.Secret` é o lugar do Parameter Store aqui. Ele guarda o valor no SSM, por stage, cifrado, e você o define uma vez pela CLI:

```bash
npx sst secret set DiscordWebhook "https://discord.com/api/webhooks/..." --stage lab
```

A diferença prática em relação ao artigo 7 está no código. No console, o webhook vinha do Parameter Store, e para isso você precisava chamar o SSM a cada cold start, com cache manual para não estourar o limite de requisições. Aqui:

```python
from sst import Resource
Resource.DiscordWebhook.value
```

O valor já chega resolvido no runtime. Não há chamada de API para fazer, nem cache para gerenciar, nem permissão de `ssm:GetParameter` para dar.

### Sobre trocar de branch e os segredos

Essa dúvida sempre aparece: trocar de `passo-4` para `passo-5` apaga o segredo?

Não. O segredo não vive no repositório, vive no SSM da conta, indexado por nome da aplicação e stage. Enquanto você mantiver `--stage lab`, ele continua lá, independente de branch, de `git checkout` e de `sst remove` da branch anterior.

Você precisa definir de novo em dois casos: se trocar de stage, ou se rodar `npx sst remove`, que leva os segredos daquele stage junto.

Para conferir:

```bash
npx sst secret list --stage lab
```

## Hands-on

### 1. Definir o segredo, antes do deploy

```bash
npx sst secret set DiscordWebhook "SUA-URL-DE-WEBHOOK" --stage lab
```

Use o mesmo webhook do artigo 7, ou crie outro no Discord em **Editar canal** → **Integrações** → **Webhooks**.

Se você deployar sem definir, o deploy falha dizendo que o segredo não tem valor. Isso é proposital: melhor falhar no deploy que num `KeyError` às duas da manhã.

### 2. Trocar de passo e ler o diff

```bash
git checkout passo-5
git diff passo-4 passo-5
```

É o maior diff da série, e é o único em que entra código Pulumi direto. Leia os comentários do bloco do pipe; eles existem por causa de erros reais.

### 3. Deployar

```bash
BUCKET_SITE=url-shortener-site-SEUNUMERO npx sst deploy --stage lab
```

Repare que a tabela vai ser **modificada**, não recriada: ligar o stream é uma alteração no lugar. Os seus links continuam lá.

> 📸 **Print:** a saída do deploy com a tabela sendo atualizada e o pipe criado.

### 4. Chegar aos 10 cliques

Crie um link e clique nele dez vezes. Da nona para a décima, o Discord recebe:

```
🎉 O link `aK3x9p` bateu 10 cliques!
Destino: https://ifc.edu.br
```

> 📸 **Print:** a mensagem no Discord, e ao lado a lista do site mostrando 10.

### 5. Seguir o caminho inteiro nos logs

Vale a pena fazer esse percurso uma vez, porque é o que torna a arquitetura concreta:

1. **Lambda do encurtador** → o log do redirect
2. **SQS** → `NumberOfMessagesSent`
3. **Lambda do contador** → `clique contado para aK3x9p`
4. **EventBridge Pipes** → o pipe → **Monitoring**, e veja `Invocations` em 1 com dezenas de registros lidos. É o filtro trabalhando: ele leu todos os cliques e deixou passar um.
5. **SNS** → `NumberOfMessagesPublished` em 1
6. **Lambda do Discord** → `parabéns postado para aK3x9p`

> 📸 **Print:** o Monitoring do pipe, mostrando a diferença entre registros lidos e invocações do destino.

### 6. Provar que o filtro é quem decide

Clique mais dez vezes no mesmo link, chegando a 20. Nada acontece. A função do Discord não foi chamada, e não existe nenhum código em lugar nenhum dizendo "só na primeira vez".

Agora crie um link novo e leve ele a 10. Comemora de novo.

Esse é o ponto do artigo: a regra de negócio "comemorar quando cruzar 10" não está em nenhuma função. Está numa configuração declarativa de seis linhas, que você pode ler e auditar.

## O que deu errado (e por quê)

**O contador chegou a 10 e nada aconteceu.** Esse foi o erro que mais custou na preparação, e a causa é traiçoeira: o filtro tinha `eventSourceARN` com o ARN da tabela. Mas o registro que chega do stream traz o ARN **do stream**, que é o da tabela com `/stream/<timestamp>` no fim. A comparação falhava sempre, em silêncio, e o pipe parecia simplesmente não funcionar.

A moral: filtro que não casa não gera erro, gera nada. Quando um pipe parece morto, suspeite do filtro antes de qualquer outra coisa, e confira no Monitoring se ele está lendo registros.

**`startingPosition: "LATEST"` e o clique que não contou.** `LATEST` lê só o que chegar depois de o pipe existir. Se você já tinha um link em 9 cliques antes do deploy, o décimo clique pode cair numa janela em que o pipe ainda não estava pronto. Para testar, use um link novo.

**O Discord respondeu 1010.** Erro do Cloudflare na frente do Discord, bloqueando o `User-Agent` padrão do `urllib`. A função manda um `User-Agent` próprio por isso:

```python
headers={"Content-Type": "application/json", "User-Agent": "url-shortener-bot/1.0"}
```

**`KeyError: 'NewImage'` na função do Discord.** Sem *input transformer* no pipe, o que chega ao SNS é o registro cru do stream, com os atributos tipados (`{"S": "..."}`, `{"N": "..."}`). E o SNS entrega o corpo como **string**, então é `json.loads(registro["Sns"]["Message"])` antes de qualquer coisa. Dois envelopes, um dentro do outro.

**`LabRole` não pode ser assumida pelo Pipes.** No Learner Lab ela pode, e isso foi verificado. Em conta comum com role própria, a trust policy precisa incluir `pipes.amazonaws.com`. Se o pipe nasce em estado de falha, é por aqui.

## Como isso sustenta event-driven

Vale listar, agora que a aplicação está inteira, o que cada peça **não** sabe:

- o encurtador não sabe que existe um contador
- o contador não sabe que existe um pipe
- o pipe não sabe o que é um encurtador de URL
- a função do Discord não sabe quem decidiu que valia comemorar

Cada uma conhece só o seu gatilho e o seu trabalho. É isso que permite trocar qualquer uma sem abrir as outras, e é isso que a arquitetura orientada a eventos está comprando.

O preço está à vista também: o fluxo inteiro não existe em nenhum arquivo. Para entender como um clique chega no Discord, você precisa ler cinco recursos e uma configuração de filtro. Num monolito, seria uma função com cinco linhas e um `if`, e você leria de cima para baixo.

Esse é o trade-off real, e quem diz que não existe está vendendo algo.

## O que ainda não dá para fazer

Nada: a aplicação está completa, nas duas metades. Falta comparar.

**Próximo:** [13. O que mudou, e o que isso custou](13-fechamento.md)
