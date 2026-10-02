# 6. Reagindo a mudanças no banco

> Parte da série *construindo um encurtador de URL serverless na AWS*.
> [Voltar ao índice](README.md)

Queremos comemorar quando um link bate 10 cliques, sem tocar em quem conta.

## O que é o DynamoDB Streams

Um registro ordenado de tudo que mudou numa tabela. Cada escrita vira um evento
com a imagem do item **antes** e **depois**, guardado por 24 horas.

É *Change Data Capture*: em vez de a aplicação avisar que algo mudou, a mudança
no dado **é** o aviso.

## O que é o EventBridge Pipes

Um conector gerenciado entre uma origem de eventos e um destino, com filtro
embutido. Ele lê de um lado, descarta o que não interessa e entrega no outro,
sem você escrever código de cola.

## Como funcionam juntos

```
contador → update_item → tabela
                           └─▶ Stream ──▶ Pipe (filtro) ──▶ destino
```

Três coisas importam:

**O Stream só tem Lambda como destino direto.** Não dá para assinar um tópico
SNS nele. O Pipes é justamente o que resolve isso: ele aceita o Stream como
origem e quase qualquer coisa como destino.

**O filtro roda antes do destino.** Registro que não casa é descartado pelo
serviço, então o destino nem é acionado e você não paga por ele.

**O registro carrega as duas imagens.** `OldImage` e `NewImage` chegam juntas, o
que permite expressar *transições*, não só estados.

## Onde entra no encurtador

Queremos o instante exato em que `clicks` cruza 10. E o filtro consegue
expressar isso sozinho:

```json
{
  "eventName": ["MODIFY"],
  "dynamodb": {
    "OldImage": { "clicks": { "N": ["9"]  } },
    "NewImage": { "clicks": { "N": ["10"] } }
  }
}
```

Duas igualdades exatas sobre strings. Dispara uma vez na vida do item.

Repare no que **não** precisou existir: nenhum campo "já comemorou", nenhuma
escrita de volta na tabela, nenhum risco de laço. O "já aconteceu?" deixou de ser
estado guardado e virou propriedade do próprio evento.

## Hands-on

### 1. Habilitar o Stream

**DynamoDB → Tables → `url-shortener-urls` → Exports and streams → DynamoDB
stream details → Turn on**.

**View type: New and old images.**

> 📸 **Print:** a tela de escolha do view type, com a opção marcada.

Vale escolher essa mesmo que pareça exagero. Trocar o view type depois exige desligar
e religar o stream, o que gera um **ARN novo**. Todo consumidor apontando para o
ARN antigo para de funcionar, em silêncio.

As outras opções: *Key attributes only* traria só o `shortId`, e o filtro acima
seria impossível; *New image* funciona para este caso mas te prende a ele.

### 2. Criar o tópico de destino

Vamos precisar de um destino para o Pipe. Console → **SNS** → **Topics** →
**Create topic** → **Standard** → nome `congrats-urls` → **Create topic**.

(O SNS é o assunto do artigo 7; por ora é só o endereço de entrega.)

### 3. Criar o Pipe

Console → **EventBridge** → **Pipes** → **Create pipe**. Nome:
`congrats-pipe-urls`.

São quatro etapas. **Source e Target são obrigatórios; Filtering e Enrichment
são opcionais.**

**Source:** `DynamoDB stream` → tabela `url-shortener-urls`. Em *Additional
settings*: **Batch size 1**, **Starting position: Latest**.

**Filtering:** cole o padrão da seção anterior.

> 📸 **Print:** a etapa de filtro com o padrão colado e o teste dando match.

O campo **Sample event** ao lado serve só para testar na tela, ele não vai para
o pipe. Os exemplos prontos da AWS não têm `clicks`, então sempre darão "no
match"; cole um evento seu com `OldImage.clicks = 9` e `NewImage.clicks = 10`.
E faça o teste negativo: troque para 10 → 11 e confirme que **não** casa. Filtro
que aceita demais é pior que filtro que não aceita nada.

**Enrichment:** pule.

**Target:** `Amazon SNS` → tópico `congrats-urls`.

**Permissions:** deixe o console criar a role. No Learner Lab, escolha a
`LabRole`, que confia em `pipes.amazonaws.com`.

**Create pipe.** Espere ficar **Running**.

### 4. Testar

