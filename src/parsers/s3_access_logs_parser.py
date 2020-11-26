import re
from datetime import datetime

from logger import log

line_pattern = r'(\S+) (\S+) \[(.*?)\] (\S+) (\S+) ' \
               r'(\S+) (\S+) (\S+) "([^"]+)" ' \
               r'(\S+) (\S+) (\S+) (\S+) (\S+) (\S+) ' \
               r'"([^"]+)" "([^"]+)" (\S+) (\S+) ' \
               r'(\S+) (\S+) (\S+) (\S+) ' \
               r'(\S+)'

line_regex = re.compile(line_pattern)

field_names = ("bucket_owner", "bucket", "time", "ip", "requester",
               "request_id", "operation", "key", "request_uri", "http_status",
               "error_code", "bytes_sent", "object_size", "total_time", "turn_around_time",
               "referer", "user_agent", "version_id", "host_id",
               "signature_version", "cipher_suite", "authentication_type", "host_header",
               "tls_version")


def parse_s3_access_log_line(line):
    match = line_regex.match(line)
    if not match:
        return None

    result = {}
    for i in range(len(field_names)):
        result[field_names[i]] = match.group(i + 1)

    result['hec_time'] = _to_hec_time(result['time'])
    return result


def _to_hec_time(s3_time):
    try:
        return datetime.strptime(s3_time, '%d/%b/%Y:%H:%M:%S %z').timestamp()
    except ValueError as ex:
        log.warn(f'Failed to parse s3 timestamp {s3_time}: {ex}')
        return None

