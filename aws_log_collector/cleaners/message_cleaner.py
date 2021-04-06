from abc import abstractmethod

from typing import List


class MessageCleaner:

    def cleanup_hec_item_message(self, hec_item, context, sfx_metrics):
        return self._cleanup_hec_item_message(hec_item, context, sfx_metrics)

    @abstractmethod
    def _cleanup_hec_item_message(self, hec_item, context, sfx_metrics):
        pass
