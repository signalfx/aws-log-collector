import base64
import gzip
import json
import logging
import os
import re
import urllib
from io import BytesIO, BufferedReader

import boto3
import itertools
import time
from time import time
from botocore.vendored import requests

log = logging.getLogger()
log.setLevel(logging.getLevelName(os.environ.get("LOG_LEVEL", "INFO").upper()))


def get_env_var(envvar, default, boolean=False):
    """
        Return the value of the given environment variable with debug logging.
        When boolean=True, parse the value as a boolean case-insensitively.
    """
    value = os.getenv(envvar, default=default)
    if boolean:
        value = value.lower() == "true"
    log.debug(f"{envvar}: {value}")
    return value


SFX_API_KEY = get_env_var("SFX_API_KEY", "<wrong-token>", boolean=False)
SFX_USE_COMPRESSION = get_env_var("SFX_USE_COMPRESSION", "false", boolean=True)

SFX_COMPRESSION_LEVEL = int(os.getenv("SFX_COMPRESSION_LEVEL", 6))

SFX_NO_SSL = get_env_var("SFX_NO_SSL", "true", boolean=True)

SFX_SKIP_SSL_VALIDATION = get_env_var("SFX_SKIP_SSL_VALIDATION", "true", boolean=True)

SFX_TAGS = get_env_var("SFX_TAGS", "")

SFX_URL = get_env_var("SFX_URL", default="http://lab-ingest.corp.signalfx.com/v1/log")

SFX_SOURCE = "source"
SFX_SERVICE = "service"
SFX_HOST = "host"
SFX_FORWARDER_VERSION = "3.17.1"

rds_regex = re.compile("/aws/rds/(instance|cluster)/(?P<host>[^/]+)/(?P<name>[^/]+)")

# Used to identify and assign sources to logs
LOG_SOURCE_SUBSTRINGS = [
    "codebuild",
    "lambda",
    "redshift",
    "cloudfront",
    "kinesis",
    "mariadb",
    "mysql",
    "apigateway",
    "route53",
    "docdb",
    "fargate",
    "dms",
    "vpc",
    "sns",
    "waf",
]


class RetriableException(Exception):
    pass


class SfxClient(object):
    """
    Client that implements a exponential retrying logic to send a batch of logs.
    """

    def __init__(self, client, max_backoff=30):
        self._client = client
        self._max_backoff = max_backoff

    def send(self, logs):
        backoff = 1
        while True:
            try:
                self._client.send(logs)
                return
            except RetriableException:
                time.sleep(backoff)
                if backoff < self._max_backoff:
                    backoff *= 2
                continue

    def __enter__(self):
        self._client.__enter__()
        return self

    def __exit__(self, ex_type, ex_value, traceback):
        self._client.__exit__(ex_type, ex_value, traceback)


class SfxHTTPClient(object):
    """
    Client that sends a batch of logs over HTTP.
    """

    _POST = "POST"
    if SFX_USE_COMPRESSION:
        _HEADERS = {"Content-type": "application/json", "Content-Encoding": "gzip"}
    else:
        _HEADERS = {"Content-type": "application/json"}

    def __init__(
            self, host, no_ssl, skip_ssl_validation, api_key, timeout=10
    ):
        self._url = host
        self._timeout = timeout
        self._session = None
        self._ssl_validation = not skip_ssl_validation
        self._HEADERS["X-SF-TOKEN"] = api_key

    def _connect(self):
        self._session = requests.Session()
        self._session.headers.update(self._HEADERS)

    def _close(self):
        self._session.close()

    def send(self, logs):
        """
        Sends a batch of log, only retry on server and network errors.
        """
        data = "\n".join(logs)

        if SFX_USE_COMPRESSION:
            data = compress_logs(data, SFX_COMPRESSION_LEVEL)

        try:
            print("Data to be sent=", data)
            print("Sending request url=", self._url)
            resp = self._session.post(
                self._url, data, timeout=self._timeout, verify=self._ssl_validation
            )
        except Exception:
            # most likely a network error
            raise RetriableException()
        if resp.status_code >= 500:
            # server error
            raise RetriableException()
        elif resp.status_code >= 400:
            # client error
            raise Exception(
                "client error, status: {}, reason {}".format(
                    resp.status_code, resp.reason
                )
            )
        else:
            # success
            return

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, ex_type, ex_value, traceback):
        self._close()


