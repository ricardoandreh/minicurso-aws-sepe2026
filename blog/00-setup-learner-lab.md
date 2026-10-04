# 0. Preparando a máquina para o AWS Learner Lab

> Parte da série *construindo um encurtador de URL serverless na AWS*.
> [Voltar ao índice](README.md)

Este artigo não constrói nada. Ele deixa sua máquina pronta para qualquer
minicurso que use o AWS Academy Learner Lab, e explica as armadilhas do
ambiente, que são poucas mas custam caro quando pegam você no meio de uma aula.

Leva uns vinte minutos na primeira vez. Depois, só repetir o passo das
credenciais a cada sessão.

Se você só vai fazer os artigos 1 a 7, que são todos no console, **nada disso é
necessário**: basta o navegador. Volte aqui quando chegar na parte de
infraestrutura como código.

## O que vamos instalar

| Ferramenta | Para quê |
|---|---|
| AWS CLI v2 | falar com a AWS pelo terminal |
| Node.js (via nvm) | rodar o SST |
| uv | gerenciar as dependências Python das funções |

## AWS CLI v2

A versão 1 ainda aparece em tutorial antigo e em pacote de distribuição. Use a
2: a 1 não recebe recursos novos há anos.

**Linux (x86_64):**

```bash
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip awscliv2.zip
sudo ./aws/install
rm -rf awscliv2.zip aws
```

**macOS:**

```bash
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o AWSCLIV2.pkg
sudo installer -pkg AWSCLIV2.pkg -target /
```

**Windows:** baixe e rode o instalador em
`https://awscli.amazonaws.com/AWSCLIV2.msi`.

Confira:

```bash
aws --version
# aws-cli/2.x.x Python/3.x.x ...
```

Se aparecer `aws-cli/1.x`, você tem a versão antiga no caminho. No Ubuntu ela
costuma vir de `apt`, e sai com `sudo apt remove awscli`.

> 📸 **Print:** a saída do `aws --version` mostrando a 2.

## Node.js, e por que não usar o do `apt`

O Node que vem nos repositórios de distribuição costuma estar várias versões
atrás. No Ubuntu 24.04, por exemplo, o `apt` entrega a 18, enquanto o SST pede
20 ou mais recente. E atualizar por `apt` depois é desconfortável, porque você
acaba com duas instalações disputando o mesmo `PATH`.

Remova a versão do sistema, se houver:

```bash
sudo apt remove nodejs npm
sudo apt autoremove
```

Instale o **nvm**, que é um gerenciador de versões por usuário:

```bash
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash
```

Feche e abra o terminal (ou rode `source ~/.bashrc`), e então:

```bash
nvm install --lts
nvm use --lts
node --version   # v22.x ou mais recente
```

Por que nvm e não `apt`:

- **Não precisa de `sudo`.** Tudo vive em `~/.nvm`, o que evita pacote
  instalado como root e permissão quebrada no `npm install -g`.
- **Troca de versão em um comando.** Se um projeto precisar de outra, é
  `nvm use 20`.
- **Não briga com o sistema.** O `apt` continua livre para gerenciar o resto.

## uv, para o Python

O suporte a Python no SST é mantido pela comunidade e espera um workspace `uv`.

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

## Credenciais do Learner Lab

Aqui começa a parte específica do ambiente.

1. Abra o laboratório no AWS Academy e clique em **Start Lab**
2. Espere o indicador ficar **verde**
3. Clique em **AWS Details** → **AWS CLI** → **Show**
4. Copie o bloco inteiro

Ele tem este formato:

```ini
[default]
aws_access_key_id=ASIA...
aws_secret_access_key=...
aws_session_token=...
```

Cole em `~/.aws/credentials`. E **configure a região**, que não vem no bloco e é
a causa de erro mais boba do dia:

```bash
aws configure set region us-east-1
```

> 📸 **Print:** a janela do AWS Details com o bloco de credenciais, **com os
> valores borrados**.

Confira:

```bash
aws sts get-caller-identity
```

Deve responder com um ARN terminado em `assumed-role/voclabs/...`.

### A alternativa: variáveis de ambiente

Também funciona exportar direto:

```bash
export AWS_ACCESS_KEY_ID=ASIA...
export AWS_SECRET_ACCESS_KEY=...
export AWS_SESSION_TOKEN=...
export AWS_DEFAULT_REGION=us-east-1
```

Só saiba que **variável de ambiente ganha do arquivo**. Se você exportou numa
sessão antiga e depois atualizou o `~/.aws/credentials`, o terminal vai
continuar usando a credencial velha, já expirada, e o erro não vai dizer isso. É
um dos jeitos mais comuns de perder meia hora. Na dúvida:

```bash
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN
```

## As três armadilhas do Learner Lab

### 1. A sessão expira, e o sintoma engana

A credencial dura algumas horas. Quando acaba, o AWS Academy anexa uma policy de
**deny explícito** chamada `voc-cancel-cred`. O efeito é cruel:

```bash
aws sts get-caller-identity   # continua respondendo normalmente
aws dynamodb list-tables      # AccessDenied
```

Você olha a identidade, vê que está logado, e procura o problema em todo lugar
menos no lugar certo. **Se uma ação que funcionava começar a dar AccessDenied
sem você ter mudado nada, é isso.** A mensagem cita `voc-cancel-cred`, e esse
nome é a confirmação.

A solução é voltar ao AWS Academy, clicar em **Start Lab** de novo e recopiar as
credenciais. Elas mudam a cada sessão.

### 2. Expirar não é o mesmo que resetar

- **Sessão expirada:** só as credenciais são revogadas. Tudo que você criou
  continua lá, intacto. Recopie e siga.
- **Reset do laboratório:** apaga Lambda, DynamoDB, SQS, SNS, API Gateway e as
  roles. Os **buckets S3 sobrevivem**, o que às vezes confunde, porque o site
  continua no ar enquanto o resto sumiu.

### 3. Permissões: o que não dá para fazer

A conta é real, mas restrita. O que mais afeta um minicurso:

| Não dá | Consequência |
|---|---|
| `iam:CreateRole`, `iam:AttachRolePolicy` | ao criar uma Lambda, escolha **Use an existing role → LabRole** |
| CloudFront | o site fica em S3 website hosting, HTTP puro |
| Bedrock | se quiser usar AI, vai ser por provider externo |

A `LabRole` existe justamente para compensar a primeira linha: ela já tem
permissão para DynamoDB, SQS, SNS, S3, SSM e o resto do que a aula usa. Em
compensação, ela é bem mais permissiva do que uma role de produção deveria ser,
e vale olhar a lista de policies dela uma vez só para ver a diferença.

## Checklist antes de começar

```bash
aws --version              # 2.x
node --version             # 20+
uv --version
aws sts get-caller-identity   # ARN com assumed-role/voclabs
aws configure get region      # us-east-1
```

Se os cinco responderem, você está pronto.

> 📸 **Print:** o terminal com os cinco comandos e suas saídas.

## Ao terminar o minicurso

O laboratório expira sozinho, mas é bom hábito apagar o que você criou. Numa
conta AWS própria isso é a diferença entre centavos e uma surpresa na fatura. O
último artigo da série tem a lista completa, na ordem certa.

**Próximo:** [1. O site sem servidor](01-s3.md)
