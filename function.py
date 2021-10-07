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

import json
import logging
import os

from aws_log_collector.cleaners.regex import RegexMessageCleaner
from aws_log_collector.converters.cloudwatch import CloudWatchLogsConverter
from aws_log_collector.converters.s3 import S3LogsConverter
from aws_log_collector.enrichers.cloudwatch import CloudWatchLogsEnricher
from aws_log_collector.enrichers.s3 import S3LogsEnricher
from aws_log_collector.lib.client import BatchClient
from aws_log_collector.lib.s3_service import S3Service
from aws_log_collector.lib.tags_cache import TagsCache
from aws_log_collector.parsers.alb import ApplicationELBParser
from aws_log_collector.parsers.cloudfront import CloudFrontParser
from aws_log_collector.parsers.nlb import NetworkELBParser
from aws_log_collector.parsers.redshift_connectionlog import RedshiftConnectionLogParser
from aws_log_collector.parsers.redshift_useractivity import RedshiftUserActivityLogParser
from aws_log_collector.parsers.redshift_userlog import RedshiftUserLogParser
from aws_log_collector.parsers.s3 import S3Parser
from aws_log_collector.logger import log
from aws_log_collector.metric import SfxMetrics

SPLUNK_LOG_URL = os.getenv("SPLUNK_LOG_URL", default="<unknown-url>")
SPLUNK_METRIC_URL = os.getenv("SPLUNK_METRIC_URL", default="<unknown-url>")
SPLUNK_API_KEY = os.getenv("SPLUNK_API_KEY", default="<unknown-token>")
MAX_REQUEST_SIZE_IN_BYTES = int(os.getenv("MAX_REQUEST_SIZE_IN_BYTES", default=2 * 1024 * 1024))
COMPRESSION_LEVEL = int(os.getenv("COMPRESSION_LEVEL", default=6))
TAGS_CACHE_TTL_SECONDS = int(os.getenv("TAGS_CACHE_TTL_SECONDS", default=15 * 60))
REDACTION_RULE = os.getenv("REDACTION_RULE", default="")
REDACTION_RULE_REPLACEMENT = os.getenv("REDACTION_RULE_REPLACEMENT", default="**REDACTED**")
INCLUDE_LOG_FIELDS = bool(os.getenv("INCLUDE_LOG_FIELDS", default=False))


class LogCollector:
    def __init__(self):
        tags_cache = TagsCache(TAGS_CACHE_TTL_SECONDS)
        s3_parsers = [
            S3Parser(),
            ApplicationELBParser(),
            NetworkELBParser(),
            CloudFrontParser(),
            RedshiftUserLogParser(),
            RedshiftUserActivityLogParser(),
            RedshiftConnectionLogParser()
        ]
        self._converters = [
            CloudWatchLogsConverter(CloudWatchLogsEnricher(tags_cache)),
            S3LogsConverter(S3LogsEnricher(tags_cache), S3Service(), s3_parsers, INCLUDE_LOG_FIELDS)
        ]
        self._cleaners = []
        if REDACTION_RULE != "":
            self._cleaners.append(RegexMessageCleaner(REDACTION_RULE, REDACTION_RULE_REPLACEMENT))

    def forward_log(self, log_event, context):
        with SfxMetrics(SPLUNK_METRIC_URL, SPLUNK_API_KEY) as sfx_metrics:
            try:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Received Event: {json.dumps(log_event)}")
                    log.debug(f"Received context: {self._dump_object(context)}")

                for converter in self._converters:
                    if converter.supports(log_event):
                        hec_items = converter.convert_to_hec(log_event, context, sfx_metrics)

                        # modifying logs based on cleaners provided
                        for cleaner in self._cleaners:
                            hec_items = [cleaner.cleanup_hec_item_message(hec_item, context, sfx_metrics) for hec_item in hec_items]

                        # convert hec_items to jsons to produce hec_logs
                        hec_logs = [json.dumps(hec_item) for hec_item in hec_items]
                        self._send(hec_logs, sfx_metrics)
                        break
                else:
                    log.warning("Received unsupported log event: " + json.dumps(log_event))
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
