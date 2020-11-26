import gzip
import json
import logging

import requests
import time

from logger import log
from metric import size_of_str


class BatchClient(object):

    @staticmethod
    def create(url, api_key, max_request_size_in_bytes, compression_level, sfx_metrics, max_retry=3):
        client = RetryableClient.create(url, api_key, compression_level, sfx_metrics)
        return BatchClient(client, max_request_size_in_bytes, max_retry)

    def __init__(self, client, max_request_size_in_bytes, max_retry):
        self._client = client
        self._max_batch_size_bytes = max_request_size_in_bytes
        self._max_retry = max_retry

    def send(self, logs):
        for batch in self._batch(logs):
            try:
                self._client.send(batch)
            except Exception:
                log.exception(f"Exception while forwarding log batch {batch}")
            else:
                if log.isEnabledFor(logging.DEBUG):
                    log.debug(f"Forwarded log batch: {json.dumps(batch)}")

    def _batch(self, items):
        batch = []
        batch_size_bytes = 0
        for item in items:
            item_size_bytes = self._size_of_bytes(item)
            if item_size_bytes > self._max_batch_size_bytes:
                log.info(
                    f"Item is bigger than max batch size ({self._max_batch_size_bytes}), going to truncate it")
                item = item.encode("utf-8")[:self._max_batch_size_bytes].decode("utf-8", "ignore")
                item_size_bytes = self._size_of_bytes(item)

            if item_size_bytes + batch_size_bytes > self._max_batch_size_bytes:
                yield batch
                batch = []
                batch_size_bytes = 0

            batch.append(item)
            batch_size_bytes += item_size_bytes

        if len(batch) > 0:
            yield batch

    def __enter__(self):
        self._client.__enter__()
        return self

    def __exit__(self, ex_type, ex_value, traceback):
        self._client.__exit__(ex_type, ex_value, traceback)

    @staticmethod
    def _size_of_bytes(item):
        return len(str(item).encode("UTF-8"))


class RetryableClient(object):

    @staticmethod
    def create(url, api_key, compression_level, sfx_metrics, max_retry=3):
        client = HTTPClient(url, api_key, compression_level, sfx_metrics)
        return RetryableClient(client, max_retry)

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


class RetryableException(Exception):
    pass


class HTTPClient(object):

    def __init__(self, host, api_key, compression_level, sfx_metrics, timeout=20):
        self._url = host
        self._headers = {"Content-type": "application/json", "Content-Encoding": "gzip", "X-SF-TOKEN": api_key}
        self._compression_level = compression_level
        self._sfx_metrics = sfx_metrics
        self._timeout = timeout
        self._session = None

    def _connect(self):
        self._session = requests.Session()
        self._session.headers.update(self._headers)

    def _close(self):
        self._session.close()
        self._session = None

    def send(self, log_events):
        log_events_combined = self._combine_events(log_events)
        data_compressed = self._compress_logs(log_events_combined)
        self._sfx_metrics.counters(
            ('sf.org.awsLogCollector.num.outputUncompressedBytes', size_of_str(log_events_combined)),
            ('sf.org.awsLogCollector.num.outputCompressedBytes', len(data_compressed)),
            ("sf.org.awsLogCollector.num.splunkLogRequests", 1)
        )
        try:
            if log.isEnabledFor(logging.DEBUG):
                log.debug(f"Data to be sent={data_compressed}")
            log.info(f"Sending request to url={self._url}")
            resp = self._session.post(self._url, data_compressed, timeout=self._timeout)
        except Exception as ex:
            # network error
            log.warn(f"Exception occurred during log sending {ex}")
            raise RetryableException()
        if resp.status_code >= 500:
            log.warn(f"Server error (status={resp.status_code}, reason={resp.reason})")
            raise RetryableException()
        elif resp.status_code >= 400:
            raise Exception(f"Client error (status={resp.status_code}, reason={resp.reason})")

        return

    @staticmethod
    def _combine_events(logs):
        return "\n".join(logs)

    def _compress_logs(self, batch):
        return gzip.compress(bytes(batch, "utf-8"), self._compression_level)

    def __enter__(self):
        self._connect()
        return self

    def __exit__(self, ex_type, ex_value, traceback):
        self._close()
