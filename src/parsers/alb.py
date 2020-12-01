import re
from typing import Dict

from parsers.parser import Parser, ParsedLine

# AWS ALB access log file format:
# bucket[/prefix]/AWSLogs/aws-account-id/elasticloadbalancing/region
# /yyyy/mm/dd/aws-account-id_elasticloadbalancing_region_load-balancer-id
# _end-time_ip-address_random-string.log.gz
#
# s3://my-bucket/prefix/AWSLogs/123456789012/elasticloadbalancing/us-east-2
# /2016/05/01/123456789012_elasticloadbalancing_us-east-2_app.my-loadbalancer.1234567890abcdef
# _20140215T2340Z_172.160.001.192_20sg8hgm.log.gz

OBJECT_KEY_REGEX = re.compile(r"AWSLogs/([\d]+)/elasticloadbalancing/([^/]+)" +
                              r"/\d{4}/\d{2}/\d{2}/\d+_elasticloadbalancing_.+" +
                              r"\d{8}T\d{4}Z_\d+\.\d+\.\d+\.\d+_.+\.log\.gz$")
ACCOUNT_ID_REGEX_GROUP_INDEX = 1
REGION_REGEX_GROUP_INDEX = 2

FIELD_NAMES = ("type", "time", "elb", "client_port", "target_port",
               "request_processing_time", "target_processing_time",
               "response_processing_time", "elb_status_code",
               "target_status_code", "received_bytes", "sent_bytes",
               "request", "user_agent", "ssl_cipher", "ssl_protocol",
               "target_group_arn", "trace_id", "domain_name",
               "chosen_cert_arn", "matched_rule_priority",
               "request_creation_time", "actions_executed",
               "redirect_url", "error_reason", "target_port_list",
               "target_status_code_list",
               "classification", "classification_reason"
               )


class ApplicationELBParser(Parser):

    def get_namespace(self):
        return "ApplicationELB"

    def supports(self, log_file_name):
        return OBJECT_KEY_REGEX.search(log_file_name) is not None

    def get_file_metadata(self, context_metadata, log_file_name) -> Dict:
        match = OBJECT_KEY_REGEX.search(log_file_name)
        return {
            "region": match.group(REGION_REGEX_GROUP_INDEX),
            "awsAccountId": match.group(ACCOUNT_ID_REGEX_GROUP_INDEX)
        }

    def try_parse(self, metadata, record):
        fields = dict(zip(FIELD_NAMES, record))

        hec_time = self.iso_time_to_hec_time(fields["request_creation_time"]) if "request_creation_time" in fields else None
        arns = self._get_arns(metadata, fields)
        return ParsedLine(hec_time, fields, arns)

    @staticmethod
    def _get_arns(metadata, fields):
        arns = []
        if fields.get("elb", "-") != "-":  # AWS uses "-" for missing/null values
            region = metadata["region"]
            account_id = metadata["awsAccountId"]
            elb = fields['elb']
            arns.append(("elbArn", f"arn:aws:elasticloadbalancing:{region}:{account_id}:loadbalancer/{elb}"))
        if fields.get("target_group_arn", "-") != "-":
            arns.append(("targetGroupArn", fields["target_group_arn"]))
        return arns