class SfxBatcher(object):
    def __init__(self, max_item_size_bytes, max_batch_size_bytes, max_items_count):
        self._max_item_size_bytes = max_item_size_bytes
        self._max_batch_size_bytes = max_batch_size_bytes
        self._max_items_count = max_items_count

    def _sizeof_bytes(self, item):
        return len(str(item).encode("UTF-8"))

    def batch(self, items):
        """
        Returns an array of batches.
        Each batch contains at most max_items_count items and
        is not strictly greater than max_batch_size_bytes.
        All items strictly greater than max_item_size_bytes are dropped.
        """
        batches = []
        batch = []
        size_bytes = 0
        size_count = 0
        for item in items:
            item_size_bytes = self._sizeof_bytes(item)
            if size_count > 0 and (
                    size_count >= self._max_items_count
                    or size_bytes + item_size_bytes > self._max_batch_size_bytes
            ):
                batches.append(batch)
                batch = []
                size_bytes = 0
                size_count = 0
            # all items exceeding max_item_size_bytes are dropped here
            if item_size_bytes <= self._max_item_size_bytes:
                batch.append(item)
                size_bytes += item_size_bytes
                size_count += 1
        if size_count > 0:
            batches.append(batch)
        return batches


def compress_logs(batch, level):
    if level < 0:
        compression_level = 0
    elif level > 9:
        compression_level = 9
    else:
        compression_level = level

    return gzip.compress(bytes(batch, "utf-8"), compression_level)


def sfx_forwarder(event, context):
    """The actual lambda function entry point"""
    if log.isEnabledFor(logging.DEBUG):
        log.debug(f"Received Event:{json.dumps(event)}")

    #log.info(f"Received Event:{json.dumps(event)}")
    #log.info(f"Received context:{dump_object(context)}")

    metrics, logs, trace_payloads = split(enrich(parse(event, context)))
    #log.info(f"My logs: {logs}")
    forward_logs(map(json.dumps, logs))

def dump_object(context):
    return '%s(%s)' % (
        type(context).__name__,
        ', '.join('%s=%s' % item for item in vars(context).items()))

lambda_handler = sfx_forwarder


def forward_logs(logs):
    batcher = SfxBatcher(256 * 1000, 2 * 1000 * 1000, 200)
    cli = SfxHTTPClient(
        SFX_URL, SFX_NO_SSL, SFX_SKIP_SSL_VALIDATION, SFX_API_KEY
    )

    with SfxClient(cli) as client:
        for batch in batcher.batch(logs):
            try:
                client.send(batch)
            except Exception:
                log.exception(f"Exception while forwarding log batch {batch}")
            else:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Forwarded log batch: {json.dumps(batch)}")


def parse(event, context):
    """Parse Lambda input to normalized events"""
    metadata = generate_metadata(context)
    try:
        # Route to the corresponding parser
        event_type = parse_event_type(event)
        if event_type == "s3":
            events = s3_handler(event, context, metadata)
        elif event_type == "awslogs":
            events = awslogs_handler(event, context, metadata)
        elif event_type == "events":
            events = cwevent_handler(event, metadata)
        elif event_type == "sns":
            events = sns_handler(event, metadata)
        elif event_type == "kinesis":
            events = kinesis_awslogs_handler(event, context, metadata)
    except Exception as e:
        # Logs through the socket the error
        err_message = "Error parsing the object. Exception: {} for event {}".format(
            str(e), event
        )
        events = [err_message]

    return normalize_events(events, metadata)


def enrich(events):
    """Adds event-specific tags and attributes to each event

    Args:
        events (dict[]): the list of event dicts we want to enrich
    """
    for event in events:
        add_metadata_to_lambda_log(event)

    return events


