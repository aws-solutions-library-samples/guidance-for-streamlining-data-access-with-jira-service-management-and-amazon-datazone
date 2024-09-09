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

import logging

from external_workflow import IExternalWorkflow
from data_zone_subscription import DataZoneSubscription

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class MockTestWorkflow(IExternalWorkflow):
    '''A mock test external workflow doing nothing but returning fixed values. Just for testing purposes.'''
    def __init__(self, accept: bool) -> None:
        self.accept = accept

    def create_issue(self, dz_subscription: DataZoneSubscription, assignee):
        logger.info(f"Mock Test Workflow: create_issue for assignee {assignee}")

        return 'IssueId1234567'


    def get_issue_status(self, issue_key):
        logger.info(f"Mock Test Workflow: get_issue_status for issue_key {issue_key}")

        return ('Accepted' if self.accept else 'Rejected', 'assignee')
