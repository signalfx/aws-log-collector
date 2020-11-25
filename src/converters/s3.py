from converters.converter import Converter
from enrichers.s3 import S3LogsEnricher


class S3LogsConverter(Converter):

    def __init__(self, logs_enricher: S3LogsEnricher):
        self._logs_enricher = logs_enricher

    def supports(self, log_event):
        try:
            records = log_event["Records"]
            return len(records) > 0 \
                and "name" in records[0]["s3"]["bucket"] \
                and "key" in records[0]["s3"]["object"]
        except KeyError:
            return False

    def _convert_to_hec(self, log_event, context, sfx_metrics):
        raise NotImplementedError
