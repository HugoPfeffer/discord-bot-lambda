import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dynamodb from "aws-cdk-lib/aws-dynamodb";
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

    const pagoLeaderboardTable = new dynamodb.Table(this, "PagoLeaderboardTable", {
      tableName: "pago-leaderboard",
      partitionKey: { name: "guild_id", type: dynamodb.AttributeType.STRING },
      sortKey:      { name: "user_id",  type: dynamodb.AttributeType.STRING },
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
          PAGO_TABLE_NAME: pagoLeaderboardTable.tableName,
        },
      }
    );

    mapTrackerTable.grantReadWriteData(dockerFunction);
    pagoLeaderboardTable.grantReadWriteData(dockerFunction);

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

    // NOTE: A CloudWatch MetricFilter on the Lambda's log group (counting
    // ConditionalCheckFailedException) was specified in the original plan
    // but couldn't be created at deploy time — the Lambda's log group is
    // created lazily on first invocation, so the filter has nothing to
    // attach to during initial deploy. Add it manually after first invoke,
    // or in a follow-up PR once we upgrade CDK and can use the L2 Function
    // logGroup property to materialize it eagerly.
  }
}
