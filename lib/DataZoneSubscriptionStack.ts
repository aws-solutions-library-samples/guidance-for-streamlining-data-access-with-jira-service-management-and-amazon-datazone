/*
MIT No Attribution

Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to
use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
the Software, and to permit persons to whom the Software is furnished to do so.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
*/

import { readFileSync } from 'fs';
import {
  Duration,
  aws_iam,
  aws_lambda,
  aws_sqs,
  aws_kms,
  RemovalPolicy,
} from 'aws-cdk-lib';
import * as cdk from 'aws-cdk-lib';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import { SqsEventSource } from 'aws-cdk-lib/aws-lambda-event-sources';
import * as logs from 'aws-cdk-lib/aws-logs';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as stepfunctions from 'aws-cdk-lib/aws-stepfunctions';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';
import { subscriptionConfig } from '../config/SubscriptionConfig';
interface Props extends cdk.StackProps {
  applicationName: string;
  dzSubscriptionRole: iam.Role;
  dzEncryptionKeyArn: string | null;
  domainId: string;

}

export class DataZoneSubscriptionStack extends cdk.Stack {
  public readonly createGetIssueFunction: aws_lambda.Function;
  public readonly changeSubscriptionStatusFunction: aws_lambda.Function;
  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);
    const subscriptionConfigForStage = subscriptionConfig();
    /*****
      A secret storing external workflow access details
    ******/
    const secret = new secretsmanager.Secret(this, 'JiraCredentialsSecret', {
      secretName: `/${subscriptionConfigForStage.WORKFLOW_TYPE}/subscription-workflow/credentials`,
      secretObjectValue: {
        Admin: cdk.SecretValue.unsafePlainText('dummy value - please replace with currect value'),
        Token: cdk.SecretValue.unsafePlainText('dummy value - please replace with currect value'),
      },
      description: 'Contains the credentials for accessing Jira through its Rest API. Must be populated correctly before invoking the DZ subscription lambda. Format and content TBD. expected format is to have 2 values related to 2 keys: Token and Admin',
    });

    // Need to populate that secret manually, as its rotation cannot be controlled by us (external API credentials).
    NagSuppressions.addResourceSuppressions(secret, [{
      id: 'AwsSolutions-SMG4',
      reason: 'Need to populate that secret manually, as its rotation cannot be controlled by us (external API credentials). Suppress this warning.',
    }], true);


    /*****
      Execution role assumed by create-get-issue lambda
    ******/

    const dzGetSubscriptionInfoPermissions: aws_iam.PolicyStatement[] = [
      new aws_iam.PolicyStatement({
        actions: [
          'datazone:GetProject',
          'datazone:GetSubscriptionRequestDetails',
          'datazone:getUserProfile',
        ],
        resources: [`arn:aws:datazone:${this.region}:${this.account}:domain/${props.domainId}`],
      }),
    ];
    // Check if dzEncryptionKeyArn is not null, then the target Amazon DataZone domain is encrypted
    // We add the required permissions
    if (props.dzEncryptionKeyArn !== null) {
      // Cast dzEncryptionKeyArn to string and add it to the array
      dzGetSubscriptionInfoPermissions.push(
        new aws_iam.PolicyStatement({
          actions: [
            'kms:Encrypt',
            'kms:Decrypt',
            'kms:ReEncrypt',
            'kms:GenerateDataKey',
            'kms:DescribeKey',
          ],
          resources: [props.dzEncryptionKeyArn.toString()],
        }),
      );
    }
    const createGetIssueExecRole = new aws_iam.Role(this, 'CreateGetIssueRole', {
      roleName: 'DataZone-CreateGetIssueRole',
      assumedBy: new aws_iam.ServicePrincipal('lambda.amazonaws.com'),
      inlinePolicies: {
        dataZoneGetSubscriptionInfo: new aws_iam.PolicyDocument({
          statements: dzGetSubscriptionInfoPermissions,
        }),
        externalWorkflowSecretAccess: new aws_iam.PolicyDocument({
          statements: [
            new aws_iam.PolicyStatement({
              actions: [
                'secretsmanager:GetResourcePolicy',
                'secretsmanager:GetSecretValue',
                'secretsmanager:DescribeSecret',
                'secretsmanager:ListSecretVersionIds',
              ],
              resources: [
                secret.secretArn,
              ],
            }),
          ],
        }),

      },
    });
    NagSuppressions.addStackSuppressions(this,
      [{
        id: 'AwsSolutions-IAM5',
        reason: 'Suppress AwsSolutions-IAM5 on the known Action wildcards, while sending state machine task status.',
      }]);

    // Add a resource-based policy to restrict access to the secret
    secret.addToResourcePolicy(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      principals: [createGetIssueExecRole],
      actions: ['secretsmanager:GetSecretValue'],
      resources: ['*'],
    }));

    // Deny that still allows someone who connects to the console to
    // and set the secret even if not able to retrieve the value
    secret.addToResourcePolicy(new iam.PolicyStatement({
      effect: iam.Effect.DENY,
      principals: [new iam.AnyPrincipal()],
      actions: ['secretsmanager:GetSecretValue'],
      resources: ['*'],
      conditions: {
        ArnNotEquals: {
          'aws:PrincipalArn': createGetIssueExecRole.roleArn,
        },
      },
    }));

    /*****
      create-get-issue lambda
    ******/

    const assetCode = aws_lambda.Code.fromAsset('src/datazone-subscription/');

    const createGetIssueLambdaName = 'dataZone-create-get-issue-status';
    const createGetIssueLogGroup = this.createLogGroup(createGetIssueLambdaName);
    let create_get_issue_handler = 'handler_create_get_issue_status';
    if (subscriptionConfigForStage.RESILIENCY_ENABLED) {
      create_get_issue_handler = 'handler_create_get_issue_status_resilient';
    }

    // this would allow for the SQS call
    // is the default lambda creation doing that?
    this.createGetIssueFunction = new aws_lambda.Function(this, createGetIssueLambdaName, {
      functionName: createGetIssueLambdaName,
      runtime: aws_lambda.Runtime.PYTHON_3_12,
      role: createGetIssueExecRole,
      code: assetCode,
      handler: `${create_get_issue_handler}.lambda_handler`,
      timeout: Duration.seconds(900),
      memorySize: 128,
      reservedConcurrentExecutions: 1, // limit the concurrency to 1 in order to avoid API throttling when calling JIRA API Rest
      environment: {
        SUBSCRIPTION_DEFAULT_APPROVER_ID: subscriptionConfigForStage.SUBSCRIPTION_DEFAULT_APPROVER_ID,
        WORKFLOW_TYPE: subscriptionConfigForStage.WORKFLOW_TYPE,
        JIRA_DOMAIN: subscriptionConfigForStage.JIRA_DOMAIN,
        JIRA_PROJECT_KEY: subscriptionConfigForStage.JIRA_PROJECT_KEY,
        JIRA_ISSUETYPE_ID: '10004', // Task id
        JIRA_SECRET_ARN: secret.secretArn,
      },
      logGroup: createGetIssueLogGroup,
    });
    createGetIssueLogGroup.grantWrite(this.createGetIssueFunction);
    //secret.grantRead(this.createGetIssueFunction)
    /*****
      Execution role assumed by change-subscription-status lambda
    ******/
    const changeSubscriptionStatusExecRole = new aws_iam.Role(this, 'ChangeSubscriptionStatusRole', {
      roleName: `${props.applicationName}-ChangeSubscriptionStatusRole`,
      assumedBy: new aws_iam.ServicePrincipal('lambda.amazonaws.com'),
      inlinePolicies: {
        ChangeSubscriptionStatus: new aws_iam.PolicyDocument({
          statements: [
            new aws_iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'sts:AssumeRole',
              ],
              resources: [
                props.dzSubscriptionRole.roleArn,
              ],
            }),
          ],
        }),
      },
    });


    /*****
      change-subscription-status lambda
    ******/
    const changeSubscriptionLambdaName = 'dataZone-change-subscription-status';
    const changeSubscriptionLogGroup = this.createLogGroup(changeSubscriptionLambdaName);

    this.changeSubscriptionStatusFunction = new aws_lambda.Function(this, changeSubscriptionLambdaName, {
      functionName: changeSubscriptionLambdaName,
      runtime: aws_lambda.Runtime.PYTHON_3_12,
      role: changeSubscriptionStatusExecRole,
      code: assetCode,
      handler: 'handler_change_subscription_status.lambda_handler',
      timeout: Duration.seconds(300),
      memorySize: 128,
      environment: {
        SUBSCRIPTION_CHANGE_ROLE_ARN: props.dzSubscriptionRole.roleArn,
      },
      logGroup: changeSubscriptionLogGroup,
    });
    changeSubscriptionLogGroup.grantWrite(this.changeSubscriptionStatusFunction);

    /*****
      Step-function execution role
    ******/
    const subscriptionStateMachineLogGroup = new logs.LogGroup(this, 'SubscriptionStateMachineLogGroup');

    const subscriptionWorkflowExecRole = new aws_iam.Role(this, 'SubscriptionWorkflowStepFunctionRole', {
      assumedBy: new aws_iam.ServicePrincipal('states.amazonaws.com'),
      inlinePolicies: {
        MonitoringPolicy: new aws_iam.PolicyDocument({
          statements: [
            new aws_iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'xray:PutTraceSegments',
                'xray:PutTelemetryRecords',
                'xray:GetSamplingRules',
                'xray:GetSamplingTargets',
                'xray:GetTraceGraph',
                'xray:GetTraceSummaries',
              ],
              resources: [
                `arn:aws:states:${this.region}:${this.account}:stateMachine:*`,
              ],
            }),
            new aws_iam.PolicyStatement({
              resources: [subscriptionStateMachineLogGroup.logGroupArn],
              actions: [
                'logs:CreateLogDelivery',
                'logs:DeleteLogDelivery',
                'logs:DescribeLogGroups',
                'logs:DescribeResourcePolicies',
                'logs:GetLogDelivery',
                'logs:ListLogDeliveries',
                'logs:PutResourcePolicy',
                'logs:UpdateLogDelivery',
                'logs:CreateLogGroup',
                'logs:CreateLogStream',
                'logs:PutLogEvents',
              ],
              effect: aws_iam.Effect.ALLOW,
            }),
          ],
        }),

        LambdaInvokeScopedAccessPolicy: new aws_iam.PolicyDocument({
          statements: [
            new aws_iam.PolicyStatement({
              effect: iam.Effect.ALLOW,
              actions: [
                'lambda:InvokeFunction',
              ],
              resources: [
                this.changeSubscriptionStatusFunction.functionArn,
                this.createGetIssueFunction.functionArn,
              ],
            }),
          ],
        }),
      },
    });

    /*****
      Step-function
    ******/

    let sfnConfigFile = './config/dz-subscription-step-function.json';
    if (subscriptionConfigForStage.RESILIENCY_ENABLED) {
      sfnConfigFile = './config/dz-subscription-step-function-resilient.json';
    }
    // Load from file and replace ARN placeholders
    let stepFunctionDefinitionJson = readFileSync(sfnConfigFile, 'utf-8');
    stepFunctionDefinitionJson = stepFunctionDefinitionJson.replace(new RegExp('\\$\\{ChangeSubscriptionStatusLambdaARN\\}', 'g'), this.changeSubscriptionStatusFunction.functionArn);
    stepFunctionDefinitionJson = stepFunctionDefinitionJson.replace(new RegExp('\\"\\$\\{jiraPollingFrequency\\}\\"', 'g'), subscriptionConfigForStage.JIRA_POLLING_FREQUENCY.toString());

    // "${JiraResiliencyQueueARN}",
    if (subscriptionConfigForStage.RESILIENCY_ENABLED) {

      // add SQS queue
      const sqsKmsKey = new aws_kms.Key(this, 'kmskeyForSQS', {
        enableKeyRotation: false,
        removalPolicy: RemovalPolicy.DESTROY,
      });

      // Suppress the AwsSolutions-KMS5 warning for the sqsKmsKey resource
      NagSuppressions.addResourceSuppressions(sqsKmsKey, [
        {
          id: 'AwsSolutions-KMS5',
          reason: 'Do not activate automatic KMS key rotation unless a strict regulatory or compliance driver requires it. Every key costs $1/month. If keys automatically rotate annually, then the keys cost $1/month in year 1, $2/month in year 2, and $N/month in year N. This adds no meaningful protection because KMS encrypts data using envelope encryption.',
        },
      ], true);

      const DLQueue = new aws_sqs.Queue(this, 'DLQueue', {
        fifo: true,
        retentionPeriod: Duration.days(7),
        deliveryDelay: Duration.seconds(20),
        encryption: aws_sqs.QueueEncryption.KMS,
        encryptionMasterKey: sqsKmsKey,
        enforceSSL: true,
        contentBasedDeduplication: true,
      });
      const resiliencyQueue = new aws_sqs.Queue(this, 'JiraResiliencyQueue', {
        fifo: true,
        retentionPeriod: Duration.hours(24),
        visibilityTimeout: Duration.minutes(15),
        deliveryDelay: Duration.seconds(20),
        encryption: aws_sqs.QueueEncryption.KMS,
        encryptionMasterKey: sqsKmsKey,
        enforceSSL: true,
        contentBasedDeduplication: true,
        deadLetterQueue: {
          queue: DLQueue,
          maxReceiveCount: 6,
        },
      });
        // add SQS permissions for create get issue lambda
      createGetIssueExecRole.addToPolicy(
        new iam.PolicyStatement({
          actions: [
            'kms:Decrypt',
            'kms:Encrypt',
            'kms:GenerateDataKey',
            'kms:DescribeKey',
          ],
          resources: [sqsKmsKey.keyArn],
        }),
      );
      createGetIssueExecRole.addToPolicy(
        new iam.PolicyStatement({
          actions: [
            'sqs:DeleteMessage',
            'sqs:GetQueueAttributes',
            'sqs:ReceiveMessage',
            'sqs:ChangeMessageVisibility',
          ],
          resources: [resiliencyQueue.queueArn],
        }),
      );
      createGetIssueExecRole.addToPolicy(
        new iam.PolicyStatement({
          actions: ['states:SendTaskSuccess', 'states:SendTaskFailure'],
          resources: [
            'arn:aws:states:' +
                this.region +
                ':' +
                this.account +
                ':stateMachine:*',
          ],
        }),
      );
      // allow the function to be triggered by the SQS queue
      this.createGetIssueFunction .addEventSource(
        new SqsEventSource(resiliencyQueue, { batchSize: 5 }),
      );

      // add SQS permissions to the step function
      subscriptionWorkflowExecRole.addToPolicy(
        new aws_iam.PolicyStatement({
          resources: [sqsKmsKey.keyArn],
          actions: [
            'kms:Encrypt',
            'kms:Decrypt',
            'kms:ReEncrypt',
            'kms:GenerateDataKey',
            'kms:DescribeKey',
          ],
          effect: aws_iam.Effect.ALLOW,
        }),
      );
      subscriptionWorkflowExecRole.addToPolicy(
        new aws_iam.PolicyStatement({
          resources: [resiliencyQueue.queueArn],
          actions: ['sqs:DeleteMessage', 'sqs:SendMessage'],
          effect: aws_iam.Effect.ALLOW,
        }),
      );

      // add the queue arn to the sfn definition
      stepFunctionDefinitionJson = stepFunctionDefinitionJson.replace(new RegExp('\\$\\{JiraResiliencyQueueARN\\}', 'g'), resiliencyQueue.queueUrl);

    } else {
      // If the resiliency is not enabled, then the function create and get issue is directly called by the step function
      stepFunctionDefinitionJson = stepFunctionDefinitionJson.replace(new RegExp('\\$\\{CreateGetIssueLambdaARN\\}', 'g'), this.createGetIssueFunction.functionArn);
    }

    const subscriptionStateMachine = new stepfunctions.StateMachine(this, 'SubscriptionStateMachine', {
      definitionBody: stepfunctions.DefinitionBody.fromString(stepFunctionDefinitionJson),
      logs: {
        destination: subscriptionStateMachineLogGroup,
        level: stepfunctions.LogLevel.ALL,
        includeExecutionData: false,
      },
      role: subscriptionWorkflowExecRole,
      tracingEnabled: true,
      stateMachineType: stepfunctions.StateMachineType.STANDARD,
    });

    // Need to suppress AFTER creating the state machine, as implicitly, it adds a DefaultPolicy that has a * resource reference.
    NagSuppressions.addResourceSuppressions(subscriptionStateMachine.role, [{
      id: 'AwsSolutions-IAM5',
      reason: 'Cannot reference concrete resource. Suppress this warning.',
    }], true);

    /*****
      Event trigger
    ******/
    new events.Rule(this, 'SubscriptionEventTrigger', {
      eventPattern: {
        source: ['aws.datazone'],
        detailType: ['Subscription Request Created'],
      },
      targets: [new targets.SfnStateMachine(subscriptionStateMachine)],
    });
  }

  private createLogGroup(lambdaName: string): logs.LogGroup {
    return new cdk.aws_logs.LogGroup(this, `${lambdaName}-LogGroup`, {
      logGroupName: `/aws/lambda/${lambdaName}`,
      retention: 365,
      removalPolicy: cdk.RemovalPolicy.DESTROY,
    });
  }
}
