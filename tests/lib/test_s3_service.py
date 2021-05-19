# Copyright 2021 Splunk, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import unittest
from unittest import TestCase

from aws_log_collector.lib.s3_service import S3Service


class S3ServiceSuite(TestCase):

    def setUp(self) -> None:
        self.s3_service = S3Service()

    @unittest.skip("uses real bucket/key, must be run with proper AWS profile/permissions")
    def test_read_lines(self):
        # note that the following bucket and/or key may not exist anymore
        bucket = "integrations-team-logs"
        key = "logs/ABCDEF12345/s3/2020-11-25-12-27-23-EC390CD533CD5C56"
        for line in self.s3_service.read_lines(bucket, key):
            print(line)


if __name__ == "__main__":
    unittest.main()
