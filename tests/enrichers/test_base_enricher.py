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
from unittest.mock import Mock

from aws_log_collector.enrichers.base_enricher import BaseEnricher
from tests.utils import lambda_context, FORWARDER_FUNCTION_NAME, AWS_REGION, AWS_ACCOUNT_ID, \
    FORWARDER_FUNCTION_VERSION


class BaseEnrichmentSuite(TestCase):

    def setUp(self) -> None:
        self.tag_cache_mock = Mock()
        self.sfx_metrics = Mock()
        self.log_enricher = BaseEnricher(self.tag_cache_mock)

    def test_context_metadata(self):
        actual = self.log_enricher.get_context_metadata(lambda_context())

        expected = {
            "logForwarder": f"{FORWARDER_FUNCTION_NAME}:{FORWARDER_FUNCTION_VERSION}",
            "region": AWS_REGION,
            "awsAccountId": AWS_ACCOUNT_ID
        }
        self.assertEqual(expected, actual)

    def test_get_tags(self):
        expected_tags = {"tag1": "val1", "tag2": "val2"}
        self.tag_cache_mock.get.return_value = expected_tags

        tags = self.log_enricher.get_tags("some:arn", self.sfx_metrics)

        self.assertEqual(expected_tags, tags)

    def test_get_tags_when_no_tags_for_arn(self):
        self.tag_cache_mock.get.return_value = None

        tags = self.log_enricher.get_tags("some:arn", self.sfx_metrics)

        self.assertEqual(None, tags)

    def test_merge(self):
        metadata = {"a": "1", "b": "2"}
        parent_tags = {"c": "3", "d": "4", "b": "ignored"}
        child_tags = {"e": "5", "f": "6", "a": "ignored", "c": "ignored"}

        merged = self.log_enricher.merge(metadata, parent_tags, child_tags)

        expected = {"a": "1", "b": "2", "c": "3", "d": "4", "e": "5", "f": "6"}
        self.assertEqual(expected, merged)


if __name__ == "__main__":
    unittest.main()
