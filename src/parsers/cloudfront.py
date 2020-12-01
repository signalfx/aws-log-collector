import re
from typing import Dict

from parsers.parser import Parser, ParsedLine

# AWS CloudFront access log file format:
# <optional prefix>/<distribution ID>.YYYY-MM-DD-HH.unique-ID.gz
#
# example-prefix/EMLARXS9EXAMPLE.2019-11-14-20.RT4KCN4SGK9.gz

OBJECT_KEY_REGEX = re.compile(r"([^/]+)\.\d{4}-\d{2}-\d{2}-\d{2}\..+\.gz$")
DISTRIBUTION_ID_REGEX_GROUP_INDEX = 1

# there are many more fields in CF logs though we do not really need them for now
FIELD_NAMES = ("date", "time", "x-edge-location")


class CloudFrontParser(Parser):

    def __init__(self):
        super().__init__(delimiter="\t")

    def get_namespace(self):
        return "CloudFront"

    def supports(self, log_file_name):
        return OBJECT_KEY_REGEX.search(log_file_name) is not None

    def get_file_metadata(self, context_metadata, log_file_name) -> Dict:
        match = OBJECT_KEY_REGEX.search(log_file_name)
        distribution_id = match.group(DISTRIBUTION_ID_REGEX_GROUP_INDEX)
        aws_account_id = context_metadata["awsAccountId"]
        return {
            "distributionArn": f"arn:aws:cloudfront::{aws_account_id}:distribution/{distribution_id}"
        }

    def try_parse(self, metadata, record):
        arns = [("distributionArn", metadata["distributionArn"])]
        # CloudFront uses Extended Log File Format that starts with a header consisting
        # of several directives; all directives start with the "#" character
        if len(record) < len(FIELD_NAMES) or str(record[0]).startswith("#"):
            return ParsedLine(None, {}, arns)
        else:
            fields = dict(zip(FIELD_NAMES, record))
            hec_time = self.iso_time_to_hec_time(fields["date"].strip() + "T" + fields["time"].strip())
            return ParsedLine(hec_time, fields, arns)