def add_metadata_to_lambda_log(event):
    """Mutate log dict to add tags, host, and service metadata

    * tags for functionname, aws_account, region
    * host from the Lambda ARN
    * service from the Lambda name

    If the event arg is not a Lambda log then this returns without doing anything

    Args:
        event (dict): the event we are adding Lambda metadata to
    """
    lambda_log_metadata = event.get("fields", {})
    lambda_log_arn = lambda_log_metadata.get("arn")

    # Do not mutate the event if it's not from Lambda
    if not lambda_log_arn:
        return

    event[SFX_HOST] = lambda_log_arn

    # Add any enhanced tags from metadata
    custom_lambda_tags = get_enriched_lambda_log_tags(event)

    event["fields"] = merge_dicts(event["fields"], custom_lambda_tags)

def generate_metadata(context):
    metadata = {
        "sourcetype": "aws",
    }
    fields = {
        "forwarderName": context.function_name.lower(),
        "forwarderVersion": SFX_FORWARDER_VERSION,
    }
    metadata['fields'] = fields

    return metadata

def extract_metric(event):
    """Extract metric from an event if possible"""
    try:
        metric = json.loads(event["message"])
        required_attrs = {"m", "v", "e", "t"}
        if not all(attr in metric for attr in required_attrs):
            return None
        if not isinstance(metric["t"], list):
            return None

        return metric
    except Exception:
        return None


def split(events):
    """Split events into metrics, logs, and trace payloads
    """
    metrics, logs, trace_payloads = [], [], []
    for event in events:
        metric = extract_metric(event)
        trace_payload = ""
        if metric:
            metrics.append(metric)
        elif trace_payload:
            trace_payloads.append(trace_payload)
        else:
            logs.append(event)
    return metrics, logs, trace_payloads


# Utility functions


def normalize_events(events, metadata):
    normalized = []
    for event in events:
        if isinstance(event, dict):
            normalized.append(merge_dicts(event, metadata))
        elif isinstance(event, str):
            normalized.append(merge_dicts({"event": event}, metadata))
        else:
            # drop this log
            continue
    return normalized


def parse_event_type(event):
    if "Records" in event and len(event["Records"]) > 0:
        if "s3" in event["Records"][0]:
            return "s3"
        elif "Sns" in event["Records"][0]:
            return "sns"
        elif "kinesis" in event["Records"][0]:
            return "kinesis"

    elif "awslogs" in event:
        return "awslogs"

    elif "detail" in event:
        return "events"
    raise Exception("Event type not supported (see #Event supported section)")


# Handle S3 events
def s3_handler(event, context, metadata):
    s3 = boto3.client("s3")

    # Get the object from the event and show its content type
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key = urllib.parse.unquote_plus(event["Records"][0]["s3"]["object"]["key"])

    source = parse_event_source(event, key)
    metadata[SFX_SOURCE] = source
    ##default service to source value
    ##Get the ARN of the service and set it as the hostname
    hostname = parse_service_arn(source, key, bucket, context)
    if hostname:
        metadata[SFX_HOST] = hostname

    # Extract the S3 object
    response = s3.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    data = body.read()

    # Decompress data that has a .gz extension or magic header http://www.onicos.com/staff/iz/formats/gzip.html
    if key[-3:] == ".gz" or data[:2] == b"\x1f\x8b":
        with gzip.GzipFile(fileobj=BytesIO(data)) as decompress_stream:
            # Reading line by line avoid a bug where gzip would take a very long time (>5min) for
            # file around 60MB gzipped
            data = b"".join(BufferedReader(decompress_stream))

    if is_cloudtrail(str(key)):
        cloud_trail = json.loads(data)
        for event in cloud_trail["Records"]:
            # Create structured object and send it
            structured_line = merge_dicts(
                event, {"aws": {"s3": {"bucket": bucket, "key": key}}}
            )
            yield structured_line
    else:
        # Check if using multiline log regex pattern
        # and determine whether line or pattern separated logs
        data = data.decode("utf-8")
        split_data = data.splitlines()

        for line in split_data:
            # Create structured object and send it
            structured_line = {
                "aws": {"s3": {"bucket": bucket, "key": key}},
                "event": line,
            }
            yield structured_line


