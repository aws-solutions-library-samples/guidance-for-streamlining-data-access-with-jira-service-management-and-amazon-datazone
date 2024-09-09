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

import * as cdk from 'aws-cdk-lib';
import * as iam from 'aws-cdk-lib/aws-iam';
import * as kms from 'aws-cdk-lib/aws-kms';
import { NagSuppressions } from 'cdk-nag';
import { Construct } from 'constructs';

interface Props extends cdk.StackProps {
  applicationName: string;
  domainId: string;
  dzEncryptionKeyArn: string | null;
}

export class DataZoneSubscriptionAutomationRoleStack extends cdk.Stack {


  public dzSubscriptionLambdaRole: iam.Role;

  constructor(scope: Construct, id: string, props: Props) {
    super(scope, id, props);

    function suppressForRole(role: cdk.aws_iam.Role) {
      NagSuppressions.addResourceSuppressions(role, [{
        id: 'AwsSolutions-IAM5',
        reason: 'This is the way AWS documentation recomends. Suppress this warning.',
      }],
      true,
      );
    }


    const dzSubscriptionManagerAccessPolicy = new cdk.aws_iam.PolicyDocument({
      statements: [
        new cdk.aws_iam.PolicyStatement({
          actions: [
            'datazone:RejectSubscriptionRequest',
            'datazone:GetProject',
            'datazone:ListProjects',
            'datazone:AcceptSubscriptionRequest',
            'datazone:GetSubscriptionRequestDetails',
            'datazone:ListSubscriptions',
            'datazone:ListSubscriptionRequests',
            'datazone:GetSubscription',
            'datazone:GetEnvironment',
            'datazone:ListDomains',
          ],
          resources: [`arn:aws:datazone:${this.region}:${this.account}:domain/${props.domainId}`],
        }),
      ],
    });
    // Check if dzEncryptionKeyArn is not null
    if (props.dzEncryptionKeyArn !== null) {
      // Cast dzEncryptionKeyArn to string and add the permissions to use the key
      dzSubscriptionManagerAccessPolicy.addStatements(
        new cdk.aws_iam.PolicyStatement({
          actions: [
            'kms:Decrypt',
            'kms:GenerateDataKey',
            'kms:DescribeKey',
          ],
          resources: [props.dzEncryptionKeyArn.toString()],
        }),
      );
    }


    const dzSubscriptionManagerRole = new iam.Role(this, `${props.applicationName}DzSubManagerRole`, {
      roleName: 'dzLambdaSubscriptionManagerRole',
      assumedBy: new iam.ServicePrincipal('lambda.amazonaws.com'),
      inlinePolicies: {
        dzSubscriptionManagerAccessPolicy,
      },
    });

    // NOTE: The dzSubscriptionManagerRole's trust policy must explicitly allow the ChangeSubscriptionStatus role to assume it.
    // However, the ChangeSubscriptionStatus role is created later, thus we cannot reference its ARN here directly.
    // Workaround is to use StringLike condition with its name.
    dzSubscriptionManagerRole.assumeRolePolicy?.addStatements(new iam.PolicyStatement({
      effect: iam.Effect.ALLOW,
      actions: ['sts:AssumeRole'],
      principals: [new iam.ArnPrincipal('*')],
      conditions: {
        StringLike: {
          'aws:PrincipalArn':
            [
              `arn:${this.partition}:iam::${this.account}:role/${props.applicationName}-ChangeSubscriptionStatus*`,
            ],
        },
      },
    }));

    this.dzSubscriptionLambdaRole = dzSubscriptionManagerRole;

    suppressForRole(dzSubscriptionManagerRole);

  }
}