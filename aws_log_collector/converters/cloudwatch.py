import base64
import gzip
import json
from io import BytesIO, BufferedReader

from aws_log_collector.converters.converter import Converter
from aws_log_collector.enrichers.cloudwatch import CloudWatchLogsEnricher
from aws_log_collector.metric import size_of_json


class CloudWatchLogsConverter(Converter):

    def __init__(self, logs_enricher: CloudWatchLogsEnricher):
        self._logs_enricher = logs_enricher

    def supports(self, log_event):
        try:
            data = log_event["awslogs"]["data"]
            return len(data) > 0
        except KeyError:
            return False

    def _convert_to_hec(self, log_event, context, sfx_metrics):
        aws_logs_base64 = log_event["awslogs"]["data"]
        aws_logs_compressed = base64.b64decode(aws_logs_base64)
        aws_logs = self._read_logs(aws_logs_compressed)
        metadata = self._logs_enricher.get_metadata(aws_logs, context, sfx_metrics)
        sfx_metrics.namespace(metadata["source"])
        self._send_input_metrics(sfx_metrics, aws_logs_base64, aws_logs_compressed, aws_logs)

        return self._enriched_logs_to_hec(aws_logs, metadata)

    @staticmethod
    def _read_logs(aws_logs):
        with gzip.GzipFile(fileobj=BytesIO(aws_logs)) as decompress_stream:
            data = b"".join(BufferedReader(decompress_stream))
        return json.loads(data)

    @staticmethod
    def _enriched_logs_to_hec(logs, metadata):

        def _get_fields():
            result = dict(metadata)
            del result["host"]
            del result["source"]
            del result["sourcetype"]
            return result

        fields = _get_fields()
        for item in logs["logEvents"]:
            timestamp_as_string = str(item['timestamp'])
            hec_item = {"event": item["message"],
                        "fields": fields,
                        "host": metadata["host"],
                        "source": metadata["source"],
                        "sourcetype": metadata["sourcetype"],
                        "time": timestamp_as_string[0:-3] + "." + timestamp_as_string[-3:],
                        }

            yield hec_item

    @staticmethod
    def _send_input_metrics(sfx_metrics, aws_logs_base64, aws_logs_compressed, logs):
        sfx_metrics.counters(
                ("sf.org.awsLogCollector.num.inputBase64Bytes", len(aws_logs_base64)),
                ("sf.org.awsLogCollector.num.inputCompressedBytes", len(aws_logs_compressed)),
                ("sf.org.awsLogCollector.num.inputUncompressedBytes", size_of_json(logs))
        )
