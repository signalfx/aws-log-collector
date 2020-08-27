import base64
import gzip
import json
import logging
import os
from io import BytesIO, BufferedReader
from logger import log
from client import BatchClient
from enrichment import LogEnricher

SPLUNK_URL = os.getenv("SPLUNK_URL", default="<unknown>")
SPLUNK_API_KEY = os.getenv("SPLUNK_API_KEY", "<wrong-token>")
MAX_REQUEST_SIZE_IN_BYTES = int(os.getenv("MAX_REQUEST_SIZE_IN_BYTES", 1024 * 800))
COMPRESSION_LEVEL = int(os.getenv("COMPRESSION_LEVEL", 6))
TAGS_CACHE_TTL_SECONDS = int(os.getenv("TAGS_CACHE_TTL_SECONDS", 15 * 60))


class LogCollector:
    def __init__(self):
        self._log_enricher = LogEnricher.create(TAGS_CACHE_TTL_SECONDS)

    def forward_log(self, log_event, context):
        if log.isEnabledFor(logging.DEBUG):
            log.debug(f"Received Event:{json.dumps(log_event)}")
            log.debug(f"Received context:{self._dump_object(context)}")

        logs = self._read_logs(log_event)
        metadata = self._log_enricher.get_matadata(logs, context)
        hec_logs = list(self._convert_to_hec(logs, metadata))
        self._send_logs(hec_logs)

    @staticmethod
    def _read_logs(log_event):
        with gzip.GzipFile(
                fileobj=BytesIO(base64.b64decode(log_event["awslogs"]["data"]))
        ) as decompress_stream:
            data = b"".join(BufferedReader(decompress_stream))
        return json.loads(data)

    @staticmethod
    def _send_logs(logs):
        with BatchClient.create(SPLUNK_URL, SPLUNK_API_KEY, MAX_REQUEST_SIZE_IN_BYTES, COMPRESSION_LEVEL) as client:
            try:
                client.send(logs)
            except Exception:
                log.exception(f"Exception while sending logs {logs}")

    @staticmethod
    def _convert_to_hec(logs, metadata):
        for item in logs["logEvents"]:
            timestamp_as_string = str(item['timestamp'])
            hec_item = {'event': item['message'],
                        "time": timestamp_as_string[0:-3] + "." + timestamp_as_string[-3:],
                        'sourcetype': 'aws',
                        'fields': dict(metadata),
                        'host': metadata['host'],
                        'source': metadata['source']}
            del hec_item['fields']['host']
            del hec_item['fields']['source']

            yield json.dumps(hec_item)

    @staticmethod
    def _dump_object(context):
        return '%s(%s)' % (
            type(context).__name__,
            ', '.join('%s=%s' % item for item in vars(context).items()))


log_forwarder = LogCollector()
lambda_handler = log_forwarder.forward_log
