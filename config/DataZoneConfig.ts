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

import { IDataZoneConfig } from './Types';


export const dataZoneConfig = (): IDataZoneConfig => {
  const environmentMapper: {
    DZ_APP_NAME: string;
    DZ_DOMAIN_ID: string;
    DZ_ENCRYPTION_KEY_ARN: string | null;
  } = {
    DZ_APP_NAME: 'ExternalWorkflowInteg',
    DZ_DOMAIN_ID: 'DZ_DOMAIN_ID_PLACEHOLDER',
    DZ_ENCRYPTION_KEY_ARN: null,
  };
  return environmentMapper;
};