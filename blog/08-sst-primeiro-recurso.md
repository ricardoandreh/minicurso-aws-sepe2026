# 8. A mesma coisa, agora em código

> Parte da série *construindo um encurtador de URL serverless na AWS*. [Voltar ao índice](README.md)

Nos sete artigos anteriores você construiu um encurtador de URL inteiro clicando no console. Funciona, está no ar, e tem um problema: você não consegue fazer de novo.

Não é força de expressão. Tente responder, sem abrir o console: quais permissões a função do contador tem? O `visibilityTimeout` da fila ficou em quanto? O filtro do pipe está exatamente igual ao que você colou? A resposta honesta é "preciso ir ver". E se alguém mexeu em algo na terça, você vai ver o que ficou, não o que você decidiu.

A partir daqui a aplicação é a mesma, mas descrita num arquivo.

## O que é infraestrutura como código

Você escreve o estado desejado da sua infraestrutura num arquivo, versiona esse arquivo, e uma ferramenta se encarrega de deixar a conta igual ao que está escrito.

A palavra que importa é **igual**, não "criar". A ferramenta compara o que você declarou com o que existe de fato e aplica só a diferença. Rodar duas vezes seguidas não cria dois de nada.

Isso muda três coisas de lugar:

**O histórico.** `git log` passa a responder quando a fila nasceu e quem mudou o timeout. Hoje essa resposta está no CloudTrail, se você souber procurar.

**A revisão.** Uma mudança de infraestrutura vira um diff que outra pessoa consegue ler antes de acontecer.

**A repetição.** Criar um ambiente de teste idêntico deixa de ser um roteiro de cliques e passa a ser um comando.

## Por que SST, e não CloudFormation ou Terraform direto

CloudFormation e Terraform são a camada de baixo: você descreve recursos da AWS, um por um, com os nomes e os ARNs e as policies na mão. Tudo o que você fez no console tem equivalente lá, incluindo a parte chata.

O SST fica uma camada acima. Ele tem **componentes**: `sst.aws.Function`, `sst.aws.Queue`, `sst.aws.Dynamo`. Cada um desses esconde vários recursos da AWS que você provavelmente ia querer juntos de qualquer jeito. E tem o `link()`, que é o motivo real de estarmos usando ele neste minicurso, e assunto do próximo artigo.

Por baixo, o SST v4 usa o Pulumi, que por sua vez fala com a API da AWS. Você não precisa saber Pulumi para seguir, mas vale saber que ele está ali: quando o SST não tiver um componente para algo, a gente desce até ele e segue em frente. Isso acontece no artigo 12.

> **Sobre o nome.** Você vai encontrar "SST Ion" em textos de 2023 e 2024. Ion era o codinome da reescrita que virou a v3. O nome foi aposentado, e aqui é só SST v4.

## Como funciona

O arquivo é `sst.config.ts`, na raiz do projeto, e tem duas funções:

```typescript
export default $config({
  app(input) { /* identidade e provedor */ },
  async run() { /* os recursos */ },
});
```

**`app()`** diz o nome da aplicação, onde guardar o estado e qual provedor usar. É o que muda menos: você escreve uma vez e esquece.

**`run()`** é onde os recursos moram. É TypeScript de verdade, não um YAML disfarçado: `if`, `for`, variáveis, funções, importar de outro arquivo. Tudo vale.

Duas ideias a mais, e elas aparecem em todos os comandos daqui para frente:

**Stage.** Um nome que isola um conjunto completo de recursos. `--stage lab` e `--stage prod` criam duas cópias independentes da aplicação na mesma conta, com nomes diferentes, sem uma encostar na outra. É o mecanismo que torna "subir um ambiente só meu" uma coisa trivial.

**Estado.** O SST guarda um registro do que ele criou, para saber o que é dele e o que ele precisa mudar na próxima vez. No nosso caso isso vai para um bucket que ele cria sozinho na primeira vez, com nome começando em `sst-state-`. Não apague.

## Onde entra no encurtador

A aplicação vai nascer de novo, em cinco passos, cada um numa branch:

| Branch | O que entra |
|---|---|
| `passo-1` | a tabela |
| `passo-2` | a função, e o `link()` |
| `passo-3` | o API Gateway, e o encurtador funcionando |
| `passo-4` | a fila e o contador |
| `passo-5` | stream, pipe, tópico, segredo e o Discord |

Você não vai escrever código. Vai trocar de branch, ler o diff e deployar. A graça está em ver quanto desaparece.

## Hands-on

Antes de começar, o [artigo 0](00-setup-learner-lab.md) precisa estar feito: AWS CLI v2, Node por nvm e credenciais válidas no perfil.

### 1. Clonar e instalar

```bash
git clone URL-DO-REPOSITORIO minicurso
cd minicurso
npm install
```

O `npm install` baixa o SST e o provedor da AWS. É o download mais pesado da aula, uns 200 MB, então vale fazer antes do café.

### 2. Ir para o primeiro passo

```bash
git checkout passo-1
cat sst.config.ts
```

São 36 linhas, e a maior parte é comentário. O que faz algo é isto:

```typescript
const tabela = new sst.aws.Dynamo("Urls", {
  fields: { shortId: "string" },
  primaryIndex: { hashKey: "shortId" },
});

return { tabela: tabela.name };
```

