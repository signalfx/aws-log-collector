import os
import re
from datetime import datetime
from urllib.parse import unquote_plus

from aws_log_collector.logger import log
from aws_log_collector.parsers.parser import Parser, ParsedLine

# S3 object key format: yyyy-MM-dd-hh-mm-ss-UniqueString/
OBJECT_KEY_REGEX = re.compile(r"\d{4}-\d{2}-\d{2}-\d{2}-\d{2}-\d{2}-[0-9A-F]{16}$")

# https://docs.aws.amazon.com/AmazonS3/latest/userguide/LogFormat.html#log-record-fields
LOG_FORMAT_VALIDATION_REGEX = re.compile(
    r"^[0-9a-f]{64} "                                                               # 'Bucket Owner'
    r"((?!xn--)(?!(?:[0-9]{1,3}\.){3}[0-9]{1,3}))[a-z0-9][a-z0-9-.]{1,61}[a-z0-9] " # 'Bucket'
    r"\[\d{2}/\w+/\d{4}:\d{2}:\d{2}:\d{2} \+\d{4}] "                                # 'Time'
    r"(((?:[0-9]{1,3}\.){3}[0-9]{1,3})|-) "                                         # 'Remote IP'
    r"[^\s]+ "                                                                      # 'Requester ARN/Canonical ID'
    r"[A-Z0-9]{16} "                                                                # 'Request ID'
    r"(SOAP|REST|WEBSITE|BATCH|S3)\.[^\s]+ "                                        # 'Operation'
    r"[^\s]+ "                                                                      # 'Key'
    r"\".*?\" "                                                                     # 'Request-URI'
    r"(([1-5][0-9]{2})|-) "                                                         # 'HTTP status'
    r"[^\s]+ "                                                                      # 'Error Code'
    r"(((\d+)|(-)) ){4}"                                                            # 'Bytes Sent' 'Object Size' 'Total Time' 'Turn-Around Time'
    r"(\".*?\" ){2}"                                                                # 'Referrer' 'User-Agent'
    r"([^\s]+ ){2}"                                                                 # 'Version Id' 'Host Id'
    r"(SigV2|SigV4|-) "                                                             # 'Signature Version'
    r"[^\s]+ "                                                                      # 'Cipher Suite'
    r"(AuthHeader|QueryString|-) "                                                  # 'Authentication Type'
    r"[^\s]+ "                                                                      # 'Host Header'
    r"(TLS[^\s]+|-)"                                                                # 'TLS version'
    r".+[^\s]$")                                                                    # any extra fields

FIELD_NAMES = (
     "bucket_owner",          # 'Bucket Owner'
     "bucket",                # 'Bucket'
     "time",                  # 'Time'
     "ip",                    # 'Remote IP'
     "requester",             # 'Requester ARN/Canonical ID'
     "request_id",            # 'Request ID'
     "operation",             # 'Operation'
     "key",                   # 'Key'
     "request_uri",           # 'Request-URI'
     "http_status",           # 'HTTP status'
     "error_code",            # 'Error Code'
     "bytes_sent",            # 'Bytes Sent'
     "object_size",           # 'Object Size'
     "total_time",            # 'Total Time'
     "turn_around_time",      # 'Turn-Around Time'
     "referer",               # 'Referrer'
     "user_agent",            # 'User-Agent'
     "version_id",            # 'Version Id'
     "host_id",               # 'Host Id'
     "signature_version",     # 'Signature Version'
     "cipher_suite",          # 'Cipher Suite'
     "authentication_type",   # 'Authentication Type'
     "host_header",           # 'Host Header'
     "tls_version"            # 'TLS version'
)

TIME_FIELD_INDEX = 2


class S3Parser(Parser):

    def get_namespace(self):
        return "s3"

    def supports(self, log_file_name):
        return OBJECT_KEY_REGEX.search(log_file_name) is not None

    def validate_line(self, line) -> bool:
        return LOG_FORMAT_VALIDATION_REGEX.search(line) is not None

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