No DynamoDB, edite um item e ponha `clicks` em `9`. Depois clique uma vez no
link curto. O contador leva para 10, o Stream gera o registro, o filtro casa.

Confira em **Pipes → congrats-pipe-urls → Monitoring**: deve aparecer uma
invocação.

> 📸 **Print:** o gráfico de invocações do pipe com o pico isolado.

Ainda não há ninguém assinando o tópico, isso fica para o próximo artigo. Por
ora, ver o pipe disparar já mostra que a cadeia está certa.

## O que deu errado (e por quê)

**O pipe nunca dispara, e não aparece erro nenhum.** Esse é o jeito mais comum
de errar aqui, e costuma ter três causas.

**Causa 1: `eventSourceARN` no filtro.** O console sugere incluir, mas o valor
que chega no registro é o ARN do **stream**, com sufixo:

```
no registro:   .../table/url-shortener-urls/stream/2026-10-01T23:28:18.225
se você puser: .../table/url-shortener-urls
```

Como string em filtro é igualdade exata, nunca casa. Tire `eventSourceARN`,
`awsRegion` e `eventSource`. Os três são redundantes, já que o pipe tem uma
origem só.

**Causa 2: comparador numérico.** Seria natural escrever
`{"clicks": {"N": [{"numeric": [">=", 10]}]}}`. Mas no registro do stream o
número vem como **string** (`{"N": "10"}`), e o operador `numeric` trabalha com
número JSON. Prefira igualdade exata, que é o que o nosso filtro faz.

**Causa 3: view type sem `OldImage`.** Se o stream foi habilitado como *New
image*, o filtro que compara as duas imagens não tem como casar.

**O filtro casa demais e comemora todo clique depois do décimo.** Aconteceu se
você filtrou por `clicks` apenas na imagem nova. É a transição que interessa,
não o valor.

## Uma garantia que torna o filtro confiável

O Stream mantém **ordem por item**. Os registros de um mesmo `shortId` saem na
sequência em que foram aplicados, mesmo que as escritas tenham vindo de
execuções concorrentes.

Isso importa aqui: o contador roda em paralelo, com várias invocações somando
cliques ao mesmo tempo. Ainda assim os registros daquele link aparecem como
7→8, 8→9, 9→10, nessa ordem, e a transição que nos interessa acontece uma vez
só. Sem essa garantia, um filtro que depende de ver `9` virar `10` seria uma
aposta.

## Onde esse desenho é frágil

Este filtro depende de `clicks` subir de um em um. Hoje sobe, porque o contador
faz um `update_item` por mensagem.

No dia em que alguém otimizar o contador para somar o lote inteiro de uma vez,
com um `ADD clicks :6`, o valor pula de 7 para 13, o par 9 → 10 **nunca existe**
e nada acontece. Sem erro, sem log.

A versão à prova de salto continua sendo só filtro, só fica feia:

```json
"OldImage": { "clicks": { "N": ["0","1","2","3","4","5","6","7","8","9"] } },
"NewImage": { "clicks": { "N": [{ "anything-but": ["0","1","2","3","4","5","6","7","8","9"] }] } }
```

"Estava abaixo de 10, agora não está." Sem comparador numérico, imune a pulo.

## Como isso sustenta event-driven

Este é o grau mais alto de desacoplamento da série.

No artigo 5, o redirect **decidiu** publicar na fila: há uma linha de código
dizendo "avise que houve um clique". Aqui não há linha nenhuma. O contador faz o
que sempre fez, escreve no banco, e não sabe que alguém está reagindo. Para
acrescentar um novo interessado, não se toca em quem produziu o dado.

Isso resolve um problema que tem nome: o **dual write**. Quando a aplicação
grava no banco *e depois* publica num broker, são duas operações sem
atomicidade. Se o processo morrer entre as duas, o dado existe e o evento não.
A solução clássica é o *transactional outbox*: gravar o evento numa tabela
`Outbox` na mesma transação e drenar depois, por polling ou CDC.

No DynamoDB o Stream **é** esse log. Não existe tabela de outbox porque não é
preciso: sobrou uma escrita só, e não há o que dessincronizar.

## O que ainda não dá para fazer

O pipe dispara e entrega no tópico, mas ninguém está ouvindo, então o aviso
ainda não chegou a lugar nenhum.

**Próximo:** [7. Avisando o mundo](07-sns-parameter-store.md)
