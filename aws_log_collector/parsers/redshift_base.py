import re
from abc import ABC
from datetime import datetime
from typing import Dict

from aws_log_collector.logger import log
from aws_log_collector.parsers.parser import Parser

# AWS Redshift access log file format:
# AWSLogs/AccountID/ServiceName/Region/Year/Month/Day/AccountID
# _ServiceName_Region_ClusterName_LogType_Timestamp.gz
#
# AWSLogs/123456789012/redshift/us-east-1/2013/10/29/123456789012
# _redshift_us-east-1_mycluster_userlog_2013-10-29T18:01.gz

OBJECT_KEY_REGEX = re.compile(r"AWSLogs/([\d]+)/redshift/([^/]+)" +
                              r"/\d{4}/\d{2}/\d{2}/\d+_redshift_" +
                              r"[^_]+_([^_]+)_(.+)_" +
                              r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}\.gz")

ACCOUNT_ID_REGEX_GROUP_INDEX = 1
REGION_REGEX_GROUP_INDEX = 2
CLUSTER_NAME_REGEX_GROUP_INDEX = 3
LOG_TYPE_REGEX_GROUP_INDEX = 4


class RedshiftBaseParser(Parser, ABC):

    def __init__(self):
        super().__init__(delimiter="|")

    def get_namespace(self):
        return "Redshift"

    def get_file_metadata(self, context_metadata, log_file_name) -> Dict:
        match = OBJECT_KEY_REGEX.search(log_file_name)
        region = match.group(REGION_REGEX_GROUP_INDEX)
        account_id = match.group(ACCOUNT_ID_REGEX_GROUP_INDEX)
        cluster_id = match.group(CLUSTER_NAME_REGEX_GROUP_INDEX)
        return {
            "region": region,
            "awsAccountId": account_id,
            "clusterArn": f"arn:aws:redshift:{region}:{account_id}:cluster:{cluster_id}",
            "logType": match.group(LOG_TYPE_REGEX_GROUP_INDEX)
        }

    @staticmethod
    def _is_redshift_log(log_file_name, log_type):
        match = OBJECT_KEY_REGEX.search(log_file_name)
        return match and match.group(LOG_TYPE_REGEX_GROUP_INDEX) == log_type

    @staticmethod
    def _redshift_time_to_hec_time(ts):
        try:
            dt = datetime.strptime(ts, "%a, %d %b %Y %H:%M:%S:%f")  # Mon, 7 Dec 2020 20:01:55:177
            return RedshiftBaseParser._naive_time_to_zone_aware_time(dt).timestamp()
        except ValueError as ex:
            log.warning(f"Failed to parse Redshift log timestamp {ts}: {ex}")
            return None
