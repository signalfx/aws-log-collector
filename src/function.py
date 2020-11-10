import base64
import gzip
import json
import logging
import os
from io import BytesIO, BufferedReader

from client import BatchClient
from enrichment import LogEnricher
from logger import log
from metric import SfxMetrics, size_of_json

SPLUNK_LOG_URL = os.getenv("SPLUNK_LOG_URL", default="<unknown-url>")
SPLUNK_METRIC_URL = os.getenv("SPLUNK_METRIC_URL", default="<unknown-url>")
SPLUNK_API_KEY = os.getenv("SPLUNK_API_KEY", default="<unknown-token>")
MAX_REQUEST_SIZE_IN_BYTES = int(os.getenv("MAX_REQUEST_SIZE_IN_BYTES", default=2 * 1024 * 1024))
COMPRESSION_LEVEL = int(os.getenv("COMPRESSION_LEVEL", default=6))
TAGS_CACHE_TTL_SECONDS = int(os.getenv("TAGS_CACHE_TTL_SECONDS", default=15 * 60))


class LogCollector:
    def __init__(self):
        self._log_enricher = LogEnricher.create(TAGS_CACHE_TTL_SECONDS)

    def forward_log(self, log_event, context):
        with SfxMetrics(SPLUNK_METRIC_URL, SPLUNK_API_KEY) as sfx_metrics:
            try:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Received Event:{json.dumps(log_event)}")
                    log.debug(f"Received context:{self._dump_object(context)}")
                aws_logs_base64 = log_event["awslogs"]["data"]
                aws_logs_compressed = base64.b64decode(aws_logs_base64)
                aws_logs = self._read_logs(aws_logs_compressed)
                metadata = self._log_enricher.get_matadata(aws_logs, context, sfx_metrics)
                sfx_metrics.namespace(metadata['source'])
                self._send_input_metrics(sfx_metrics, aws_logs_base64, aws_logs_compressed, aws_logs)

                hec_logs = list(self._convert_to_hec(aws_logs, metadata))
                self._send_logs(hec_logs, sfx_metrics)
            except Exception as ex:
                log.error(f"Exception occurred: {ex}")
                sfx_metrics.inc_counter('sf.org.awsLogCollector.num.errors')
                raise ex
            finally:
                sfx_metrics.inc_counter('sf.org.awsLogCollector.num.invocations')

    @staticmethod
    def _read_logs(aws_logs):
        with gzip.GzipFile(
                fileobj=BytesIO(aws_logs)
        ) as decompress_stream:
            data = b"".join(BufferedReader(decompress_stream))
        return json.loads(data)

    @staticmethod
    def _send_logs(logs, sfx_metrics):
        with BatchClient.create(SPLUNK_LOG_URL, SPLUNK_API_KEY, MAX_REQUEST_SIZE_IN_BYTES, COMPRESSION_LEVEL,
                                sfx_metrics) as client:
            client.send(logs)

    @staticmethod
    def _convert_to_hec(logs, metadata):

        def _get_fields():
            result = dict(metadata)
            del result['host']
            del result['source']
            del result['sourcetype']
            return result

        fields = _get_fields()
        for item in logs["logEvents"]:
            timestamp_as_string = str(item['timestamp'])
            hec_item = {'event': item['message'],
                        'fields': fields,
                        'host': metadata['host'],
                        'source': metadata['source'],
                        'sourcetype': metadata['sourcetype'],
                        "time": timestamp_as_string[0:-3] + "." + timestamp_as_string[-3:],
                        }

            yield json.dumps(hec_item)

    @staticmethod
    def _send_input_metrics(sfx_metrics, aws_logs_base64, aws_logs_compressed, logs):
        sfx_metrics.counters(
                ('sf.org.awsLogCollector.num.inputBase64Bytes', len(aws_logs_base64)),
                ('sf.org.awsLogCollector.num.inputCompressedBytes', len(aws_logs_compressed)),
                ('sf.org.awsLogCollector.num.inputUncompressedBytes', size_of_json(logs))
        )

    @staticmethod
    def _dump_object(context):
        return '%s(%s)' % (
            type(context).__name__,
            ', '.join('%s=%s' % item for item in vars(context).items()))


log_forwarder = LogCollector()
lambda_handler = log_forwarder.forward_log
