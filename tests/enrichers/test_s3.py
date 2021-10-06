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

from aws_log_collector.enrichers.s3 import S3LogsEnricher

BUCKET_TAGS = {"a": "1", "b": "2"}
OBJECT_TAGS = {"aa": "11", "bb": "22"}
COMMON_METADATA = {"foo": "bar"}
BUCKET = "bucket1"
OBJECT_KEY = "key1"


class S3EnrichmentSuite(TestCase):

    def setUp(self) -> None:
        self.tag_cache_mock = Mock()
        self.sfx_metrics = Mock()
        self.log_enricher = S3LogsEnricher(self.tag_cache_mock)

    def test_s3_enrichment_with_bucket_and_object_tags(self):
        # GIVEN
        self.tag_cache_mock.get.side_effect = lambda arn, _: OBJECT_TAGS if arn.endswith(OBJECT_KEY) else BUCKET_TAGS
        arns = [
            ("bucketArn", f"arn:aws:s3:::{BUCKET}"),
            ("objectArn", f"arn:aws:s3:::{BUCKET}/{OBJECT_KEY}"),
        ]

        # WHEN
        logLine = Mock()
        logLine.arns = arns
        actual = self.log_enricher.get_metadata(logLine, COMMON_METADATA, self.sfx_metrics, False)

        # THEN
        expected = {
            "bucketArn": f"arn:aws:s3:::{BUCKET}",
            "objectArn": f"arn:aws:s3:::{BUCKET}/{OBJECT_KEY}",
            **COMMON_METADATA,
            **BUCKET_TAGS,
            **OBJECT_TAGS
        }
        self.assertEqual(expected, actual)

    def test_s3_enrichment_without_object_key(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = BUCKET_TAGS
        arns = [("bucketArn", f"arn:aws:s3:::{BUCKET}")]

        # WHEN
        logLine = Mock()
        logLine.arns = arns
        actual = self.log_enricher.get_metadata(logLine, COMMON_METADATA, self.sfx_metrics, False)

        # THEN
        expected = {
            "bucketArn": f"arn:aws:s3:::{BUCKET}",
            **COMMON_METADATA,
            **BUCKET_TAGS
        }
        self.assertEqual(expected, actual)

    def test_s3_enrichment_without_tags(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = None
        arns = [
            ("bucketArn", f"arn:aws:s3:::{BUCKET}"),
            ("objectArn", f"arn:aws:s3:::{BUCKET}/{OBJECT_KEY}"),
        ]

        # WHEN
        logLine = Mock()
        logLine.arns = arns
        actual = self.log_enricher.get_metadata(logLine, COMMON_METADATA, self.sfx_metrics, False)

        # THEN
        expected = {
            "bucketArn": f"arn:aws:s3:::{BUCKET}",
            "objectArn": f"arn:aws:s3:::{BUCKET}/{OBJECT_KEY}",
            **COMMON_METADATA
        }
        self.assertEqual(expected, actual)


if __name__ == "__main__":
    unittest.main()