# Handle CloudWatch logs from Kinesis
def kinesis_awslogs_handler(event, context, metadata):
    def reformat_record(record):
        return {"awslogs": {"data": record["kinesis"]["data"]}}

    return itertools.chain.from_iterable(
        awslogs_handler(reformat_record(r), context, metadata) for r in event["Records"]
    )


# Handle CloudWatch logs
def awslogs_handler(event, context, metadata):
    # Get logs
    with gzip.GzipFile(
            fileobj=BytesIO(base64.b64decode(event["awslogs"]["data"]))
    ) as decompress_stream:
        # Reading line by line avoid a bug where gzip would take a very long
        # time (>5min) for file around 60MB gzipped
        data = b"".join(BufferedReader(decompress_stream))
    logs = json.loads(data)

    # Set the source on the logs
    source = logs.get("logGroup", "cloudwatch")
    metadata[SFX_SOURCE] = parse_event_source(event, source)

    # Default service to source value

    # Build aws attributes
    aws_attributes = {
        "aws": {
            "awslogs": {
                "logGroup": logs["logGroup"],
                "logStream": logs["logStream"],
                "owner": logs["owner"],
            }
        }
    }

    # Set host as log group where cloudwatch is source
    if metadata[SFX_SOURCE] == "cloudwatch":
        metadata[SFX_HOST] = aws_attributes["aws"]["awslogs"]["logGroup"]

    metadata["fields"]["logGroup"] = logs["logGroup"]
    metadata["fields"]["logStream"] = logs["logStream"]

    # When parsing rds logs, use the cloudwatch log group name to derive the
    # rds instance name, and add the log name of the stream ingested
    if metadata[SFX_SOURCE] == "rds":
        match = rds_regex.match(logs["logGroup"])
        if match is not None:
            metadata[SFX_HOST] = match.group("host")
            # We can intuit the sourcecategory in some cases
            if match.group("name") == "postgresql":
                metadata["fields"]["dbType"] = match.group("name")
            else:
                metadata["fields"]["logname"] = match.group("name")

    # For Lambda logs we want to extract the function name,
    # then rebuild the arn of the monitored lambda using that name.
    # Start by splitting the log group to get the function name
    if metadata[SFX_SOURCE] == "lambda":
        log_group_parts = logs["logGroup"].split("/lambda/")
        if len(log_group_parts) > 1:
            lowercase_function_name = log_group_parts[1].lower()
            # Split the arn of the forwarder to extract the prefix
            arn_parts = context.invoked_function_arn.split("function:")
            if len(arn_parts) > 0:
                arn_prefix = arn_parts[0]
                #temporary fix with correct account id in arn
                arn_prefix_parts = arn_prefix.split(":")
                arn_prefix = ":".join(arn_prefix_parts[0:-2] + ["134183635603"]) + ":"

                # Rebuild the arn with the lowercased function name
                lowercase_arn = arn_prefix + "function:" + lowercase_function_name
                # Add the lowercased arn as a log attribute
                metadata["fields"]["arn"] = lowercase_arn
                metadata["fields"]["functionName"] = lowercase_function_name

    for log in logs["logEvents"]:
        log["event"] = log["message"]
        timestamp_as_string = str(log["timestamp"])
        #log["time"] = timestamp_as_string[0:-3] + "." + timestamp_as_string[-3:]
        del log["timestamp"]
        del log["message"]
        del log["id"]
        yield log
    #yield merge_dicts(log, aws_attributes)


# Handle Cloudwatch Events
def cwevent_handler(event, metadata):
    data = event

    # Set the source on the log
    source = data.get("source", "cloudwatch")
    service = source.split(".")
    if len(service) > 1:
        metadata[SFX_SOURCE] = service[1]
    else:
        metadata[SFX_SOURCE] = "cloudwatch"

    yield data


