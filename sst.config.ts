/// <reference path="./.sst/platform/config.d.ts" />

export default $config({
  app(input) {
    return {
      name: "central-chamados",
      removal: input?.stage === "production" ? "retain" : "remove",
      home: "aws",
      providers: { aws: { region: "us-east-1" } },
    };
  },

  async run() {
    // O AWS Learner Lab nega `iam:CreateRole`, então lá todas as Functions são
    // fixadas na LabRole que já existe na conta. Numa conta AWS normal deixe
    // `false`: o SST cria uma role por Function com apenas o que o `link()`
    // daquela função exige — que é o comportamento desejável. Para voltar ao
    // Lab, basta trocar esta linha para `true`.
    const usarLabRole = false;
    const role = usarLabRole
      ? `arn:aws:iam::${(await aws.getCallerIdentity()).accountId}:role/LabRole`
      : undefined;
    const runtime = "python3.13";
    const fnDir = "functions/src/functions";

    const tabela = new sst.aws.Dynamo("Chamados", {
      fields: { id: "string" },
      primaryIndex: { hashKey: "id" },
    });

    const groqApiKey = new sst.Secret("GroqApiKey");
    const discordWebhook = new sst.Secret("DiscordWebhook");
    const apiKey = new sst.Secret("ApiKey");

    const strandsLayer = new aws.lambda.LayerVersion("StrandsLayer", {
      layerName: "strands-openai",
      code: $asset("layers/strands-openai/build"),
      compatibleRuntimes: [runtime],
      compatibleArchitectures: ["x86_64"],
    });

    const fila = new sst.aws.Queue("ChamadosFila", { visibilityTimeout: "90 seconds" });
    const topico = new sst.aws.SnsTopic("ChamadosTopico");
    const bucket = new sst.aws.Bucket("Relatorios");

    fila.subscribe({
      handler: `${fnDir}/agente.handler`,
      runtime,
      role,
      layers: [strandsLayer.arn],
      memory: "512 MB",
      timeout: "30 seconds",
      link: [topico, bucket, groqApiKey],
    });

    topico.subscribe("DiscordNotifier", {
      handler: `${fnDir}/discord.handler`,
      runtime,
      role,
      memory: "256 MB",
      timeout: "15 seconds",
      link: [tabela, discordWebhook],
    });

    const frontendBucket = new sst.aws.Bucket("Frontend", { access: "public", enforceHttps: false });

    new aws.s3.BucketWebsiteConfiguration("FrontendWebsite", {
      bucket: frontendBucket.name,
      indexDocument: { suffix: "index.html" },
      errorDocument: { key: "index.html" },
    });

    const siteUrl = $interpolate`http://${frontendBucket.name}.s3-website-us-east-1.amazonaws.com`;

    const api = new sst.aws.ApiGatewayV2("Api", {
      cors: {
        allowOrigins: [siteUrl],
        allowMethods: ["GET", "POST"],
        allowHeaders: ["content-type", "x-api-key"],
      },
    });

    const apiAuth = api.addAuthorizer({
      name: "ApiKeyAuthorizer",
      lambda: {
        function: {
          handler: `${fnDir}/authorizer.handler`,
          runtime,
          role,
          memory: "128 MB",
          timeout: "5 seconds",
          link: [apiKey],
        },
        identitySources: ["$request.header.x-api-key"],
        payload: "2.0",
        response: "simple",
        ttl: "5 minutes",
      },
    });

    const auth = { auth: { lambda: apiAuth.id } };
    const chamadosApi = new sst.aws.Function("ChamadosApi", {
      handler: `${fnDir}/api.handler`,
      runtime,
      role,
      memory: "256 MB",
      timeout: "10 seconds",
      link: [tabela, fila],
    });
    api.route("POST /chamados", chamadosApi.arn, auth);
    api.route("GET /chamados", chamadosApi.arn, auth);

    return {
      site: siteUrl,
      api: api.url,
      bucket: frontendBucket.name,
    };
  },
});
