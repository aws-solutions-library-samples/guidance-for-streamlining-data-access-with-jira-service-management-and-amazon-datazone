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
import boto3
import botocore


class DataZoneSubscription:
    '''Represents all information for a DZ subscription and performs all API calls for obtaining that info.'''
    @staticmethod
    def fromEvent(event):
        subscription = DataZoneSubscription()
        subscription.__parse_dz_event(event=event)
        return subscription

    def __init__(self, domain_id=None, sub_request_id=None, role_arn=None) -> None:
        '''Constructor getting details as parameters.'''
        try:
            if role_arn is None:
                self.dz_client = boto3.client("datazone")
            else:
                self.dz_client = self.__assume_admin_role(role_arn)

            self.domain_id = domain_id
            self.subscription_req_id = sub_request_id

        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"An error occurred: {error_code} - {error_message}")
            raise e

    def get_subscription_info(self):
        self.__get_project_name_from_id()

        # Issue currently noticed on the documentation, this API call only works with 'SSO' as an input for both IAM and SSO objects
        # I raised an issue for it

        self.__get_user_from_dz_id('SSO')

        self.__get_subscription_details()

    def accept_subscription(self, acceptance_reason):
        try:
            return self.dz_client.accept_subscription_request(
                decisionComment=acceptance_reason,
                domainIdentifier=self.domain_id,
                identifier=self.subscription_req_id
            )
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"An error occurred: {error_code} - {error_message}")
            raise e

    def reject_subscription(self, rejection_reason):
        try:
            return self.dz_client.reject_subscription_request(
                decisionComment=rejection_reason,
                domainIdentifier=self.domain_id,
                identifier=self.subscription_req_id
            )
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"An error occurred: {error_code} - {error_message}")
            raise e

    def __assume_admin_role(self, role_arn):
        sts_client = boto3.client('sts')
        assumed_role = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName="AssumeRoleSessionForDZSubGrant"
        )

        credentials = assumed_role['Credentials']
        dz_api_client = boto3.client(
            "datazone",
            aws_access_key_id=credentials["AccessKeyId"],
            aws_secret_access_key=credentials["SecretAccessKey"],
            aws_session_token=credentials["SessionToken"]
        )
        return dz_api_client

    def __parse_dz_event(self, event):
        # Parse metadata
        self.domain_id = event['detail']['metadata']['domain']
        self.subscription_req_id = event['detail']['metadata']['id']
        self.project_subscriber_id = event['detail']['metadata']['owningProjectId']

        # Parse data
        self.requester_id = event['detail']['data']['requesterId']
        self.data_owner_project = event['detail']['data']['subscribedListings'][0]['ownerProjectId']
        self.request_date = event['time']

    def __get_db_from_arn(self, table_arn):
        table_arn_splitted = table_arn.split('/')
        return table_arn_splitted[1]

    def __get_subscription_details(self):
        response = self.dz_client.get_subscription_request_details(
            domainIdentifier=self.domain_id,
            identifier=self.subscription_req_id
        )

        subscribed_listings = response.get('subscribedListings', [])
        if not subscribed_listings:
            raise ValueError(
                "No subscribed listings found in the response.")

        target_data_info = subscribed_listings[0].get(
            'item', {}).get('assetListing', {})
        if not target_data_info:
            raise ValueError(
                "No target data information found in the response.")

        target_data_form = json.loads(target_data_info.get('forms', {}))
        if not target_data_form:
            raise ValueError("No target data form found in the response.")

        target_data_source_form = target_data_form.get(
            'DataSourceReferenceForm', {}).get('dataSourceIdentifier', {})
        if not target_data_source_form:
            raise ValueError(
                "No target data source form found in the response.")

        self.account = target_data_source_form.get(
            'GlueConfigurationForm', {}).get('accountId')
        self.region = target_data_form.get(
            'GlueTableForm', {}).get('region')
        self.table_tech_name = target_data_form.get(
            'GlueTableForm', {}).get('tableName')
        self.table_arn = target_data_form.get(
            'GlueTableForm', {}).get('tableArn')
        self.db_name = self.__get_db_from_arn(self.table_arn)
        self.bucket_location = target_data_form.get(
            'GlueTableForm', {}).get('sourceLocation')
        self.owner_project_name = subscribed_listings[0].get(
            'ownerProjectName')
        self.table_catalog_name = subscribed_listings[0].get('name')
        self.request_reason = response.get('requestReason')
        self.data_type = target_data_source_form.get(
            'DataSourceCommonForm', {}).get('type')

    def __get_user_from_dz_id(self, user_type):
        response = self.dz_client.get_user_profile(
            domainIdentifier=self.domain_id,
            type=user_type,
            userIdentifier=self.requester_id
        )
        self.requester_details = ''
        self.requester_type = response.get('type')

        if self.requester_type == 'SSO':
            self.requester_details = response.get(
                'details', {}).get('sso', {}).get('username')

        elif self.requester_type == 'IAM':
            self.requester_details = response.get(
                'details', {}).get('iam', {}).get('arn')

    def __get_project_name_from_id(self):
        try:
            response = self.dz_client.get_project(
                domainIdentifier=self.domain_id,
                identifier=self.project_subscriber_id
            )
            self.project_name = response['name']
        except botocore.exceptions.ClientError as e:
            error_code = e.response['Error']['Code']
            error_message = e.response['Error']['Message']
            print(f"An error occurred: {error_code} - {error_message}")
            raise e
