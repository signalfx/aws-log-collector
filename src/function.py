import base64
import gzip
import json
import logging
import os
import time
from io import BytesIO, BufferedReader

import boto3
import requests

MAX_REQUEST_SIZE_IN_BYTES = int(os.getenv("MAX_REQUEST_SIZE_IN_BYTES", 1024 * 800))
COMPRESSION_LEVEL = int(os.getenv("COMPRESSION_LEVEL", 6))
TAGS_CACHE_TTL_SECONDS = int(os.getenv("TAGS_CACHE_TTL_SECONDS", 15 * 60))
SFX_URL = os.getenv("SFX_URL", default="http://lab-ingest.corp.signalfx.com/v1/log")
SFX_API_KEY = os.getenv("SFX_API_KEY", "<wrong-token>")
LOG_GROUP_SOURCE_NAMES = [
    "lambda",
    "rds",
    "eks",
    "apigateway",
    "kinesis"
]

log = logging.getLogger()
log.setLevel(logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO").upper()))


class RetryableException(Exception):
    pass


class RetryableClient(object):

    def __init__(self, client, max_retry=3):
        self._client = client
        self._max_retry = max_retry

    def send(self, logs):
        backoff = 1
        attempt = 0
        while True:
            try:
                self._client.send(logs)
                return
            except RetryableException as err:
                if attempt < self._max_retry:
                    attempt += 1
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    raise err

    def __enter__(self):
        self._client.__enter__()
        return self

    def __exit__(self, ex_type, ex_value, traceback):
        self._client.__exit__(ex_type, ex_value, traceback)


class Batcher(object):

    def __init__(self, max_batch_size_bytes):
        self._max_batch_size_bytes = max_batch_size_bytes

    def batch(self, items):
        batches = []
        batch = []
        batch_size_bytes = 0
        for item in items:
            item_size_bytes = self._size_of_bytes(item)
            if item_size_bytes > self._max_batch_size_bytes:
                log.info(f"Item is bigger than max batch size ({self._max_batch_size_bytes}), going to truncate it")
                item = item.encode("utf-8")[:self._max_batch_size_bytes].decode("utf-8", "ignore")
                item_size_bytes = self._size_of_bytes(item)

            if item_size_bytes + batch_size_bytes > self._max_batch_size_bytes:
                batches.append(batch)
                batch = []
                batch_size_bytes = 0

            batch.append(item)
            batch_size_bytes += item_size_bytes

        if len(batch) > 0:
            batches.append(batch)
        return batches

    @staticmethod
    def _size_of_bytes(item):
        return len(str(item).encode("UTF-8"))


class SfxHTTPClient(object):

    def __init__(self, host, api_key, timeout=10):
        self._url = host
        self._timeout = timeout
        self._session = None
        self._headers = {"Content-type": "application/json", "Content-Encoding": "gzip", "X-SF-TOKEN": api_key}

    def _connect(self):
        self._session = requests.Session()
        self._session.headers.update(self._headers)

    def _close(self):
        self._session.close()
        self._session = None

    def send(self, log_events):
        data = self._combine_events(log_events)
        data = self._compress_logs(data)

        try:
            log.debug(f"Data to be sent={data}")
            log.info(f"Sending request to url={self._url}")
            resp = self._session.post(self._url, data, timeout=self._timeout)
        except Exception:
            # network error
            raise RetryableException()
        if resp.status_code >= 500:
            raise RetryableException()
        elif resp.status_code >= 400:
            raise Exception(f"client error (status={resp.status_code}, reason={resp.reason})")

        return

    @staticmethod
    def _combine_events(logs):
        return "\n".join(logs)

    @staticmethod
    def _compress_logs(batch):
        return gzip.compress(bytes(batch, "utf-8"), COMPRESSION_LEVEL)

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, ex_type, ex_value, traceback):
        self._close()


class TagsCache(object):
    resource_tagging_client = boto3.client("resourcegroupstaggingapi")

    def __init__(self, cache_ttl_seconds=TAGS_CACHE_TTL_SECONDS):
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


