from aws_log_collector.logger import log


class BaseEnricher:

    def __init__(self, tags_cache):
        self._tags_cache = tags_cache

    def get_context_metadata(self, context):
        region, aws_account_id = self._parse_log_collector_function_arn(context)
        return {
            "logForwarder": self._get_log_forwarder(context),
            "region": region,
            "awsAccountId": aws_account_id
        }

    def get_tags(self, arn, sfx_metrics):
        if arn:
            return self._tags_cache.get(arn, sfx_metrics)

    @staticmethod
    def merge(metadata, *tags_list):
        for tags in tags_list:
            if tags:
                for tag_name in tags.keys():
                    if tag_name not in metadata:
                        metadata[tag_name] = tags[tag_name]
                    else:
                        log.debug(f"Skipping tag with reserved name {tag_name}:{tags[tag_name]}")
        return metadata

    @staticmethod
    def _get_log_forwarder(context):
        return context.function_name.lower() + ":" + context.function_version

    @staticmethod
    def _parse_log_collector_function_arn(context):
        parts = context.invoked_function_arn.split(":")
        region, account_id = parts[3], parts[4]
        return region, account_id
