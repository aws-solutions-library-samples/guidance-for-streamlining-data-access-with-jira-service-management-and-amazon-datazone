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

from enum import Enum
import json
import logging
import urllib3
from urllib3._collections import HTTPHeaderDict
import base64
import boto3
from botocore.exceptions import ClientError
from urllib3.exceptions import MaxRetryError
from external_workflow import IExternalWorkflow
from data_zone_subscription import DataZoneSubscription
from exceptions import ExternalWorkflowNotReachable, ExternalWorkflowRespondedWithNOK

logger = logging.getLogger()
logger.setLevel(logging.INFO)

URLLIB3_RETRIES = 10
URLLIB3_BACKOFF_FACTOR = 0.5

# Create a class that implements the interface
class JiraWorkflow(IExternalWorkflow):
    def __init__(self, url, secret_arn, project_key, issue_type):
        self.url = url
        self.admin, token = self.__get_jira_creds(secret_arn)
        self.project_key = project_key
        self.issue_type = issue_type

        retries = urllib3.Retry(
            total=URLLIB3_RETRIES, backoff_factor=URLLIB3_BACKOFF_FACTOR
        )
        self.http = urllib3.PoolManager(
            retries=retries,
        )
        self.http = urllib3.PoolManager(
            retries=retries,
            cert_reqs='CERT_REQUIRED', # endorce use of certificate 
            # you can add your certificate bundle if requireed 
        )
        
        """
        # certificate authentification
        # add the certificate if required (example: in case of a Jira instance on-premises)
        http = urllib3.PoolManager(
                cert_reqs="CERT_REQUIRED", key_file=key_file, cert_file=cert_file
        )"""
        self.headers = self.__get_headers(self.admin, token)

    def __get_jira_creds(self, secret_arn):

        try:
            secretsmanager_client = boto3.client("secretsmanager")
            response = secretsmanager_client.get_secret_value(SecretId=secret_arn)
            secret = json.loads(response["SecretString"])
            jira_token = secret["Token"]
            admin = secret["Admin"]
            return admin, jira_token

        except ClientError as err:
            error_message = f"Couldn't get value for secret. {err}\n"
            error_message = (
                error_message
                + "create a secret in secret manager of the DataZone domain account, specify 2 values under 2 keys: Admin Token.\n"
            )
            error_message = (
                error_message
                + "The project admin can be an email of an admin member and project token can be generated and retrieved from jira project settings"
            )
            logger.error(error_message)
            raise

    def __get_headers(self, admin, token):
        try:
            headers = HTTPHeaderDict()
            headers.add("Content-Type", "application/json")
            # TODO: adapt auth with requires a certificate
            # headers.add("Authorization", "Bearer " + token)
            credentials = base64.b64encode(f"{admin}:{token}".encode("utf-8")).decode(
                "utf-8"
            )

            headers.add("Authorization", f"Basic {credentials}")
            return headers
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None

    def create_issue(self, dz_subscription: DataZoneSubscription, assignee):

        url = self.url
        try:
            payload = json.dumps(
                {
                    "fields": {
                        "project": {"key": self.project_key},
                        "assignee": {"id": assignee},
                        "summary": "DataZone Subscription Request Created for "
                        + dz_subscription.table_catalog_name,
                        "description": "{*}Request type:{*} DataZone Subscription Request Created on "
                        + "{*}domain Id:{*} "
                        + dz_subscription.domain_id
                        + "\n \n {*}With request information{*} : \n{*}Request Id:{*} "
                        + dz_subscription.subscription_req_id
                        + " \n{*}Requester Details:{*} "
                        + dz_subscription.requester_details
                        + " \n{*}Requester Type:{*} "
                        + dz_subscription.requester_type
                        + " \n{*}Project subscriber:{*} "
                        + dz_subscription.project_name
                        + " \n{*}Request Date:{*}: "
                        + dz_subscription.request_date
                        + " \n{*}Request Reason:{*} "
                        + dz_subscription.request_reason
                        + " \n\n{*}Details about target data:{*}  \n"
                        + " \n{*}Target Data Type:{*} "
                        + dz_subscription.data_type
                        + "\n{*}Data Technical Name:{*} "
                        + dz_subscription.table_tech_name
                        + "\n{*}Data Table Arn:{*} "
                        + dz_subscription.table_arn
                        + "\n{*}Data Database Name:{*} "
                        + dz_subscription.db_name
                        + "\n{*}Data Bucket:{*} "
                        + dz_subscription.bucket_location
                        + "\n{*}Data Project Name:{*} "
                        + dz_subscription.owner_project_name,
                        "issuetype": {"id": self.issue_type},
                        "labels": [dz_subscription.owner_project_name],
                    }
                }
            )

            http = self.http
            headers = self.headers

            response = http.request("POST", url, body=payload, headers=headers)

            if response.status == 201:
                json_data = json.loads(response.data.decode("utf-8"))
                logger.info(f"Created new issue. Issue key: {json_data['key']}")
                return json_data["key"]
            elif response.status == 400:
                # put metric for data access request
                raise ExternalWorkflowRespondedWithNOK(
                    f"Error. Could not create a jira issue. Server responded with {response.status}. Bad request. This can happen if request is missing required fields, has invalid field values or is invalid for any other reason."
                )
            elif response.status == 401:
                raise ExternalWorkflowRespondedWithNOK(
                    f"Error. Could not create a jira issue. Server responded with {response.status}. Unauthorized. The authentication credentials are incorrect or missing."
                )
            elif response.status == 403:
                raise ExternalWorkflowRespondedWithNOK(
                    f"Error. Could not create a jira issue. Server responded with {response.status}. Forbidden. The user does not have the necessary permission to create a ticket."
                )
            elif response.status == 429:
                raise ExternalWorkflowNotReachable(
                    f"Error. Could not get issue. Server responded with {response.status}. Jira Rate Limit Response."
                )
            else:
                raise ExternalWorkflowRespondedWithNOK(
                    f"Error. Could not create a jira issue. Server responded with {response.status}."
                )
        except MaxRetryError as err:
            logger.error(f"Jira request failed. MaxRetryError Exception {err}")
            raise ExternalWorkflowNotReachable
        except Exception as e:
            logger.error(
                f"create_issue(). General exception during issue creation: {e}.")
            raise e
            # return 'PROBLEM IN EXECUTING ISSUE CREATION'

    def get_issue_status(self, issue_key):
        try:
            url = self.url + issue_key
            approval_status = None
            approver = None

            http = self.http
            headers = self.headers

            response = http.request("GET", url, headers=headers)
            print(f"response status {response.status}")
            if response.status == 200:
                response_json = json.loads(response.data)
                approval_status = (
                    response_json.get("fields", {}).get("status", {}).get("name", None)
                )
                approver = (
                    response_json.get("fields", {})
                    .get("assignee", {})
                    .get("displayName", None)
                )

            elif response.status == 401:
                raise ExternalWorkflowRespondedWithNOK(
                    f"Error. Could not get issue. Server responded with {response.status}. Unauthorized. The authentication credentials are incorrect or missing."
                )
            elif response.status == 404:
                raise ExternalWorkflowRespondedWithNOK(
                    f"Error. Could not get issue. Server responded with {response.status}. Not Found. Returned if the issue is not found or the user does not have permission to view it."
                )
            elif response.status == 429:
                raise ExternalWorkflowRespondedWithNOK(
                    f"Error. Could not get issue. Server responded with {response.status}. Jira Rate Limit Response."
                )
            else:
                raise ExternalWorkflowRespondedWithNOK(
                    f"Error. Could not create a jira issue. Server responded with {response.status}."
                )

            return approval_status, approver

        except MaxRetryError as err:
            logger.error(f"Jira request failed. MaxRetryError Exception {err}")
            raise ExternalWorkflowNotReachable
