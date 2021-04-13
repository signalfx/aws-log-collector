import boto3
from botocore.config import Config
import time
from aws_log_collector.logger import log

SUPPORTED_NAMESPACES = ["lambda", "rds", "eks", "apigateway", "s3", "elasticloadbalancing",
                        "redshift"]

SUPPORTED_GLOBAL_NAMESPACES = ["cloudfront"]


class TagsCache(object):
    resource_tagging_client = boto3.client("resourcegroupstaggingapi")
    global_resource_tagging_client = boto3.client("resourcegroupstaggingapi",
                                                  config=Config(region_name="us-east-1"))

    def __init__(self, cache_ttl_seconds):
        self.tags_by_arn = {}
        self.cache_ttl_seconds = cache_ttl_seconds
        self.last_fetch_time = 0

    def get(self, resource_arn, sfx_metrics):
        if self._is_expired():
            self._refresh(sfx_metrics)

        return self.tags_by_arn.get(resource_arn.lower(), None)

    def _is_expired(self):
        return time.time() > self.last_fetch_time + self.cache_ttl_seconds

    def _refresh(self, sfx_metrics):
        self.last_fetch_time = time.time()
        self.tags_by_arn = self._build_cache()
        sfx_metrics.inc_counter("sf.org.awsLogCollector.num.tagCacheRefresh")

    def _build_cache(self):
        tags_by_arn_cache = {}

        TagsCache._load_tags(self.resource_tagging_client, SUPPORTED_NAMESPACES, tags_by_arn_cache)
        TagsCache._load_tags(self.global_resource_tagging_client, SUPPORTED_GLOBAL_NAMESPACES, tags_by_arn_cache)

        return tags_by_arn_cache

    @staticmethod
    def _load_tags(resource_tagging_client, supported_namespaces, tags_by_arn_cache):
        get_resources_paginator = resource_tagging_client.get_paginator("get_resources")

        try:
            for page in get_resources_paginator.paginate(
                    ResourceTypeFilters=supported_namespaces, ResourcesPerPage=100
            ):
                page_tags_by_arn = TagsCache._parse_get_resources_response_for_tags_by_arn(page)
                tags_by_arn_cache.update(page_tags_by_arn)
        except Exception as ex:
            log.exception(f"Encountered an Exception when trying to fetch tags (exception={ex})")


    @staticmethod
    def _parse_get_resources_response_for_tags_by_arn(resources_page):
        tags_by_arn = {}

        aws_resource_list = resources_page["ResourceTagMappingList"]
        for aws_resource in aws_resource_list:
            arn = aws_resource["ResourceARN"].lower()
            log.debug(f"loading tags for {arn}")
            aws_tags = aws_resource["Tags"]
            tags = tags_by_arn.get(arn, {})
            for raw_tag in aws_tags:
                tags[raw_tag["Key"]] = raw_tag.get("Value", "null")
            tags_by_arn[arn] = tags

        return tags_by_arn
