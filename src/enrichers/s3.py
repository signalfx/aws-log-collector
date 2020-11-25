from enrichers.tags_cache import TagsCache


class S3LogsEnricher:

    @staticmethod
    def create(tags_cache: TagsCache):
        return S3LogsEnricher(tags_cache)

    def __init__(self, tags_cache):
        self._tags_cache = tags_cache

    def get_matadata(self, raw_logs, context, sfx_metrics):
        raise NotImplementedError
