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

    def get_metadata(self, parsed_line, metadata, sfx_metrics, include_log_fields):
        result = copy.deepcopy(metadata)

        for item in parsed_line.arns:
            name, arn = item
            tags = self.get_tags(arn, sfx_metrics)
            result = self.merge(result, {name: arn}, tags)

        if include_log_fields:
            result["event"] = parsed_line.fields

        return result
