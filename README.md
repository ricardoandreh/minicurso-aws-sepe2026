# Encurtador de URL, minicurso AWS + SST v4

Material do minicurso do IFC: um encurtador de URL serverless construído duas
vezes, primeiro clicando no console da AWS e depois declarado em código com
SST v4.

A série de artigos está em [`blog/`](blog/), e é por lá que se começa.

## O que tem em cada branch

| Branch | Conteúdo |
|---|---|
| `url-shortener` | esta. A aplicação do console e a série de artigos |
| `passo-1` … `passo-5` | a mesma aplicação em código, um recurso por vez |
| `main` | Central de Chamados, a segunda aplicação, usada no fechamento |
| `outbox-streams` | a Central de Chamados sem escrita dupla, com Streams e Pipes |

As branches de passo são cumulativas, então `git diff passo-N passo-N+1` mostra
exatamente o que aquele passo acrescenta:

```bash
git checkout passo-3
git diff passo-2 passo-3
BUCKET_SITE=seu-bucket npx sst deploy --stage lab
```

| Branch | `sst.config.ts` | O que entra |
|---|---|---|
| `passo-1` | 36 linhas | a tabela |
| `passo-2` | 53 | a função, e o `link()` |
| `passo-3` | 80 | o API Gateway, e o encurtador funcionando |
| `passo-4` | 94 | a fila e o contador |
| `passo-5` | 147 | stream, pipe, tópico, segredo e o Discord |

## Nesta branch

```
blog/                    a série de 14 artigos, começando pelo README
url-shortener/           a aplicação da Parte 1
  index.html             frontend de arquivo único, sem build
  lambdas/               api.py, contador.py, discord.py, lendo os.environ
functions/               onde os handlers da Parte 2 vão morar, a partir do passo-2
scripts/checar-lab.sh    conferir o Learner Lab depois de cada Start
```

O `sst.config.ts` não existe aqui de propósito: ele nasce no `passo-1`, com um
recurso só, e é isso que o artigo 8 pede para você ler antes de qualquer deploy.

## Antes de começar a Parte 2

```bash
npm install
eval "$(aws configure export-credentials --profile labs --format env)"
```

O `export-credentials` é necessário porque o SST fala com a AWS pelo provedor em
Go do Pulumi, que não lê todas as formas de credencial que o AWS CLI lê. O
[artigo 0](blog/00-setup-learner-lab.md) tem o resto do setup.

## Depois de todo Start do Learner Lab

Parar e reiniciar o lab deixa as assinaturas de fila em `Disabled` e os pipes em
`Stopped`, sem erro visível em lugar nenhum:

```bash
./scripts/checar-lab.sh --corrigir
```
