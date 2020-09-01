import time

import boto3

from logger import log

LOG_GROUP_NAME_PREFIX_TO_NAMESPACE_MAPPING = {
    "/aws/lambda": "lambda",
    "/aws/rds": "rds",
    "/aws/eks": "eks",
    "api-gateway-": "api-gateway"
}


class LogEnricher:

    @staticmethod
    def create(cache_ttl_seconds):
        return LogEnricher(TagsCache(cache_ttl_seconds))

    def __init__(self, tag_cache):
        self._tag_cache = tag_cache

    def get_matadata(self, raw_logs, context):
        metadata = self._basic_enrichment(raw_logs, context)
        tags = self._get_tags(metadata)
        return self._merge(metadata, tags)

    def _basic_enrichment(self, logs, context):

        def _get_aws_namespace(log_group):
            log_group_lower = log_group.lower()
            for prefix, source in LOG_GROUP_NAME_PREFIX_TO_NAMESPACE_MAPPING.items():
                if log_group_lower.startswith(prefix):
                    return source
            return "other"

        log_group = logs['logGroup']
        aws_namespace = _get_aws_namespace(log_group)
        metadata = {'index': 'main',
                      'logGroup': log_group,
                      'logStream': logs['logStream'],
                      'source': aws_namespace,
                      'sourcetype': "aws:" + aws_namespace,
                      'logForwarder': context.function_name.lower() + ":" + context.function_version,
                      'region': self._parse_log_collector_function_arn(context)[0],
                      'awsAccountId': logs['owner']}
        namespace_metadata = self._enricher_factory(metadata['source'])(context, log_group)
        metadata.update(namespace_metadata)
        return metadata

    def _enricher_factory(self, source):
        def lambda_enricher(context, log_group):
            fwd_arn_parts = context.invoked_function_arn.split('function')
            arn_prefix = fwd_arn_parts[0]
            function_name = log_group.split('/')[-1].lower()
            arn = arn_prefix + "function:" + function_name
            return {'host': arn, 'arn': arn, 'functionName': function_name}

        def rds_enricher(context, log_group):
            log_group_parts = log_group.split('/')
            if len(log_group_parts) == 6:
                _, _, _, cluster_or_instance, host, name = log_group_parts
                deployment_type = "db" if cluster_or_instance == "instance" else cluster_or_instance
                region, account_id = self._parse_log_collector_function_arn(context)
                metadata = {'host': host,
                              'arn': f"arn:aws:rds:{region}:{account_id}:{deployment_type}:{host}"}
                if name == 'postgresql':
                    # only for postgresql we can detect dbType
                    metadata['dbType'] = name
                else:
                    metadata['dbLogName'] = name
                return metadata
            else:
                log.warning(f"Cannot parse rds logGroup = {log_group}")
                return default_enricher(context, log_group)

        def eks_enricher(context, log_group):
            log_group_parts = log_group.split("/")
            if len(log_group_parts) == 5:
                region, account_id = self._parse_log_collector_function_arn(context)
                _, _, _, eks_cluster_name, _ = log_group_parts
                arn = f"arn:aws:eks:{region}:{account_id}:cluster/{eks_cluster_name}"
                return {'host': eks_cluster_name, 'arn': arn, 'eksClusterName': eks_cluster_name}
            else:
                log.warning(f"Cannot parse eks logGroup = {log_group}")
                return default_enricher(context, log_group)

        def api_gateway_enricher(context, log_group):
            log_group_parts = log_group.split("/")
            if len(log_group_parts) == 2:
                prefix, stage = log_group_parts
                api_gateway_id = prefix.split("_")[-1]
                region, _ = self._parse_log_collector_function_arn(context)
                arn = f"arn:aws:apigateway:{region}::/restapis/{api_gateway_id}/stages/{stage}"
                return {'arn': arn, 'host': arn, 'apiGatewayStage': stage, 'apiGatewayId': api_gateway_id}
            else:
                log.warning(f"Cannot parse apigateway logGroup = {log_group}")
                return default_enricher(context, log_group)

        def default_enricher(_, log_group):
            return {'host': log_group}

        enrichers = {
            'lambda': lambda_enricher,
            'rds': rds_enricher,
            'eks': eks_enricher,
            'api-gateway': api_gateway_enricher
        }
        return enrichers.get(source, default_enricher)

    def _get_tags(self, enrichment):
        arn = enrichment.get('arn')
        if arn:
            return self._tag_cache.get(arn)

    @staticmethod
    def _merge(enrichment, tags):
        if tags:
            for tag_name in tags.keys():
                if tag_name not in enrichment:
                    enrichment[tag_name] = tags[tag_name]
                else:
                    log.debug(f"Skipping tag with reserved name {tag_name}")
        return enrichment

    @staticmethod
    def _parse_log_collector_function_arn(context):
        parts = context.invoked_function_arn.split(":")
        region, account_id = parts[3], parts[4]
        return region, account_id


class TagsCache(object):
    resource_tagging_client = boto3.client("resourcegroupstaggingapi")

    def __init__(self, cache_ttl_seconds):
        self.tags_by_arn = {}
        self.cache_ttl_seconds = cache_ttl_seconds
        self.last_fetch_time = 0

    def _refresh(self):
        self.last_fetch_time = time.time()
        self.tags_by_arn = self.build_cache()

    def _is_expired(self):
        return time.time() > self.last_fetch_time + self.cache_ttl_seconds

    def get(self, resource_arn):
        if self._is_expired():
            self._refresh()

        return self.tags_by_arn.get(resource_arn.lower(), None)

    def build_cache(self):
        tags_by_arn_cache = {}
        get_resources_paginator = self.resource_tagging_client.get_paginator("get_resources")

        try:
            for page in get_resources_paginator.paginate(
                    ResourceTypeFilters=["lambda", "rds", "eks", "apigateway"], ResourcesPerPage=100
            ):
                page_tags_by_arn = self.parse_get_resources_response_for_tags_by_arn(page)
                tags_by_arn_cache.update(page_tags_by_arn)
        except Exception as ex:
            log.exception(f"Encountered an Exception when trying to fetch tags (exception={ex})")

        return tags_by_arn_cache

    @staticmethod
    def parse_get_resources_response_for_tags_by_arn(resources_page):
        tags_by_arn = {}

        aws_resource_list = resources_page["ResourceTagMappingList"]
        for aws_resource in aws_resource_list:
            arn = aws_resource["ResourceARN"].lower()
            aws_tags = aws_resource["Tags"]
            tags = tags_by_arn.get(arn, {})
            for raw_tag in aws_tags:
                tags[raw_tag["Key"]] = raw_tag.get("Value", "null")
            tags_by_arn[arn] = tags

        return tags_by_arn
