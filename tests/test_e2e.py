import base64
import gzip
import json
import unittest
from unittest import TestCase
from unittest.mock import patch

import signalfx

from enrichers.test_cloudwatch import lambda_context, read_json_file, CUSTOM_TAGS, FORWARDER_FUNCTION_ARN_PREFIX, \
    FORWARDER_FUNCTION_NAME, FORWARDER_FUNCTION_VERSION, AWS_REGION, AWS_ACCOUNT_ID
from function import LogCollector
from lib.client import BatchClient
from lib.s3_service import S3Service
from lib.tags_cache import TagsCache
from utils import read_text_file


@patch.object(signalfx.SignalFx, "ingest")
@patch.object(S3Service, "read_lines")
@patch.object(BatchClient, "send")
@patch.object(TagsCache, "get")
class LogCollectingSuite(TestCase):

    def setUp(self) -> None:
        self.log_forwarder = LogCollector()

    def test_lambda(self, tags_cache_get_mock, send_method_mock, _, __):
        # GIVEN
        tags_cache_get_mock.return_value = CUSTOM_TAGS
        event, cw_event = self._read_aws_log_event_from_file('data/sample_lambda_log.json')

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

    def test_s3(self, tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, _):
        # GIVEN
        bucket_arn = "arn:aws:s3:::integrations-team"
        bucket_tags = {"bucket-tag-1": 1, "bucket-tag-2": "abc"}
        object_tags = {"object-tag-1": 10, "object-tag-2": "def"}
        tags_cache_get_mock.side_effect = lambda arn, _: bucket_tags if arn == bucket_arn else object_tags

        s3_service_read_lines_mock.return_value = read_text_file("data/sample_s3_access_log.txt")
        s3_event = read_json_file("data/sample_s3_log_event.json")

        # WHEN
        self.log_forwarder.forward_log(s3_event, lambda_context())

        # THEN
        expected_hec_events = read_json_file("data/expected_s3_access_log_hec_items.json")
        actual_hec_events = self._parse_hec_events_to_json(send_method_mock.call_args)
        self.assertEqual(expected_hec_events, actual_hec_events)

    def _read_aws_log_event_from_file(self, file_name):
        log_event = read_json_file(file_name)
        aws_event = {'awslogs': {'data': self._encode(json.dumps(log_event))}}
        return log_event, aws_event

    @staticmethod
    def _parse_hec_events_to_json(raw_hec_events):
        events = raw_hec_events[0][0]
        return list(map(lambda s: json.loads(s), events))

    @staticmethod
    def _encode(event):
        result = base64.encodebytes(gzip.compress(bytes(event, "utf-8")))
        return result


if __name__ == "__main__":
    unittest.main()