# Handle Sns events
def sns_handler(event, metadata):
    data = event
    # Set the source on the log
    metadata[SFX_SOURCE] = "sns"

    for ev in data["Records"]:
        # Create structured object and send it
        structured_line = ev
        yield structured_line


def merge_dicts(a, b, path=None):
    if path is None:
        path = []
    for key in b:
        if key in a:
            if isinstance(a[key], dict) and isinstance(b[key], dict):
                merge_dicts(a[key], b[key], path + [str(key)])
            elif a[key] == b[key]:
                pass  # same leaf value
            else:
                raise Exception(
                    "Conflict while merging metadatas and the log entry at %s"
                    % ".".join(path + [str(key)])
                )
        else:
            a[key] = b[key]
    return a


cloudtrail_regex = re.compile(
    "\d+_CloudTrail_\w{2}-\w{4,9}-\d_\d{8}T\d{4}Z.+.json.gz$", re.I
)


def is_cloudtrail(key):
    match = cloudtrail_regex.search(key)
    return bool(match)


def parse_event_source(event, key):
    lowercase_key = str(key).lower()

    if "elasticloadbalancing" in lowercase_key:
        return "elb"

    if "api-gateway" in lowercase_key:
        return "apigateway"

    if is_cloudtrail(str(key)) or (
            "logGroup" in event and event["logGroup"] == "CloudTrail"
    ):
        return "cloudtrail"

    if "/aws/rds" in lowercase_key:
        return "rds"

    # Use the source substrings to find if the key matches any known services
    for source in LOG_SOURCE_SUBSTRINGS:
        if source in lowercase_key:
            return source

    # If the source AWS service cannot be parsed from the key, return the service
    # that contains the logs as the source, "cloudwatch" or "s3"
    if "awslogs" in event:
        return "cloudwatch"

    if "Records" in event and len(event["Records"]) > 0:
        if "s3" in event["Records"][0]:
            return "s3"

    return "aws"


def parse_service_arn(source, key, bucket, context):
    if source == "elb":
        # For ELB logs we parse the filename to extract parameters in order to rebuild the ARN
        # 1. We extract the region from the filename
        # 2. We extract the loadbalancer name and replace the "." by "/" to match the ARN format
        # 3. We extract the id of the loadbalancer
        # 4. We build the arn
        idsplit = key.split("/")
        # If there is a prefix on the S3 bucket, idsplit[1] will be "AWSLogs"
        # Remove the prefix before splitting they key
        if len(idsplit) > 1 and idsplit[1] == "AWSLogs":
            idsplit = idsplit[1:]
            keysplit = "/".join(idsplit).split("_")
        # If no prefix, split the key
        else:
            keysplit = key.split("_")
        if len(keysplit) > 3:
            region = keysplit[2].lower()
            name = keysplit[3]
            elbname = name.replace(".", "/")
            if len(idsplit) > 1:
                idvalue = idsplit[1]
                return "arn:aws:elasticloadbalancing:{}:{}:loadbalancer/{}".format(
                    region, idvalue, elbname
                )
    if source == "s3":
        # For S3 access logs we use the bucket name to rebuild the arn
        if bucket:
            return "arn:aws:s3:::{}".format(bucket)
    if source == "cloudfront":
        # For Cloudfront logs we need to get the account and distribution id from the lambda arn and the filename
        # 1. We extract the cloudfront id  from the filename
        # 2. We extract the AWS account id from the lambda arn
        # 3. We build the arn
        namesplit = key.split("/")
        if len(namesplit) > 0:
            filename = namesplit[len(namesplit) - 1]
            # (distribution-ID.YYYY-MM-DD-HH.unique-ID.gz)
            filenamesplit = filename.split(".")
            if len(filenamesplit) > 3:
                distributionID = filenamesplit[len(filenamesplit) - 4].lower()
                arn = context.invoked_function_arn
                arnsplit = arn.split(":")
                if len(arnsplit) == 7:
                    awsaccountID = arnsplit[4].lower()
                    return "arn:aws:cloudfront::{}:distribution/{}".format(
                        awsaccountID, distributionID
                    )
    if source == "redshift":
        # For redshift logs we leverage the filename to extract the relevant information
        # 1. We extract the region from the filename
        # 2. We extract the account-id from the filename
        # 3. We extract the name of the cluster
        # 4. We build the arn: arn:aws:redshift:region:account-id:cluster:cluster-name
        namesplit = key.split("/")
        if len(namesplit) == 8:
            region = namesplit[3].lower()
            accountID = namesplit[1].lower()
            filename = namesplit[7]
            filesplit = filename.split("_")
            if len(filesplit) == 6:
                clustername = filesplit[3]
                return "arn:aws:redshift:{}:{}:cluster:{}:".format(
                    region, accountID, clustername
                )
    return


