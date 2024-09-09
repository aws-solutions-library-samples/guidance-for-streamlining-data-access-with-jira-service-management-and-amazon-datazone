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
Defines the lambda handler triggered by the DZ subscription step function to (A) either create a new external workflow ticket,
or (B) to check if the ticket has been Accepted or Rejected.

(A) Command "CREATE_ISSUE"
It parses the event and gets all the necessary information from DataZone in order to create a ticket for a DataZone subscription request.

(B) Command "GET_ISSUE_STATUS"
This function also gets called repeatedly by the step function to check if the ticket has been resolved (Accepted or Rejected). This is a polling mechanism.
"""


import os
import logging

from common import create_workflow, create_issue_from_dz_subscription

logger = logging.getLogger()
logger.setLevel(logging.INFO)

default_approver = os.environ['SUBSCRIPTION_DEFAULT_APPROVER_ID']
workflow_type = os.environ['WORKFLOW_TYPE']


def lambda_handler(event, context):
    logger.info(f"=======================")
    logger.info(f"create-get-issue-status - Event: {str(event)}")
    logger.info(f"=======================")
    logger.info(f"SUBSCRIPTION_DEFAULT_APPROVER_ID={default_approver}")
    logger.info(f"WORKFLOW_TYPE={workflow_type}")
    

    external_workflow = create_workflow(workflow_type)

    command = event.get('Command', None)
    event = event.get('Payload', None)

    logger.info(f"Command = {command}")

    if command == "CREATE_ISSUE":
        logger.info("Creating issue for DZ subscription.")
        issue_key, dz_subscription = create_issue_from_dz_subscription(external_workflow, event, default_approver)
        response_data = {
            'statusCode': 200,
            'domain_id': dz_subscription.domain_id,
            'subscription_req_id': dz_subscription.subscription_req_id,
            'issue_key': issue_key
        }
    elif command == "GET_ISSUE_STATUS":
        issue_key = event.get("issue_key")
        if not issue_key:
            raise ValueError("Missing 'issue_key' in the event data.")
        
        logger.info(f"Getting issue status for issue key {issue_key}.")
        approval_status, approver = external_workflow.get_issue_status(issue_key)
        response_data = {
            'statusCode': 200,
            'domain_id': event.get('domain_id'),
            'subscription_req_id': event.get('subscription_req_id'),
            'issue_key': issue_key,
            'approver': approver,
            'approval_status': approval_status
        }
    else:
        raise ValueError("Command not defined under expected key 'command' or command has invalid value. Only CREATE_ISSUE or GET_ISSUE_STATUS are allowed.")

    return response_data