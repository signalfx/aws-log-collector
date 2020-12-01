import os
import re
from datetime import datetime
from urllib.parse import unquote_plus

from logger import log
from parsers.parser import Parser, ParsedLine

# S3 object key format: YYYY-mm-DD-HH-MM-SS-UniqueString/
OBJECT_KEY_REGEX = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-[a-zA-Z0-9_-]+$")

FIELD_NAMES = ("bucket_owner", "bucket", "time", "ip", "requester",
               "request_id", "operation", "key", "request_uri", "http_status",
               "error_code", "bytes_sent", "object_size", "total_time", "turn_around_time",
               "referer", "user_agent", "version_id", "host_id",
               "signature_version", "cipher_suite", "authentication_type", "host_header",
               "tls_version")
TIME_FIELD_INDEX = 2


class S3Parser(Parser):

    def get_namespace(self):
        return "s3"

    def supports(self, log_file_name):
        return OBJECT_KEY_REGEX.search(log_file_name) is not None

    def try_parse(self, _, record):
        self._fix_time_field(record)
        fields = dict(zip(FIELD_NAMES, record))

        hec_time = self._to_hec_time(fields["time"]) if "time" in fields else None
        arns = self._get_arns(fields)
        return ParsedLine(hec_time, fields, arns)

    @staticmethod
    def _fix_time_field(record):
        """
        time field contains space so we need to join it with the next field.
        The format is [%d/%b/%Y:%H:%M:%S %z] e.g. [06/Feb/2019:00:00:38 +0000]
        """
        if len(record) > TIME_FIELD_INDEX + 2:
            record[TIME_FIELD_INDEX] = record[TIME_FIELD_INDEX] + " " + record.pop(TIME_FIELD_INDEX + 1)

    @staticmethod
    def _to_hec_time(s3_time):
        try:
            return datetime.strptime(s3_time, "[%d/%b/%Y:%H:%M:%S %z]").timestamp()
        except ValueError as ex:
            log.warning(f"Failed to parse s3 timestamp {s3_time}: {ex}")
            return None

    @staticmethod
    def _get_arns(fields):
        arns = []
        if fields.get("bucket", "-") != "-":  # AWS uses "-" for missing/null values
            arns.append(("bucketArn", "arn:aws:s3:::" + fields["bucket"]))

            if fields.get("key", "-") != "-":
                decoded_key = S3Parser._decode_key(fields["key"])
                arns.append(("objectArn", "arn:aws:s3:::" + os.path.join(fields["bucket"], decoded_key)))
        return arns

    @staticmethod
    def _decode_key(url_encoded_s3_request_key):
        """
        Decodes S3 object key as stored in the S3 access log
        """
        s3_request_key = unquote_plus(url_encoded_s3_request_key)  # name%2Bwith%2Bspaces%252Band%2B%252B%2Bpluses.jpeg
        raw_key_name = unquote_plus(s3_request_key)  # name+with+spaces%2Band+%2B+pluses.jpeg
        return raw_key_name  # name with spaces+and + pluses.jpeg
