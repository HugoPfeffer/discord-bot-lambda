import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
import * as events from "aws-cdk-lib/aws-events";
import * as targets from "aws-cdk-lib/aws-events-targets";
import * as dotenv from "dotenv";

dotenv.config();

export class DiscordBotLambdaStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const discordPublicKey = process.env.DISCORD_PUBLIC_KEY;
    if (!discordPublicKey) {
      throw new Error("DISCORD_PUBLIC_KEY must be set in .env or environment");
    }

    const mapTrackerTable = new dynamodb.Table(this, "MapTrackerTable", {
      partitionKey: {
        name: "guild_id",
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PAY_PER_REQUEST,
      removalPolicy: cdk.RemovalPolicy.RETAIN,
    });

    const dockerFunction = new lambda.DockerImageFunction(
      this,
      "DockerFunction",
      {
        code: lambda.DockerImageCode.fromImageAsset("./src"),
        memorySize: 512,
        timeout: cdk.Duration.seconds(10),
        architecture: lambda.Architecture.X86_64,
        environment: {
          DISCORD_PUBLIC_KEY: discordPublicKey,
          MAP_TRACKER_TABLE_NAME: mapTrackerTable.tableName,
        },
      }
    );

    mapTrackerTable.grantReadWriteData(dockerFunction);

    const functionUrl = dockerFunction.addFunctionUrl({
      authType: lambda.FunctionUrlAuthType.NONE,
      cors: {
        allowedOrigins: ["*"],
        allowedMethods: [lambda.HttpMethod.ALL],
        allowedHeaders: ["*"],
      },
    });

    // Required since Oct 2025: Function URLs with AuthType NONE need both
    // lambda:InvokeFunctionUrl (added automatically by CDK) AND lambda:InvokeFunction
    new lambda.CfnPermission(this, "AllowPublicInvokeFunction", {
      functionName: dockerFunction.functionName,
      action: "lambda:InvokeFunction",
      principal: "*",
    });

    new cdk.CfnOutput(this, "FunctionUrl", {
      value: functionUrl.url,
    });

    // --- FiveM player watcher ---

    const discordToken = process.env.DISCORD_TOKEN;
    const fivemCfxId = process.env.FIVEM_CFX_ID;
    const fivemPlayerId = process.env.FIVEM_PLAYER_ID;
    const discordChannelId = process.env.DISCORD_CHANNEL_ID;

    if (!discordToken || !fivemCfxId || !fivemPlayerId || !discordChannelId) {
      throw new Error(
        "DISCORD_TOKEN, FIVEM_CFX_ID, FIVEM_PLAYER_ID, and DISCORD_CHANNEL_ID must be set in .env or environment"
      );
    }

    const watcherTable = new dynamodb.Table(this, "WatcherStateTable", {
      partitionKey: {
        name: "watchId",
        type: dynamodb.AttributeType.STRING,
      },
      billingMode: dynamodb.BillingMode.PROVISIONED,
      readCapacity: 1,
      writeCapacity: 1,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });

    const watcherFunction = new lambda.DockerImageFunction(
      this,
      "WatcherFunction",
      {
        code: lambda.DockerImageCode.fromImageAsset("./src", {
          cmd: ["watcher.handler"],
        }),
        memorySize: 256,
        timeout: cdk.Duration.seconds(30),
        architecture: lambda.Architecture.X86_64,
        environment: {
          DISCORD_TOKEN: discordToken,
          FIVEM_CFX_ID: fivemCfxId,
          FIVEM_PLAYER_ID: fivemPlayerId,
          DISCORD_CHANNEL_ID: discordChannelId,
          TABLE_NAME: watcherTable.tableName,
        },
      }
    );

    watcherTable.grantReadWriteData(watcherFunction);

    new events.Rule(this, "WatcherSchedule", {
      schedule: events.Schedule.rate(cdk.Duration.minutes(1)),
      targets: [new targets.LambdaFunction(watcherFunction)],
    });
  }
}
