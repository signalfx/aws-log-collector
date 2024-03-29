# Copyright 2021 Splunk, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import json

import signalfx
import time


def size_of_str(string):
    return len(bytes(string, "utf-8"))


def size_of_json(obj):
    return size_of_str(json.dumps(obj))


def _current_time():
    return int(round(time.time() * 1000))


class SfxMetrics(object):

    def __init__(self, splunk_url, splunk_api_key):
        self._sfx_metrics = signalfx.SignalFx(ingest_endpoint=splunk_url).ingest(splunk_api_key)
        self._namespace = "unknown"

    def __enter__(self):
        return self

    def __exit__(self, ex_type, ex_value, traceback):
        self._sfx_metrics.stop()

    def inc_counter(self, metric_name):
        self.counters((metric_name, 1))

    def counters(self, *metric_name_values):
        counters = list(map(lambda metric_name_value: self.counter(metric_name_value[0], metric_name_value[1]),
                            metric_name_values))
        self._sfx_metrics.send(counters=counters)

    def namespace(self, namespace):
        self._namespace = namespace

    def counter(self, metric_name, metric_value):
        return {'metric': metric_name,
                'value': metric_value,
                'dimensions': {'namespace': self._namespace},
                'timestamp': _current_time()}
