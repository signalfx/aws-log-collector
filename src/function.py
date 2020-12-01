import json
import logging
import os

from converters.cloudwatch import CloudWatchLogsConverter
from converters.s3 import S3LogsConverter
from enrichers.cloudwatch import CloudWatchLogsEnricher
from enrichers.s3 import S3LogsEnricher
from lib.client import BatchClient
from lib.s3_service import S3Service
from lib.tags_cache import TagsCache
from logger import log
from metric import SfxMetrics
from parsers.alb import ApplicationELBParser
from parsers.cloudfront import CloudFrontParser
from parsers.nlb import NetworkELBParser
from parsers.s3 import S3Parser

SPLUNK_LOG_URL = os.getenv("SPLUNK_LOG_URL", default="<unknown-url>")
SPLUNK_METRIC_URL = os.getenv("SPLUNK_METRIC_URL", default="<unknown-url>")
SPLUNK_API_KEY = os.getenv("SPLUNK_API_KEY", default="<unknown-token>")
MAX_REQUEST_SIZE_IN_BYTES = int(os.getenv("MAX_REQUEST_SIZE_IN_BYTES", default=2 * 1024 * 1024))
COMPRESSION_LEVEL = int(os.getenv("COMPRESSION_LEVEL", default=6))
TAGS_CACHE_TTL_SECONDS = int(os.getenv("TAGS_CACHE_TTL_SECONDS", default=15 * 60))


class LogCollector:
    def __init__(self):
        tags_cache = TagsCache(TAGS_CACHE_TTL_SECONDS)
        s3_parsers = [S3Parser(), ApplicationELBParser(), NetworkELBParser(),
                      CloudFrontParser()]
        self._converters = [
            CloudWatchLogsConverter(CloudWatchLogsEnricher(tags_cache)),
            S3LogsConverter(S3LogsEnricher(tags_cache), S3Service(), s3_parsers)
        ]

    def forward_log(self, log_event, context):
        with SfxMetrics(SPLUNK_METRIC_URL, SPLUNK_API_KEY) as sfx_metrics:
            try:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Received Event: {json.dumps(log_event)}")
                    log.debug(f"Received context: {self._dump_object(context)}")

                for converter in self._converters:
                    if converter.supports(log_event):
                        hec_logs = converter.convert_to_hec(log_event, context, sfx_metrics)
                        self._send(hec_logs, sfx_metrics)
                        break
                else:
                    log.warning("Received unsupported log event: " + log_event)
                    sfx_metrics.inc_counter('sf.org.awsLogCollector.num.skipped_log_events')
            except Exception as ex:
                log.error(f"Exception occurred: {ex}")
                sfx_metrics.inc_counter('sf.org.awsLogCollector.num.errors')
                raise ex
            finally:
                sfx_metrics.inc_counter('sf.org.awsLogCollector.num.invocations')

    @staticmethod
    def _send(logs, sfx_metrics):
        log.debug(f"About to send {len(logs)} log item(s)...")
        for item in logs:
            log.debug(item)

        with BatchClient.create(SPLUNK_LOG_URL, SPLUNK_API_KEY, MAX_REQUEST_SIZE_IN_BYTES, COMPRESSION_LEVEL,
                                sfx_metrics) as client:
            client.send(logs)

    @staticmethod
    def _dump_object(context):
        return '%s(%s)' % (
            type(context).__name__,
            ', '.join('%s=%s' % item for item in vars(context).items()))


log_forwarder = LogCollector()
lambda_handler = log_forwarder.forward_log
