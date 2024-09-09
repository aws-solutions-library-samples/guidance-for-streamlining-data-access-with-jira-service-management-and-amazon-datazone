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
Defines the lambda handler triggered by the DZ subscription step function to update the subscription status when the status of the external workflow ticket has changed.
"""
import logging
import os

from data_zone_subscription import DataZoneSubscription

logger = logging.getLogger()
logger.setLevel(logging.INFO)


subscription_change_role_arn = os.environ['SUBSCRIPTION_CHANGE_ROLE_ARN']


def lambda_handler(event, context):
    logger.info(f"=======================")
    logger.info(f"change-subscription-status - Event: {str(event)}")
    logger.info(f"=======================")
    logger.info(f"SUBSCRIPTION_CHANGE_ROLE_ARN={subscription_change_role_arn}")
    
    domain_id = event['Payload']['domain_id']
    issue_key = event['Payload']['issue_key']
    sub_req_id = event['Payload']['subscription_req_id']
    approver = event['Payload']['approver']
    approval_status = event['Payload']['approval_status']
    status_change_reason = f'Status of subscription changed to {approval_status} by {approver} based on issue {issue_key}.'

    dz_subscription = DataZoneSubscription(domain_id, sub_req_id, subscription_change_role_arn)

    if approval_status == 'Rejected':
        logger.info(f"Rejecting subscription request {sub_req_id} based on issue {issue_key}.")
        response = dz_subscription.reject_subscription(status_change_reason)
        logger.info(f"Rejection response: {str(response)}")

    elif approval_status == 'Accepted':
        logger.info(f"Approving subscription request {sub_req_id} based on issue {issue_key}.")
        response = dz_subscription.accept_subscription(status_change_reason) 
        logger.info(f"Approval response: {str(response)}")
        
    else:
        logger.info(f"Approval status is neither 'Approved' nor 'Rejected', skipping without changing subscription status.")
        status_change_reason = f'No relevant change in status.'

    return {
        'statusCode': 200,
        'status_change_reason': status_change_reason
    }
