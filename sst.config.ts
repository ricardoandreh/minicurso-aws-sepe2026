/// <reference path="./.sst/platform/config.d.ts" />

/**
 * Encurtador de URL: projeto completo.
 *
 * Parte 1 (console): tabela, funcao, API, fila.
 * Parte 2 (codigo): mesmo projeto declarado em SST v4.
 *
 * O stream, o pipe com filtro, o topico SNS e a funcao que posta no Discord
 * reagem a mudancas na tabela sem que quem escreve saiba que existem.
 *
 * Deploy:
 *   npm install
 *   eval "$(aws configure export-credentials --profile labs --format env)"
 *   npx sst secret set DiscordWebhook "https://discord.com/api/webhooks/..." --stage lab
 *   npx sst deploy --stage lab
 */
export default $config({
  app(input) {
    return {
      name: "url-shortener",
      removal: input?.stage === "production" ? "retain" : "remove",
      home: "aws",
      providers: { aws: { region: "us-east-1" } },
    };
  },

  async run() {
    const contaId = await aws.getCallerIdentity().then((i) => i.accountId);
    const role = `arn:aws:iam::${contaId}:role/LabRole`;
    const runtime = "python3.13";
    const fnDir = "functions/src/functions";

    const bucketSite = process.env.BUCKET_SITE;
    if (!bucketSite) {
      throw new Error(
        "Informe o bucket do site, criado no hands-on da Parte 1:\n" +
          "  BUCKET_SITE=seu-bucket npx sst deploy --stage lab",
      );
    }
    const siteUrl = `http://${bucketSite}.s3-website-us-east-1.amazonaws.com`;

    // O stream e o que permite reagir a mudancas na tabela sem que quem
    // escreveu precise avisar ninguem. `new-and-old-images` e obrigatorio
    // aqui: o filtro do pipe compara o valor antes com o depois.
    const tabela = new sst.aws.Dynamo("Urls", {
      fields: { shortId: "string" },
      primaryIndex: { hashKey: "shortId" },
      stream: "new-and-old-images",
    });

    // Contar clique nao pode atrasar o redirect, entao sai do caminho critico
    // e vai para a fila. visibilityTimeout >= timeout de quem consome.
    const fila = new sst.aws.Queue("Cliques", { visibilityTimeout: "60 seconds" });

    // `allowHeaders: ["content-type"]` nao e detalhe: o frontend manda
    // `Content-Type: application/json`, e e justamente esse cabecalho que
    // obriga o navegador a fazer preflight. Sem ele, o preflight volta 204 sem
    // autorizar nada e o navegador cancela a requisicao, sem erro na API.
    const api = new sst.aws.ApiGatewayV2("Api", {
      cors: {
        allowOrigins: [siteUrl],
        allowMethods: ["GET", "POST"],
        allowHeaders: ["content-type"],
      },
    });

    // Uma Function para as tres rotas: elas reagem ao mesmo gatilho, escalam
    // juntas e falham juntas. Construir a Function antes e passar o `arn` para
    // cada rota e o que faz as tres compartilharem a mesma Lambda: passar o
    // caminho do handler tres vezes criaria tres funcoes identicas, sem avisar.
    const encurtador = new sst.aws.Function("Encurtador", {
      handler: `${fnDir}/api.lambda_handler`,
      runtime,
      role,
      memory: "256 MB",
      timeout: "10 seconds",
      link: [tabela, fila],
      environment: {
        TABELA_NOME: tabela.name,
        FILA_URL: fila.url,
      },
    });

    // A precedencia e do API Gateway, nao nossa: `GET /urls` vence
    // `GET /{shortId}` porque literal ganha de variavel. Fosse ao contrario,
    // listar seria tratado como o redirect de um link de id "urls".
    api.route("POST /shorten", encurtador.arn);
    api.route("GET /urls", encurtador.arn);
    api.route("GET /{shortId}", encurtador.arn);

    // Funcao separada porque o gatilho e outro: fila, assincrono, pode ser
    // retentado sem ninguem esperando do outro lado. `subscribe` cria a funcao
    // e a event source mapping de uma vez, sem ARN nem policy escritos a mao.
    fila.subscribe({
      handler: `${fnDir}/contador.lambda_handler`,
      runtime,
      role,
      memory: "128 MB",
      timeout: "15 seconds",
      link: [tabela],
      environment: {
        TABELA_NOME: tabela.name,
      },
    });

    // O equivalente do Parameter Store aqui. Setado uma vez por stage, via
    // CLI, e nunca no codigo.
    const webhook = new sst.Secret("DiscordWebhook");

    const topico = new sst.aws.SnsTopic("Parabens");

    topico.subscribe("Discord", {
      handler: `${fnDir}/discord.lambda_handler`,
      runtime,
      role,
      memory: "128 MB",
      timeout: "10 seconds",
      link: [webhook],
      environment: {
        WEBHOOK_PARAM: webhook.name,
      },
    });

    // O SST v4 tem `sst.aws.Bus`, que e o barramento do EventBridge, mas nao
    // tem componente para Pipes. O recurso existe no provider que o SST ja
    // embute, e `aws` e global aqui, entao e so escrever: sem instalar nada,
    // sem import. E o exemplo de que o abstrator cobre o comum e, quando nao
    // cobre, voce desce um nivel e segue.
    //
    // O filtro e quem decide tudo, e por isso a funcao do Discord nao guarda
    // estado nenhum: ela so notifica. Duas igualdades exatas sobre strings,
    // porque no registro do stream o numero vem como string ({"N": "10"}) e o
    // comparador numerico do EventBridge espera numero JSON.
    //
    // Nao ponha `eventSourceARN` no filtro: o valor que chega e o ARN do
    // *stream*, com sufixo /stream/<timestamp>, e nao o da tabela. A
    // comparacao falharia sempre, em silencio.
    new aws.pipes.Pipe("Parabens10", {
      roleArn: role,
      source: tabela.nodes.table.streamArn,
      target: topico.arn,
      sourceParameters: {
        dynamodbStreamParameters: { startingPosition: "LATEST", batchSize: 1 },
        filterCriteria: {
          filters: [{
            pattern: JSON.stringify({
              eventName: ["MODIFY"],
              dynamodb: {
                OldImage: { clicks: { N: ["9"] } },
                NewImage: { clicks: { N: ["10"] } },
              },
            }),
          }],
        },
      },
    });

    return { site: siteUrl, api: api.url, bucket: bucketSite };
  },
});
