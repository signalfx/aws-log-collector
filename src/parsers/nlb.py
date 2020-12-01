import re
from typing import Dict

from parsers.parser import Parser, ParsedLine

# AWS NLB access log file format:
# bucket[/prefix]/AWSLogs/aws-account-id/elasticloadbalancing/region
# /yyyy/mm/dd/aws-account-id_elasticloadbalancing_region_load-balancer-id
# _end-time_random-string.log.gz
#
# s3://my-bucket/prefix/AWSLogs/123456789012/elasticloadbalancing/us-east-2
# /2016/05/01/123456789012_elasticloadbalancing_us-east-2_net.my-network-loadbalancer.c6e77e28c25b2234
# _20140215T2340Z_20sg8hgm.log.gz

OBJECT_KEY_REGEX = re.compile(r"AWSLogs/([\d]+)/elasticloadbalancing/([^/]+)" +
                              r"/\d{4}/\d{2}/\d{2}/\d+_elasticloadbalancing_.+" +
                              r"\d{8}T\d{4}Z_.+\.log\.gz$")
ACCOUNT_ID_REGEX_GROUP_INDEX = 1
REGION_REGEX_GROUP_INDEX = 2

FIELD_NAMES = ("type", "version", "time", "elb", "listener",
               "client:port", "destination:port",
               "connection_time", "tls_handshake_time",
               "received_bytes", "sent_bytes",
               "incoming_tls_alert", "chosen_cert_arn", "chosen_cert_serial",
               "tls_cipher", "tls_protocol_version", "tls_named_group",
               "domain_name",
               "alpn_fe_protocol", "alpn_be_protocol", "alpn_client_preference_list",
               )


class NetworkELBParser(Parser):

    def get_namespace(self):
        return "NetworkELB"

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

        hec_time = self.iso_time_to_hec_time(fields["time"]) if "time" in fields else None
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
        return arns
