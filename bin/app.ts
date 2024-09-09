#!/usr/bin/env node
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

import 'source-map-support/register';
import * as cdk from 'aws-cdk-lib';
import { dataZoneConfig } from '../config/DataZoneConfig';
import { DataZoneSubscriptionAutomationRoleStack } from '../lib/DataZoneSubscriptionAutomationRoleStack';
import { DataZoneSubscriptionStack } from '../lib/DataZoneSubscriptionStack';
import { AwsSolutionsChecks } from 'cdk-nag';

const app = new cdk.App();
const configs = dataZoneConfig();
const applicationName = configs.DZ_APP_NAME;


const dzSubAutomationRoleStack = new DataZoneSubscriptionAutomationRoleStack(app, `${applicationName}DataZoneAccessStack`, {
  applicationName: applicationName,
  domainId: configs.DZ_DOMAIN_ID,
  dzEncryptionKeyArn: configs.DZ_ENCRYPTION_KEY_ARN,
});
new DataZoneSubscriptionStack(app, `${applicationName}DataZoneSubscriptionStack`, {
  applicationName: applicationName,
  dzSubscriptionRole: dzSubAutomationRoleStack.dzSubscriptionLambdaRole,
  dzEncryptionKeyArn: configs.DZ_ENCRYPTION_KEY_ARN,
  domainId: configs.DZ_DOMAIN_ID,
});
cdk.Aspects.of(app).add(new AwsSolutionsChecks({verbose: true}))