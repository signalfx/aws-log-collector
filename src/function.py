import base64
import gzip
import json
import logging
import os
from io import BytesIO, BufferedReader

import boto3
import time
from botocore.vendored import requests

SFX_COMPRESSION_LEVEL = int(os.getenv("SFX_COMPRESSION_LEVEL", 6))
SFX_MAX_REQUEST_SIZE_IN_BYTES = int(os.getenv("SFX_MAX_REQUEST_SIZE_IN_BYTES", 1024 * 800))
TAGS_CACHE_TTL_SECONDS = int(os.getenv("TAGS_CACHE_TTL_SECONDS", 15 * 60))
SFX_URL = os.getenv("SFX_URL", default="http://lab-ingest.corp.signalfx.com/v1/log")
SFX_API_KEY = os.getenv("SFX_API_KEY", "<wrong-token>")

LOG_GROUP_SOURCE_NAMES = [
    "apigateway",
    "cloudfront",
    "codebuild",
    "eks",
    "fargate",
    "kinesis",
    "lambda",
    "sns",
    "rds",
    "redshift",
    "route53",
    "vpc"
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
                item = item[0:self._max_batch_size_bytes]
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

    def send(self, log_events):
        data = self._combine_events(log_events)
        data = self._compress_logs(data)

        try:
            print("Data to be sent=", data)
            print("Sending request url=", self._url)
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
        return gzip.compress(bytes(batch, "utf-8"), SFX_COMPRESSION_LEVEL)

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

        return self.tags_by_arn.get(resource_arn, None)

    def build_cache(self):
        tags_by_arn_cache = {}
        get_resources_paginator = self.resource_tagging_client.get_paginator("get_resources")

        try:
            for page in get_resources_paginator.paginate(
                    ResourceTypeFilters=["lambda"], ResourcesPerPage=100
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
            # todo(karol) can use map here
            tags = {}
            for raw_tag in aws_tags:
                tags[raw_tag["Key"]] = raw_tag.get("Value", "null")

            tags_by_arn[arn] = {**tags_by_arn.get(arn, {}), **tags}

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

    def _read_logs(self, log_event):
        with gzip.GzipFile(
                fileobj=BytesIO(base64.b64decode(log_event["awslogs"]["data"]))
        ) as decompress_stream:
            data = b"".join(BufferedReader(decompress_stream))
        return json.loads(data)

    def _basic_enrichment(self, logs, context):
        def _get_source(log_group):
            for aws_source in LOG_GROUP_SOURCE_NAMES:
                if aws_source in log_group:
                    return aws_source
            return "cloudwatch"

        def _enricher_factory(source):
            def lambda_enricher():
                fwd_arn_parts = context.invoked_function_arn.split('function')
                arn_prefix = fwd_arn_parts[0]
                # fix account id
                arn_prefix_parts = arn_prefix.split(":")
                arn_prefix = ":".join(arn_prefix_parts[0:-2] + [enrichment['aws_account_id']]) + ":"

                # Rebuild the arn with the lowercased function name
                function_name = log_group.split('/')[-1].lower()
                arn = arn_prefix + "function:" + function_name
                enrichment['host'] = arn
                enrichment['arn'] = arn
                enrichment['functionName'] = function_name

            def rds_enricher():
                enrichment['host'], enrichment['dbType'] = log_group.split('/')[-2:]

            def default_enricher():
                enrichment['host'] = enrichment['logGroup']

            enrichers = {
                'lambda': lambda_enricher,
                'rds': rds_enricher
            }
            return enrichers.get(source, default_enricher)

        def _parse_log_forwarder_arn(arn):
            split_arn = arn.split(":")
            if len(split_arn) > 7:
                split_arn = split_arn[:7]
            _, _, _, region, account_id, _, _ = split_arn
            return region

        enrichment = {}
        log_group = logs['logGroup']
        enrichment['logGroup'] = log_group
        enrichment['logStream'] = logs['logStream']
        enrichment['source'] = _get_source(log_group.lower())
        enrichment['logForwarder'] = context.function_name.lower() + ":" + context.function_version
        enrichment['region'] = _parse_log_forwarder_arn(context.invoked_function_arn)
        enrichment['aws_account_id'] = logs['owner']
        _enricher_factory(enrichment['source'])()

        logs['enrichment'] = enrichment
        return logs

    def _tags_enrichment(self, enriched_logs):
        arn = enriched_logs['enrichment'].get('arn')
        if arn:
            enriched_logs['enrichment'].update(self._tag_cache.get(arn))
        return enriched_logs

    def _send_logs(self, logs):
        batcher = Batcher(SFX_MAX_REQUEST_SIZE_IN_BYTES)
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

    def _convert_to_hec(self, enriched_logs):
        logs = []

        for item in enriched_logs["logEvents"]:
            item['event'] = item['message']
            del item['message']
            del item['id']
            # TODO add time instead of timestamp
            # log["time"] = timestamp_as_string[0:-3] + "." + timestamp_as_string[-3:]
            del item['timestamp']

            item['sourcetype'] = 'aws'
            item['fields'] = enriched_logs['enrichment']
            item['host'] = item['fields']['host']
            del item['fields']['host']
            item['source'] = item['fields']['source']
            del item['fields']['source']

            logs.append(json.dumps(item))

        return logs

    @staticmethod
    def _dump_object(context):
        return '%s(%s)' % (
            type(context).__name__,
            ', '.join('%s=%s' % item for item in vars(context).items()))


log_forwarder = LogCollector()
lambda_handler = log_forwarder.forward_log
