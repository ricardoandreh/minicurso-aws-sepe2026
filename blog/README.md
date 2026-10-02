# Série: construindo um encurtador de URL serverless na AWS

Sete artigos que constroem, do zero e pelo AWS Management Console, um encurtador
de URL completo. Cada artigo apresenta um serviço, mostra onde ele entra na
aplicação e termina com algo funcionando.

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

| # | Artigo | Serviço | Ao final você tem |
|---|---|---|---|
| 1 | [O site sem servidor](01-s3.md) | S3 | uma URL pública servindo seu HTML |
| 2 | [Onde o dado mora](02-dynamodb.md) | DynamoDB | uma tabela com itens de formatos diferentes |
| 3 | [O código que roda sem servidor](03-lambda.md) | Lambda · IAM · CloudWatch | uma função que grava e lê no banco |
| 4 | [A porta de entrada](04-api-gateway.md) | API Gateway | o encurtador funcionando no navegador |
| 5 | [Tirando trabalho do caminho crítico](05-sqs.md) | SQS | contagem de cliques sem atrasar o redirect |
| 6 | [Reagindo a mudanças no banco](06-streams-pipes.md) | DynamoDB Streams · EventBridge Pipes | detecção do marco de 10 cliques, sem código |
| 7 | [Avisando o mundo](07-sns-parameter-store.md) | SNS · Parameter Store | parabéns chegando no Discord |

Os artigos 1 a 5 constroem o encurtador. Os 6 e 7 são a parte opcional: quando
um link bate 10 cliques, um parabéns é postado num canal do Discord.

## Estrutura de cada artigo

1. **O que é** — uma frase, sem jargão
2. **Como funciona** — o modelo mental que você precisa ter
3. **Onde entra no encurtador** — o papel concreto na aplicação
4. **Hands-on** — passos numerados no console
5. **O que deu errado (e por quê)** — os erros reais que aparecem nesse passo
6. **Como isso sustenta serverless e event-driven** — a ideia que fica
7. **O que ainda não dá para fazer** — a ponte para o próximo artigo

## Convenções

**Prints.** Os lugares onde vale uma captura de tela estão marcados assim:

> 📸 **Print:** o que capturar

**Região.** Tudo em `us-east-1`. Criar recurso numa região e procurar em outra
é o erro mais comum de quem está começando.

**Nomes.** Os recursos seguem o prefixo `url-shortener-`, e são sempre os
mesmos ao longo da série:

| Recurso | Nome |
|---|---|
| Bucket do site | `url-shortener-site-SEUNUMERO` |
| Tabela | `url-shortener-urls` |
| Função HTTP | `url-shortener-api` |
| Fila | `url-shortener-queue` |
| Função do contador | `url-shortener-counter` |
| Tópico SNS | `congrats-urls` |
| Função do Discord | `url-shortener-alert` |

**Ambiente.** Os artigos assumem uma conta AWS comum. Onde o AWS Academy
Learner Lab se comporta diferente — e ele se comporta, principalmente em IAM —
há uma nota explícita.

**Código.** Está em [`../url-shortener/`](../url-shortener/): `index.html` e as
três funções em `lambdas/`.

## Limpeza

No fim da série, para não deixar nada cobrando: apague na ordem inversa — pipe,
tópico, funções, fila, tabela, bucket. O artigo 7 tem a lista completa.
