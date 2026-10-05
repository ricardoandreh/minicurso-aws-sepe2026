# 2. Onde o dado mora

> Parte da série *construindo um encurtador de URL serverless na AWS*. [Voltar ao índice](README.md)

No artigo anterior o site subiu, mas não tem com quem falar. Vamos dar a ele um lugar para guardar os links.

## O que é o DynamoDB

Um banco de dados NoSQL gerenciado pela AWS. Você cria a tabela e usa. Não há instância, versão, backup manual, nem CPU para monitorar.

## Como funciona

Você guarda **itens** numa **tabela**. Um item é um conjunto de atributos, parecido com um JSON.

O que mais muda em relação a um banco relacional:

**Não existe schema.** Cada item pode ter atributos diferentes. O banco não reclama se um tem um campo que o outro não tem.

**A chave é decidida na criação e não muda.** A **partition key** é como o DynamoDB encontra o item. Buscar por ela é instantâneo, a qualquer volume. Buscar por outra coisa exige varrer a tabela ou criar um índice.

**Você paga por operação, não por tempo.** No modo *on-demand*, cada leitura e cada escrita tem um custo. Uma tabela parada não custa quase nada.

Essa terceira característica é o que faz o DynamoDB combinar com Lambda: não faz sentido ter uma função que só existe durante a execução conversando com um banco que precisa ficar ligado o dia inteiro.

## Onde entra no encurtador

Ele guarda a tradução que é o coração da aplicação:

```
shortId  "aK3x9p"   ← partition key
longUrl  "https://exemplo.com/uma-pagina-bem-longa"
clicks   0
createdAt 1790742633
```

Quando alguém acessa o link curto, o `shortId` vem na URL. É exatamente a partition key, ou seja, a busca mais barata e mais rápida que o DynamoDB oferece, bem no caminho que mais importa para o usuário.

## Hands-on

### 1. Criar a tabela

Console → **DynamoDB** → **Tables** → **Create table**.

- **Table name:** `url-shortener-urls`
- **Partition key:** `shortId`, tipo **String**
- **Table settings:** Default settings
- **Create table**

Espere sair de *Creating* e ficar **Active**.

> 📸 **Print:** a tela de criação com a partition key preenchida.

### 2. Inserir um item

Entre na tabela → **Explore table items** → **Create item** → alterne para **JSON view** → cole:

```json
{
  "shortId":   "abc123",
  "longUrl":   "https://aws.amazon.com",
  "clicks":    0,
  "createdAt": 1790742633
}
```

**Create item.**

### 3. Inserir um item diferente

Repita, mas com um atributo a mais:

```json
{
  "shortId":   "xyz789",
  "longUrl":   "https://docs.aws.amazon.com",
  "clicks":    5,
  "createdAt": 1790742900,
  "criadoPor": "ricardo"
}
```

Os dois convivem na mesma tabela, com formatos diferentes, e ninguém reclamou.

> 📸 **Print:** a lista de itens mostrando os dois lado a lado, com o atributo extra visível em um deles.

### 4. Buscar pela chave

Ainda em **Explore table items**, mude de *Scan* para **Query** e procure por `shortId = abc123`.

Repare na diferença de conceito:

- **Query** usa a partition key. O DynamoDB vai direto no item.
- **Scan** lê a tabela inteira e filtra depois.

Com dois itens parece igual. Com dois milhões, não é.

## Como isso sustenta serverless

Repare no que você **não** fez: não escolheu tamanho de instância, não configurou réplica, não definiu quanto disco reservar, não criou usuário de banco. A tabela está pronta para uma requisição por dia ou um milhão por segundo, e você não precisa decidir qual antes.

E o "sem schema" não é desleixo. É o que permite o padrão que você vai ver no artigo 6: **o mesmo item vai ganhando atributos conforme atravessa o fluxo**. A aplicação grava `shortId` e `longUrl`; o contador acrescenta cliques; mais tarde outro processo acrescenta um marco. Nenhum deles precisou declarar nada antes. Num banco relacional, cada um desses passos seria uma migração.

## O que ainda não dá para fazer

Você tem onde guardar e um site que não sabe guardar. Falta o que fica no meio: alguém que receba o pedido, gere o código curto e escreva na tabela.

**Próximo:** [3. O código que roda sem servidor](03-lambda.md)
