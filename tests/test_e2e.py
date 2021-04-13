import base64
import gzip
import json
import unittest
from unittest import TestCase
from unittest.mock import patch

import signalfx

from function import LogCollector
from aws_log_collector.lib.client import BatchClient
from aws_log_collector.lib.s3_service import S3Service
from aws_log_collector.lib.tags_cache import TagsCache
from tests.utils import get_read_lines_mock
from tests.enrichers.test_cloudwatch import lambda_context, read_json_file, CUSTOM_TAGS, FORWARDER_FUNCTION_ARN_PREFIX, \
    FORWARDER_FUNCTION_NAME, FORWARDER_FUNCTION_VERSION, AWS_REGION, AWS_ACCOUNT_ID


@patch.object(signalfx.SignalFx, "ingest")
@patch.object(S3Service, "read_lines")
@patch.object(BatchClient, "send")
@patch.object(TagsCache, "get")
# TODO should not require connection to AWS
# @unittest.skipUnless(
#     os.environ.get('AWS_ACCESS_KEY_ID', False), 'Run only if AWS credentials are configured'
# )
class LogCollectingSuite(TestCase):

    def setUp(self) -> None:
        self.log_forwarder = LogCollector()

    def test_cloudwatch(self, tags_cache_get_mock, send_method_mock, _, __):
        # GIVEN
        tags_cache_get_mock.return_value = CUSTOM_TAGS
        event, cw_event = self._read_aws_log_event_from_file('tests/data/lambda_log.json')

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
                "logForwarder": FORWARDER_FUNCTION_NAME + ":" + FORWARDER_FUNCTION_VERSION,
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

    def test_s3_s3(self, tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, _):
        scenario = {
            "name": "s3",
            "arn_to_tags": {
                "arn:aws:s3:::integrations-team":
                    {"bucket-tag-1": 1, "bucket-tag-2": "abc"},
                "arn:aws:s3:::integrations-team/WhatsApp Image 2020-07-05 at 18.34.43.jpeg":
                    {"object-tag-1": 10, "object-tag-2": "def"}
            }
        }
        self._test_s3_logs_handling(tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, scenario)

    def test_s3_alb(self, tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, _):
        scenario = {
            "name": "alb",
            "arn_to_tags": {
                "arn:aws:elasticloadbalancing:us-east-2:840385940912:loadbalancer/app/my-loadbalancer/50dc6c495c0c9188":
                    {"elb-a": 1, "elb-b": "one"},
                "arn:aws:elasticloadbalancing:us-east-2:840385940912:targetgroup/my-targets/73e2d6bc24d8a067":
                    {"tg-a": 10, "tg-b": "ten"}
            }
        }
        self._test_s3_logs_handling(tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, scenario)

    def test_s3_nlb(self, tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, _):
        scenario = {
            "name": "nlb",
            "arn_to_tags": {
                "arn:aws:elasticloadbalancing:us-east-2:840385940912:loadbalancer/net/my-network-loadbalancer/c6e77e28c25b2234":
                    {"lb-a": 1, "lb-b": "two"}
            }
        }
        self._test_s3_logs_handling(tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, scenario)

    def test_s3_cloudfront(self, tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, _):
        scenario = {
            "name": "cloudfront",
            "arn_to_tags": {
                "arn:aws:cloudfront::134183635603:distribution/EMLARXS9EXAMPLE":
                    {"dist-a": 1, "dist-b": "two"}
            }
        }
        self._test_s3_logs_handling(tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, scenario)

    def test_s3_redshift_connectionlog(self, tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, _):
        scenario = {
            "name": "redshift_connectionlog",
            "arn_to_tags": {
                "arn:aws:redshift:eu-central-1:906383545488:cluster:redshift-cluster-1": {"tagA": 1, "tagB": "two"}
            }
        }
        self._test_s3_logs_handling(tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, scenario)

    def test_s3_redshift_userlog(self, tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, _):
        scenario = {
            "name": "redshift_userlog",
            "arn_to_tags": {
                "arn:aws:redshift:eu-central-1:906383545488:cluster:redshift-cluster-1": {"tagA": 1, "tagB": "two"}
            }
        }
        self._test_s3_logs_handling(tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, scenario)

    def test_s3_redshift_useractivitylog(self, tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, _):
        scenario = {
            "name": "redshift_useractivitylog",
            "arn_to_tags": {
                "arn:aws:redshift:eu-central-1:906383545488:cluster:redshift-cluster-1": {"tagA": "a", "tagB": "b"}
            }
        }
        self._test_s3_logs_handling(tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, scenario)

    def _test_s3_logs_handling(self, tags_cache_get_mock, send_method_mock, s3_service_read_lines_mock, scenario):
        # GIVEN
        scenario_name = scenario["name"]
        arn_to_tags = scenario["arn_to_tags"]
        tags_cache_get_mock.side_effect = lambda arn, _: arn_to_tags[arn] if arn in arn_to_tags else None

        s3_event = read_json_file(f"tests/data/e2e/{scenario_name}_event.json")
        s3_service_read_lines_mock.side_effect = get_read_lines_mock(f"tests/data/e2e/{scenario_name}.log")

        # WHEN
        self.log_forwarder.forward_log(s3_event, lambda_context())

        # THEN
        expected_hec_events = read_json_file(f"tests/data/e2e/{scenario_name}_hec_items.json")
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
