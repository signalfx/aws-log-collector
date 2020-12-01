from abc import abstractmethod

from typing import List


class Converter:

    @abstractmethod
    def supports(self, log_event) -> bool:
        pass

    def convert_to_hec(self, log_event, context, sfx_metrics) -> List[tuple]:
        return list(self._convert_to_hec(log_event, context, sfx_metrics))

    @abstractmethod
    def _convert_to_hec(self, log_event, context, sfx_metrics):
        pass
