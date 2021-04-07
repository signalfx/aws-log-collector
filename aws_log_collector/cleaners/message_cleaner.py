from abc import abstractmethod

from typing import List


class MessageCleaner:

    @abstractmethod
    def cleanup_hec_item_message(self, hec_item, context, sfx_metrics):
        pass
