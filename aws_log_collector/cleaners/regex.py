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
