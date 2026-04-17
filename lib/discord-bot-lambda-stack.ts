import * as cdk from "aws-cdk-lib";
import { Construct } from "constructs";
import * as lambda from "aws-cdk-lib/aws-lambda";
import * as dotenv from "dotenv";

dotenv.config();

export class DiscordBotLambdaStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    const discordPublicKey = process.env.DISCORD_PUBLIC_KEY;
    if (!discordPublicKey) {
      throw new Error("DISCORD_PUBLIC_KEY must be set in .env or environment");
    }

    const dockerFunction = new lambda.DockerImageFunction(
      this,
      "DockerFunction",
      {
        code: lambda.DockerImageCode.fromImageAsset("./src"),
        memorySize: 1024,
        timeout: cdk.Duration.seconds(10),
        architecture: lambda.Architecture.X86_64,
        environment: {
          DISCORD_PUBLIC_KEY: discordPublicKey,
        },
      }
    );

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
  }
}