Compare com o artigo 2. A partition key é a mesma, o tipo é o mesmo, e é só isso que o console também perguntou. O `fields` só declara os atributos que participam de chave ou índice, porque os outros o DynamoDB não precisa saber.

O `return` define os **outputs**: valores que o SST imprime no fim do deploy e guarda para você consultar depois.

> 📸 **Print:** o `sst.config.ts` do `passo-1` aberto no editor, inteiro, numa tela só.

### 3. Deployar

Com as credenciais exportadas no ambiente (artigo 0):

```bash
npx sst deploy --stage lab
```

A primeira vez demora, de um a dois minutos, porque ele cria o bucket de estado antes de qualquer coisa. No fim:

```
✓  Complete
   tabela: url-shortener-lab-UrlsTable-xxxxxxxx
```

Repare no nome. Você não escolheu, e ele não é arbitrário: tem o nome da aplicação, o stage, o nome lógico que você deu, e um sufixo aleatório. Nome de recurso deixou de ser uma decisão sua, o que também significa que você nunca mais vai ter um conflito de nome.

> 📸 **Print:** a saída do deploy com o output `tabela` visível.

### 4. Conferir no console

Console → **DynamoDB** → **Tables**. A tabela está lá, ao lado da `url-shortener-urls` que você criou na mão no artigo 2. As duas são iguais, e foram feitas de maneiras bem diferentes.

> 📸 **Print:** a lista de tabelas mostrando as duas lado a lado.

### 5. O deploy que não faz nada

Rode de novo:

```bash
npx sst deploy --stage lab
```

Dez segundos, e nenhuma mudança. Isso é a parte importante: o comando não é "criar", é "deixar igual ao que está escrito". Já estava igual.

### 6. O deploy que conserta

Agora quebre de propósito. No console, abra a tabela nova, vá em **Additional settings** e ligue o **Point-in-time recovery**. Você acabou de fazer o que todo mundo faz numa sexta-feira à noite.

```bash
npx sst refresh --stage lab
npx sst diff --stage lab
npx sst deploy --stage lab
```

Três comandos, três papéis. O `refresh` lê o que existe de verdade na conta e atualiza o estado do SST. O `diff` mostra o que está diferente do arquivo, sem mudar nada. O `deploy` desfaz a sua alteração, porque ela não está no arquivo.

Guarde o `sst diff`: é o comando que você vai rodar antes de qualquer deploy em algo que importa.

Esse é o nome do problema que a IaC resolve: **drift**. A conta foi mudada por fora, e agora o arquivo e a realidade discordam. Sem IaC, ninguém descobre. Com IaC, um comando mostra e outro resolve.

> 📸 **Print:** a saída do `deploy` mostrando a propriedade sendo revertida.

## O que deu errado (e por quê)

**`AWS credentials are not configured`, mesmo com `aws sts get-caller-identity` funcionando.** O SST fala com a AWS pelo provedor em Go do Pulumi, que lê credenciais de um jeito mais restrito que o AWS CLI. Se as suas vêm de SSO ou de qualquer coisa que não seja chave no `~/.aws/credentials`, ele não acha. A saída é materializar as credenciais no ambiente:

```bash
eval "$(aws configure export-credentials --profile labs --format env)"
```

No Learner Lab isso é obrigatório de todo jeito, porque lá a sessão tem token temporário e expira junto com o lab.

**`Error: 403 ... GetBucketObjectLockConfiguration`.** Essa é específica do Learner Lab e é o motivo de o primeiro recurso ser uma tabela e não um bucket. Uma SCP da organização do Lab nega essa chamada, e o provedor Pulumi a faz ao criar **e também ao apenas referenciar** um bucket. Resultado prático: nenhum bucket pode ser gerenciado por IaC nesse ambiente, nem `sst.aws.Bucket`, nem `Bucket.get()`, nem `sst.aws.StaticSite`. O bucket do site continua sendo o que você criou no artigo 1, e a partir do artigo 10 a gente passa o nome dele por variável de ambiente.

Em conta AWS comum nada disso existe e o bucket é um componente como qualquer outro.

**A tabela apareceu em outra região.** O `providers` do `app()` fixa `us-east-1`. Se você mudou, mudou para a aplicação inteira.

**O deploy ficou parado em `Creating...` por muito tempo e falhou.** No Learner Lab a sessão do lab expira e as credenciais morrem no meio do caminho. Renove o lab, exporte as credenciais de novo e rode o deploy outra vez. Ele continua de onde parou.

## Como isso sustenta serverless

Repare no que você não fez neste artigo: não inventou nome, não anotou ARN, não clicou em *Confirm*. E principalmente, não precisou lembrar de nada.

Isso escala de um jeito que o console não escala. Sete recursos dão para guardar na cabeça. Setenta, não. E a quantidade de peças pequenas é justamente a característica de uma arquitetura serverless: você troca poucos serviços grandes por muitos recursos pequenos, cada um com configuração própria. Sem um arquivo descrevendo o conjunto, essa troca sai caro.

## O que ainda não dá para fazer

Você tem uma tabela vazia que ninguém consulta. Falta o código, e com ele a parte do artigo 3 que mais incomodou: a variável de ambiente que você digitou e a policy que você anexou a mão.

**Próximo:** [9. Uma linha em vez de três passos](09-sst-link.md)
