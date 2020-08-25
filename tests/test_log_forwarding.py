import base64
import gzip
from unittest.mock import patch

from unittest import TestCase
import unittest
import json

from aws_lambda_context import LambdaContext

from function import LogCollector
from function import RetryableClient, TagsCache

LAMBDA_CUSTOM_TAGS = {'someTag1': 'someTagValue1', 'someTag2': 'someTagValue2'}
AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "134183635603"
FORWARDER_FUNCTION_ARN_PREFIX = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:"
FORWARDER_FUNCTION_NAME = 'sfx_aws_log_forwarder'
FORWARDER_FUNCTION_VERSION = '1.0.1'


@patch.object(RetryableClient, "send")
@patch('function.SfxHTTPClient')
@patch.object(TagsCache, "get")
class LogForwardingSuite(TestCase):

    def test_lambda(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        log_forwarder = LogCollector()
        tags_cache_get_mock.return_value = LAMBDA_CUSTOM_TAGS
        cw_event = self._read_from_file('sample_lambda_log.json')
        context = self._lambda_context()
        event = {'awslogs': {'data': self._encode(json.dumps(cw_event))}}

        # WHEN
        log_forwarder.forward_log(event, context)

        # THEN
        log_message = cw_event['logEvents'][0]['message']
        log_group = cw_event['logGroup']
        log_stream = cw_event['logStream']
        function_name = log_group.split('/')[-1]
        arn = FORWARDER_FUNCTION_ARN_PREFIX + function_name

        expected_event = {
            "event": log_message,
            "time": "1595335478.131",
            "sourcetype": "aws",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "aws_account_id": AWS_ACCOUNT_ID,
                "arn": arn,
                "functionName": function_name,
                **LAMBDA_CUSTOM_TAGS,
            },
            "host": arn,
            "source": "lambda",
        }

        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def test_lambda_no_tags(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        log_forwarder = LogCollector()
        tags_cache_get_mock.return_value = None
        cw_event = self._read_from_file('sample_lambda_log.json')
        context = self._lambda_context()
        event = {'awslogs': {'data': self._encode(json.dumps(cw_event))}}

        # WHEN
        log_forwarder.forward_log(event, context)

        # THEN
        log_message = cw_event['logEvents'][0]['message']
        log_group = cw_event['logGroup']
        log_stream = cw_event['logStream']
        function_name = log_group.split('/')[-1]
        arn = FORWARDER_FUNCTION_ARN_PREFIX + function_name

        expected_event = {
            "event": log_message,
            "time": "1595335478.131",
            "sourcetype": "aws",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "aws_account_id": AWS_ACCOUNT_ID,
                "arn": arn,
                "functionName": function_name
            },
            "host": arn,
            "source": "lambda",
        }

        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def test_rds(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        log_forwarder = LogCollector()
        cw_event = self._read_from_file('sample_rds_log.json')
        context = self._lambda_context()
        event = {'awslogs': {'data': self._encode(json.dumps(cw_event))}}

        # WHEN
        log_forwarder.forward_log(event, context)

        # THEN
        log_message = cw_event['logEvents'][0]['message']
        log_group = cw_event['logGroup']
        log_stream = cw_event['logStream']
        db_type = log_group.split('/')[-1]
        host = log_group.split('/')[-2]

        expected_event = {
            "event": log_message,
            "time": "1597746012.000",
            "sourcetype": "aws",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "aws_account_id": AWS_ACCOUNT_ID,
                "dbType": db_type,
                # TODO: check if can generate arn?
                # **LAMBDA_CUSTOM_TAGS,
            },
            "host": host,
            "source": "rds",

        }
        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def test_eks(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        log_forwarder = LogCollector()
        cw_event = self._read_from_file('sample_eks_log.json')
        context = self._lambda_context()
        event = {'awslogs': {'data': self._encode(json.dumps(cw_event))}}

        # WHEN
        log_forwarder.forward_log(event, context)

        # THEN
        log_message = cw_event['logEvents'][0]['message']
        log_group = cw_event['logGroup']
        log_stream = cw_event['logStream']

        expected_event = {
            "event": log_message,
            "time": "1597746392.945",
            "sourcetype": "aws",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "aws_account_id": AWS_ACCOUNT_ID,
                # TODO: check if can generate arn?
                # **LAMBDA_CUSTOM_TAGS,
            },
            "host": log_group,
            "source": "eks",
        }

        send_method_mock.assert_called_with([json.dumps(expected_event)])

    @staticmethod
    def _encode(event):
        result = base64.encodebytes(gzip.compress(bytes(event, "utf-8")))
        return result

    @staticmethod
    def _read_from_file(file_name):
        with open(file_name, 'r') as file:
            return json.loads(file.read())

    @staticmethod
    def _lambda_context():
        context = LambdaContext()
        context.function_name = FORWARDER_FUNCTION_NAME
        context.function_version = FORWARDER_FUNCTION_VERSION
        context.invoked_function_arn = FORWARDER_FUNCTION_ARN_PREFIX + "sfx_aws_log_forwarder"
        return context


if __name__ == "__main__":
    unittest.main()

