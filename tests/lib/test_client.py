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

from unittest.case import TestCase
from unittest.mock import MagicMock, call, Mock

from aws_log_collector.lib.client import RetryableException, RetryableClient, BatchClient


class RetryClientSuite(TestCase):

    def setUp(self):
        self._mock_client = MagicMock()
        self._request = "some request"
        self._retry_client = RetryableClient(client=self._mock_client, max_retry=2)

    def test_no_retry_needed(self):
        self._retry_client.send(self._request)
        self._mock_client.send.assert_called_once()

    def test_success_after_one_retry(self):
        self._mock_client.send.side_effect = [RetryableException("1"), RetryableException("2"), "success"]
        self._retry_client.send(self._request)
        self.assertEqual(3, self._mock_client.send.call_count)

    def test_failure_after_two_retries(self):
        self._mock_client.send.side_effect = [RetryableException("1"), RetryableException("2"), RetryableException("3")]
        self.assertRaises(RetryableException, self._retry_client.send, self._request)
        self.assertEqual(3, self._mock_client.send.call_count)


class BatchingSuite(TestCase):

    def setUp(self):
        self.client = Mock()
        self.batch_client = BatchClient(self.client, 1024, max_retry=3)

    def test_no_batching_needed(self):
        # GIVEN
        items = ["x" * 128, "y" * 512, "z" * 384]

        # WHEN
        self.batch_client.send(items)

        # THEN
        self.assertEqual(1, self.client.send.call_count)
        self.assertEqual(call(items), self.client.send.call_args_list[0])

    def test_batching(self):
        # GIVEN
        items = ["x" * 512, "y" * 256, "z" * 1024, "a" * 64]

        # WHEN
        self.batch_client.send(items)

        # THEN
        self.assertEqual(3, self.client.send.call_count)
        self.assertEqual(call([items[0], items[1]]), self.client.send.call_args_list[0])
        self.assertEqual(call([items[2]]), self.client.send.call_args_list[1])
        self.assertEqual(call([items[3]]), self.client.send.call_args_list[2])

    def test_batching_with_multi_bytes_character(self):
        # GIVEN
        # € (U+20AC)  occupies 3 bytes in unicode
        items = ["€" * 128, "y" * 512, "z" * 384]

        # WHEN
        self.batch_client.send(items)

        # THEN
        self.assertEqual(2, self.client.send.call_count)
        self.assertEqual(call([items[0], items[1]]), self.client.send.call_args_list[0])
        self.assertEqual(call([items[2]]), self.client.send.call_args_list[1])

    def test_truncate_if_item_is_too_big(self):
        # GIVEN
        items = ["x" * 2048]

        # WHEN
        self.batch_client.send(items)

        # THEN
        self.assertEqual(1, self.client.send.call_count)
        self.assertEqual(call(["x" * 1024]), self.client.send.call_args_list[0])

    def test_truncate_if_item_is_too_big_with_multi_bytes_character(self):
        # GIVEN
        # € (U+20AC)  occupies 3 bytes in unicode
        items = ["€" * 2048]

        # WHEN
        self.batch_client.send(items)

        # THEN
        self.assertEqual(1, self.client.send.call_count)
        # 341 '€' takes 1023 bytes
        self.assertEqual(call(["€" * 341]), self.client.send.call_args_list[0])
