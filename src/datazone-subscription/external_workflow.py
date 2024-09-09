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

from abc import abstractmethod
from data_zone_subscription import DataZoneSubscription
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class IExternalWorkflow():
    '''Represents an external workflow system and all the interactions possible with it.'''
    @abstractmethod
    def create_issue(self, dz_subscription: DataZoneSubscription, assignee):
        '''Creates an issue in the external workflow system. Returns an id (issue_key) for the newly created issue.'''
        pass
    
    @abstractmethod
    def get_issue_status(self, issue_key):
        '''Retrieves the current issue status from the external workflow system. Returns a tuple of approval status and approver.'''
        pass
