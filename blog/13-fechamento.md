# 13. O que mudou, e o que isso custou

> Parte da série *construindo um encurtador de URL serverless na AWS*.
> [Voltar ao índice](README.md)

Você construiu a mesma aplicação duas vezes. É um desperdício de tempo
excelente, porque agora dá para comparar com conhecimento de causa, e não por
slide de fornecedor.

## Lado a lado

| | No console (artigos 1 a 7) | Em código (artigos 8 a 12) |
|---|---|---|
| Criar a tabela | 1 tela | 4 linhas |
| Criar a função e dar acesso ao banco | 3 telas, incluindo 2 de IAM | 1 campo `link` |
| Criar a API com 3 rotas | 5 telas | 4 linhas |
| Configurar CORS | 1 tela, e um erro silencioso | 5 linhas |
| Criar fila, consumidor e trigger | 4 telas, mais 2 de IAM | 1 `subscribe` |
| Ligar stream, pipe, tópico e assinante | 6 telas, e um JSON colado a mão | 30 linhas |
| **Refazer tudo do zero** | repetir os cliques | 1 comando |
| **Saber o que está configurado** | abrir 12 telas | ler 147 linhas |
| **Descobrir que alguém mudou algo** | sorte, ou CloudTrail | `sst diff` |

A última linha é a que paga a conta.

## O que desapareceu de verdade

Vale ser específico, porque "é mais fácil" não é argumento:

**Nome de recurso.** Você não escolheu nenhum, e portanto nunca mais vai ter um
conflito de nome, nem um `-v2` no fim de nada.

**ARN no código.** Zero, nas três funções. No console, cada integração pedia um.

**Policy escrita a mão.** O `link()` deriva a permissão mínima do componente.
Numa conta comum isso significa uma role por função, com acesso só ao que ela
usa. Esse é o ganho que o Learner Lab esconde, porque lá todas as funções
compartilham a `LabRole`.

**Variável de ambiente de configuração.** Continuam existindo por baixo, mas você
não digita nenhuma, e portanto não cola o ARN da fila no lugar da URL.

**A permissão de invocação que o console deixa você esquecer.** `api.route()`
sempre escreve. Era a causa do 500 sem log nenhum.

## O que ficou pior, ou pelo menos mais caro

Essa parte normalmente não aparece nos tutoriais.

**Tem uma linguagem no meio.** O `sst.config.ts` é TypeScript. Dá para seguir sem
saber TypeScript, mas quando der erro, o erro é de TypeScript, e aí não dá.

**Tem uma máquina para preparar.** Node, nvm, `npm install` de 200 MB,
credenciais exportadas para o ambiente. No console, bastava o navegador. O
[artigo 0](00-setup-learner-lab.md) existe por isso.

**O ciclo é mais lento para uma mudança boba.** Mudar o timeout de uma função no
console são três cliques e vale na hora. Em código são duas linhas e um deploy. O
`sst dev` existe justamente para encurtar isso no dia a dia, e vale explorar
depois.

**Tem estado para cuidar.** Aquele bucket `sst-state-*` não é opcional. Se ele
sumir, o SST esquece o que criou, e os recursos ficam órfãos na conta.

**A abstração vaza, e você precisa saber o que tem embaixo.** O Pipes não tem
componente, e a saída foi escrever Pulumi direto com `tabela.nodes.table.streamArn`.
Isso é bom, é melhor que não poder, mas significa que entender o SST sem entender
o que ele gera não é suficiente.

E uma observação que é consequência das duas metades juntas, não de nenhuma
delas: **a IaC não te ensina a arquitetura**. Se você tivesse começado no artigo
8, teria deployado 147 linhas que funcionam e não saberia o que é um event source
mapping, nem por que o `visibilityTimeout` importa, nem por que o filtro do pipe
compara strings. O console foi lento de propósito.

## O que uma conta AWS comum muda

O Learner Lab apertou a aplicação em três lugares, e vale saber como fica sem
isso:

**O bucket volta para dentro do código.** Sem a SCP que nega
`s3:GetBucketObjectLockConfiguration`, um `sst.aws.Bucket` resolve, e o
`BUCKET_SITE` desaparece.

