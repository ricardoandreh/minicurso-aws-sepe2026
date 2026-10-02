# Série: construindo um encurtador de URL serverless na AWS

Treze artigos que constroem um encurtador de URL completo, duas vezes. Primeiro
clicando no AWS Management Console, serviço por serviço. Depois a mesma aplicação
inteira declarada em código, com SST v4.

A repetição é o ponto. Na segunda vez você já sabe quantos cliques cada peça
custou, e aí dá para perceber o que a infraestrutura como código faz desaparecer.

A aplicação ao final:

```
Browser
   │
   ├─ site estático ──────────▶ S3
   │
   └─ chamadas HTTP ──────────▶ API Gateway ──▶ Lambda (3 rotas)
                                                  ├──▶ DynamoDB
                                                  └──▶ SQS ──▶ Lambda contador ──▶ DynamoDB
                                                                                      │
                                                                               DynamoDB Streams
                                                                                      │
                                                                             EventBridge Pipes
                                                                                      │
                                                                                    SNS ──▶ Lambda ──▶ Discord
                                                                                              │
                                                                                      Parameter Store
```

## Os artigos

### Preparação

| # | Artigo | Ao final você tem |
|---|---|---|
| 0 | [Preparando a máquina para o AWS Learner Lab](00-setup-learner-lab.md) | CLI, Node e credenciais prontos |

Independente do resto da série, e reaproveitável em qualquer minicurso que use o
Learner Lab. **Só é necessário a partir do artigo 8**: os artigos 1 a 7 são
todos no console e pedem apenas o navegador.

### Parte 1: no console, clique a clique

| # | Artigo | Serviço | Ao final você tem |
|---|---|---|---|
| 1 | [O site sem servidor](01-s3.md) | S3 | uma URL pública servindo seu HTML |
| 2 | [Onde o dado mora](02-dynamodb.md) | DynamoDB | uma tabela com itens de formatos diferentes |
| 3 | [O código que roda sem servidor](03-lambda.md) | Lambda · IAM · CloudWatch | uma função que grava e lê no banco |
| 4 | [A porta de entrada](04-api-gateway.md) | API Gateway | o encurtador funcionando no navegador |
| 5 | [Tirando trabalho do caminho crítico](05-sqs.md) | SQS | contagem de cliques sem atrasar o redirect |
| 6 | [Reagindo a mudanças no banco](06-streams-pipes.md) | DynamoDB Streams · EventBridge Pipes | detecção do marco de 10 cliques, sem código |
| 7 | [Avisando o mundo](07-sns-parameter-store.md) | SNS · Parameter Store | parabéns chegando no Discord |

### Parte 2: a mesma aplicação, agora em código

| # | Artigo | Assunto | Branch |
|---|---|---|---|
| 8 | [A mesma coisa, agora em código](08-sst-primeiro-recurso.md) | IaC, SST v4, stage, estado, drift | `passo-1` |
| 9 | [Uma linha em vez de três passos](09-sst-link.md) | o `link()`, e a policy que você não escreve | `passo-2` |
| 10 | [A API, agora em três linhas](10-sst-api.md) | rotas compartilhando uma Lambda, CORS | `passo-3` |
| 11 | [A fila, e o que o `subscribe` esconde](11-sst-fila.md) | event source mapping, at-least-once | `passo-4` |
| 12 | [Reagindo ao dado, não ao código](12-sst-stream-pipe-sns.md) | stream, Pipes via Pulumi, SNS, segredo | `passo-5` |
| 13 | [O que mudou, e o que isso custou](13-fechamento.md) | comparação, custo, limpeza, próximos passos | |

Aqui você não escreve código. Em cada artigo você troca de branch, lê o diff e
deploya:

```bash
git checkout passo-3
git diff passo-2 passo-3
BUCKET_SITE=seu-bucket npx sst deploy --stage lab
```

As branches são cumulativas, então `git diff passo-N passo-N+1` mostra
exatamente o que aquele artigo acrescenta, e nada mais.

| Branch | Linhas no `sst.config.ts` | O que entra |
|---|---|---|
| `passo-1` | 36 | a tabela |
| `passo-2` | 53 | a função, e o `link()` |
| `passo-3` | 80 | o API Gateway, e o encurtador funcionando |
| `passo-4` | 94 | a fila e o contador |
| `passo-5` | 147 | stream, pipe, tópico, segredo e o Discord |

## Estrutura de cada artigo

1. **O que é**: uma frase, sem jargão
2. **Como funciona**: o modelo mental que ajuda a entender o resto
3. **Onde entra no encurtador**: o papel dele na aplicação
4. **Hands-on**: passos numerados, no console na Parte 1 e no terminal na Parte 2
5. **O que deu errado (e por quê)**: os erros que costumam aparecer nesse passo
6. **Como isso sustenta serverless e event-driven**: a ideia que fica
7. **O que ainda não dá para fazer**: a ponte para o próximo artigo

## Convenções

**Prints.** Os lugares onde vale uma captura de tela estão marcados assim:

> 📸 **Print:** o que capturar

**Região.** Tudo em `us-east-1`. Criar recurso numa região e procurar em outra
é o erro mais comum de quem está começando.

**Nomes.** Na Parte 1 você escolhe os nomes, e eles seguem o prefixo
`url-shortener-`:

| Recurso | Nome |
|---|---|
| Bucket do site | `url-shortener-site-SEUNUMERO` |
| Tabela | `url-shortener-urls` |
| Função HTTP | `url-shortener-api` |
| Fila | `url-shortener-queue` |
| Função do contador | `url-shortener-counter` |
| Tópico SNS | `congrats-urls` |
| Função do Discord | `url-shortener-alert` |

Na Parte 2 você não escolhe nenhum: o SST monta o nome a partir da aplicação, do
stage e do nome lógico do componente. Os recursos das duas partes convivem na
mesma conta sem se atropelar, e é bom que convivam, porque a comparação é a aula.

**Stage.** Na Parte 2, sempre `--stage lab`. Trocar de stage cria uma cópia nova
da aplicação inteira, e os segredos não acompanham.

**Ambiente.** Os artigos assumem uma conta AWS comum. O AWS Academy Learner Lab
se comporta diferente em três pontos (IAM, S3 via IaC e CloudFront), e onde isso
acontece tem uma nota avisando. O artigo 13 resume o que uma conta comum muda.

**Código.** A versão da Parte 1 está em
[`../url-shortener/`](../url-shortener/): `index.html` e as três funções em
`lambdas/`, lendo configuração de variáveis de ambiente, como o console pede.

A versão da Parte 2 está nas branches `passo-1` a `passo-5`: o `sst.config.ts`
na raiz e as mesmas três funções em `functions/src/functions/`, lendo
configuração de `Resource`. A diferença entre os dois conjuntos de arquivos é
pequena de propósito, e é o assunto do artigo 9.

## Limpeza

O artigo 13 tem as duas listas, uma para o que o SST criou (`npx sst remove`) e
uma para o que você criou no console, na ordem inversa da construção.