GET_RESOURCES_LAMBDA_FILTER = "lambda"
TAGS_CACHE_TTL_SECONDS = 3600
resource_tagging_client = boto3.client("resourcegroupstaggingapi")
from collections import defaultdict


def should_fetch_custom_tags():
    """Checks the env var to determine if the customer has opted-in to fetching custom tags
    """
    return os.environ.get("SFX_FETCH_LAMBDA_TAGS", "true").lower() == "true"


def sanitize_aws_tag_string(tag, remove_colons=False):
    global Sanitize, Dedupe, FixInit

    # 1. Replace colons with _
    # 2. Convert to all lowercase unicode string
    # 3. Convert bad characters to underscores
    # 4. Dedupe contiguous underscores
    # 5. Remove initial underscores/digits such that the string
    #    starts with an alpha char
    #    FIXME: tag normalization incorrectly supports tags starting
    #    with a ':', but this behavior should be phased out in future
    #    as it results in unqueryable data.  See dogweb/#11193
    # 6. Strip trailing underscores

    if len(tag) == 0:
        # if tag is empty, nothing to do
        return tag

    if remove_colons:
        tag = tag.replace(":", "_")
    tag = Dedupe("_", Sanitize("_", tag.lower()))
    first_char = tag[0]
    if first_char == "_" or "0" <= first_char <= "9":
        tag = FixInit("", tag)
    tag = tag.rstrip("_")
    return tag


def get_tag_string_from_aws_dict(aws_key_value_tag_dict):
    key = aws_key_value_tag_dict["Key"]
    value = aws_key_value_tag_dict.get("Value")
    if not value:
        return {key: "null"}

    result = {key: value}
    return result


def parse_get_resources_response_for_tags_by_arn(get_resources_page):
    """Parses a page of GetResources response for the mapping from ARN to tags

    Args:
        get_resources_page (dict<str, dict<str, dict | str>[]>): one page of the GetResources response.
            Partial example:
                {"ResourceTagMappingList": [{
                    'ResourceARN': 'arn:aws:lambda:us-east-1:123497598159:function:my-test-lambda',
                    'Tags': [{'Key': 'stage', 'Value': 'dev'}, {'Key': 'team', 'Value': 'serverless'}]
                }]}

    Returns:
        tags_by_arn (dict<str, str[]>): Lambda tag lists keyed by ARN
    """
    tags_by_arn = defaultdict(list)

    aws_resouce_tag_mappings = get_resources_page["ResourceTagMappingList"]
    for aws_resource_tag_mapping in aws_resouce_tag_mappings:
        function_arn = aws_resource_tag_mapping["ResourceARN"]
        lowercase_function_arn = function_arn.lower()

        raw_aws_tags = aws_resource_tag_mapping["Tags"]
        tags = {}
        for raw_tag in raw_aws_tags:
            tags = merge_dicts(tags, get_tag_string_from_aws_dict(raw_tag))

        tags_by_arn[lowercase_function_arn] = merge_dicts(tags_by_arn.get(lowercase_function_arn, {}), tags)

    return tags_by_arn


