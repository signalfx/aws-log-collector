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

import re

from aws_log_collector.cleaners.message_cleaner import MessageCleaner


class RegexMessageCleaner(MessageCleaner):

    def __init__(self, regex_str, replacement_str):
        self.pattern = r'' + regex_str
        self.replacement_str = replacement_str
        return

    def cleanup_hec_item_message(self, hec_item, context, sfx_metrics):
        log_message = hec_item["event"]
        self._send_result_metrics(sfx_metrics, len(re.findall(self.pattern, log_message)))
        hec_item["event"] = re.sub(self.pattern, self.replacement_str, log_message)
        return hec_item

    @staticmethod
    def _send_result_metrics(sfx_metrics, removed_matches_count):
        sfx_metrics.counters(
            ("sf.org.awsLogCollector.num.redactedItems", removed_matches_count)
        )
