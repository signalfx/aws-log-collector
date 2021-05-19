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