def build_tags_by_arn_cache():
    """Makes API calls to GetResources to get the live tags of the account's Lambda functions

    Returns an empty dict instead of fetching custom tags if the tag fetch env variable is not set to true

    Returns:
        tags_by_arn_cache (dict<str, str[]>): each Lambda's tags in a dict keyed by ARN
    """
    tags_by_arn_cache = {}
    get_resources_paginator = resource_tagging_client.get_paginator("get_resources")

    try:
        for page in get_resources_paginator.paginate(
                ResourceTypeFilters=[GET_RESOURCES_LAMBDA_FILTER], ResourcesPerPage=100
        ):
            page_tags_by_arn = parse_get_resources_response_for_tags_by_arn(page)
            tags_by_arn_cache.update(page_tags_by_arn)

    except Exception:
        log.exception(
            "Encountered a ClientError when trying to fetch tags. You may need to give "
            "this Lambda's role the 'tag:GetResources' permission"
        )

    log.debug(
        "Built this tags cache from GetResources API calls: %s", tags_by_arn_cache
    )

    return tags_by_arn_cache


class LambdaTagsCache(object):
    def __init__(self, tags_ttl_seconds=TAGS_CACHE_TTL_SECONDS):
        self.tags_ttl_seconds = tags_ttl_seconds

        self.tags_by_arn = {}
        self.missing_arns = set()
        self.last_tags_fetch_time = 0

    def _refresh(self):
        """Populate the tags in the cache by making calls to GetResources
        """
        self.last_tags_fetch_time = time()

        # If the custom tag fetch env var is not set to true do not fetch

        if not should_fetch_custom_tags():
            log.debug(
                "Not fetching custom tags because the env variable SFX_FETCH_LAMBDA_TAGS is not set to true"
            )
            return

        self.tags_by_arn = build_tags_by_arn_cache()
        self.missing_arns -= set(self.tags_by_arn.keys())

    def _is_expired(self):
        """Returns bool for whether the tag fetch TTL has expired
        """
        earliest_time_to_refetch_tags = (
                self.last_tags_fetch_time + self.tags_ttl_seconds
        )
        return time() > earliest_time_to_refetch_tags

    def _should_refresh_if_missing_arn(self, resource_arn):
        """ Determines whether to try and fetch a missing lambda arn.
        We only refresh if we encounter an arn that we haven't seen
        since the last refresh. This prevents refreshing on every call when
        tags can't be found for an arn.
        """
        if resource_arn in self.missing_arns:
            return False
        return self.tags_by_arn.get(resource_arn) is None

    def get(self, resource_arn):
        if self._is_expired() or self._should_refresh_if_missing_arn(resource_arn):
            self._refresh()
        function_tags = self.tags_by_arn.get(resource_arn, None)

        if function_tags is None:
            self.missing_arns.add(resource_arn)
            return []

        return function_tags


# Store the cache in the global scope so that it will be reused as long as
# the log forwarder Lambda container is running
account_lambda_tags_cache = LambdaTagsCache()


def get_enriched_lambda_log_tags(log_event):
    """ Retrieves extra tags from lambda, either read from the function arn, or by fetching lambda tags from the function itself.

    Args:
        log (dict<str, str | dict | int>): a log parsed from the event in the split method
    """
    # Note that this arn attribute has been lowercased already
    log_function_arn = log_event.get("fields", {}).get("arn")

    if not log_function_arn:
        return []
    tags_from_arn = parse_lambda_tags_from_arn(log_function_arn)
    lambda_custom_tags = account_lambda_tags_cache.get(log_function_arn)
    # Combine and dedup tags
    tags = merge_dicts(tags_from_arn, lambda_custom_tags)
    return tags


def parse_lambda_tags_from_arn(arn):
    """Generate the list of lambda tags based on the data in the arn

    Args:
        arn (str): Lambda ARN.
            ex: arn:aws:lambda:us-east-1:172597598159:function:my-lambda[:optional-version]
    """
    # Cap the number of times to split
    split_arn = arn.split(":")

    # If ARN includes version / alias at the end, drop it
    if len(split_arn) > 7:
        split_arn = split_arn[:7]

    _, _, _, region, account_id, _, function_name = split_arn

    return {
        "region": region,
        "aws_account": account_id,
        "functionName": function_name
    }