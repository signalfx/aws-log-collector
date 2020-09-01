import base64
import gzip
import json
import unittest
from unittest import TestCase
from unittest.mock import patch

from client import BatchClient
from enrichment import TagsCache
from function import LogCollector
from test_enrichment import lambda_context, read_from_file, CUSTOM_TAGS, FORWARDER_FUNCTION_ARN_PREFIX, \
    FORWARDER_FUNCTION_NAME, FORWARDER_FUNCTION_VERSION, AWS_REGION, AWS_ACCOUNT_ID


@patch.object(BatchClient, "send")
@patch.object(TagsCache, "get")
class LogCollectingSuite(TestCase):

    def setUp(self) -> None:
        self.log_forwarder = LogCollector()

    def test_lambda(self, tags_cache_get_mock, send_method_mock):
        # GIVEN
        tags_cache_get_mock.return_value = CUSTOM_TAGS
        event, cw_event = self._read_aws_log_event_from_file('sample_lambda_log.json')

        # WHEN
        self.log_forwarder.forward_log(cw_event, lambda_context())

        # THEN
        log_message = event['logEvents'][0]['message']
        log_group = event['logGroup']
        log_stream = event['logStream']
        function_name = log_group.split('/')[-1]
        arn = FORWARDER_FUNCTION_ARN_PREFIX + function_name

        expected_event = {
            "event": log_message,
            "index": "main",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "awsAccountId": AWS_ACCOUNT_ID,
                "arn": arn,
                "functionName": function_name,
                **CUSTOM_TAGS,
            },
            "host": arn,
            "source": "lambda",
            "sourcetype": "aws:lambda",
            "time": "1595335478.131",
        }

        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def _read_aws_log_event_from_file(self, file_name):
        log_event = read_from_file(file_name)
        aws_event = {'awslogs': {'data': self._encode(json.dumps(log_event))}}
        return log_event, aws_event

    @staticmethod
    def _encode(event):
        result = base64.encodebytes(gzip.compress(bytes(event, "utf-8")))
        return result


if __name__ == "__main__":
    unittest.main()

