from abc import abstractmethod


class Converter:

    @abstractmethod
    def supports(self, log_event):
        pass

    def convert_to_hec(self, log_event, context, sfx_metrics):
        return list(self._convert_to_hec(log_event, context, sfx_metrics))

    @abstractmethod
    def _convert_to_hec(self, log_event, context, sfx_metrics):
        pass
