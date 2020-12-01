import json
from typing import List
from urllib.parse import unquote_plus

from converters.converter import Converter
from enrichers.s3 import S3LogsEnricher
from lib.s3_service import S3Service
from logger import log
from parsers.parser import Parser, ParsedLine


class S3LogsConverter(Converter):

    def __init__(self, logs_enricher: S3LogsEnricher, s3_service: S3Service, parsers: List[Parser]):
        self._logs_enricher = logs_enricher
        self._s3_service = s3_service
        self._parsers = parsers

    def supports(self, log_event):
        try:
            records = log_event["Records"]
            return len(records) > 0 \
                   and "name" in records[0]["s3"]["bucket"] \
                   and "key" in records[0]["s3"]["object"]
        except KeyError:
            return False

    def _convert_to_hec(self, log_event, context, sfx_metrics):
        context_metadata = self._logs_enricher.get_context_metadata(context)

        records = log_event["Records"]
        for record in records:
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])
            try:
                parser = self._find_parser(key)
                if parser is None:
                    log.error(f"Parser not found for object s3://{bucket}/{key}")
                    sfx_metrics.inc_counter('sf.org.awsLogCollector.num.s3.unsupported_log_files')
                    continue

                yield from self._convert_s3_object_to_hec_items(bucket, key, parser, context_metadata, sfx_metrics)
            except Exception as e:
                log.error(f"Failed to process s3 log file: s3://{bucket}/{key} error: {e}")
                sfx_metrics.inc_counter('sf.org.awsLogCollector.num.s3.errors')

    def _convert_s3_object_to_hec_items(self, bucket, key, parser, context_metadata, sfx_metrics):
        namespace = parser.get_namespace()
        file_metadata = parser.get_file_metadata(context_metadata, key)
        common_metadata = {**context_metadata, **file_metadata}

        bytes_received = 0
        for line in self._s3_service.read_lines(bucket, key):
            bytes_received += len(line)
            parsed_line = parser.parse(common_metadata, line)
            metadata = self._logs_enricher.get_metadata(parsed_line.arns, common_metadata, sfx_metrics)
            yield self._to_hec(namespace, parsed_line, metadata)

        self._send_input_metrics(sfx_metrics, namespace, bytes_received)

    def _find_parser(self, log_file_name):
        for parser in self._parsers:
            if parser.supports(log_file_name):
                return parser
        else:
            return None

    @staticmethod
    def _to_hec(namespace, parsed_line, metadata):
        hec_item = {
            "event": parsed_line.raw_log_line,
            "fields": metadata,
            "source": namespace,
            "sourcetype": "aws:" + namespace,
            "time": parsed_line.hec_time
        }
        return json.dumps(hec_item)

    @staticmethod
    def _send_input_metrics(sfx_metrics, namespace, bytes_received):
        sfx_metrics.namespace(namespace)
        sfx_metrics.counters(
            ("sf.org.awsLogCollector.num.inputUncompressedBytes", bytes_received)
        )
