"""
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
"""

"""
Defines common functions between handlers
"""
import os
import logging

from data_zone_subscription import DataZoneSubscription
from mock_test_workflow import MockTestWorkflow
from jira_workflow import JiraWorkflow

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def create_workflow(workflow_type_string):
    if workflow_type_string == "MOCK_ACCEPT":
        return MockTestWorkflow(True)
    elif workflow_type_string ==  "MOCK_REJECT":
        return MockTestWorkflow(False)
    elif workflow_type_string == "JIRA":
        JIRA_DOMAIN = os.environ['JIRA_DOMAIN']
        JIRA_URL = f"https://{JIRA_DOMAIN}/rest/api/latest/issue/"
        JIRA_PROJECT_KEY = os.environ['JIRA_PROJECT_KEY']
        JIRA_ISSUETYPE_ID = os.environ['JIRA_ISSUETYPE_ID']
        JIRA_SECRET_ARN = os.environ['JIRA_SECRET_ARN']
        return JiraWorkflow(JIRA_URL, JIRA_SECRET_ARN, JIRA_PROJECT_KEY, JIRA_ISSUETYPE_ID)
    else:
        raise RuntimeError(f"Unsupported workflow type {workflow_type_string}, try one of the following types: MOCK_ACCEPT, MOCK_REJECT, JIRA")

def create_issue_from_dz_subscription(external_workflow, event, default_approver):
    '''Obtains more details about the subscription information from DataZone based on the input event, then creates a new issue in the external workflow system.'''
    dz_subscription = DataZoneSubscription.fromEvent(event)

    dz_subscription.get_subscription_info()
    
    issue_key = external_workflow.create_issue(dz_subscription, default_approver)

    return issue_key, dz_subscription

