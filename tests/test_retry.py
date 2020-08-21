from unittest import TestCase
from unittest.mock import MagicMock, call

from function import RetryableClient, RetryableException


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