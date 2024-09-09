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
import json
import os
import re
import time
import boto3
from botocore.exceptions import ClientError
import logging
import urllib3
from urllib3._collections import HTTPHeaderDict
from urllib3.exceptions import MaxRetryError
# import OpenSSL
from datetime import datetime, timezone
from enum import Enum
from common import create_workflow, create_issue_from_dz_subscription
from exceptions import ExternalWorkflowNotReachable, ExternalWorkflowRespondedWithNOK


logger = logging.getLogger()
logger.setLevel(logging.INFO)

secretsmanager_client = boto3.client("secretsmanager")
stepfunctions_client = boto3.client("stepfunctions")

# jira token and certificate
jira_token = ""
cwd = "/tmp/"
cert_file = cwd + "/client.cert"
key_file = cwd + "/client.key"

workflow_params = None

#JIRA_DEFAULT_APPROVER = os.environ["SUBSCRIPTION_DEFAULT_APPROVER_ID"]


URLLIB3_BACKOFF_FACTOR = 0.5
URLLIB3_RETRIES = 10

THROTTLE_SLEEP_TIME_SECS = 2



# Used in callback to tell statemachine if the response should be handled as success or error
class StepFunctionCallbackStatus(Enum):
    SUCCESS = 1
    FAILURE = 2

# =========CALLBACK=============
def statemachine_callback(callback_token, messageId, callback_status, response):
    try:
        logger.info(f"Calling stepfunctions with status {callback_status}")

        if callback_status == StepFunctionCallbackStatus.SUCCESS:
            sf_response = stepfunctions_client.send_task_success(
                taskToken=callback_token, output=json.dumps(response)
            )
        elif callback_status == StepFunctionCallbackStatus.FAILURE:
            sf_response = stepfunctions_client.send_task_failure(
                taskToken=callback_token, error=json.dumps(response)
            )

        logger.info(f"Sent callback for messageId {messageId}")

    except Exception as e:
        logger.error(
            f"statemachine_callback. Error during stepfunction callback. messageId {messageId} {e}. This can happen if the taskToken is wrong Or if the step function that created the taskToken is not running anymore."
        )

default_approver = os.environ['SUBSCRIPTION_DEFAULT_APPROVER_ID']
workflow_type = os.environ['WORKFLOW_TYPE']
# =========LAMBDA=============
def lambda_handler(event, context):
    # The lambda will process every record in the batch.
    # As soon it hits the first jira unreachable error, it will stop processing records.
    # The remaining records will be kept in the queue.

    response = None
    batch_item_failures = []
    sqs_batch_response = {}
    unprocessed = set()

    logger.info(f"=======================")
    logger.info(f"Lambda_jira_service - Event: {str(event)}")
    logger.info(f"=======================")
    logger.info(f"Batch size: {len(event['Records'])}")
    logger.info(f"WORKFLOW_TYPE={workflow_type}")
    external_workflow = create_workflow(workflow_type)
    
    # populate unprocessed set
    for record in event["Records"]:
        messageId = record["messageId"]
        unprocessed.add(messageId)

    # process each record
    for record in event["Records"]:
        logger.info(f"Lambda processing record: {record}")

        # throttle api requests to Jira
        time.sleep(THROTTLE_SLEEP_TIME_SECS)

        messageId = record["messageId"]
        messageGroupId = record["attributes"]["MessageGroupId"]
        messageBody = json.loads(record["body"])
        callback_token = messageBody["TaskToken"]
        command = messageBody["Command"]
        payload = messageBody["Payload"]

        logger.info(f"Lambda processing payload: {payload}")

        # execute command specified in the payload
        try:
            if command == "CREATE_ISSUE":
                logger.info(f"Creating issue for DZ subscription. {messageId}")
                #response = create_issue(payload)
                issue_key, dz_subscription = create_issue_from_dz_subscription(external_workflow, payload, default_approver)
                response_data = {
                    'statusCode': 200,
                    'domain_id': dz_subscription.domain_id,
                    'subscription_req_id': dz_subscription.subscription_req_id,
                    'issue_key': issue_key
                }
                statemachine_callback(
                    callback_token,
                    messageId,
                    StepFunctionCallbackStatus.SUCCESS,
                    response_data,
                )
                unprocessed.remove(record["messageId"])

            elif command == "GET_ISSUE_STATUS":
                issue_key = payload.get("issue_key")
                if not issue_key:
                    raise ValueError("Missing 'issue_key' in the event data.")
                
                logger.info(f"Getting issue status for issue key {issue_key}.")
                #response = get_issue_status(payload)
                approval_status, approver = external_workflow.get_issue_status(issue_key)
                response_data = {
                    'statusCode': 200,
                    'domain_id': payload.get('domain_id'),
                    'subscription_req_id': payload.get('subscription_req_id'),
                    'issue_key': issue_key,
                    'approver': approver,
                    'approval_status': approval_status,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                statemachine_callback(
                    callback_token,
                    messageId,
                    StepFunctionCallbackStatus.SUCCESS,
                    response_data,
                )
                unprocessed.remove(record["messageId"])

        except ExternalWorkflowRespondedWithNOK as e:
            # let step function continue on fail branch
            # pop the message from the queue
            logger.error(f"lambda_handler: Caught ExternalWorkflowRespondedWithNOK. {e}")
            response = f"ExternalWorkflowRespondedWithNOK. {e}"
            statemachine_callback(
                callback_token, messageId, StepFunctionCallbackStatus.FAILURE, response
            )
            unprocessed.remove(record["messageId"])

        except ExternalWorkflowNotReachable as e:
            # stop all processing and do not pop any remaining messages in batch
            logger.error(
                f"lambda_handler: Caught ExternalWorkflowNotReachable. {e}. Will keep message {messageId} to Q and retry."
            )
            raise e

        except Exception as e:
            logger.error(f"lambda_handler: Caught Error. {e}")
            response = f"Error. {e}"
            statemachine_callback(
                callback_token, messageId, StepFunctionCallbackStatus.FAILURE, response
            )
            unprocessed.remove(record["messageId"])

    # all records have been processed OR ExternalWorkflowNotReachable was detected
    for messageId in unprocessed:
        logger.info(f"Unprocessed messages: {len(unprocessed)}")
        batch_item_failures.append({"itemIdentifier": messageId})

    sqs_batch_response["batchItemFailures"] = batch_item_failures
    logger.info(f"Jira service lambda finished processing batch.")
    logger.info(
        f"Records in batch = {len(event['Records'])}. Unprocessed records = {len(batch_item_failures)}"
    )

    return sqs_batch_response
