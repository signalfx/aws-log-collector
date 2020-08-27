import base64
import gzip
from unittest.mock import patch

from unittest import TestCase
import unittest
import json

from aws_lambda_context import LambdaContext

from function import LogCollector
from function import RetryableClient, TagsCache

CUSTOM_TAGS = {'someTag1': 'someTagValue1', 'someTag2': 'someTagValue2'}
AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "134183635603"
FORWARDER_FUNCTION_ARN_PREFIX = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:"
FORWARDER_FUNCTION_NAME = 'splunk_aws_log_forwarder'
FORWARDER_FUNCTION_VERSION = '1.0.1'


@patch.object(RetryableClient, "send")
@patch('function.SplunkHTTPClient')
@patch.object(TagsCache, "get")
class LogForwardingSuite(TestCase):

    def setUp(self) -> None:
        self.log_forwarder = LogCollector()

    def test_lambda(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        tags_cache_get_mock.return_value = CUSTOM_TAGS
        event, cw_event = self._read_aws_log_event_from_file('sample_lambda_log.json')

        # WHEN
        self.log_forwarder.forward_log(cw_event, self._lambda_context())

        # THEN
        log_message = event['logEvents'][0]['message']
        log_group = event['logGroup']
        log_stream = event['logStream']
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
                "awsAccountId": AWS_ACCOUNT_ID,
                "arn": arn,
                "functionName": function_name,
                **CUSTOM_TAGS,
            },
            "host": arn,
            "source": "lambda",
        }

        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def _read_aws_log_event_from_file(self, file_name):
        log_event = self._read_from_file(file_name)
        aws_event = {'awslogs': {'data': self._encode(json.dumps(log_event))}}
        return log_event, aws_event

    def test_lambda_no_tags(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        tags_cache_get_mock.return_value = None
        event, cw_event = self._read_aws_log_event_from_file('sample_lambda_log.json')

        # WHEN
        self.log_forwarder.forward_log(cw_event, self._lambda_context())

        # THEN
        log_message = event['logEvents'][0]['message']
        log_group = event['logGroup']
        log_stream = event['logStream']
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
                "awsAccountId": AWS_ACCOUNT_ID,
                "arn": arn,
                "functionName": function_name
            },
            "host": arn,
            "source": "lambda",
        }

        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def test_rds_postgres(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        tags_cache_get_mock.return_value = CUSTOM_TAGS
        event, cw_event = self._read_aws_log_event_from_file('sample_rds_postgres_log.json')
        # WHEN
        self.log_forwarder.forward_log(cw_event, self._lambda_context())

        # THEN
        log_message = event['logEvents'][0]['message']
        log_group = event['logGroup']
        log_stream = event['logStream']
        _, _, _, _, host, db_type = log_group.split('/')
        arn = f"arn:aws:rds:{AWS_REGION}:{AWS_ACCOUNT_ID}:db:{host}"
        expected_event = {
            "event": log_message,
            "time": "1597746012.000",
            "sourcetype": "aws",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "awsAccountId": AWS_ACCOUNT_ID,
                "arn": arn,
                "dbType": db_type,
                **CUSTOM_TAGS,
            },
            "host": host,
            "source": "rds",

        }
        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def test_rds_mysql(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        tags_cache_get_mock.return_value = CUSTOM_TAGS
        event, cw_event = self._read_aws_log_event_from_file('sample_rds_mysql_log.json')
        # WHEN
        self.log_forwarder.forward_log(cw_event, self._lambda_context())

        # THEN
        log_message = event['logEvents'][0]['message']
        log_group = event['logGroup']
        log_stream = event['logStream']
        _, _, _, _, host, log_name = log_group.split('/')
        arn = f"arn:aws:rds:{AWS_REGION}:{AWS_ACCOUNT_ID}:db:{host}"
        expected_event = {
            "event": log_message,
            "time": "1598432405.376",
            "sourcetype": "aws",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "awsAccountId": AWS_ACCOUNT_ID,
                "arn": arn,
                "dbLogName": log_name,
                **CUSTOM_TAGS,
            },
            "host": host,
            "source": "rds",

        }
        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def test_rds_aurora_cluster(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        tags_cache_get_mock.return_value = CUSTOM_TAGS
        event, cw_event = self._read_aws_log_event_from_file('sample_rds_aurora_cluster_log.json')
        # WHEN
        self.log_forwarder.forward_log(cw_event, self._lambda_context())

        # THEN
        log_message = event['logEvents'][0]['message']
        log_group = event['logGroup']
        log_stream = event['logStream']
        _, _, _, _, host, log_name = log_group.split('/')
        arn = f"arn:aws:rds:{AWS_REGION}:{AWS_ACCOUNT_ID}:cluster:{host}"
        expected_event = {
            "event": log_message,
            "time": "1598432405.376",
            "sourcetype": "aws",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "awsAccountId": AWS_ACCOUNT_ID,
                "arn": arn,
                "dbLogName": log_name,
                **CUSTOM_TAGS,
            },
            "host": host,
            "source": "rds",

        }
        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def test_eks(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        tags_cache_get_mock.return_value = CUSTOM_TAGS
        event, cw_event = self._read_aws_log_event_from_file('sample_eks_log.json')
        # WHEN
        self.log_forwarder.forward_log(cw_event, self._lambda_context())

        # THEN
        log_message = event['logEvents'][0]['message']
        log_group = event['logGroup']
        log_stream = event['logStream']
        _, _, _, eks_cluster_name, _ = log_group.split("/")
        arn = f"arn:aws:eks:{AWS_REGION}:{AWS_ACCOUNT_ID}:cluster/{eks_cluster_name}"
        expected_event = {
            "event": log_message,
            "time": "1597746392.945",
            "sourcetype": "aws",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "awsAccountId": AWS_ACCOUNT_ID,
                "arn": arn,
                "eksClusterName": eks_cluster_name,
                **CUSTOM_TAGS
            },
            "host": eks_cluster_name,
            "source": "eks",
        }

        send_method_mock.assert_called_with([json.dumps(expected_event)])

    def test_api_gateway(self, tags_cache_get_mock, _, send_method_mock):
        # GIVEN
        tags_cache_get_mock.return_value = CUSTOM_TAGS
        event, cw_event = self._read_aws_log_event_from_file('sample_api_gateway_log.json')
        # WHEN
        self.log_forwarder.forward_log(cw_event, self._lambda_context())

        # THEN
        log_message = event['logEvents'][0]['message']
        log_group = event['logGroup']
        log_stream = event['logStream']

        arn = "arn:aws:apigateway:us-east-1::/restapis/kgiqlx3nok/stages/prod"
        expected_event = {
            "event": log_message,
            "time": "1598449007.634",
            "sourcetype": "aws",
            "fields": {
                "logGroup": log_group,
                "logStream": log_stream,
                "logForwarder": FORWARDER_FUNCTION_NAME+":"+FORWARDER_FUNCTION_VERSION,
                "region": AWS_REGION,
                "awsAccountId": AWS_ACCOUNT_ID,
                "arn": arn,
                "apiGatewayStage": "prod",
                "apiGatewayId": "kgiqlx3nok",
                **CUSTOM_TAGS
            },
            "host": arn,
            "source": "api-gateway",
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
        context.invoked_function_arn = FORWARDER_FUNCTION_ARN_PREFIX + "splunk_aws_log_forwarder"
        return context


if __name__ == "__main__":
    unittest.main()

