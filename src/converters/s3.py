import json
from urllib.parse import unquote_plus

from converters.converter import Converter
from enrichers.s3 import S3LogsEnricher
from lib.s3_service import S3Service
from logger import log
from parsers.s3_access_logs_parser import parse_s3_access_log_line


class S3LogsConverter(Converter):

    def __init__(self, logs_enricher: S3LogsEnricher, s3_service: S3Service):
        self._logs_enricher = logs_enricher
        self._s3_service = s3_service

    def supports(self, log_event):
        try:
            records = log_event["Records"]
            return len(records) > 0 \
                   and "name" in records[0]["s3"]["bucket"] \
                   and "key" in records[0]["s3"]["object"]
        except KeyError:
            return False

    def _convert_to_hec(self, log_event, context, sfx_metrics):
        common_metadata = self._logs_enricher.get_common_metadata(context)

        records = log_event["Records"]
        for record in records:
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])
            try:
                namespace = self._s3_service.get_aws_namespace(key) or "unknown"

                bytes_received = 0
                for line in self._s3_service.read_lines(bucket, key):
                    bytes_received += len(line)
                    parsed_line = self._parse_line(namespace, line)
                    metadata = self._logs_enricher.get_metadata(namespace, parsed_line, common_metadata, sfx_metrics)
                    yield self._to_hec(namespace, parsed_line, metadata)

                self._send_input_metrics(sfx_metrics, namespace, bytes_received)
            except Exception as e:
                log.error(f"Failed to process s3 log file: s3://{bucket}/{key} error: {e}")
                sfx_metrics.inc_counter('sf.org.awsLogCollector.num.s3.errors')

    @staticmethod
    def _parse_line(namespace, line):
        if namespace == "s3":
            parsed = parse_s3_access_log_line(line)
        else:
            parsed = None

        return {"raw_log_line": line} if parsed is None else {"raw_log_line": line, **parsed}

    @staticmethod
    def _to_hec(namespace, parsed_line, metadata):
        hec_item = {
            "event": parsed_line.get("raw_log_line"),
            "fields": metadata,
            "source": namespace,
            "sourcetype": "aws:" + namespace,
            "time": parsed_line.get("hec_time"),
        }
        return json.dumps(hec_item)

    @staticmethod
    def _send_input_metrics(sfx_metrics, namespace, bytes_received):
        sfx_metrics.namespace(namespace)
        sfx_metrics.counters(
            ("sf.org.awsLogCollector.num.inputUncompressedBytes", bytes_received)
        )
