import copy

from aws_log_collector.enrichers.base_enricher import BaseEnricher


class S3LogsEnricher(BaseEnricher):

    def get_metadata(self, arns, metadata, sfx_metrics):
        result = copy.deepcopy(metadata)

        for item in arns:
            name, arn = item
            tags = self.get_tags(arn, sfx_metrics)
            result = self.merge(result, {name: arn}, tags)

        return result