**Cada função ganha a sua role.** Você omite o campo `role`, e o `link()` passa a
gerar permissão mínima de verdade. Se você tem conta pessoal, faça
`npx sst deploy --stage pessoal` lá e compare as roles. É o momento em que o
`link()` faz sentido de corpo inteiro.

**O site ganha CDN e HTTPS.** `sst.aws.StaticSite` cuida de bucket, CloudFront,
certificado e invalidação de cache de uma vez. E aí o site deixa de ser HTTP
puro, o que, de passagem, resolve a única coisa que impedia essa aplicação de
tirar nota cheia no Lighthouse.

## Limpeza

Duas listas, porque você construiu de dois jeitos.

**O que o SST criou:**

```bash
npx sst remove --stage lab
```

Isso remove tudo na ordem certa, inclusive os segredos daquele stage. O bucket de
estado fica, e pode ficar: custa frações de centavo.

**O que você criou no console**, na ordem inversa da construção, porque recurso
com dependente não apaga:

1. o pipe do EventBridge
2. a assinatura e o tópico SNS
3. a função do Discord
4. o trigger do SQS, depois a função do contador, depois a fila
5. a função das rotas e a HTTP API
6. o parâmetro no Parameter Store
7. a tabela
8. o bucket do site (apague os objetos antes)

> 📸 **Print:** o console de Lambda vazio no fim.

Se você estiver no Learner Lab, encerrar o lab derruba a maior parte sozinho, mas
não conte com isso: confira.

## Sobre custo

A aplicação inteira, nas duas versões, com algumas centenas de cliques de teste,
cabe na casa de centavos. O motivo é o modelo: tudo aqui cobra por uso, e nada
cobra por estar ligado.

| Serviço | Como cobra | Parada |
|---|---|---|
| S3 | armazenamento e requisição | praticamente zero para um HTML |
| DynamoDB on-demand | por leitura e escrita | zero |
| Lambda | por invocação e duração | zero |
| API Gateway HTTP | por requisição | zero |
| SQS | por requisição | zero |
| SNS | por publicação | zero |
| Pipes | por registro processado | cobra pelos lidos, não pelos filtrados |
| Streams | por leitura do stream | zero |

A linha do Pipes é a única com pegadinha: ele cobra por registro lido do stream,
e o filtro descarta **depois** de ler. Com dez cliques por dia não muda nada; com
um stream de alto volume e um filtro muito restritivo, muda.

## Para onde ir depois

Três direções, em ordem de proximidade:

**Idempotência.** O contador desta aplicação conta duas vezes se uma mensagem for
reentregue, e a gente escolheu aceitar. Transformar isso em "conta exatamente uma
vez" é um exercício ótimo: precisa de um identificador por mensagem, de um
registro do que já foi processado e de uma escrita condicional. Faça no contador
e sinta o custo.

**Dead Letter Queue e observabilidade.** O que acontece com uma mensagem que
falha para sempre? Hoje ela retenta até expirar e enche o log. Uma DLQ e um alarme
no CloudWatch são dez linhas no config, e são a diferença entre uma aplicação de
aula e uma que alguém opera.

**O problema da escrita dupla.** Este é o grande. O encurtador faz
`put_item` e depois `send_message`, duas escritas em sistemas diferentes, sem
transação entre elas. Se a segunda falhar, o primeiro já foi. Nesta aplicação a
gente contornou com um `try` e uma decisão explícita de que perder a contagem é
aceitável. Quando **não** é aceitável, a resposta é o padrão *Transactional
Outbox*, ou usar o stream como fonte da verdade, que é o que o pipe já faz no
artigo 12.

Essa última é a ponte para a outra aplicação deste minicurso, a Central de
Chamados, que existe justamente para mostrar o problema acontecendo e as duas
saídas.

## Fecho

Duas frases para levar.

A primeira: o `link()` não é açúcar sintático. Ele muda qual caminho é o mais
curto, e por isso muda o que as pessoas fazem com prazo apertado. Permissão
mínima deixou de depender de disciplina.

A segunda: nada aqui era difícil. Era espalhado. E a diferença entre "difícil" e
"espalhado" é exatamente onde a infraestrutura como código trabalha.

---

> Parte da série *construindo um encurtador de URL serverless na AWS*.
> [Voltar ao índice](README.md)
