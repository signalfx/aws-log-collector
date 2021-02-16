import unittest
from unittest import TestCase
from unittest.mock import Mock

from aws_log_collector.enrichers.cloudwatch import CloudWatchLogsEnricher
from tests.utils import lambda_context, read_json_file, FORWARDER_FUNCTION_ARN_PREFIX, FORWARDER_FUNCTION_NAME, AWS_REGION, AWS_ACCOUNT_ID, \
    FORWARDER_FUNCTION_VERSION

CUSTOM_TAGS = {'someTag1': 'someTagValue1', 'someTag2': 'someTagValue2'}


class CloudWatchEnrichmentSuite(TestCase):

    def setUp(self) -> None:
        self.tag_cache_mock = Mock()
        self.sfx_metrics = Mock()
        self.log_enricher = CloudWatchLogsEnricher(self.tag_cache_mock)

    def test_lambda_enrichment(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_json_file('tests/data/lambda_log.json')

        # WHEN
        actual = self.log_enricher.get_metadata(event, lambda_context(), self.sfx_metrics)

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
            "sourcetype": "aws:lambda",
            **CUSTOM_TAGS
        }
        self.assertEqual(expected, actual)

    def test_lambda_enrichment_no_tags(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = None
        event = read_json_file('tests/data/lambda_log.json')

        # WHEN
        actual = self.log_enricher.get_metadata(event, lambda_context(), self.sfx_metrics)

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
            "sourcetype": "aws:lambda",
        }
        self.assertEqual(expected, actual)

    def test_rds_postgres(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_json_file('tests/data/rds_postgres_log.json')

        # WHEN
        actual = self.log_enricher.get_metadata(event, lambda_context(), self.sfx_metrics)

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
            "sourcetype": "aws:rds",
        }
        self.assertEqual(expected, actual)

    def test_rds_mysql(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_json_file('tests/data/rds_mysql_log.json')

        # WHEN
        actual = self.log_enricher.get_metadata(event, lambda_context(), self.sfx_metrics)

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
            "sourcetype": "aws:rds",
        }
        self.assertEqual(expected, actual)

    def test_rds_aurora_cluster(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_json_file('tests/data/rds_aurora_cluster_log.json')

        # WHEN
        actual = self.log_enricher.get_metadata(event, lambda_context(), self.sfx_metrics)

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
            "sourcetype": "aws:rds",
        }
        self.assertEqual(expected, actual)

    def test_eks(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_json_file('tests/data/eks_log.json')

        # WHEN
        actual = self.log_enricher.get_metadata(event, lambda_context(), self.sfx_metrics)

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
            "sourcetype": "aws:eks",
        }

        self.assertEqual(expected, actual)

    def test_api_gateway(self):
        # GIVEN
        self.tag_cache_mock.get.return_value = CUSTOM_TAGS
        event = read_json_file('tests/data/api_gateway.json')

        # WHEN
        actual = self.log_enricher.get_metadata(event, lambda_context(), self.sfx_metrics)

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
            "sourcetype": "aws:api-gateway",
            **CUSTOM_TAGS,
        }

        self.assertEqual(expected, actual)

    def test_parse_lambda_arn_without_version(self):
        # GIVEN
        context = lambda_context()

        # WHEN
        region, account_id = self.log_enricher._parse_log_collector_function_arn(context)

        # THEN
        self.assertEqual(AWS_REGION, region)
        self.assertEqual(AWS_ACCOUNT_ID, account_id)

    def test_parse_lambda_arn_with_version(self):
        # GIVEN
        context = lambda_context()
        context.invoked_function_arn += ":33"

        # WHEN
        region, account_id = self.log_enricher._parse_log_collector_function_arn(context)

        # THEN
        self.assertEqual(AWS_REGION, region)
        self.assertEqual(AWS_ACCOUNT_ID, account_id)


if __name__ == "__main__":
    unittest.main()
