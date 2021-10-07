# Copyright 2021 Splunk, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from typing import List
from urllib.parse import unquote_plus

from aws_log_collector.converters.converter import Converter
from aws_log_collector.enrichers.s3 import S3LogsEnricher
from aws_log_collector.lib.s3_service import S3Service
from aws_log_collector.logger import log
from aws_log_collector.parsers.parser import Parser


class S3LogsConverter(Converter):

    def __init__(self, logs_enricher: S3LogsEnricher, s3_service: S3Service, parsers: List[Parser], include_log_fields: bool):
        self._logs_enricher = logs_enricher
        self._s3_service = s3_service
        self._parsers = parsers
        self._include_log_fields = include_log_fields

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
                    sfx_metrics.inc_counter("sf.org.awsLogCollector.num.s3.unsupported_log_files")
                    continue

                yield from self._convert_s3_object_to_hec_items(bucket, key, parser, context_metadata, sfx_metrics)
            except Exception as e:
                log.error(f"Failed to process s3 log file: s3://{bucket}/{key} error: {e}")
                sfx_metrics.inc_counter("sf.org.awsLogCollector.num.s3.errors")

    def _convert_s3_object_to_hec_items(self, bucket, key, parser, context_metadata, sfx_metrics):
        namespace = parser.get_namespace()
        file_metadata = parser.get_file_metadata(context_metadata, key)
        common_metadata = {**context_metadata, **file_metadata}

        bytes_received = 0
        raw_lines_generator = self._s3_service.read_lines(bucket, key)
        for line in parser.complete_lines(raw_lines_generator):
            if bytes_received == 0 and (parser.validate_line(line) is False):
                log.error(f"First S3 file line is invalid: {line};"
                          f" skipping file with key: {key}; in bucket: {bucket}")
                break
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

    def _to_hec(self, namespace, parsed_line, metadata):
        if (self._include_log_fields):
            metadata["event"] = parsed_line.fields

        hec_item = {
            "event": parsed_line.log_line,
            "fields": metadata,
            "source": namespace,
            "sourcetype": "aws:" + namespace,
            "time": parsed_line.hec_time
        }
        return hec_item

    @staticmethod
    def _send_input_metrics(sfx_metrics, namespace, bytes_received):
        sfx_metrics.namespace(namespace)
        sfx_metrics.counters(
            ("sf.org.awsLogCollector.num.inputUncompressedBytes", bytes_received)
        )
