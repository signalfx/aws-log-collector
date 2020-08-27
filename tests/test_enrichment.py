import json
import unittest
from unittest import TestCase
from unittest.mock import Mock

from aws_lambda_context import LambdaContext

from enrichment import LogEnricher

CUSTOM_TAGS = {'someTag1': 'someTagValue1', 'someTag2': 'someTagValue2'}
AWS_REGION = "us-east-1"
AWS_ACCOUNT_ID = "134183635603"
FORWARDER_FUNCTION_ARN_PREFIX = f"arn:aws:lambda:{AWS_REGION}:{AWS_ACCOUNT_ID}:function:"
FORWARDER_FUNCTION_NAME = 'splunk_aws_log_forwarder'
FORWARDER_FUNCTION_VERSION = '1.0.1'


class LogEnrichmentSuite(TestCase):

    def setUp(self) -> None:
        self.tag_cache_mock = Mock()
        self.log_enricher = LogEnricher(self.tag_cache_mock)

    def test_lambda_enrichment(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_from_file('sample_lambda_log.json')

        # WHEN
        actual = self.log_enricher.get_matadata(event, lambda_context())

        # THEN
        log_group = event['logGroup']
        function_name = log_group.split('/')[-1]
        arn = FORWARDER_FUNCTION_ARN_PREFIX + function_name

        expected = {
            "logGroup": log_group,
            "logStream": (event['logStream']),
            "logForwarder": FORWARDER_FUNCTION_NAME + ":" + FORWARDER_FUNCTION_VERSION,
            "region": AWS_REGION,
            "awsAccountId": AWS_ACCOUNT_ID,
            "arn": arn,
            "functionName": function_name,
            "host": arn,
            "source": "lambda",
            **CUSTOM_TAGS
        }
        self.assertEqual(expected, actual)

    def test_lambda_enrichment_no_tags(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = None
        event = read_from_file('sample_lambda_log.json')

        # WHEN
        actual = self.log_enricher.get_matadata(event, lambda_context())

        # THEN
        log_group = event['logGroup']
        function_name = log_group.split('/')[-1]
        arn = FORWARDER_FUNCTION_ARN_PREFIX + function_name

        expected = {
            "logGroup": log_group,
            "logStream": (event['logStream']),
            "logForwarder": FORWARDER_FUNCTION_NAME + ":" + FORWARDER_FUNCTION_VERSION,
            "region": AWS_REGION,
            "awsAccountId": AWS_ACCOUNT_ID,
            "arn": arn,
            "functionName": function_name,
            "host": arn,
            "source": "lambda",
        }
        self.assertEqual(expected, actual)

    def test_rds_postgres(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_from_file('sample_rds_postgres_log.json')

        # WHEN
        actual = self.log_enricher.get_matadata(event, lambda_context())

        # THEN
        log_group = event['logGroup']
        _, _, _, _, host, db_type = log_group.split('/')
        expected = {
            "logGroup": log_group,
            "logStream": (event['logStream']),
            "logForwarder": FORWARDER_FUNCTION_NAME + ":" + FORWARDER_FUNCTION_VERSION,
            "region": AWS_REGION,
            "awsAccountId": AWS_ACCOUNT_ID,
            "arn": f"arn:aws:rds:{AWS_REGION}:{AWS_ACCOUNT_ID}:db:{host}",
            "dbType": db_type,
            **CUSTOM_TAGS,
            "host": host,
            "source": "rds",

        }
        self.assertEqual(expected, actual)

    def test_rds_mysql(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_from_file('sample_rds_mysql_log.json')

        # WHEN
        actual = self.log_enricher.get_matadata(event, lambda_context())

        # THEN
        log_group = event['logGroup']
        _, _, _, _, host, log_name = log_group.split('/')
        expected = {
            "logGroup": log_group,
            "logStream": (event['logStream']),
            "logForwarder": FORWARDER_FUNCTION_NAME + ":" + FORWARDER_FUNCTION_VERSION,
            "region": AWS_REGION,
            "awsAccountId": AWS_ACCOUNT_ID,
            "arn": f"arn:aws:rds:{AWS_REGION}:{AWS_ACCOUNT_ID}:db:{host}",
            "dbLogName": log_name,
            **CUSTOM_TAGS,
            "host": host,
            "source": "rds",

        }
        self.assertEqual(expected, actual)

    def test_rds_aurora_cluster(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_from_file('sample_rds_aurora_cluster_log.json')

        # WHEN
        actual = self.log_enricher.get_matadata(event, lambda_context())

        # THEN
        log_group = event['logGroup']
        _, _, _, _, host, log_name = log_group.split('/')
        expected = {
            "logGroup": log_group,
            "logStream": (event['logStream']),
            "logForwarder": FORWARDER_FUNCTION_NAME + ":" + FORWARDER_FUNCTION_VERSION,
            "region": AWS_REGION,
            "awsAccountId": AWS_ACCOUNT_ID,
            "arn": f"arn:aws:rds:{AWS_REGION}:{AWS_ACCOUNT_ID}:cluster:{host}",
            "dbLogName": log_name,
            **CUSTOM_TAGS,
            "host": host,
            "source": "rds",

        }
        self.assertEqual(expected, actual)

    def test_eks(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_from_file('sample_eks_log.json')

        # WHEN
        actual = self.log_enricher.get_matadata(event, lambda_context())

        # THEN
        log_group = event['logGroup']
        _, _, _, eks_cluster_name, _ = log_group.split("/")
        expected = {
            "logGroup": log_group,
            "logStream": (event['logStream']),
            "logForwarder": FORWARDER_FUNCTION_NAME + ":" + FORWARDER_FUNCTION_VERSION,
            "region": AWS_REGION,
            "awsAccountId": AWS_ACCOUNT_ID,
            "arn": f"arn:aws:eks:{AWS_REGION}:{AWS_ACCOUNT_ID}:cluster/{eks_cluster_name}",
            "eksClusterName": eks_cluster_name,
            **CUSTOM_TAGS,
            "host": eks_cluster_name,
            "source": "eks",
        }

        self.assertEqual(expected, actual)

    def test_api_gateway(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_from_file('sample_api_gateway_log.json')

        # WHEN
        actual = self.log_enricher.get_matadata(event, lambda_context())

        # THEN
        arn = "arn:aws:apigateway:us-east-1::/restapis/kgiqlx3nok/stages/prod"
        expected = {
            "logGroup": (event['logGroup']),
            "logStream": (event['logStream']),
            "logForwarder": FORWARDER_FUNCTION_NAME + ":" + FORWARDER_FUNCTION_VERSION,
            "region": AWS_REGION,
            "awsAccountId": AWS_ACCOUNT_ID,
            "arn": arn,
            "apiGatewayStage": "prod",
            "apiGatewayId": "kgiqlx3nok",
            "host": arn,
            "source": "api-gateway",
            **CUSTOM_TAGS,
        }

        self.assertEqual(expected, actual)


def read_from_file(file_name):
    with open(file_name, 'r') as file:
        return json.loads(file.read())


def lambda_context():
    context = LambdaContext()
    context.function_name = FORWARDER_FUNCTION_NAME
    context.function_version = FORWARDER_FUNCTION_VERSION
    context.invoked_function_arn = FORWARDER_FUNCTION_ARN_PREFIX + "splunk_aws_log_forwarder"
    return context


if __name__ == "__main__":
    unittest.main()