class LogCollector:
    def __init__(self):
        self._tag_cache = TagsCache()

    def forward_log(self, log_event, context):
        if log.isEnabledFor(logging.DEBUG):
            log.debug(f"Received Event:{json.dumps(log_event)}")
            log.debug(f"Received context:{self._dump_object(context)}")

        raw_logs = self._read_logs(log_event)
        enriched_logs = self._basic_enrichment(raw_logs, context)
        enriched_logs = self._tags_enrichment(enriched_logs)
        hec_logs = self._convert_to_hec(enriched_logs)
        self._send_logs(hec_logs)

    @staticmethod
    def _read_logs(log_event):
        with gzip.GzipFile(
                fileobj=BytesIO(base64.b64decode(log_event["awslogs"]["data"]))
        ) as decompress_stream:
            data = b"".join(BufferedReader(decompress_stream))
        return json.loads(data)

    @staticmethod
    def _enricher_factory(source):
        def lambda_enricher(context, log_group):
            fwd_arn_parts = context.invoked_function_arn.split('function')
            arn_prefix = fwd_arn_parts[0]
            function_name = log_group.split('/')[-1].lower()
            arn = arn_prefix + "function:" + function_name
            return {'host': arn, 'arn': arn, 'functionName': function_name}

        def rds_enricher(context, log_group):
            log_group_parts = log_group.split('/')
            enrichment = {}
            if len(log_group_parts) == 6:
                _, _, _, cluster_or_instance, host, _ = log_group_parts
                enrichment['host'] = host
                name = log_group_parts[5]
                deployment_type = "db" if cluster_or_instance == "instance" else cluster_or_instance
                region, account_id = _parse_invoked_function_arn(context)
                enrichment['arn'] = f"arn:aws:rds:{region}:{account_id}:{deployment_type}:{host}"
                if name == 'postgresql':
                    enrichment['dbType'] = name
                else:
                    enrichment['dbLogName'] = name
            else:
                log.warning(f"Cannot parse rds logGroup = {log_group}")
            return enrichment

        def eks_enricher(context, log_group):
            _, _, _, region, account_id, _, _ = context.invoked_function_arn.split(":")
            log_group_parts = log_group.split("/")
            if len(log_group_parts) == 5:
                _, _, _, eks_cluster_name, _ = log_group.split("/")
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
                region, _ = _parse_invoked_function_arn(context)
                arn = f"arn:aws:apigateway:{region}::/restapis/{api_gateway_id}/stages/{stage}"
                return {'arn': arn, 'host': arn, 'apiGatewayStage': stage, 'apiGatewayId': api_gateway_id}
            else:
                log.warning(f"Cannot parse apigateway logGroup = {log_group}")
                return default_enricher(context, log_group)

        def default_enricher(_, log_group):
            return {'host': log_group}

        def _parse_invoked_function_arn(context):
            _, _, _, region, account_id, _, _ = context.invoked_function_arn.split(":")
            return region, account_id

        enrichers = {
            'lambda': lambda_enricher,
            'rds': rds_enricher,
            'eks': eks_enricher,
            'apigateway': api_gateway_enricher
        }
        return enrichers.get(source, default_enricher)

    def _basic_enrichment(self, logs, context):
        def _get_source(log_group):
            for aws_source in LOG_GROUP_SOURCE_NAMES:
                if aws_source in log_group:
                    return aws_source
            if log_group.startswith("api-gateway-"):
                return "apigateway"
            return "cloudwatch"

        def _get_region(arn):
            split_arn = arn.split(":")
            if len(split_arn) > 7:
                split_arn = split_arn[:7]
            _, _, _, region, _, _, _ = split_arn
            return region

        log_group = logs['logGroup']
        enrichment = {'logGroup': log_group,
                      'logStream': logs['logStream'],
                      'source': _get_source(log_group.lower()),
                      'logForwarder': context.function_name.lower() + ":" + context.function_version,
                      'region': _get_region(context.invoked_function_arn),
                      'aws_account_id': logs['owner']}
        namespace_metadata = self._enricher_factory(enrichment['source'])(context, log_group)
        enrichment.update(namespace_metadata)
        logs['enrichment'] = enrichment
        return logs

    def _tags_enrichment(self, enriched_logs):
        arn = enriched_logs['enrichment'].get('arn')
        if arn:
            tags = self._tag_cache.get(arn)
            if tags:
                enrichment = enriched_logs['enrichment']
                for tag_name in tags.keys():
                    if tag_name not in enriched_logs['enrichment']:
                        enrichment[tag_name] = tags[tag_name]
                    else:
                        log.debug(f"Skipping tag with reserved name {tag_name}")
        return enriched_logs

    @staticmethod
    def _send_logs(logs):
        batcher = Batcher(MAX_REQUEST_SIZE_IN_BYTES)
        http_client = SfxHTTPClient(SFX_URL, SFX_API_KEY)

        with RetryableClient(http_client) as client:
            for batch in batcher.batch(logs):
                try:
                    client.send(batch)
                except Exception:
                    log.exception(f"Exception while forwarding log batch {batch}")
                else:
                    if log.isEnabledFor(logging.DEBUG):
                        log.debug(f"Forwarded log batch: {json.dumps(batch)}")

    @staticmethod
    def _convert_to_hec(enriched_logs):
        for item in enriched_logs["logEvents"]:
            hec_item = {}
            hec_item['event'] = item['message']
            timestamp_as_string = str(item['timestamp'])
            hec_item["time"] = timestamp_as_string[0:-3] + "." + timestamp_as_string[-3:]
            hec_item['sourcetype'] = 'aws'
            hec_item['fields'] = dict(enriched_logs['enrichment'])
            hec_item['host'] = hec_item['fields']['host']
            hec_item['source'] = hec_item['fields']['source']
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
